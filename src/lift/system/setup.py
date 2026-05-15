from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from lift import __version__
from lift.system.agents import agent_status, set_default_agent
from lift.system.models import (
    begin_oauth_login,
    bundled_setup_prompt_path,
    configure_api_key_provider,
    model_status,
    oauth_bridge_report,
)
from lift.system.paths import ensure_runtime_dirs, lift_home, settings_path


def write_settings(
    *,
    output_root: str | None = None,
    default_seed: int = 123,
    baseline_model: str = "ridge",
    nuisance_model: str = "ridge",
    default_agent: str | None = None,
    default_provider: str | None = None,
    default_model: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    path = settings_path()
    if path.exists() and not overwrite:
        settings = read_settings()
        paths = ensure_runtime_dirs()
        return {"settings_path": str(path), "created": False, "settings": settings, "paths": paths}

    home = lift_home()
    settings = {
        "lift_version": __version__,
        "output_root": str(Path(output_root).expanduser()) if output_root else str(home / "outputs"),
        "default_seed": default_seed,
        "baseline_model": baseline_model,
        "nuisance_model": nuisance_model,
    }
    if default_agent:
        settings["default_agent"] = default_agent
    if default_provider:
        settings["default_provider"] = default_provider
    if default_model:
        settings["default_model"] = default_model
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    paths = ensure_runtime_dirs()
    return {"settings_path": str(path), "created": True, "settings": settings, "paths": paths}


def read_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Lift settings must be a JSON object: {path}")
    return payload


def is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_interactive_setup(
    *,
    output_root: str | None = None,
    default_seed: int = 123,
    baseline_model: str = "ridge",
    nuisance_model: str = "ridge",
    overwrite: bool = False,
) -> dict[str, Any]:
    settings_result = write_settings(
        output_root=output_root,
        default_seed=default_seed,
        baseline_model=baseline_model,
        nuisance_model=nuisance_model,
        overwrite=overwrite,
    )

    selection = _run_setup_prompt()
    if selection.get("status") == "cancelled":
        return {"settings": settings_result, "model_auth": None, "cancelled": True}
    if selection.get("status") != "ok":
        return {"settings": settings_result, "model_auth": selection, "cancelled": False}

    method = selection.get("method")
    auth_result: dict[str, Any] | None = None
    if method == "oauth":
        provider = str(selection.get("provider") or "openai-codex")
        auth_result = begin_oauth_login(provider)
    elif method == "api-key":
        auth_result = configure_api_key_provider(
            str(selection.get("provider") or "openai"),
            api_key=str(selection.get("api_key") or ""),
            model=str(selection.get("model") or ""),
            make_default=True,
        )
    else:
        auth_result = {"status": "error", "message": f"Unknown setup method: {method}"}

    if not _auth_completed(auth_result):
        print("│")
        print("◆  Model setup incomplete")
        print(f"│  {str((auth_result or {}).get('message') or 'Model provider login did not complete.')}")
        print("└  Run lift again to retry setup.")
        return {"settings": settings_result, "model_auth": auth_result, "cancelled": False}

    agent_result = _configure_recommended_agent()
    status = model_status()
    print("│")
    print("◆ Packages")
    print("  No additional package install required.")
    print("│")
    print("◆  Optional packages")
    print("│  ◻ memory (Preference and correction memory across sessions.)")
    print("│  ◻ generative-ui")
    print("│")
    print("◇  Ready")
    print(f"│  Model: {status.get('current') or status.get('recommended') or 'not configured'}")
    if agent_result:
        print(f"│  Agent: {agent_result.get('default_agent')}")
    print("└  Lift is ready.")
    return {"settings": settings_result, "model_auth": auth_result, "agent": agent_result}


def _auth_completed(auth_result: dict[str, Any] | None) -> bool:
    if not auth_result:
        return False
    if str(auth_result.get("status", "")).lower() not in {"ok", "success", "authenticated", "logged_in"}:
        return False
    return isinstance(model_status().get("current"), str)


def _configure_recommended_agent() -> dict[str, Any] | None:
    status = agent_status()
    recommended = status.get("recommended")
    if not isinstance(recommended, str):
        return None
    return set_default_agent(recommended)


def _run_setup_prompt() -> dict[str, Any]:
    command = _setup_prompt_command()
    if not command:
        return {
            "status": "error",
            "message": "Feynman-style setup prompt requires node and @clack/prompts. Reinstall Lift with the default installer.",
        }

    with tempfile.TemporaryDirectory(prefix="lift-setup-") as temp_dir:
        result_path = Path(temp_dir) / "result.json"
        result = subprocess.run(
            [*command, "--result-path", str(result_path)],
            check=False,
            text=True,
        )
        if result.returncode != 0 and not result_path.exists():
            return {"status": "error", "message": "Setup prompt failed.", "returncode": result.returncode}
        if not result_path.exists():
            return {"status": "error", "message": "Setup prompt did not write a result."}
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"status": "error", "message": "Invalid setup prompt result."}


def _setup_prompt_command() -> list[str] | None:
    node = shutil.which("node")
    if not node:
        return None

    override = os.environ.get("LIFT_SETUP_PROMPT")
    if override:
        return [node, override]

    bridge = oauth_bridge_report()
    installed = Path(str(bridge["install_dir"])) / "setup_prompt.mjs"
    dependency = Path(str(bridge["install_dir"])) / "node_modules" / "@clack" / "prompts"
    if installed.exists() and dependency.exists():
        return [node, str(installed)]

    bundled = Path(bundled_setup_prompt_path())
    if bundled.exists():
        return [node, str(bundled)]

    return None
