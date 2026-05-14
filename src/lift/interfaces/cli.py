from __future__ import annotations

import argparse
import json
from pathlib import Path

from lift.data.load import load_csv
from lift.data.schema import infer_schema, validate_rows
from lift.workflow.run import AnalyzeConfig, analyze


def main() -> None:
    parser = argparse.ArgumentParser(prog="lift")
    subcommands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subcommands.add_parser("inspect")
    inspect_parser.add_argument("dataset")

    analyze_parser = subcommands.add_parser("analyze")
    analyze_parser.add_argument("dataset")
    analyze_parser.add_argument("--seed", type=int, default=123)
    analyze_parser.add_argument("--output-root", default="outputs")
    analyze_parser.add_argument("--maximize-kpi", default="maximize_kpi")
    analyze_parser.add_argument("--constraint-kpi", default="constraint_kpi")
    analyze_parser.add_argument("--budget", type=float)
    analyze_parser.add_argument("--min-roi", type=float)

    subcommands.add_parser("outputs")
    subcommands.add_parser("doctor")
    subcommands.add_parser("status")

    args = parser.parse_args()
    if args.command == "inspect":
        rows = load_csv(args.dataset)
        schema = infer_schema(rows)
        validation = validate_rows(rows, schema)
        print(json.dumps({"rows": len(rows), "schema": schema.to_dict(), "validation": validation}, indent=2))
    elif args.command == "analyze":
        result = analyze(
            args.dataset,
            AnalyzeConfig(
                seed=args.seed,
                output_root=args.output_root,
                maximize_kpi=args.maximize_kpi,
                constraint_kpi=args.constraint_kpi,
                budget=args.budget,
                min_roi=args.min_roi,
            ),
        )
        print(json.dumps(result, indent=2))
    elif args.command == "outputs":
        root = Path("outputs")
        runs = sorted(path.name for path in root.iterdir() if path.is_dir()) if root.exists() else []
        print(json.dumps({"runs": runs}, indent=2))
    elif args.command == "doctor":
        print(json.dumps({"status": "ok", "fractional_uplift_runtime_dependency": False}, indent=2))
    elif args.command == "status":
        print(json.dumps({"status": "ready"}, indent=2))


if __name__ == "__main__":
    main()
