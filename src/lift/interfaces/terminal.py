from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Any

from lift import __version__
from lift.system.agents import agent_status
from lift.system.models import model_status
from lift.system.paths import default_output_root


WORKFLOWS = [
    ("/inspect", "infer schema and validate treatment/control data"),
    ("/analyze", "estimate incremental value and write artifacts"),
    ("/simulate", "run budget and ROI constrained targeting"),
    ("/report", "open or refresh a run report"),
    ("/outputs", "list previous Lift runs"),
    ("/doctor", "diagnose runtime, dependencies, and auth state"),
    ("/setup", "configure local settings and agent access"),
]


def render_dashboard() -> str:
    model = model_status()
    agents = agent_status()
    left = [
        ("model", model["current"] or model["recommended"] or "not configured"),
        ("directory", _shorten(str(Path.cwd()))),
        ("outputs", _shorten(default_output_root())),
        ("session", _latest_session_id()),
        ("system", _system_line()),
        ("agents", _agent_line(agents)),
    ]
    right = [f"{name:<10} {description}" for name, description in WORKFLOWS]
    return "\n".join(
        [
            "",
            _logo(),
            f"{'v' + __version__:^92}",
            _panel(left, right),
            "",
            "Type /help for commands, /exit to quit.",
        ]
    )


def _logo() -> str:
    return "\n".join(
        [
            "  _      _  __ _   ",
            " | |    (_)/ _| |  ",
            " | |     _| |_| |_ ",
            " | |    | |  _| __|",
            " | |____| | | | |_ ",
            " |______|_|_|  \\__|",
        ]
    )


def _panel(left: list[tuple[str, str]], right: list[str]) -> str:
    width = max(96, min(shutil.get_terminal_size((118, 24)).columns - 2, 132))
    left_width = 48
    right_width = width - left_width - 7
    lines = max(len(left), len(right))
    output = ["+" + "-" * width + "+"]
    for index in range(lines):
        left_text = ""
        if index < len(left):
            key, value = left[index]
            left_text = f"{key:<10} {value}"
        right_text = right[index] if index < len(right) else ""
        output.append(
            "| "
            + left_text[:left_width].ljust(left_width)
            + " | "
            + right_text[:right_width].ljust(right_width)
            + " |"
        )
    output.append("+" + "-" * width + "+")
    return "\n".join(output)


def _shorten(value: str, limit: int = 34) -> str:
    if len(value) <= limit:
        return value
    return "..." + value[-(limit - 3):]


def _latest_session_id() -> str:
    root = Path(default_output_root())
    if not root.exists():
        return "none"
    runs = sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime)
    return runs[-1].name if runs else "none"


def _system_line() -> str:
    cpu_count = os.cpu_count() or 1
    return f"{platform.system().lower()} · {cpu_count} cores · python {platform.python_version()}"


def _agent_line(status: dict[str, Any]) -> str:
    default = status.get("default_agent")
    available = [
        name
        for name, record in status.get("agents", {}).items()
        if record.get("available")
    ]
    if default:
        return f"{default} default"
    if available:
        return ", ".join(available)
    return "codex/claude not detected"
