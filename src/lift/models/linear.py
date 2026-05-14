from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FeatureEncoder:
    feature_columns: list[str]
    numeric_columns: list[str] = field(default_factory=list)
    categorical_values: dict[str, list[str]] = field(default_factory=dict)

    def fit(self, rows: list[dict[str, Any]]) -> "FeatureEncoder":
        numeric: list[str] = []
        categorical: dict[str, set[str]] = {}
        for column in self.feature_columns:
            is_numeric = True
            values: set[str] = set()
            for row in rows:
                value = row.get(column, "")
                if value in ("", None):
                    continue
                try:
                    float(value)
                except (TypeError, ValueError):
                    is_numeric = False
                    values.add(str(value))
            if is_numeric:
                numeric.append(column)
            else:
                categorical[column] = values
        self.numeric_columns = numeric
        self.categorical_values = {key: sorted(value) for key, value in categorical.items()}
        return self

    def transform_row(self, row: dict[str, Any]) -> list[float]:
        vector = [1.0]
        for column in self.numeric_columns:
            raw = row.get(column, 0.0)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                value = 0.0
            if not math.isfinite(value):
                value = 0.0
            vector.append(value)
        for column, values in self.categorical_values.items():
            raw = str(row.get(column, ""))
            vector.extend(1.0 if raw == value else 0.0 for value in values)
        return vector

    def transform(self, rows: list[dict[str, Any]]) -> list[list[float]]:
        return [self.transform_row(row) for row in rows]

    @property
    def width(self) -> int:
        return 1 + len(self.numeric_columns) + sum(len(values) for values in self.categorical_values.values())


@dataclass
class RidgeRegressor:
    alpha: float = 1.0
    coefficients: list[float] = field(default_factory=list)

    def fit(
        self,
        matrix: list[list[float]],
        target: list[float],
        weights: list[float] | None = None,
    ) -> "RidgeRegressor":
        if not matrix:
            self.coefficients = []
            return self
        width = len(matrix[0])
        weights = weights or [1.0] * len(matrix)
        xtx = [[0.0 for _ in range(width)] for _ in range(width)]
        xty = [0.0 for _ in range(width)]
        for row, y_value, weight in zip(matrix, target, weights):
            safe_weight = max(float(weight), 0.0)
            for i in range(width):
                xty[i] += safe_weight * row[i] * y_value
                for j in range(width):
                    xtx[i][j] += safe_weight * row[i] * row[j]
        for i in range(width):
            xtx[i][i] += self.alpha
        self.coefficients = _solve(xtx, xty)
        return self

    def predict_one(self, vector: list[float]) -> float:
        if not self.coefficients:
            return 0.0
        return sum(coef * value for coef, value in zip(self.coefficients, vector))

    def predict(self, matrix: list[list[float]]) -> list[float]:
        return [self.predict_one(row) for row in matrix]


def _solve(matrix: list[list[float]], values: list[float]) -> list[float]:
    size = len(values)
    augmented = [row[:] + [value] for row, value in zip(matrix, values)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda idx: abs(augmented[idx][col]))
        if abs(augmented[pivot][col]) < 1e-12:
            continue
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        augmented[col] = [value / divisor for value in augmented[col]]
        for row_idx in range(size):
            if row_idx == col:
                continue
            factor = augmented[row_idx][col]
            augmented[row_idx] = [
                current - factor * pivot_value
                for current, pivot_value in zip(augmented[row_idx], augmented[col])
            ]
    return [augmented[row][size] for row in range(size)]
