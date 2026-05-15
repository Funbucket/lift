from __future__ import annotations

import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

from lift import __version__
from lift.system.models import model_status
from lift.system.paths import ensure_runtime_dirs, lift_home, settings_path


def pi_runtime_status() -> dict[str, Any]:
    node = _which("node")
    pi_cli = _pi_cli_path()
    extension = _asset_path("lift_tools.mjs")
    prompts = _asset_path("prompts")
    return {
        "available": bool(node and pi_cli.exists() and extension.exists() and prompts.exists()),
        "node": node,
        "pi_cli": str(pi_cli),
        "extension": str(extension),
        "prompt_templates": str(prompts),
        "session_dir": str(lift_home() / "sessions"),
    }


def launch_pi_chat(*, initial_prompt: str | None = None, print_mode: bool = False) -> int:
    status = pi_runtime_status()
    if not status["available"]:
        missing = [
            label
            for label, present in (
                ("node", bool(status["node"])),
                ("Pi CLI", Path(str(status["pi_cli"])).exists()),
                ("Lift Pi extension", Path(str(status["extension"])).exists()),
                ("Lift prompt templates", Path(str(status["prompt_templates"])).exists()),
            )
            if not present
        ]
        raise RuntimeError(
            "Feynman-style natural-language runtime is not installed. "
            f"Missing: {', '.join(missing)}. Reinstall Lift with the default installer."
        )

    paths = ensure_runtime_dirs()
    current_model = model_status().get("current")
    if not isinstance(current_model, str) or not current_model:
        raise RuntimeError("No default model configured. Run lift setup first.")

    args = [
        str(status["node"]),
        str(status["pi_cli"]),
        "--session-dir",
        str(paths["sessions"]),
        "--extension",
        str(status["extension"]),
        "--prompt-template",
        str(status["prompt_templates"]),
        "--system-prompt",
        _system_prompt(),
        "--model",
        current_model,
    ]
    if print_mode:
        args.append("--print")
    if initial_prompt:
        args.append(initial_prompt)

    env = {
        **os.environ,
        "LIFT_HOME": str(lift_home()),
        "LIFT_BIN": _lift_bin(),
        "LIFT_VERSION": __version__,
        "PI_CODING_AGENT_DIR": str(lift_home()),
        "PI_SKIP_VERSION_CHECK": os.environ.get("PI_SKIP_VERSION_CHECK", "1"),
    }
    result = subprocess.run(args, cwd=Path.cwd(), env=env, check=False)
    return int(result.returncode or 0)


def _system_prompt() -> str:
    return """You are Lift, a local-first incrementality decision agent for campaign analysis.

Answer natural-language questions by using the Lift tools. Do not invent incremental ROI, AUCC, iROI, targets, trust ratings, or CSV/report paths. If the user asks about a dataset, inspect and analyze the CSV before answering. If the user asks about budgets, ROI constraints, or whom to target, use the simulation/export tools. If the user asks whether results are trustworthy, use the trust and overlap fields in Lift artifacts. Keep answers concise and include the run id and artifact paths when relevant."""


def _pi_cli_path() -> Path:
    return lift_home() / "oauth-bridge" / "node_modules" / "@mariozechner" / "pi-coding-agent" / "dist" / "cli.js"


def _asset_path(name: str) -> Path:
    return Path(str(files("lift.pi_assets").joinpath(name)))


def _lift_bin() -> str:
    return os.environ.get("LIFT_BIN") or sys.argv[0] or "lift"


def _which(name: str) -> str | None:
    path = os.environ.get("PATH", "")
    for directory in path.split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None
