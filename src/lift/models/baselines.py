from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from lift.data.schema import Schema
from lift.models.linear import FeatureEncoder, RidgeRegressor


@dataclass
class ModelResult:
    name: str
    scores: list[float]
    expected_incremental_gain: list[float]
    expected_incremental_cost: list[float]
    metadata: dict[str, Any]


def train_baselines(rows: list[dict[str, Any]], schema: Schema, *, seed: int) -> list[ModelResult]:
    encoder = FeatureEncoder(schema.feature_columns).fit(rows)
    matrix = encoder.transform(rows)
    gain = [float(row[schema.maximize_kpi]) for row in rows]
    cost = [float(row[schema.constraint_kpi]) for row in rows]
    treatment = [int(row[schema.treatment]) for row in rows]

    random_scores = _random_scores(len(rows), seed)
    response_scores = RidgeRegressor(alpha=1.0).fit(matrix, gain).predict(matrix)
    tau_gain = _t_learner_effect(matrix, gain, treatment)
    tau_cost = _t_learner_effect(matrix, cost, treatment)
    profit = [g - c for g, c in zip(tau_gain, tau_cost)]

    return [
        ModelResult(
            name="random",
            scores=random_scores,
            expected_incremental_gain=[0.0] * len(rows),
            expected_incremental_cost=[0.0] * len(rows),
            metadata={"type": "baseline", "seed": seed},
        ),
        ModelResult(
            name="response_model",
            scores=response_scores,
            expected_incremental_gain=[0.0] * len(rows),
            expected_incremental_cost=[0.0] * len(rows),
            metadata={"type": "baseline", "description": "Ranks by predicted maximize KPI response."},
        ),
        ModelResult(
            name="t_learner_gain",
            scores=tau_gain,
            expected_incremental_gain=tau_gain,
            expected_incremental_cost=tau_cost,
            metadata={"type": "baseline", "description": "T-learner for maximize KPI."},
        ),
        ModelResult(
            name="t_learner_cost",
            scores=[-value for value in tau_cost],
            expected_incremental_gain=tau_gain,
            expected_incremental_cost=tau_cost,
            metadata={"type": "baseline", "description": "Ranks by lower estimated incremental cost."},
        ),
        ModelResult(
            name="profit_ranking",
            scores=profit,
            expected_incremental_gain=tau_gain,
            expected_incremental_cost=tau_cost,
            metadata={"type": "baseline", "description": "T-learner gain minus cost."},
        ),
    ]


def _random_scores(size: int, seed: int) -> list[float]:
    generator = random.Random(seed)
    return [generator.random() for _ in range(size)]


def _t_learner_effect(matrix: list[list[float]], target: list[float], treatment: list[int]) -> list[float]:
    treated_x = [row for row, flag in zip(matrix, treatment) if flag == 1]
    treated_y = [value for value, flag in zip(target, treatment) if flag == 1]
    control_x = [row for row, flag in zip(matrix, treatment) if flag == 0]
    control_y = [value for value, flag in zip(target, treatment) if flag == 0]
    treated_model = RidgeRegressor(alpha=1.0).fit(treated_x, treated_y)
    control_model = RidgeRegressor(alpha=1.0).fit(control_x, control_y)
    return [
        treated_model.predict_one(row) - control_model.predict_one(row)
        for row in matrix
    ]
