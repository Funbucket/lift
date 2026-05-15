from __future__ import annotations

import json
import sys
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import typer

from lift import __version__
from lift.data.load import load_csv, read_json, read_mapping
from lift.data.schema import infer_schema, validate_rows
from lift.system.agents import agent_status, set_default_agent
from lift.system.doctor import doctor_report
from lift.system.models import (
    begin_oauth_login,
    bundled_oauth_bridge_path,
    bundled_setup_prompt_path,
    configure_api_key_provider,
    model_status,
    oauth_bridge_report,
    set_default_model,
)
from lift.system.paths import default_output_root
from lift.system.pi import launch_pi_chat, pi_runtime_status
from lift.system.setup import is_interactive_terminal, run_interactive_setup, write_settings
from lift.system.skills import install_skill
from lift.workflow.run import AnalyzeConfig, analyze
from lift.workflow.simulate import refresh_report, report_run, simulate_run
from lift.interfaces.repl import run_repl


app = typer.Typer(
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
model_app = typer.Typer(help="Configure model providers and defaults.")
agent_app = typer.Typer(help="Configure external agent integrations.")
app.add_typer(model_app, name="model")
app.add_typer(agent_app, name="agent")

_TOP_LEVEL_COMMANDS = {
    "agent",
    "analyze",
    "doctor",
    "export-targets",
    "install-skills",
    "inspect",
    "model",
    "outputs",
    "quickstart",
    "repl",
    "report",
    "runtime",
    "setup",
    "simulate",
    "status",
    "version",
}


@app.callback()
def callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        if is_interactive_terminal() and not _model_is_configured():
            result = run_interactive_setup()
            if result.get("cancelled") or not _model_is_configured():
                return
        if is_interactive_terminal() and _model_is_configured():
            prompt = " ".join(ctx.args).strip() or None
            try:
                code = launch_pi_chat(initial_prompt=prompt)
            except Exception as exc:
                typer.echo(f"Natural-language runtime unavailable: {exc}", err=True)
                typer.echo("Falling back to legacy slash-command REPL.", err=True)
            else:
                raise typer.Exit(code=code)
        run_repl()


@app.command("inspect")
def inspect_dataset(
    dataset: Path,
    unit_id: str = "unit_id",
    treatment: str = "treatment",
    maximize_kpi: str = "maximize_kpi",
    constraint_kpi: str = "constraint_kpi",
    propensity: str = "treatment_propensity",
) -> None:
    rows = load_csv(dataset)
    schema = infer_schema(
        rows,
        unit_id=unit_id,
        treatment=treatment,
        maximize_kpi=maximize_kpi,
        constraint_kpi=constraint_kpi,
        treatment_propensity=propensity,
    )
    validation = validate_rows(rows, schema)
    _echo_json({"rows": len(rows), "schema": schema.to_dict(), "validation": validation})


@app.command("analyze")
def analyze_dataset(
    dataset: Path,
    config: Path | None = None,
    seed: int | None = None,
    output_root: str | None = None,
    unit_id: str | None = None,
    treatment: str | None = None,
    maximize_kpi: str | None = None,
    constraint_kpi: str | None = None,
    propensity: str | None = None,
    budget: float | None = None,
    min_roi: float | None = None,
    lambda_grid: str | None = None,
    estimate_propensity: bool = False,
    validation_fraction: float | None = None,
    baseline_model: str | None = None,
    nuisance_model: str | None = None,
    feature_columns: str | None = None,
    exclude_feature_columns: str | None = None,
) -> None:
    try:
        config_values = _config_values(
            config=config,
            seed=seed,
            output_root=output_root,
            unit_id=unit_id,
            treatment=treatment,
            maximize_kpi=maximize_kpi,
            constraint_kpi=constraint_kpi,
            propensity=propensity,
            budget=budget,
            min_roi=min_roi,
            lambda_grid=lambda_grid,
            estimate_propensity=estimate_propensity,
            validation_fraction=validation_fraction,
            baseline_model=baseline_model,
            nuisance_model=nuisance_model,
            feature_columns=feature_columns,
            exclude_feature_columns=exclude_feature_columns,
        )
        _echo_json(analyze(dataset, AnalyzeConfig(**config_values)))
    except Exception as exc:
        _exit_error("analyze_failed", str(exc))


@app.command("simulate")
def simulate(
    run_id: str,
    output_root: str = default_output_root(),
    budget: float | None = None,
    min_roi: float | None = None,
) -> None:
    try:
        _echo_json(
            simulate_run(
                run_id,
                output_root=output_root,
                budget=budget,
                min_roi=min_roi,
                write_artifacts=True,
            )
        )
    except Exception as exc:
        _exit_error("simulate_failed", str(exc))


@app.command("export-targets")
def export_targets(
    run_id: str,
    output_root: str = default_output_root(),
    budget: float | None = None,
    min_roi: float | None = None,
) -> None:
    try:
        result = simulate_run(
            run_id,
            output_root=output_root,
            budget=budget,
            min_roi=min_roi,
            write_artifacts=True,
        )
        _echo_json({"targets_path": str(Path(output_root) / run_id / "targets.csv"), **result})
    except Exception as exc:
        _exit_error("export_targets_failed", str(exc))


@app.command("report")
def report(run_id: str, output_root: str = default_output_root(), refresh: bool = False) -> None:
    if refresh:
        typer.echo(refresh_report(run_id, output_root=output_root))
    else:
        typer.echo(report_run(run_id, output_root=output_root))


@app.command("outputs")
def outputs(output_root: str = default_output_root()) -> None:
    root = Path(output_root)
    runs = [_run_summary(path) for path in sorted(root.iterdir()) if path.is_dir()] if root.exists() else []
    _echo_json({"runs": runs})


@app.command("doctor")
def doctor() -> None:
    _echo_json(doctor_report())


@app.command("setup")
def setup(
    output_root: str | None = None,
    default_seed: int = 123,
    baseline_model: str = "ridge",
    nuisance_model: str = "ridge",
    default_agent: str | None = None,
    default_provider: str | None = None,
    default_model: str | None = None,
    non_interactive: bool = False,
    overwrite: bool = False,
) -> None:
    try:
        if is_interactive_terminal() and not non_interactive:
            run_interactive_setup(
                output_root=output_root,
                default_seed=default_seed,
                baseline_model=baseline_model,
                nuisance_model=nuisance_model,
                overwrite=overwrite,
            )
            return
        _echo_json(
            write_settings(
                output_root=output_root,
                default_seed=default_seed,
                baseline_model=baseline_model,
                nuisance_model=nuisance_model,
                default_agent=default_agent,
                default_provider=default_provider,
                default_model=default_model,
                overwrite=overwrite,
            )
        )
    except Exception as exc:
        _exit_error("setup_failed", str(exc))


@app.command("install-skills")
def install_skills(
    target: str = "codex",
    project_root: str | None = None,
    overwrite: bool = False,
) -> None:
    try:
        _echo_json(install_skill(target=target, project_root=project_root, overwrite=overwrite))
    except Exception as exc:
        _exit_error("install_skills_failed", str(exc))


@app.command("quickstart")
def quickstart(
    output_root: str | None = None,
    seed: int = 123,
    budget: float = 5.0,
    min_roi: float = 0.1,
) -> None:
    try:
        example = files("lift.examples").joinpath("randomized_coupon.csv")
        with as_file(example) as dataset:
            result = analyze(
                dataset,
                AnalyzeConfig(
                    seed=seed,
                    output_root=output_root or default_output_root(),
                    budget=budget,
                    min_roi=min_roi,
                ),
            )
        _echo_json({"dataset": "builtin:randomized_coupon", **result})
    except Exception as exc:
        _exit_error("quickstart_failed", str(exc))


@app.command("status")
def status() -> None:
    _echo_json({"status": "ready"})


@app.command("repl")
def legacy_repl() -> None:
    run_repl()


@app.command("version")
def version() -> None:
    _echo_json({"version": __version__})


@app.command("runtime")
def runtime() -> None:
    _echo_json(pi_runtime_status())


@model_app.command("list")
def model_list() -> None:
    _echo_json(model_status())


@model_app.command("login")
def model_login(
    provider: str | None = typer.Argument(None),
    method: str = "oauth",
    api_key: str | None = None,
    model: str | None = None,
    no_default: bool = False,
) -> None:
    try:
        if method == "oauth":
            _echo_json(begin_oauth_login(provider or "openai-codex"))
            return
        if method == "api-key":
            _echo_json(
                configure_api_key_provider(
                    provider or "openai",
                    api_key=api_key,
                    model=model,
                    make_default=not no_default,
                )
            )
            return
        raise ValueError("method must be one of: oauth, api-key")
    except Exception as exc:
        _exit_error("model_login_failed", str(exc))


@model_app.command("set")
def model_set(spec: str) -> None:
    try:
        _echo_json(set_default_model(spec))
    except Exception as exc:
        _exit_error("model_set_failed", str(exc))


@model_app.command("bridge")
def model_bridge() -> None:
    _echo_json(oauth_bridge_report())


@model_app.command("bridge-path")
def model_bridge_path(raw: bool = False) -> None:
    path = bundled_oauth_bridge_path()
    if raw:
        typer.echo(path)
    else:
        _echo_json({"bridge_path": path})


@model_app.command("setup-prompt-path")
def model_setup_prompt_path(raw: bool = False) -> None:
    path = bundled_setup_prompt_path()
    if raw:
        typer.echo(path)
    else:
        _echo_json({"setup_prompt_path": path})


@agent_app.command("status")
def agent_status_command() -> None:
    _echo_json(agent_status())


@agent_app.command("set")
def agent_set(name: str) -> None:
    try:
        _echo_json(set_default_agent(name))
    except Exception as exc:
        _exit_error("agent_set_failed", str(exc))


def main() -> None:
    if _argv_is_initial_prompt(sys.argv[1:]):
        _run_initial_prompt_from_argv(sys.argv[1:])
        return
    app()


def _argv_is_initial_prompt(args: list[str]) -> bool:
    if not args:
        return False
    first = args[0]
    if first.startswith("-"):
        return False
    return first not in _TOP_LEVEL_COMMANDS


def _run_initial_prompt_from_argv(args: list[str]) -> None:
    prompt = " ".join(args).strip()
    if is_interactive_terminal() and not _model_is_configured():
        result = run_interactive_setup()
        if result.get("cancelled") or not _model_is_configured():
            return
    try:
        code = launch_pi_chat(initial_prompt=prompt or None, print_mode=not is_interactive_terminal())
    except Exception as exc:
        _exit_error("natural_language_runtime_failed", str(exc))
    raise typer.Exit(code=code)


def _config_values(
    *,
    config: Path | None,
    seed: int | None,
    output_root: str | None,
    unit_id: str | None,
    treatment: str | None,
    maximize_kpi: str | None,
    constraint_kpi: str | None,
    propensity: str | None,
    budget: float | None,
    min_roi: float | None,
    lambda_grid: str | None,
    estimate_propensity: bool,
    validation_fraction: float | None,
    baseline_model: str | None,
    nuisance_model: str | None,
    feature_columns: str | None,
    exclude_feature_columns: str | None,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if config:
        values.update(read_mapping(config))
    cli_values: dict[str, Any] = {
        "seed": seed,
        "output_root": output_root,
        "unit_id": unit_id,
        "treatment": treatment,
        "maximize_kpi": maximize_kpi,
        "constraint_kpi": constraint_kpi,
        "treatment_propensity": propensity,
        "budget": budget,
        "min_roi": min_roi,
        "estimate_propensity": estimate_propensity or None,
        "validation_fraction": validation_fraction,
        "baseline_model": baseline_model,
        "nuisance_model": nuisance_model,
    }
    if lambda_grid:
        cli_values["lambda_grid"] = tuple(float(value) for value in lambda_grid.split(",") if value.strip())
    if feature_columns:
        cli_values["feature_columns"] = _csv_list(feature_columns)
    if exclude_feature_columns:
        cli_values["exclude_feature_columns"] = _csv_list(exclude_feature_columns)
    values.update({key: value for key, value in cli_values.items() if value is not None})
    return values


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _echo_json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _model_is_configured() -> bool:
    status = model_status()
    current = status.get("current")
    return isinstance(current, str) and bool(current)


def _exit_error(code: str, message: str) -> None:
    _echo_json({"error": {"code": code, "message": message}})
    raise typer.Exit(code=1)


def _run_summary(path: Path) -> dict[str, Any]:
    run_path = path / "run.json"
    if not run_path.exists():
        return {"run_id": path.name, "status": "unknown"}
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


if __name__ == "__main__":
    main()
