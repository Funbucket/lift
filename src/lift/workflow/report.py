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
    return f"""# Lift Report

## Summary

- Run: `{run_id}`
- Primary model: `{models["primary_model"]}`
- Trust level: `{trust["trust_level"]}`
- Exported targets: {simulation.get("target_count", 0)}
- Constraint status: `{simulation.get("constraint_status", "unknown")}`
- Expected incremental ROI: {simulation.get("expected_incremental_roi", "n/a")}

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
