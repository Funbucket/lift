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

    def test_analyze_error_is_structured_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["analyze", "missing.csv"])
        self.assertEqual(result.exit_code, 1)
        payload = json.loads(result.output)
        self.assertEqual(payload["error"]["code"], "analyze_failed")


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
