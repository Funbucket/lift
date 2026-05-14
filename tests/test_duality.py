from __future__ import annotations

import unittest

from lift.data.schema import infer_schema, prepare_rows, validate_rows
from lift.models.duality import DualityRLearner


class DualityRLearnerTest(unittest.TestCase):
    def test_duality_score_matches_formula(self) -> None:
        rows = _rows()
        schema = infer_schema(rows)
        validation = validate_rows(rows, schema)
        self.assertTrue(validation["valid"], validation)
        prepared = prepare_rows(rows, schema)

        model = DualityRLearner(lambda_grid=[0.5]).fit_predict(prepared, schema)

        self.assertEqual(model.name, "duality_r_learner")
        self.assertEqual(model.metadata["lambda"], 0.5)
        for score, gain, cost in zip(
            model.scores,
            model.expected_incremental_gain,
            model.expected_incremental_cost,
        ):
            self.assertLess(abs(score - (gain - 0.5 * max(cost, 0.0))), 1e-9)


def _rows() -> list[dict[str, str]]:
    return [
        {"unit_id": "u1", "treatment": "1", "treatment_propensity": "0.5", "maximize_kpi": "4", "constraint_kpi": "1", "feature_1": "1"},
        {"unit_id": "u2", "treatment": "0", "treatment_propensity": "0.5", "maximize_kpi": "1", "constraint_kpi": "0", "feature_1": "1"},
        {"unit_id": "u3", "treatment": "1", "treatment_propensity": "0.5", "maximize_kpi": "5", "constraint_kpi": "2", "feature_1": "2"},
        {"unit_id": "u4", "treatment": "0", "treatment_propensity": "0.5", "maximize_kpi": "1", "constraint_kpi": "0", "feature_1": "2"},
        {"unit_id": "u5", "treatment": "1", "treatment_propensity": "0.5", "maximize_kpi": "2", "constraint_kpi": "4", "feature_1": "3"},
        {"unit_id": "u6", "treatment": "0", "treatment_propensity": "0.5", "maximize_kpi": "1", "constraint_kpi": "0", "feature_1": "3"},
    ]


if __name__ == "__main__":
    unittest.main()
