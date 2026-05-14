from __future__ import annotations

from statistics import mean
from typing import Any

from lift.data.schema import Schema


def diagnose(rows: list[dict[str, Any]], schema: Schema, validation: dict[str, Any]) -> dict[str, Any]:
    treatment_count = sum(1 for row in rows if int(row[schema.treatment]) == 1)
    control_count = len(rows) - treatment_count
    propensities = [float(row[schema.treatment_propensity]) for row in rows]
    warnings = list(validation.get("warnings", []))
    errors = list(validation.get("errors", []))

    low_overlap_count = sum(1 for value in propensities if value < 0.05 or value > 0.95)
    low_overlap_rate = low_overlap_count / max(len(rows), 1)
    if low_overlap_count:
        warnings.append(f"{low_overlap_count} rows have propensity outside [0.05, 0.95].")
    observational = _is_observational(propensities)
    if observational:
        warnings.append("Observational propensity detected; hidden confounding risk remains.")

    balance = _covariate_balance(rows, schema)
    high_imbalance = [item for item in balance if abs(item["standardized_difference"]) > 0.25]
    if high_imbalance:
        warnings.append("Covariate imbalance detected for: " + ", ".join(item["feature"] for item in high_imbalance[:5]))
    if schema.excluded_feature_columns:
        warnings.append(
            "Likely leakage columns were excluded from modeling features: "
            + ", ".join(schema.excluded_feature_columns)
        )

    rating = "high"
    if errors:
        rating = "blocked"
    elif low_overlap_rate > 0.2:
        rating = "low"
    elif low_overlap_count or observational or high_imbalance or schema.excluded_feature_columns:
        rating = "medium"
    percentiles = _propensity_percentiles(propensities)

    return {
        "trust_level": rating,
        "treatment_count": treatment_count,
        "control_count": control_count,
        "treatment_ratio": treatment_count / max(len(rows), 1),
        "propensity_source": "provided_or_inferred",
        "propensity_min": min(propensities) if propensities else None,
        "propensity_max": max(propensities) if propensities else None,
        "propensity_mean": mean(propensities) if propensities else None,
        "propensity_percentiles": percentiles,
        "low_overlap_count": low_overlap_count,
        "low_overlap_rate": low_overlap_rate,
        "overlap_status": _overlap_status(low_overlap_rate),
        "observational": observational,
        "covariate_balance": balance,
        "high_imbalance_features": [item["feature"] for item in high_imbalance],
        "leakage_candidates": schema.excluded_feature_columns,
        "leakage_action": "excluded_from_features" if schema.excluded_feature_columns else "none_detected",
        "warnings": warnings,
        "errors": errors,
    }


def _is_observational(propensities: list[float]) -> bool:
    if not propensities:
        return False
    return max(propensities) - min(propensities) > 1e-9


def _overlap_status(low_overlap_rate: float) -> str:
    if low_overlap_rate > 0.2:
        return "poor"
    if low_overlap_rate > 0.0:
        return "watch"
    return "ok"


def _propensity_percentiles(propensities: list[float]) -> dict[str, float | None]:
    if not propensities:
        return {"p01": None, "p05": None, "p50": None, "p95": None, "p99": None}
    ordered = sorted(propensities)
    return {
        "p01": _quantile(ordered, 0.01),
        "p05": _quantile(ordered, 0.05),
        "p50": _quantile(ordered, 0.50),
        "p95": _quantile(ordered, 0.95),
        "p99": _quantile(ordered, 0.99),
    }


def _quantile(ordered: list[float], q: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _covariate_balance(rows: list[dict[str, Any]], schema: Schema) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for feature in schema.feature_columns:
        values: list[tuple[int, float]] = []
        for row in rows:
            try:
                values.append((int(row[schema.treatment]), float(row.get(feature, 0.0))))
            except (TypeError, ValueError):
                values = []
                break
        if not values:
            continue
        treated = [value for flag, value in values if flag == 1]
        control = [value for flag, value in values if flag == 0]
        if not treated or not control:
            continue
        pooled = _std([value for _flag, value in values])
        standardized = 0.0 if pooled == 0.0 else (mean(treated) - mean(control)) / pooled
        diagnostics.append({"feature": feature, "standardized_difference": standardized})
    return diagnostics


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return variance ** 0.5
