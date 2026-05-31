from __future__ import annotations

from typing import Any


def render_report(
    *,
    run_id: str,
    campaign: dict[str, Any],
    trust: dict[str, Any],
    models: dict[str, Any],
    evaluations: dict[str, Any],
    simulation: dict[str, Any],
) -> str:
    leaderboard_lines = "\n".join(
        _leaderboard_line(row)
        for row in evaluations.get("leaderboard", [])
    )
    warnings = "\n".join(f"- {warning}" for warning in trust.get("warnings", [])) or "- None"
    leakage = ", ".join(trust.get("leakage_candidates", [])) or "None"
    imbalance = ", ".join(trust.get("high_imbalance_features", [])) or "None"
    target_count = simulation.get("target_count", 0)
    anti_target_count = simulation.get("anti_target_count", 0)
    anti_target_note = (
        f"{anti_target_count} customers with non-positive incremental score or gain.\n"
        f"See `anti-targets.csv` — these customers are expected to have zero or negative\n"
        f"response to treatment. Treating them wastes budget or may reduce KPI."
        if anti_target_count > 0
        else "None identified (all scored customers have positive expected uplift)."
    )
    iroi = simulation.get("expected_incremental_roi", "n/a")
    iroi_display = f"{iroi:.4f}" if isinstance(iroi, (int, float)) and iroi != float("inf") else str(iroi)
    return f"""# Lift Report

## Summary

- Run: `{run_id}`
- Primary model: `{models["primary_model"]}`
- Trust level: `{trust["trust_level"]}`
- Exported targets: {target_count}
- Do-not-target segment: {anti_target_count}
- Constraint status: `{simulation.get("constraint_status", "unknown")}`
- Expected incremental ROI: {iroi_display}

## Campaign Incrementality

- Incremental maximize KPI: {campaign["incremental_maximize_kpi"]:.6f}
- Incremental constraint KPI: {campaign["incremental_constraint_kpi"]:.6f}
- Incremental ROI: {campaign["incremental_roi"]}

## Budget Simulation

- Budget: {simulation.get("budget")}
- Minimum ROI: {simulation.get("min_roi")}
- Expected incremental gain: {simulation.get("expected_incremental_gain")}
- Expected incremental cost: {simulation.get("expected_incremental_cost")}
- Expected incremental profit: {simulation.get("expected_incremental_profit")}

> Note: target selection uses a greedy algorithm sorted by model score.
> This approximates but does not guarantee the global optimum under budget/ROI constraints.

## Trust

- Overlap status: `{trust.get("overlap_status", "unknown")}`
- Low-overlap rows: {trust.get("low_overlap_count", 0)} ({trust.get("low_overlap_rate", 0.0):.2%})
- Propensity range: {trust.get("propensity_min")} - {trust.get("propensity_max")}
- Observational: {trust.get("observational", False)}
- High-imbalance features: {imbalance}
- Leakage candidates excluded: {leakage}

{warnings}

## Model Leaderboard

{leaderboard_lines}

## Do-Not-Target Segment

{anti_target_note}

## Limitations

- Observational analyses retain hidden confounding risk. Causal estimates may be biased.
- Target selection is a greedy approximation. Budget and ROI constraints are enforced greedily, not globally optimised.
- Recommendations are policy simulations, not automatic campaign execution.
- `anti-targets.csv` lists customers with non-positive predicted uplift but does not guarantee harm from treatment.
"""


def _leaderboard_line(row: dict[str, Any]) -> str:
    budget_gain = row.get("gain_at_budget")
    min_roi_gain = row.get("gain_at_min_roi")
    aucc = row.get("aucc")
    aucc_str = f"{aucc:.6f}" if aucc is not None else "n/a"
    return (
        f"- {row['model']}: AUUC={row.get('auuc', 0.0):.6f}, "
        f"AUCC={aucc_str}, "
        f"Qini={row.get('qini', 0.0):.6f}, "
        f"gain_at_budget={budget_gain if budget_gain is not None else 'n/a'}, "
        f"gain_at_min_roi={min_roi_gain if min_roi_gain is not None else 'n/a'}"
    )
