from __future__ import annotations

import unittest

from lift.data.schema import infer_schema, prepare_rows
from lift.evaluation.metrics import campaign_incrementality, evaluate_ranking


class MetricsTest(unittest.TestCase):
    def test_campaign_incrementality_has_ci_for_randomized_data(self) -> None:
        rows = prepare_rows(_rows(), infer_schema(_rows()))
        schema = infer_schema(_rows())

        result = campaign_incrementality(rows, schema)

        self.assertIn("incremental_maximize_kpi_ci95", result)
        self.assertIsNotNone(result["incremental_maximize_kpi_ci95"])

    def test_ranking_includes_auuc_and_qini(self) -> None:
        raw_rows = _rows()
        schema = infer_schema(raw_rows)
        rows = prepare_rows(raw_rows, schema)

        result = evaluate_ranking(rows, schema, [4.0, 1.0, 3.0, 2.0])

        self.assertIn("auuc", result)
        self.assertIn("qini", result)


def _rows() -> list[dict[str, str]]:
    return [
        {"unit_id": "u1", "treatment": "1", "treatment_propensity": "0.5", "maximize_kpi": "4", "constraint_kpi": "1", "feature_1": "1"},
        {"unit_id": "u2", "treatment": "0", "treatment_propensity": "0.5", "maximize_kpi": "1", "constraint_kpi": "0", "feature_1": "1"},
        {"unit_id": "u3", "treatment": "1", "treatment_propensity": "0.5", "maximize_kpi": "5", "constraint_kpi": "2", "feature_1": "2"},
        {"unit_id": "u4", "treatment": "0", "treatment_propensity": "0.5", "maximize_kpi": "1", "constraint_kpi": "0", "feature_1": "2"},
    ]


if __name__ == "__main__":
    unittest.main()
