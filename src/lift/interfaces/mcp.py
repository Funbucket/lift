from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from lift.data.load import load_csv, read_json
from lift.data.schema import prepare_rows, infer_schema, validate_rows
from lift.system.doctor import doctor_report
from lift.system.paths import default_output_root
from lift.trust.diagnostics import diagnose
from lift.workflow.run import AnalyzeConfig, analyze
from lift.workflow.simulate import refresh_report, report_run, simulate_run


JSON = dict[str, Any]


TOOLS: dict[str, dict[str, Any]] = {
    "inspect_dataset": {
        "description": "Inspect a campaign dataset and infer Lift schema.",
        "inputSchema": {
            "type": "object",
            "properties": {"dataset": {"type": "string"}},
            "required": ["dataset"],
        },
    },
    "validate_dataset": {
        "description": "Validate a dataset against Lift's binary treatment data contract.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string"},
                "schema": {"type": "object"},
            },
            "required": ["dataset"],
        },
    },
    "validate_causal_assumptions": {
        "description": "Run causal trust diagnostics including overlap, balance, leakage, and hidden confounding warnings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string"},
                "schema": {"type": "object"},
            },
            "required": ["dataset"],
        },
    },
    "analyze_campaign": {
        "description": "Run Lift analysis and write artifacts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string"},
                "config": {"type": "object"},
            },
            "required": ["dataset"],
        },
    },
    "simulate_budget": {
        "description": "Simulate budget/ROI constraints for a completed run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "output_root": {"type": "string"},
                "budget": {"type": "number"},
                "min_roi": {"type": "number"},
            },
            "required": ["run_id"],
        },
    },
    "generate_report": {
        "description": "Read or refresh a run report.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "output_root": {"type": "string"},
                "refresh": {"type": "boolean"},
            },
            "required": ["run_id"],
        },
    },
    "export_targets": {
        "description": "Export targets for a completed run using optional budget/ROI constraints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "output_root": {"type": "string"},
                "budget": {"type": "number"},
                "min_roi": {"type": "number"},
            },
            "required": ["run_id"],
        },
    },
    "list_outputs": {
        "description": "List Lift run outputs.",
        "inputSchema": {
            "type": "object",
            "properties": {"output_root": {"type": "string"}},
        },
    },
    "doctor": {
        "description": "Return Lift runtime diagnostics.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def run_mcp_server() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_json_rpc(request)
        except Exception as exc:
            response = _error_response(None, -32603, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


def handle_json_rpc(request: JSON) -> JSON | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        return _success_response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "lift", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return _success_response(request_id, {"tools": [_tool_descriptor(name, spec) for name, spec in TOOLS.items()]})
    if method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in TOOL_HANDLERS:
            return _error_response(request_id, -32602, f"Unknown tool: {name}")
        result = TOOL_HANDLERS[name](arguments)
        return _success_response(request_id, _tool_result(result))
    return _error_response(request_id, -32601, f"Unknown method: {method}")


def inspect_dataset(arguments: JSON) -> JSON:
    rows = load_csv(arguments["dataset"])
    schema = _schema_from_arguments(rows, arguments.get("schema", {}))
    validation = validate_rows(rows, schema)
    return {"rows": len(rows), "schema": schema.to_dict(), "validation": validation}


def validate_dataset(arguments: JSON) -> JSON:
    rows = load_csv(arguments["dataset"])
    schema = _schema_from_arguments(rows, arguments.get("schema", {}))
    validation = validate_rows(rows, schema)
    return {"valid": validation["valid"], "schema": schema.to_dict(), **validation}


def validate_causal_assumptions(arguments: JSON) -> JSON:
    rows = load_csv(arguments["dataset"])
    schema = _schema_from_arguments(rows, arguments.get("schema", {}))
    validation = validate_rows(rows, schema)
    if not validation["valid"]:
        return {"trust_level": "blocked", "schema": schema.to_dict(), "validation": validation}
    prepared = prepare_rows(rows, schema)
    trust = diagnose(prepared, schema, validation)
    return {"schema": schema.to_dict(), "trust": trust}


def analyze_campaign(arguments: JSON) -> JSON:
    config = dict(arguments.get("config", {}))
    return analyze(arguments["dataset"], AnalyzeConfig(**config))


def simulate_budget(arguments: JSON) -> JSON:
    return simulate_run(
        arguments["run_id"],
        output_root=arguments.get("output_root", default_output_root()),
        budget=arguments.get("budget"),
        min_roi=arguments.get("min_roi"),
        write_artifacts=True,
    )


def export_targets(arguments: JSON) -> JSON:
    output_root = arguments.get("output_root", default_output_root())
    result = simulate_run(
        arguments["run_id"],
        output_root=output_root,
        budget=arguments.get("budget"),
        min_roi=arguments.get("min_roi"),
        write_artifacts=True,
    )
    return {
        "targets_path": str(Path(output_root) / arguments["run_id"] / "targets.csv"),
        **result,
    }


def generate_report(arguments: JSON) -> JSON:
    output_root = arguments.get("output_root", default_output_root())
    if arguments.get("refresh"):
        content = refresh_report(arguments["run_id"], output_root=output_root)
    else:
        content = report_run(arguments["run_id"], output_root=output_root)
    return {"report": content}


def list_outputs(arguments: JSON) -> JSON:
    root = Path(arguments.get("output_root", default_output_root()))
    runs = []
    if root.exists():
        for path in sorted(root.iterdir()):
            if not path.is_dir():
                continue
            run_path = path / "run.json"
            if run_path.exists():
                run = read_json(run_path)
                runs.append({"run_id": path.name, "status": run.get("status"), "dataset_path": run.get("dataset_path")})
            else:
                runs.append({"run_id": path.name, "status": "unknown"})
    return {"runs": runs}


TOOL_HANDLERS: dict[str, Callable[[JSON], JSON]] = {
    "inspect_dataset": inspect_dataset,
    "validate_dataset": validate_dataset,
    "validate_causal_assumptions": validate_causal_assumptions,
    "analyze_campaign": analyze_campaign,
    "simulate_budget": simulate_budget,
    "export_targets": export_targets,
    "generate_report": generate_report,
    "list_outputs": list_outputs,
    "doctor": lambda _arguments: doctor_report(),
}


def _schema_from_arguments(rows: list[dict[str, Any]], schema_args: JSON | None) -> Any:
    schema_args = dict(schema_args or {})
    return infer_schema(
        rows,
        unit_id=schema_args.get("unit_id", "unit_id"),
        treatment=schema_args.get("treatment", "treatment"),
        maximize_kpi=schema_args.get("maximize_kpi", "maximize_kpi"),
        constraint_kpi=schema_args.get("constraint_kpi", "constraint_kpi"),
        treatment_propensity=schema_args.get("treatment_propensity", "treatment_propensity"),
        sample_weight=schema_args.get("sample_weight", "sample_weight"),
        constraint_offset_kpi=schema_args.get("constraint_offset_kpi"),
        feature_columns=schema_args.get("feature_columns"),
        exclude_feature_columns=schema_args.get("exclude_feature_columns"),
    )


def _tool_descriptor(name: str, spec: JSON) -> JSON:
    return {"name": name, **spec}


def _tool_result(payload: JSON) -> JSON:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _success_response(request_id: Any, result: JSON) -> JSON:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: Any, code: int, message: str) -> JSON:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
