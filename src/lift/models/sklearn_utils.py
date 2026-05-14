from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from lift.data.schema import Schema

INTERCEPT_ONLY_FEATURE = "__lift_intercept__"


def feature_frame(rows: list[dict[str, Any]], schema: Schema) -> pd.DataFrame:
    if not schema.feature_columns:
        return pd.DataFrame({INTERCEPT_ONLY_FEATURE: [1.0] * len(rows)})
    return pd.DataFrame(rows)[schema.feature_columns].copy()


def outcome_vector(rows: list[dict[str, Any]], column: str) -> list[float]:
    return [float(row[column]) for row in rows]


def treatment_vector(rows: list[dict[str, Any]], schema: Schema) -> list[int]:
    return [int(row[schema.treatment]) for row in rows]


SUPPORTED_REGRESSION_MODELS = {"ridge", "random_forest", "gradient_boosting"}


def regression_pipeline(
    rows: list[dict[str, Any]],
    schema: Schema,
    *,
    model_type: str = "ridge",
    model_params: dict[str, Any] | None = None,
    seed: int = 123,
    alpha: float = 1.0,
) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", feature_preprocessor(rows, schema)),
            ("model", make_regressor(model_type, model_params=model_params, seed=seed, alpha=alpha)),
        ]
    )


def make_regressor(
    model_type: str,
    *,
    model_params: dict[str, Any] | None = None,
    seed: int = 123,
    alpha: float = 1.0,
) -> Any:
    params = dict(model_params or {})
    if model_type == "ridge":
        params.setdefault("alpha", alpha)
        return Ridge(**params)
    if model_type == "random_forest":
        params.setdefault("n_estimators", 100)
        params.setdefault("min_samples_leaf", 2)
        params.setdefault("random_state", seed)
        return RandomForestRegressor(**params)
    if model_type == "gradient_boosting":
        params.setdefault("n_estimators", 100)
        params.setdefault("learning_rate", 0.05)
        params.setdefault("max_depth", 3)
        params.setdefault("random_state", seed)
        return GradientBoostingRegressor(**params)
    raise ValueError(f"Unsupported regression model '{model_type}'. Supported: {sorted(SUPPORTED_REGRESSION_MODELS)}")


def feature_preprocessor(rows: list[dict[str, Any]], schema: Schema) -> ColumnTransformer:
    feature_columns = schema.feature_columns or [INTERCEPT_ONLY_FEATURE]
    numeric_columns, categorical_columns = split_feature_columns(rows, feature_columns)
    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if numeric_columns:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric_columns,
            )
        )
    if categorical_columns:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("one_hot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical_columns,
            )
        )
    return ColumnTransformer(transformers=transformers, remainder="drop")


def split_feature_columns(rows: list[dict[str, Any]], feature_columns: list[str]) -> tuple[list[str], list[str]]:
    numeric_columns: list[str] = []
    categorical_columns: list[str] = []
    for column in feature_columns:
        if _is_numeric_column(rows, column):
            numeric_columns.append(column)
        else:
            categorical_columns.append(column)
    return numeric_columns, categorical_columns


def _is_numeric_column(rows: list[dict[str, Any]], column: str) -> bool:
    for row in rows:
        value = row.get(column)
        if value in ("", None):
            continue
        try:
            float(value)
        except (TypeError, ValueError):
            return False
    return True
