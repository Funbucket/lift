from __future__ import annotations

import math
from typing import Any

from lift.data.schema import Schema


def campaign_incrementality(rows: list[dict[str, Any]], schema: Schema) -> dict[str, Any]:
    gain = _incremental_mean(rows, schema, schema.maximize_kpi)
    cost = _incremental_mean(rows, schema, schema.constraint_kpi)
    return {
        "incremental_maximize_kpi": gain,
        "incremental_constraint_kpi": cost,
        "incremental_roi": _safe_divide(gain, cost),
        "treatment_count": sum(1 for row in rows if int(row[schema.treatment]) == 1),
        "control_count": sum(1 for row in rows if int(row[schema.treatment]) == 0),
    }


def evaluate_ranking(rows: list[dict[str, Any]], schema: Schema, scores: list[float]) -> dict[str, Any]:
    ordered = sorted(zip(rows, scores), key=lambda item: item[1], reverse=True)
    curve: list[dict[str, float]] = []
    for index in range(1, len(ordered) + 1):
        cohort = [row for row, _score in ordered[:index]]
        inc_gain = _incremental_mean(cohort, schema, schema.maximize_kpi)
        inc_cost = _incremental_mean(cohort, schema, schema.constraint_kpi)
        share = index / len(ordered)
        curve.append(
            {
                "target_count": float(index),
                "target_share": share,
                "incremental_gain": inc_gain,
                "incremental_cost": inc_cost,
                "incremental_roi": _safe_divide(inc_gain, inc_cost),
                "cpia": _safe_divide(inc_cost, inc_gain),
            }
        )
    return {
        "aucc": _area_under_curve(curve, "target_share", "incremental_gain"),
        "max_incremental_gain": max((point["incremental_gain"] for point in curve), default=0.0),
        "max_incremental_roi": max(
            (point["incremental_roi"] for point in curve if math.isfinite(point["incremental_roi"])),
            default=0.0,
        ),
        "target_count_at_max_gain": _target_count_at_max(curve, "incremental_gain"),
        "curve": curve,
    }


def budget_frontier(
    rows: list[dict[str, Any]],
    schema: Schema,
    scores: list[float],
    expected_gain: list[float],
    expected_cost: list[float],
) -> list[dict[str, Any]]:
    ordered = sorted(
        zip(rows, scores, expected_gain, expected_cost),
        key=lambda item: item[1],
        reverse=True,
    )
    frontier: list[dict[str, Any]] = []
    cumulative_gain = 0.0
    cumulative_cost = 0.0
    for rank, (row, score, gain, cost) in enumerate(ordered, start=1):
        safe_cost = max(float(cost), 0.0)
        cumulative_gain += float(gain)
        cumulative_cost += safe_cost
        frontier.append(
            {
                "rank": rank,
                "unit_id": row[schema.unit_id],
                "score": score,
                "cumulative_expected_gain": cumulative_gain,
                "cumulative_expected_cost": cumulative_cost,
                "cumulative_expected_profit": cumulative_gain - cumulative_cost,
                "cumulative_expected_roi": _safe_divide(cumulative_gain, cumulative_cost),
            }
        )
    return frontier


def select_targets(
    rows: list[dict[str, Any]],
    schema: Schema,
    scores: list[float],
    expected_gain: list[float],
    expected_cost: list[float],
    *,
    budget: float | None = None,
    min_roi: float | None = None,
    trust_level: str,
) -> list[dict[str, Any]]:
    ordered = sorted(
        zip(rows, scores, expected_gain, expected_cost),
        key=lambda item: item[1],
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    cumulative_gain = 0.0
    cumulative_cost = 0.0
    for rank, (row, score, gain, cost) in enumerate(ordered, start=1):
        safe_cost = max(float(cost), 0.0)
        if score <= 0.0 or gain <= 0.0:
            continue
        next_gain = cumulative_gain + float(gain)
        next_cost = cumulative_cost + safe_cost
        if budget is not None and next_cost > budget:
            continue
        if min_roi is not None and next_cost > 0 and next_gain / next_cost < min_roi:
            continue
        cumulative_gain = next_gain
        cumulative_cost = next_cost
        selected.append(
            {
                "unit_id": row[schema.unit_id],
                "rank": len(selected) + 1,
                "score": score,
                "recommended_treatment": 1,
                "expected_incremental_gain": gain,
                "expected_incremental_cost": safe_cost,
                "expected_incremental_profit": gain - safe_cost,
                "expected_incremental_roi": _safe_divide(gain, safe_cost),
                "selection_reason": "positive cost-aware incremental score",
                "trust_level": trust_level,
            }
        )
    return selected


def _incremental_mean(rows: list[dict[str, Any]], schema: Schema, column: str) -> float:
    treated_num = treated_den = control_num = control_den = 0.0
    for row in rows:
        propensity = min(max(float(row[schema.treatment_propensity]), 1e-6), 1.0 - 1e-6)
        sample_weight = float(row.get(schema.sample_weight, 1.0)) if schema.sample_weight else 1.0
        if int(row[schema.treatment]) == 1:
            weight = sample_weight / propensity
            treated_num += weight * float(row[column])
            treated_den += weight
        else:
            weight = sample_weight / (1.0 - propensity)
            control_num += weight * float(row[column])
            control_den += weight
    if treated_den == 0.0 or control_den == 0.0:
        return 0.0
    return treated_num / treated_den - control_num / control_den


def _area_under_curve(curve: list[dict[str, float]], x_key: str, y_key: str) -> float:
    if not curve:
        return 0.0
    area = 0.0
    previous_x = 0.0
    previous_y = 0.0
    for point in curve:
        x_value = point[x_key]
        y_value = point[y_key]
        area += (x_value - previous_x) * (y_value + previous_y) / 2.0
        previous_x = x_value
        previous_y = y_value
    return area


def _target_count_at_max(curve: list[dict[str, float]], key: str) -> int:
    if not curve:
        return 0
    return int(max(curve, key=lambda point: point[key])["target_count"])


def _safe_divide(numerator: float, denominator: float) -> float:
    if abs(denominator) < 1e-12:
        return math.inf if numerator > 0 else 0.0
    return numerator / denominator
