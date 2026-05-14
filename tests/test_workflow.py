from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from lift.workflow.run import AnalyzeConfig, analyze


class WorkflowTest(unittest.TestCase):
    def test_analyze_writes_core_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset = root / "coupon.csv"
            with dataset.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "unit_id",
                        "treatment",
                        "treatment_propensity",
                        "maximize_kpi",
                        "constraint_kpi",
                        "feature_1",
                    ],
                )
                writer.writeheader()
                for index in range(20):
                    treated = index % 2
                    writer.writerow(
                        {
                            "unit_id": f"u{index}",
                            "treatment": treated,
                            "treatment_propensity": "0.5",
                            "maximize_kpi": 3 + treated + (index % 3),
                            "constraint_kpi": treated * (1 + (index % 2)),
                            "feature_1": index % 5,
                        }
                    )

            result = analyze(dataset, AnalyzeConfig(seed=7, output_root=str(root / "outputs")))

            run_dir = root / "outputs" / result["run_id"]
            for name in [
                "run.json",
                "schema.json",
                "trust.json",
                "campaign_incrementality.json",
                "models.json",
                "evaluation.json",
                "budget-frontier.csv",
                "targets.csv",
                "report.md",
                "provenance.md",
            ]:
                self.assertTrue((run_dir / name).exists(), name)
            self.assertEqual(result["primary_model"], "duality_r_learner")


if __name__ == "__main__":
    unittest.main()
