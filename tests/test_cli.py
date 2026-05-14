from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from lift.interfaces.cli import app


class CliTest(unittest.TestCase):
    def test_outputs_returns_run_summaries(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset = root / "coupon.csv"
            _write_dataset(dataset)

            analyze = runner.invoke(
                app,
                [
                    "analyze",
                    str(dataset),
                    "--output-root",
                    str(root / "outputs"),
                    "--seed",
                    "5",
                ],
            )
            self.assertEqual(analyze.exit_code, 0, analyze.output)

            outputs = runner.invoke(app, ["outputs", "--output-root", str(root / "outputs")])
            self.assertEqual(outputs.exit_code, 0, outputs.output)
            payload = json.loads(outputs.output)
            self.assertEqual(len(payload["runs"]), 1)
            self.assertIn("trust_level", payload["runs"][0])

            run_id = json.loads(analyze.output)["run_id"]
            simulate = runner.invoke(
                app,
                [
                    "simulate",
                    run_id,
                    "--output-root",
                    str(root / "outputs"),
                    "--budget",
                    "3",
                    "--min-roi",
                    "0.1",
                ],
            )
            self.assertEqual(simulate.exit_code, 0, simulate.output)
            report = runner.invoke(app, ["report", run_id, "--output-root", str(root / "outputs"), "--refresh"])
            self.assertEqual(report.exit_code, 0, report.output)
            self.assertIn("## Budget Simulation", report.output)

    def test_yaml_config_can_select_estimators(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset = root / "coupon.csv"
            config = root / "config.yaml"
            _write_dataset(dataset)
            config.write_text(
                "\n".join(
                    [
                        "seed: 6",
                        f"output_root: {root / 'outputs'}",
                        "baseline_model: random_forest",
                        "baseline_model_params:",
                        "  n_estimators: 10",
                        "  min_samples_leaf: 1",
                        "nuisance_model: gradient_boosting",
                        "nuisance_model_params:",
                        "  n_estimators: 10",
                        "  max_depth: 2",
                        "feature_columns: [feature_1]",
                    ]
                ),
                encoding="utf-8",
            )

            result = runner.invoke(app, ["analyze", str(dataset), "--config", str(config)])

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            models = json.loads(
                (root / "outputs" / payload["run_id"] / "models.json").read_text(encoding="utf-8")
            )
            response = next(model for model in models["models"] if model["name"] == "response_model")
            duality = next(model for model in models["models"] if model["name"] == "duality_r_learner")
            self.assertEqual(response["metadata"]["estimator"], "random_forest")
            self.assertEqual(duality["metadata"]["nuisance_estimator"], "gradient_boosting")

    def test_analyze_error_is_structured_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["analyze", "missing.csv"])
        self.assertEqual(result.exit_code, 1)
        payload = json.loads(result.output)
        self.assertEqual(payload["error"]["code"], "analyze_failed")

    def test_doctor_reports_runtime_status(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertIn(payload["status"], {"ok", "warning"})
        self.assertFalse(payload["fractional_uplift_runtime_dependency"])
        self.assertIn("dependencies", payload)


def _write_dataset(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
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
        for index in range(8):
            treated = index % 2
            writer.writerow(
                {
                    "unit_id": f"u{index}",
                    "treatment": treated,
                    "treatment_propensity": "0.5",
                    "maximize_kpi": 2 + treated + index % 2,
                    "constraint_kpi": treated,
                    "feature_1": index,
                }
            )


if __name__ == "__main__":
    unittest.main()
