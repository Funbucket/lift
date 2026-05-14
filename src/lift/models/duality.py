from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.model_selection import KFold

from lift.data.schema import Schema
from lift.evaluation.metrics import evaluate_ranking
from lift.models.baselines import ModelResult
from lift.models.sklearn_utils import feature_frame, outcome_vector, regression_pipeline, treatment_vector


@dataclass
class DualityRLearner:
    lambda_grid: list[float]
    ridge_alpha: float = 1.0
    min_denominator: float = 1e-3
    cross_fit_folds: int = 2
    seed: int = 123

    def fit_predict(
        self,
        rows: list[dict[str, Any]],
        schema: Schema,
        *,
        validation_indices: set[int] | None = None,
    ) -> ModelResult:
        treatment = treatment_vector(rows, schema)
        propensity = [_clip(float(row[schema.treatment_propensity]), self.min_denominator) for row in rows]
        gain = outcome_vector(rows, schema.maximize_kpi)
        cost = outcome_vector(rows, schema.constraint_kpi)

        tau_gain = self._r_learner_effect(rows, schema, treatment, propensity, gain)
        tau_cost = self._r_learner_effect(rows, schema, treatment, propensity, cost)

        selected_lambda = self.lambda_grid[0]
        selected_metric = float("-inf")
        selected_scores = tau_gain[:]
        grid_results: list[dict[str, float]] = []
        for lambda_value in self.lambda_grid:
            scores = [
                gain_value - lambda_value * max(cost_value, 0.0)
                for gain_value, cost_value in zip(tau_gain, tau_cost)
            ]
            eval_rows, eval_scores = _validation_view(rows, scores, validation_indices)
            metrics = evaluate_ranking(eval_rows, schema, eval_scores)
            aucc = float(metrics["aucc"])
            grid_results.append({"lambda": lambda_value, "aucc": aucc})
            if aucc > selected_metric:
                selected_metric = aucc
                selected_lambda = lambda_value
                selected_scores = scores

        return ModelResult(
            name="duality_r_learner",
            scores=selected_scores,
            expected_incremental_gain=tau_gain,
            expected_incremental_cost=tau_cost,
            metadata={
                "type": "core",
                "lambda": selected_lambda,
                "selected_lambda_metric": selected_metric,
                "lambda_grid": self.lambda_grid,
                "lambda_grid_results": grid_results,
                "score_formula": "tau_gain - lambda * max(tau_cost, 0)",
                "ridge_alpha": self.ridge_alpha,
                "cross_fit_folds": min(self.cross_fit_folds, len(rows)),
                "seed": self.seed,
                "lambda_selection": "validation_aucc" if validation_indices else "in_sample_aucc",
                "validation_count": len(validation_indices) if validation_indices else 0,
            },
        )

    def _r_learner_effect(
        self,
        rows: list[dict[str, Any]],
        schema: Schema,
        treatment: list[int],
        propensity: list[float],
        outcome: list[float],
    ) -> list[float]:
        mean_prediction = self._cross_fit_mean_prediction(rows, schema, outcome)
        residualized_target: list[float] = []
        weights: list[float] = []
        for flag, prop, y_value, m_value in zip(treatment, propensity, outcome, mean_prediction):
            residual_treatment = flag - prop
            if abs(residual_treatment) < self.min_denominator:
                residual_treatment = self.min_denominator if residual_treatment >= 0 else -self.min_denominator
            residualized_target.append((y_value - m_value) / residual_treatment)
            weights.append(residual_treatment * residual_treatment)
        features = feature_frame(rows, schema)
        tau_model = regression_pipeline(rows, schema, alpha=self.ridge_alpha)
        tau_model.fit(features, residualized_target, model__sample_weight=np.asarray(weights))
        return tau_model.predict(features).tolist()

    def _cross_fit_mean_prediction(
        self,
        rows: list[dict[str, Any]],
        schema: Schema,
        outcome: list[float],
    ) -> list[float]:
        features = feature_frame(rows, schema)
        base_model = regression_pipeline(rows, schema, alpha=self.ridge_alpha)
        if len(rows) < 4 or self.cross_fit_folds <= 1:
            return base_model.fit(features, outcome).predict(features).tolist()

        fold_count = min(self.cross_fit_folds, len(rows))
        predictions = [0.0] * len(rows)
        splitter = KFold(n_splits=fold_count, shuffle=True, random_state=self.seed)
        for train_indices, validation_indices in splitter.split(features):
            model = clone(base_model)
            model.fit(features.iloc[train_indices], [outcome[int(index)] for index in train_indices])
            for index in validation_indices:
                predictions[int(index)] = float(model.predict(features.iloc[[int(index)]])[0])
        return predictions


def _clip(value: float, epsilon: float) -> float:
    return min(max(value, epsilon), 1.0 - epsilon)


def _validation_view(
    rows: list[dict[str, Any]],
    scores: list[float],
    validation_indices: set[int] | None,
) -> tuple[list[dict[str, Any]], list[float]]:
    if not validation_indices:
        return rows, scores
    eval_rows = [row for index, row in enumerate(rows) if index in validation_indices]
    eval_scores = [score for index, score in enumerate(scores) if index in validation_indices]
    return eval_rows, eval_scores
