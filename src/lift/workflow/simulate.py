from __future__ import annotations

from pathlib import Path
from typing import Any

from lift.data.load import load_csv, read_json, write_csv
from lift.evaluation.metrics import model_policy_metrics
from lift.workflow.artifacts import ArtifactStore
from lift.workflow.report import render_report


POLICY_SCORE_FIELDS = [
    "unit_id",
    "score",
    "expected_incremental_gain",
    "expected_incremental_cost",
    "expected_incremental_profit",
    "expected_incremental_roi",
]

TARGET_FIELDS = [
    "unit_id",
    "rank",
    "score",
    "recommended_treatment",
    "expected_incremental_gain",
    "expected_incremental_cost",
    "expected_incremental_profit",
    "expected_incremental_roi",
    "selection_reason",
    "trust_level",
]


def simulate_run(
    run_id: str,
    *,
    output_root: str | Path = "outputs",
    budget: float | None = None,
    min_roi: float | None = None,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    store = ArtifactStore(output_root)
    run_dir = store.require_run_dir(run_id)
    scores = [_coerce_score_row(row) for row in load_csv(run_dir / "policy-scores.csv")]
    trust = read_json(run_dir / "trust.json")
    targets = select_policy_scores(
        scores,
        budget=budget,
        min_roi=min_roi,
        trust_level=str(trust.get("trust_level", "unknown")),
    )
    summary = _summary(run_id, targets, budget, min_roi)
    if write_artifacts:
        write_csv(run_dir / "targets.csv", targets, TARGET_FIELDS)
        store.write_json(run_id, "simulation.json", summary)
    return summary


def select_policy_scores(
    scores: list[dict[str, Any]],
    *,
    budget: float | None,
    min_roi: float | None,
    trust_level: str,
) -> list[dict[str, Any]]:
    ordered = sorted(scores, key=lambda row: float(row["score"]), reverse=True)
    selected: list[dict[str, Any]] = []
    cumulative_gain = 0.0
    cumulative_cost = 0.0
    for row in ordered:
        score = float(row["score"])
        gain = float(row["expected_incremental_gain"])
        cost = max(float(row["expected_incremental_cost"]), 0.0)
        if score <= 0.0 or gain <= 0.0:
            continue
        next_gain = cumulative_gain + gain
        next_cost = cumulative_cost + cost
        if budget is not None and next_cost > budget:
            continue
        if min_roi is not None and next_cost > 0 and next_gain / next_cost < min_roi:
            continue
        cumulative_gain = next_gain
        cumulative_cost = next_cost
        selected.append(
            {
                "unit_id": row["unit_id"],
                "rank": len(selected) + 1,
                "score": score,
                "recommended_treatment": 1,
                "expected_incremental_gain": gain,
                "expected_incremental_cost": cost,
                "expected_incremental_profit": gain - cost,
                "expected_incremental_roi": _safe_divide(gain, cost),
                "selection_reason": "positive cost-aware incremental score",
                "trust_level": trust_level,
            }
        )
    return selected


def report_run(run_id: str, *, output_root: str | Path = "outputs") -> str:
    store = ArtifactStore(output_root)
    path = store.require_run_dir(run_id) / "report.md"
    return path.read_text(encoding="utf-8")


def refresh_report(run_id: str, *, output_root: str | Path = "outputs") -> str:
    store = ArtifactStore(output_root)
    run_dir = store.require_run_dir(run_id)
    simulation = read_json(run_dir / "simulation.json")
    content = render_report(
        run_id=run_id,
        campaign=read_json(run_dir / "campaign_incrementality.json"),
        trust=read_json(run_dir / "trust.json"),
        models=read_json(run_dir / "models.json"),
        evaluations=_evaluation_for_simulation(run_dir),
        simulation=simulation,
    )
    store.write_markdown(run_id, "report.md", content)
    return content


def _evaluation_for_simulation(run_dir: Path) -> dict[str, Any]:
    evaluation = read_json(run_dir / "evaluation.json")
    simulation = read_json(run_dir / "simulation.json")
    if not (run_dir / "curves.csv").exists():
        return evaluation
    curves = _curves_by_model(load_csv(run_dir / "curves.csv"))
    models = dict(evaluation.get("models", {}))
    for model_name, curve in curves.items():
        if model_name not in models:
            continue
        models[model_name] = {
            **models[model_name],
            **model_policy_metrics(
                curve,
                budget=simulation.get("budget"),
                min_roi=simulation.get("min_roi"),
            ),
        }
    leaderboard = sorted(
        (
            {
                "model": name,
                "auuc": result.get("auuc", 0.0),
                "qini": result.get("qini", 0.0),
                "gain_at_budget": result.get("gain_at_budget"),
                "gain_at_min_roi": result.get("gain_at_min_roi"),
            }
            for name, result in models.items()
        ),
        key=lambda row: (
            row["gain_at_budget"] if row["gain_at_budget"] is not None else float("-inf"),
            row["gain_at_min_roi"] if row["gain_at_min_roi"] is not None else float("-inf"),
            row["auuc"],
        ),
        reverse=True,
    )
    return {"models": models, "leaderboard": leaderboard}


def _curves_by_model(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, float]]]:
    curves: dict[str, list[dict[str, float]]] = {}
    for row in rows:
        model = str(row["model"])
        curves.setdefault(model, []).append(
            {
                key: float(value)
                for key, value in row.items()
                if key != "model"
            }
        )
    return curves


def _coerce_score_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": row["unit_id"],
        "score": float(row["score"]),
        "expected_incremental_gain": float(row["expected_incremental_gain"]),
        "expected_incremental_cost": float(row["expected_incremental_cost"]),
        "expected_incremental_profit": float(row["expected_incremental_profit"]),
        "expected_incremental_roi": float(row["expected_incremental_roi"]),
    }


def _summary(
    run_id: str,
    targets: list[dict[str, Any]],
    budget: float | None,
    min_roi: float | None,
) -> dict[str, Any]:
    expected_gain = sum(float(row["expected_incremental_gain"]) for row in targets)
    expected_cost = sum(float(row["expected_incremental_cost"]) for row in targets)
    expected_profit = expected_gain - expected_cost
    expected_roi = _safe_divide(expected_gain, expected_cost)
    feasible = True
    if budget is not None and expected_cost > budget:
        feasible = False
    if min_roi is not None and (not targets or (expected_cost > 0 and expected_roi < min_roi)):
        feasible = False
    return {
        "run_id": run_id,
        "budget": budget,
        "min_roi": min_roi,
        "constraint_status": "satisfied" if feasible else "failed",
        "target_count": len(targets),
        "expected_incremental_gain": expected_gain,
        "expected_incremental_cost": expected_cost,
        "expected_incremental_profit": expected_profit,
        "expected_incremental_roi": expected_roi,
    }


def _safe_divide(numerator: float, denominator: float) -> float:
    if abs(denominator) < 1e-12:
        return float("inf") if numerator > 0 else 0.0
    return numerator / denominator
