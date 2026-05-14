from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lift.data.load import load_csv, read_json
from lift.data.schema import infer_schema, validate_rows
from lift.workflow.run import AnalyzeConfig, analyze
from lift.workflow.simulate import report_run, simulate_run


def main() -> None:
    parser = argparse.ArgumentParser(prog="lift")
    subcommands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subcommands.add_parser("inspect")
    inspect_parser.add_argument("dataset")
    inspect_parser.add_argument("--unit-id", default="unit_id")
    inspect_parser.add_argument("--treatment", default="treatment")
    inspect_parser.add_argument("--maximize-kpi", default="maximize_kpi")
    inspect_parser.add_argument("--constraint-kpi", default="constraint_kpi")
    inspect_parser.add_argument("--propensity", default="treatment_propensity")

    analyze_parser = subcommands.add_parser("analyze")
    analyze_parser.add_argument("dataset")
    analyze_parser.add_argument("--config")
    analyze_parser.add_argument("--seed", type=int)
    analyze_parser.add_argument("--output-root")
    analyze_parser.add_argument("--unit-id")
    analyze_parser.add_argument("--treatment")
    analyze_parser.add_argument("--maximize-kpi")
    analyze_parser.add_argument("--constraint-kpi")
    analyze_parser.add_argument("--propensity")
    analyze_parser.add_argument("--budget", type=float)
    analyze_parser.add_argument("--min-roi", type=float)
    analyze_parser.add_argument("--lambda-grid")

    simulate_parser = subcommands.add_parser("simulate")
    simulate_parser.add_argument("run_id")
    simulate_parser.add_argument("--output-root", default="outputs")
    simulate_parser.add_argument("--budget", type=float)
    simulate_parser.add_argument("--min-roi", type=float)

    export_parser = subcommands.add_parser("export-targets")
    export_parser.add_argument("run_id")
    export_parser.add_argument("--output-root", default="outputs")
    export_parser.add_argument("--budget", type=float)
    export_parser.add_argument("--min-roi", type=float)

    report_parser = subcommands.add_parser("report")
    report_parser.add_argument("run_id")
    report_parser.add_argument("--output-root", default="outputs")

    outputs_parser = subcommands.add_parser("outputs")
    outputs_parser.add_argument("--output-root", default="outputs")
    subcommands.add_parser("doctor")
    subcommands.add_parser("status")

    args = parser.parse_args()
    if args.command == "inspect":
        rows = load_csv(args.dataset)
        schema = infer_schema(
            rows,
            unit_id=args.unit_id,
            treatment=args.treatment,
            maximize_kpi=args.maximize_kpi,
            constraint_kpi=args.constraint_kpi,
            treatment_propensity=args.propensity,
        )
        validation = validate_rows(rows, schema)
        print(json.dumps({"rows": len(rows), "schema": schema.to_dict(), "validation": validation}, indent=2))
    elif args.command == "analyze":
        config_values = _config_values(args)
        result = analyze(
            args.dataset,
            AnalyzeConfig(**config_values),
        )
        print(json.dumps(result, indent=2))
    elif args.command == "simulate":
        result = simulate_run(
            args.run_id,
            output_root=args.output_root,
            budget=args.budget,
            min_roi=args.min_roi,
            write_artifacts=True,
        )
        print(json.dumps(result, indent=2))
    elif args.command == "export-targets":
        result = simulate_run(
            args.run_id,
            output_root=args.output_root,
            budget=args.budget,
            min_roi=args.min_roi,
            write_artifacts=True,
        )
        print(json.dumps({"targets_path": str(Path(args.output_root) / args.run_id / "targets.csv"), **result}, indent=2))
    elif args.command == "report":
        print(report_run(args.run_id, output_root=args.output_root))
    elif args.command == "outputs":
        root = Path(args.output_root)
        runs = sorted(path.name for path in root.iterdir() if path.is_dir()) if root.exists() else []
        print(json.dumps({"runs": runs}, indent=2))
    elif args.command == "doctor":
        print(json.dumps({"status": "ok", "fractional_uplift_runtime_dependency": False}, indent=2))
    elif args.command == "status":
        print(json.dumps({"status": "ready"}, indent=2))


def _config_values(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if args.config:
        values.update(read_json(args.config))
    cli_values = {
        "seed": args.seed,
        "output_root": args.output_root,
        "unit_id": args.unit_id,
        "treatment": args.treatment,
        "maximize_kpi": args.maximize_kpi,
        "constraint_kpi": args.constraint_kpi,
        "treatment_propensity": args.propensity,
        "budget": args.budget,
        "min_roi": args.min_roi,
    }
    if args.lambda_grid:
        cli_values["lambda_grid"] = tuple(float(value) for value in args.lambda_grid.split(",") if value.strip())
    values.update({key: value for key, value in cli_values.items() if value is not None})
    return values


if __name__ == "__main__":
    main()
