from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

import typer

from lift.data.load import load_csv
from lift.data.schema import infer_schema, validate_rows
from lift.interfaces.terminal import render_dashboard
from lift.system.doctor import doctor_report
from lift.system.paths import default_output_root
from lift.system.setup import write_settings
from lift.workflow.run import AnalyzeConfig, analyze
from lift.workflow.simulate import refresh_report, report_run, simulate_run


HELP_TEXT = """Commands:
  /inspect <dataset>
  /analyze <dataset> [--config path] [--budget n] [--min-roi n]
  /simulate <run-id> [--budget n] [--min-roi n]
  /report <run-id> [--refresh]
  /outputs
  /doctor
  /setup
  /help
  /exit
"""


def run_repl() -> None:
    typer.echo(render_dashboard())
    while True:
        try:
            line = input("lift> ").strip()
        except EOFError:
            typer.echo()
            return
        if not line:
            continue
        if line in {"/exit", "/quit", "exit", "quit"}:
            return
        try:
            output = handle_repl_command(line)
            if output is not None:
                typer.echo(output)
        except Exception as exc:
            typer.echo(json.dumps({"error": {"code": "repl_command_failed", "message": str(exc)}}, indent=2))


def handle_repl_command(line: str) -> str | None:
    args = shlex.split(line)
    command = _normalize_command(args[0])
    rest = args[1:]
    if command == "/help":
        return HELP_TEXT
    if command == "/doctor":
        return _json(doctor_report())
    if command == "/setup":
        return _json(write_settings(overwrite=False))
    if command == "/outputs":
        options = _parse_options(rest)
        output_root = str(options.get("output_root", default_output_root()))
        root = Path(output_root)
        runs = [_run_summary(path) for path in sorted(root.iterdir()) if path.is_dir()] if root.exists() else []
        return _json({"runs": runs})
    if command == "/inspect":
        dataset = _require_arg(rest, "dataset")
        rows = load_csv(dataset)
        schema = infer_schema(rows)
        validation = validate_rows(rows, schema)
        return _json({"rows": len(rows), "schema": schema.to_dict(), "validation": validation})
    if command == "/analyze":
        dataset = _require_arg(rest, "dataset")
        options = _parse_options(rest[1:])
        result = analyze(dataset, _analyze_config(options))
        return _json(result)
    if command == "/simulate":
        run_id = _require_arg(rest, "run-id")
        options = _parse_options(rest[1:])
        result = simulate_run(
            run_id,
            output_root=str(options.get("output_root", default_output_root())),
            budget=_optional_float(options.get("budget")),
            min_roi=_optional_float(options.get("min_roi")),
        )
        return _json(result)
    if command == "/report":
        run_id = _require_arg(rest, "run-id")
        options = _parse_options(rest[1:])
        output_root = str(options.get("output_root", default_output_root()))
        if options.get("refresh"):
            return refresh_report(run_id, output_root=output_root)
        return report_run(run_id, output_root=output_root)
    raise ValueError(f"Unknown command: {command}")


def _normalize_command(command: str) -> str:
    if command.startswith("/"):
        return command
    return f"/{command}"


def _analyze_config(options: dict[str, Any]) -> AnalyzeConfig:
    return AnalyzeConfig(
        seed=int(options.get("seed", 123)),
        output_root=str(options.get("output_root", default_output_root())),
        budget=_optional_float(options.get("budget")),
        min_roi=_optional_float(options.get("min_roi")),
        estimate_propensity=bool(options.get("estimate_propensity", False)),
        baseline_model=str(options.get("baseline_model", "ridge")),
        nuisance_model=str(options.get("nuisance_model", "ridge")),
    )


def _parse_options(args: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    index = 0
    while index < len(args):
        token = args[index]
        if token.startswith("--"):
            key = token[2:].replace("-", "_")
            if index + 1 < len(args) and not args[index + 1].startswith("--"):
                options[key] = args[index + 1]
                index += 2
            else:
                options[key] = True
                index += 1
        index += 1 if not token.startswith("--") else 0
    return options


def _require_arg(args: list[str], label: str) -> str:
    if not args or args[0].startswith("--"):
        raise ValueError(f"Missing required {label}")
    return args[0]


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def _run_summary(path: Path) -> dict[str, Any]:
    run_path = path / "run.json"
    if not run_path.exists():
        return {"run_id": path.name, "status": "unknown"}
    from lift.data.load import read_json

    run = read_json(run_path)
    trust_path = path / "trust.json"
    simulation_path = path / "simulation.json"
    trust = read_json(trust_path) if trust_path.exists() else {}
    simulation = read_json(simulation_path) if simulation_path.exists() else {}
    return {
        "run_id": path.name,
        "status": run.get("status"),
        "created_at": run.get("created_at"),
        "dataset_path": run.get("dataset_path"),
        "trust_level": trust.get("trust_level"),
        "target_count": simulation.get("target_count"),
        "expected_incremental_roi": simulation.get("expected_incremental_roi"),
    }
