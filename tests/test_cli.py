from __future__ import annotations

import csv
import json
import sys
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

    def test_mcp_commands_are_not_exposed(self) -> None:
        runner = CliRunner()
        help_result = runner.invoke(app, ["--help"])
        self.assertEqual(help_result.exit_code, 0, help_result.output)
        self.assertNotIn("mcp", help_result.output)
        self.assertNotIn("mcp-config", help_result.output)

    def test_no_command_opens_dashboard_repl(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(
                app,
                [],
                input="/exit\n",
                env={"LIFT_HOME": str(Path(temp_dir) / "home")},
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("/analyze", result.output)
            self.assertIn("Type /help", result.output)

    def test_setup_writes_settings(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"
            outputs = Path(temp_dir) / "outputs"
            result = runner.invoke(
                app,
                [
                    "setup",
                    "--output-root",
                    str(outputs),
                    "--default-seed",
                    "77",
                    "--overwrite",
                ],
                env={"LIFT_HOME": str(home)},
            )
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            settings_path = Path(payload["settings_path"])
            self.assertTrue(settings_path.exists())
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["output_root"], str(outputs))
            self.assertEqual(settings["default_seed"], 77)
            self.assertEqual(payload["paths"]["outputs"], str(outputs))

    def test_install_skills_writes_repo_skill(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(
                app,
                [
                    "install-skills",
                    "--target",
                    "repo",
                    "--project-root",
                    temp_dir,
                    "--overwrite",
                ],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            skill_path = Path(payload["skill_path"])
            self.assertTrue(skill_path.exists())
            text = skill_path.read_text(encoding="utf-8")
            self.assertIn("lift analyze", text)
            self.assertIn("Do not invent incremental ROI", text)

    def test_model_api_key_login_writes_auth_and_default_model(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"
            result = runner.invoke(
                app,
                [
                    "model",
                    "login",
                    "openai",
                    "--method",
                    "api-key",
                    "--api-key",
                    "test-key",
                    "--model",
                    "gpt-test",
                ],
                env={"LIFT_HOME": str(home)},
            )
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["provider"], "openai")
            auth = json.loads((home / "auth.json").read_text(encoding="utf-8"))
            settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(auth["providers"]["openai"]["type"], "api_key")
            self.assertEqual(settings["default_provider"], "openai")
            self.assertEqual(settings["default_model"], "gpt-test")

    def test_model_oauth_login_reports_bridge_requirement(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(
                app,
                ["model", "login", "openai-codex", "--method", "oauth"],
                env={"LIFT_HOME": str(Path(temp_dir) / "home"), "LIFT_OAUTH_BRIDGE": ""},
            )
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["status"], "bridge_required")

    def test_model_bridge_reports_bundled_script(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(app, ["model", "bridge"], env={"LIFT_HOME": str(Path(temp_dir) / "home")})
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertIn("bundled_script", payload)
            self.assertTrue(Path(payload["bundled_script"]).exists())
            self.assertEqual(payload["npm_package"], "@mariozechner/pi-coding-agent")

            raw = runner.invoke(app, ["model", "bridge-path", "--raw"])
            self.assertEqual(raw.exit_code, 0, raw.output)
            self.assertTrue(Path(raw.output.strip()).exists())

    def test_model_oauth_login_uses_bridge_and_persists_model(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            bridge = root / "fake_bridge.py"
            bridge.write_text(
                "\n".join(
                    [
                        "import json",
                        "import sys",
                        "assert sys.argv[1] == 'login'",
                        "assert '--auth-path' in sys.argv",
                        "print(json.dumps({",
                        "  'status': 'ok',",
                        "  'provider': sys.argv[2],",
                        "  'models': ['gpt-oauth'],",
                        "  'default_model': 'gpt-oauth'",
                        "}))",
                    ]
                ),
                encoding="utf-8",
            )

            result = runner.invoke(
                app,
                ["model", "login", "openai-codex", "--method", "oauth"],
                env={
                    "LIFT_HOME": str(home),
                    "LIFT_OAUTH_BRIDGE": f"{sys.executable} {bridge}",
                },
            )

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["model"], "gpt-oauth")
            auth = json.loads((home / "auth.json").read_text(encoding="utf-8"))
            settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(auth["providers"]["openai-codex"]["type"], "oauth")
            self.assertEqual(settings["default_provider"], "openai-codex")
            self.assertEqual(settings["default_model"], "gpt-oauth")

    def test_model_oauth_login_returns_bridge_error_payload(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bridge = root / "fake_bridge_error.py"
            bridge.write_text(
                "\n".join(
                    [
                        "import json",
                        "import sys",
                        "print(json.dumps({'status': 'error', 'message': 'denied'}))",
                        "sys.exit(7)",
                    ]
                ),
                encoding="utf-8",
            )

            result = runner.invoke(
                app,
                ["model", "login", "openai-codex", "--method", "oauth"],
                env={
                    "LIFT_HOME": str(root / "home"),
                    "LIFT_OAUTH_BRIDGE": f"{sys.executable} {bridge}",
                },
            )

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["message"], "denied")
            self.assertEqual(payload["returncode"], 7)

    def test_agent_set_writes_default_agent(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"
            result = runner.invoke(app, ["agent", "set", "codex"], env={"LIFT_HOME": str(home)})
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["default_agent"], "codex")
            settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["default_agent"], "codex")

    def test_quickstart_runs_packaged_example(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            result = runner.invoke(
                app,
                [
                    "quickstart",
                    "--output-root",
                    str(output_root),
                    "--budget",
                    "5",
                    "--min-roi",
                    "0.1",
                ],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["dataset"], "builtin:randomized_coupon")
            self.assertEqual(payload["primary_model"], "duality_r_learner")
            self.assertTrue((output_root / payload["run_id"] / "report.md").exists())


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
