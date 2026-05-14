from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sklearn.model_selection import train_test_split

from lift import __version__
from lift.data.load import dataset_fingerprint, load_csv, write_csv
from lift.data.schema import Schema, infer_schema, prepare_rows, validate_rows
from lift.evaluation.metrics import (
    budget_frontier,
    campaign_incrementality,
    evaluate_ranking,
    model_policy_metrics,
    select_targets,
)
from lift.models.baselines import ModelResult, train_baselines
from lift.models.duality import DualityRLearner
from lift.trust.diagnostics import diagnose
from lift.trust.propensity import apply_propensity_estimates, estimate_propensity
from lift.workflow.artifacts import ArtifactStore
from lift.workflow.simulate import POLICY_SCORE_FIELDS, TARGET_FIELDS


@dataclass
class AnalyzeConfig:
    seed: int = 123
    output_root: str = "outputs"
    maximize_kpi: str = "maximize_kpi"
    constraint_kpi: str = "constraint_kpi"
    treatment: str = "treatment"
    unit_id: str = "unit_id"
    treatment_propensity: str = "treatment_propensity"
    budget: float | None = None
    min_roi: float | None = None
    lambda_grid: tuple[float, ...] = (0.0, 0.25, 0.5, 1.0, 2.0, 5.0)
    estimate_propensity: bool = False
    validation_fraction: float = 0.25


def analyze(dataset_path: str | Path, config: AnalyzeConfig) -> dict[str, Any]:
    raw_rows = load_csv(dataset_path)
    schema = infer_schema(
        raw_rows,
        unit_id=config.unit_id,
        treatment=config.treatment,
        maximize_kpi=config.maximize_kpi,
        constraint_kpi=config.constraint_kpi,
        treatment_propensity=config.treatment_propensity,
    )
    validation = validate_rows(raw_rows, schema)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))

    rows = prepare_rows(raw_rows, schema)
    propensity_payload: dict[str, Any] = {
        "source": "provided_or_inferred",
        "estimated": False,
        "feature_columns": schema.feature_columns,
    }
    if config.estimate_propensity:
        propensity_result = estimate_propensity(rows, schema, seed=config.seed)
        rows = apply_propensity_estimates(rows, schema, propensity_result["propensity"])
        propensity_payload = {
            key: value
            for key, value in propensity_result.items()
            if key != "propensity"
        }
        propensity_payload["estimated"] = True

    trust = diagnose(rows, schema, validation)
    campaign = campaign_incrementality(rows, schema)
    models = train_baselines(rows, schema, seed=config.seed)
    validation_indices = _validation_indices(len(rows), config.validation_fraction, config.seed)
    models.append(
        DualityRLearner(lambda_grid=list(config.lambda_grid), seed=config.seed).fit_predict(
            rows,
            schema,
            validation_indices=validation_indices,
        )
    )

    evaluations = {
        model.name: evaluate_ranking(rows, schema, model.scores)
        for model in models
    }
    primary = _primary_model(models)
    frontier = budget_frontier(
        rows,
        schema,
        primary.scores,
        primary.expected_incremental_gain,
        primary.expected_incremental_cost,
    )
    policy_scores = _policy_scores(rows, schema, primary)
    targets = select_targets(
        rows,
        schema,
        primary.scores,
        primary.expected_incremental_gain,
        primary.expected_incremental_cost,
        budget=config.budget,
        min_roi=config.min_roi,
        trust_level=trust["trust_level"],
    )

    run_id = _run_id(Path(dataset_path), config.seed)
    store = ArtifactStore(config.output_root)
    run_payload = {
        "seed": config.seed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "dataset_fingerprint": dataset_fingerprint(dataset_path),
        "model_versions": {"lift": __version__},
        "config": config.__dict__,
        "status": "completed",
    }
    model_payload = {"models": [_model_summary(model) for model in models], "primary_model": primary.name}
    evaluation_payload = _evaluation_payload(evaluations, budget=config.budget, min_roi=config.min_roi)
    curves = _curve_rows(evaluations)

    store.write_json(run_id, "run.json", run_payload)
    store.write_json(run_id, "schema.json", schema.to_dict())
    store.write_json(run_id, "propensity.json", propensity_payload)
    store.write_json(run_id, "trust.json", trust)
    store.write_json(run_id, "campaign_incrementality.json", campaign)
    store.write_json(run_id, "models.json", model_payload)
    store.write_json(run_id, "evaluation.json", evaluation_payload)
    write_csv(store.run_dir(run_id) / "curves.csv", curves, list(curves[0].keys()) if curves else [])
    write_csv(store.run_dir(run_id) / "budget-frontier.csv", frontier, list(frontier[0].keys()) if frontier else [])
    write_csv(store.run_dir(run_id) / "policy-scores.csv", policy_scores, POLICY_SCORE_FIELDS)
    write_csv(store.run_dir(run_id) / "targets.csv", targets, TARGET_FIELDS)
    store.write_json(run_id, "simulation.json", _simulation_payload(run_id, targets, config.budget, config.min_roi))
    store.write_markdown(run_id, "report.md", _report(run_id, campaign, trust, model_payload, evaluation_payload, len(targets)))
    store.write_markdown(run_id, "provenance.md", _provenance(run_payload, list(_artifact_names())))

    return {
        "run_id": run_id,
        "run_dir": str(store.run_dir(run_id)),
        "trust_level": trust["trust_level"],
        "primary_model": primary.name,
        "target_count": len(targets),
    }


def _primary_model(models: list[ModelResult]) -> ModelResult:
    for model in models:
        if model.name == "duality_r_learner":
            return model
    return models[-1]


def _model_summary(model: ModelResult) -> dict[str, Any]:
    finite_scores = [score for score in model.scores if score == score and score not in (float("inf"), float("-inf"))]
    return {
        "name": model.name,
        "metadata": model.metadata,
        "score_min": min(finite_scores) if finite_scores else None,
        "score_max": max(finite_scores) if finite_scores else None,
        "score_count": len(model.scores),
    }


def _evaluation_payload(
    evaluations: dict[str, dict[str, Any]],
    *,
    budget: float | None,
    min_roi: float | None,
) -> dict[str, Any]:
    models: dict[str, Any] = {}
    for name, result in evaluations.items():
        scalar = {key: value for key, value in result.items() if key != "curve"}
        scalar.update(model_policy_metrics(result["curve"], budget=budget, min_roi=min_roi))
        models[name] = scalar
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


def _curve_rows(evaluations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model_name, result in evaluations.items():
        for point in result["curve"]:
            rows.append({"model": model_name, **point})
    return rows


def _policy_scores(rows: list[dict[str, Any]], schema: Schema, model: ModelResult) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row, score, gain, cost in zip(
        rows,
        model.scores,
        model.expected_incremental_gain,
        model.expected_incremental_cost,
    ):
        safe_cost = max(float(cost), 0.0)
        output.append(
            {
                "unit_id": row[schema.unit_id],
                "score": score,
                "expected_incremental_gain": gain,
                "expected_incremental_cost": safe_cost,
                "expected_incremental_profit": gain - safe_cost,
                "expected_incremental_roi": _safe_divide(gain, safe_cost),
            }
        )
    return output


def _run_id(path: Path, seed: int) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{path.stem}-{timestamp}-s{seed}"


def _validation_indices(size: int, validation_fraction: float, seed: int) -> set[int]:
    if size < 4 or validation_fraction <= 0.0:
        return set()
    validation_count = max(2, int(size * validation_fraction))
    validation_count = min(validation_count, size - 2)
    indices = list(range(size))
    _train, validation = train_test_split(
        indices,
        test_size=validation_count,
        random_state=seed,
        shuffle=True,
    )
    return {int(index) for index in validation}


def _artifact_names() -> tuple[str, ...]:
    return (
        "run.json",
        "schema.json",
        "propensity.json",
        "trust.json",
        "campaign_incrementality.json",
        "models.json",
        "evaluation.json",
        "curves.csv",
        "budget-frontier.csv",
        "policy-scores.csv",
        "targets.csv",
        "simulation.json",
        "report.md",
        "provenance.md",
    )


def _simulation_payload(
    run_id: str,
    targets: list[dict[str, Any]],
    budget: float | None,
    min_roi: float | None,
) -> dict[str, Any]:
    expected_gain = sum(float(row["expected_incremental_gain"]) for row in targets)
    expected_cost = sum(float(row["expected_incremental_cost"]) for row in targets)
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
        "expected_incremental_profit": expected_gain - expected_cost,
        "expected_incremental_roi": expected_roi,
    }


def _report(
    run_id: str,
    campaign: dict[str, Any],
    trust: dict[str, Any],
    models: dict[str, Any],
    evaluations: dict[str, Any],
    target_count: int,
) -> str:
    leaderboard_lines = "\n".join(
        _leaderboard_line(row)
        for row in evaluations.get("leaderboard", [])
    )
    warnings = "\n".join(f"- {warning}" for warning in trust.get("warnings", [])) or "- None"
    return f"""# Lift Report

## Summary

- Run: `{run_id}`
- Primary model: `{models["primary_model"]}`
- Trust level: `{trust["trust_level"]}`
- Exported targets: {target_count}

## Campaign Incrementality

- Incremental maximize KPI: {campaign["incremental_maximize_kpi"]:.6f}
- Incremental constraint KPI: {campaign["incremental_constraint_kpi"]:.6f}
- Incremental ROI: {campaign["incremental_roi"]}

## Trust

{warnings}

## Model Leaderboard

{leaderboard_lines}

## Limitations

Observational analyses retain hidden confounding risk. Recommendations are policy simulations, not automatic campaign execution.
"""


def _leaderboard_line(row: dict[str, Any]) -> str:
    budget_gain = row.get("gain_at_budget")
    min_roi_gain = row.get("gain_at_min_roi")
    return (
        f"- {row['model']}: AUUC={row.get('auuc', 0.0):.6f}, "
        f"Qini={row.get('qini', 0.0):.6f}, "
        f"gain_at_budget={budget_gain if budget_gain is not None else 'n/a'}, "
        f"gain_at_min_roi={min_roi_gain if min_roi_gain is not None else 'n/a'}"
    )


def _provenance(run_payload: dict[str, Any], artifacts: list[str]) -> str:
    artifact_lines = "\n".join(f"- {name}" for name in artifacts)
    return f"""# Provenance

- Dataset path: `{run_payload["dataset_path"]}`
- Dataset fingerprint: `{run_payload["dataset_fingerprint"]}`
- Seed: {run_payload["seed"]}
- Status: {run_payload["status"]}

## Artifacts

{artifact_lines}
"""


def _safe_divide(numerator: float, denominator: float) -> float:
    if abs(denominator) < 1e-12:
        return float("inf") if numerator > 0 else 0.0
    return numerator / denominator
