from __future__ import annotations

from typing import Any

from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline

from lift.data.schema import Schema
from lift.models.sklearn_utils import feature_frame, feature_preprocessor


def estimate_propensity(
    rows: list[dict[str, Any]],
    schema: Schema,
    *,
    folds: int = 2,
    seed: int = 123,
    clip_min: float = 0.01,
    clip_max: float = 0.99,
) -> dict[str, Any]:
    if not schema.feature_columns:
        rate = _treatment_rate(rows, schema)
        estimates = [rate] * len(rows)
        return {
            "source": "constant_treatment_rate",
            "propensity": estimates,
            "clip_min": clip_min,
            "clip_max": clip_max,
            "folds": 0,
        }

    treatment = [float(row[schema.treatment]) for row in rows]
    if min(sum(treatment), len(treatment) - sum(treatment)) < folds:
        rate = _treatment_rate(rows, schema)
        return {
            "source": "constant_treatment_rate_insufficient_class_count",
            "propensity": [rate] * len(rows),
            "clip_min": clip_min,
            "clip_max": clip_max,
            "folds": 0,
        }
    estimates = _cross_fit_predictions(
        rows,
        schema,
        [int(value) for value in treatment],
        folds=min(max(folds, 2), len(rows)),
        seed=seed,
    )
    clipped = [min(max(value, clip_min), clip_max) for value in estimates]
    return {
        "source": "estimated_linear_probability_cross_fit",
        "propensity": clipped,
        "raw_min": min(estimates) if estimates else None,
        "raw_max": max(estimates) if estimates else None,
        "clip_min": clip_min,
        "clip_max": clip_max,
        "folds": min(max(folds, 2), len(rows)),
        "feature_columns": schema.feature_columns,
    }


def apply_propensity_estimates(
    rows: list[dict[str, Any]],
    schema: Schema,
    estimates: list[float],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row, propensity in zip(rows, estimates):
        updated = dict(row)
        updated[schema.treatment_propensity] = propensity
        output.append(updated)
    return output


def _cross_fit_predictions(
    rows: list[dict[str, Any]],
    schema: Schema,
    target: list[int],
    *,
    folds: int,
    seed: int,
) -> list[float]:
    features = feature_frame(rows, schema)
    base_model = Pipeline(
        steps=[
            ("preprocess", feature_preprocessor(rows, schema)),
            ("model", LogisticRegression(max_iter=1000, random_state=seed)),
        ]
    )
    if len(rows) < 4:
        return base_model.fit(features, target).predict_proba(features)[:, 1].tolist()
    predictions = [0.0] * len(rows)
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train_indices, validation_indices in splitter.split(features, target):
        model = clone(base_model)
        model.fit(features.iloc[train_indices], [target[int(index)] for index in train_indices])
        for index in validation_indices:
            predictions[int(index)] = float(model.predict_proba(features.iloc[[int(index)]])[0, 1])
    return predictions


def _treatment_rate(rows: list[dict[str, Any]], schema: Schema) -> float:
    rate = sum(float(row[schema.treatment]) for row in rows) / max(len(rows), 1)
    return min(max(rate, 0.01), 0.99)
