from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_LEAKAGE_HINTS = (
    "clicked",
    "used",
    "post_",
    "after_",
    "outcome",
    "revenue_after",
    "purchase_after",
)


@dataclass(frozen=True)
class Schema:
    unit_id: str = "unit_id"
    treatment: str = "treatment"
    maximize_kpi: str = "maximize_kpi"
    constraint_kpi: str = "constraint_kpi"
    treatment_propensity: str = "treatment_propensity"
    sample_weight: str | None = "sample_weight"
    constraint_offset_kpi: str | None = None
    feature_columns: list[str] = field(default_factory=list)
    excluded_feature_columns: list[str] = field(default_factory=list)

    def logical_columns(self) -> set[str]:
        columns = {
            self.unit_id,
            self.treatment,
            self.maximize_kpi,
            self.constraint_kpi,
            self.treatment_propensity,
        }
        if self.sample_weight:
            columns.add(self.sample_weight)
        if self.constraint_offset_kpi:
            columns.add(self.constraint_offset_kpi)
        return columns

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "treatment": self.treatment,
            "maximize_kpi": self.maximize_kpi,
            "constraint_kpi": self.constraint_kpi,
            "treatment_propensity": self.treatment_propensity,
            "sample_weight": self.sample_weight,
            "constraint_offset_kpi": self.constraint_offset_kpi,
            "feature_columns": self.feature_columns,
            "excluded_feature_columns": self.excluded_feature_columns,
        }


def infer_schema(
    rows: list[dict[str, Any]],
    *,
    unit_id: str = "unit_id",
    treatment: str = "treatment",
    maximize_kpi: str = "maximize_kpi",
    constraint_kpi: str = "constraint_kpi",
    treatment_propensity: str = "treatment_propensity",
    sample_weight: str | None = "sample_weight",
    constraint_offset_kpi: str | None = None,
) -> Schema:
    if not rows:
        raise ValueError("Dataset is empty.")

    columns = list(rows[0].keys())
    logical = {
        unit_id,
        treatment,
        maximize_kpi,
        constraint_kpi,
        treatment_propensity,
    }
    if sample_weight and sample_weight in columns:
        logical.add(sample_weight)
    else:
        sample_weight = None
    if constraint_offset_kpi:
        logical.add(constraint_offset_kpi)

    leakage = [column for column in columns if _looks_like_leakage(column)]
    feature_columns = [
        column
        for column in columns
        if column not in logical and column not in leakage
    ]

    return Schema(
        unit_id=unit_id,
        treatment=treatment,
        maximize_kpi=maximize_kpi,
        constraint_kpi=constraint_kpi,
        treatment_propensity=treatment_propensity,
        sample_weight=sample_weight,
        constraint_offset_kpi=constraint_offset_kpi,
        feature_columns=feature_columns,
        excluded_feature_columns=leakage,
    )


def validate_rows(rows: list[dict[str, Any]], schema: Schema) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    columns = set(rows[0].keys()) if rows else set()

    required = [schema.unit_id, schema.treatment, schema.maximize_kpi, schema.constraint_kpi]
    for column in required:
        if column not in columns:
            errors.append(f"Missing required column: {column}")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    seen_ids: set[str] = set()
    treatment_values: set[int] = set()
    for index, row in enumerate(rows):
        unit_id = str(row.get(schema.unit_id, ""))
        if unit_id in seen_ids:
            errors.append(f"Duplicated unit_id at row {index}: {unit_id}")
        seen_ids.add(unit_id)

        try:
            treatment = int(float(row[schema.treatment]))
        except (TypeError, ValueError):
            errors.append(f"Non-numeric treatment at row {index}")
            continue
        treatment_values.add(treatment)
        if treatment not in (0, 1):
            errors.append(f"Treatment must be binary at row {index}: {treatment}")

        for column in (schema.maximize_kpi, schema.constraint_kpi):
            try:
                float(row[column])
            except (TypeError, ValueError):
                errors.append(f"Non-numeric KPI column {column} at row {index}")

        if schema.treatment_propensity in row and row[schema.treatment_propensity] not in ("", None):
            try:
                propensity = float(row[schema.treatment_propensity])
                if propensity <= 0.0 or propensity >= 1.0:
                    errors.append(f"Propensity must be in (0, 1) at row {index}: {propensity}")
            except (TypeError, ValueError):
                errors.append(f"Non-numeric propensity at row {index}")

    if treatment_values != {0, 1}:
        errors.append("Dataset must contain both treatment and control rows.")

    if schema.excluded_feature_columns:
        warnings.append(
            "Excluded likely post-treatment/leakage columns: "
            + ", ".join(schema.excluded_feature_columns)
        )

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def coerce_row(row: dict[str, Any], schema: Schema, inferred_propensity: float) -> dict[str, Any]:
    coerced = dict(row)
    coerced[schema.treatment] = int(float(row[schema.treatment]))
    coerced[schema.maximize_kpi] = float(row[schema.maximize_kpi])
    coerced[schema.constraint_kpi] = float(row[schema.constraint_kpi])
    if schema.treatment_propensity in row and row[schema.treatment_propensity] not in ("", None):
        coerced[schema.treatment_propensity] = float(row[schema.treatment_propensity])
    else:
        coerced[schema.treatment_propensity] = inferred_propensity
    if schema.sample_weight:
        raw_weight = row.get(schema.sample_weight, 1.0)
        coerced[schema.sample_weight] = float(raw_weight) if raw_weight not in ("", None) else 1.0
    if schema.constraint_offset_kpi:
        coerced[schema.constraint_offset_kpi] = float(row.get(schema.constraint_offset_kpi, 0.0) or 0.0)
    return coerced


def prepare_rows(rows: list[dict[str, Any]], schema: Schema) -> list[dict[str, Any]]:
    treatment_rate = sum(int(float(row[schema.treatment])) for row in rows) / len(rows)
    clipped_rate = min(max(treatment_rate, 1e-3), 1.0 - 1e-3)
    return [coerce_row(row, schema, clipped_rate) for row in rows]


def _looks_like_leakage(column: str) -> bool:
    normalized = column.lower()
    return any(hint in normalized for hint in DEFAULT_LEAKAGE_HINTS)
