from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from lift.system.paths import settings_path


AGENTS = {
    "codex": {
        "command": "codex",
        "skill_path": Path.home() / ".codex" / "skills" / "lift" / "SKILL.md",
    },
    "claude": {
        "command": "claude",
        "skill_path": Path.cwd() / ".agents" / "skills" / "lift" / "SKILL.md",
    },
}


def agent_status() -> dict[str, Any]:
    settings = _read_settings()
    configured = settings.get("default_agent")
    agents = {name: _agent_record(name, spec) for name, spec in AGENTS.items()}
    return {
        "default_agent": configured,
        "agents": agents,
        "recommended": _recommended_agent(agents),
    }


def set_default_agent(name: str) -> dict[str, Any]:
    if name not in AGENTS:
        raise ValueError(f"unknown agent: {name}")
    settings = _read_settings()
    settings["default_agent"] = name
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return {"default_agent": name, "agents": agent_status()["agents"]}


def _agent_record(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    command = str(spec["command"])
    path = shutil.which(command)
    skill_path = Path(spec["skill_path"])
    return {
        "available": path is not None,
        "command": command,
        "path": path,
        "version": _version(command) if path else None,
        "skill_installed": skill_path.exists(),
        "skill_path": str(skill_path),
    }


def _recommended_agent(agents: dict[str, dict[str, Any]]) -> str | None:
    for name in ("codex", "claude"):
        if agents[name]["available"]:
            return name
    return None


def _version(command: str) -> str | None:
    try:
        result = subprocess.run(
            [command, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else None


def _read_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
