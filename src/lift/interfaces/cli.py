from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from lift.data.load import load_csv, read_json, read_mapping
from lift.data.schema import infer_schema, validate_rows
from lift.system.doctor import doctor_report
from lift.system.paths import default_output_root
from lift.workflow.run import AnalyzeConfig, analyze
from lift.workflow.simulate import refresh_report, report_run, simulate_run


app = typer.Typer(no_args_is_help=True)


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


@app.command("status")
def status() -> None:
    _echo_json({"status": "ready"})


def main() -> None:
    app()


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
