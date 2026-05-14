from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lift.data.schema import Schema
from lift.evaluation.metrics import evaluate_ranking
from lift.models.baselines import ModelResult
from lift.models.linear import FeatureEncoder, RidgeRegressor


@dataclass
class DualityRLearner:
    lambda_grid: list[float]
    ridge_alpha: float = 1.0
    min_denominator: float = 1e-3

    def fit_predict(self, rows: list[dict[str, Any]], schema: Schema) -> ModelResult:
        encoder = FeatureEncoder(schema.feature_columns).fit(rows)
        matrix = encoder.transform(rows)
        treatment = [int(row[schema.treatment]) for row in rows]
        propensity = [_clip(float(row[schema.treatment_propensity]), self.min_denominator) for row in rows]
        gain = [float(row[schema.maximize_kpi]) for row in rows]
        cost = [float(row[schema.constraint_kpi]) for row in rows]

        tau_gain = self._r_learner_effect(matrix, treatment, propensity, gain)
        tau_cost = self._r_learner_effect(matrix, treatment, propensity, cost)

        selected_lambda = self.lambda_grid[0]
        selected_metric = float("-inf")
        selected_scores = tau_gain[:]
        grid_results: list[dict[str, float]] = []
        for lambda_value in self.lambda_grid:
            scores = [
                gain_value - lambda_value * max(cost_value, 0.0)
                for gain_value, cost_value in zip(tau_gain, tau_cost)
            ]
            metrics = evaluate_ranking(rows, schema, scores)
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
            },
        )

    def _r_learner_effect(
        self,
        matrix: list[list[float]],
        treatment: list[int],
        propensity: list[float],
        outcome: list[float],
    ) -> list[float]:
        mean_model = RidgeRegressor(alpha=self.ridge_alpha).fit(matrix, outcome)
        mean_prediction = mean_model.predict(matrix)
        residualized_target: list[float] = []
        weights: list[float] = []
        for flag, prop, y_value, m_value in zip(treatment, propensity, outcome, mean_prediction):
            residual_treatment = flag - prop
            if abs(residual_treatment) < self.min_denominator:
                residual_treatment = self.min_denominator if residual_treatment >= 0 else -self.min_denominator
            residualized_target.append((y_value - m_value) / residual_treatment)
            weights.append(residual_treatment * residual_treatment)
        tau_model = RidgeRegressor(alpha=self.ridge_alpha).fit(matrix, residualized_target, weights)
        return tau_model.predict(matrix)


def _clip(value: float, epsilon: float) -> float:
    return min(max(value, epsilon), 1.0 - epsilon)
