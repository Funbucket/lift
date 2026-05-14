from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from lift.data.schema import Schema
from lift.models.sklearn_utils import feature_frame, outcome_vector, regression_pipeline, treatment_vector


@dataclass
class ModelResult:
    name: str
    scores: list[float]
    expected_incremental_gain: list[float]
    expected_incremental_cost: list[float]
    metadata: dict[str, Any]


def train_baselines(rows: list[dict[str, Any]], schema: Schema, *, seed: int) -> list[ModelResult]:
    features = feature_frame(rows, schema)
    gain = outcome_vector(rows, schema.maximize_kpi)
    cost = outcome_vector(rows, schema.constraint_kpi)
    treatment = treatment_vector(rows, schema)

    random_scores = _random_scores(len(rows), seed)
    response_model = regression_pipeline(rows, schema, alpha=1.0).fit(features, gain)
    response_scores = response_model.predict(features).tolist()
    tau_gain = _t_learner_effect(rows, schema, gain, treatment)
    tau_cost = _t_learner_effect(rows, schema, cost, treatment)
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


def _t_learner_effect(
    rows: list[dict[str, Any]],
    schema: Schema,
    target: list[float],
    treatment: list[int],
) -> list[float]:
    treated_rows = [row for row, flag in zip(rows, treatment) if flag == 1]
    treated_y = [value for value, flag in zip(target, treatment) if flag == 1]
    control_rows = [row for row, flag in zip(rows, treatment) if flag == 0]
    control_y = [value for value, flag in zip(target, treatment) if flag == 0]
    treated_model = regression_pipeline(rows, schema, alpha=1.0).fit(feature_frame(treated_rows, schema), treated_y)
    control_model = regression_pipeline(rows, schema, alpha=1.0).fit(feature_frame(control_rows, schema), control_y)
    features = feature_frame(rows, schema)
    return (treated_model.predict(features) - control_model.predict(features)).tolist()
