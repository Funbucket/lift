from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from lift import __version__
from lift.system.agents import agent_status, set_default_agent
from lift.system.models import (
    API_KEY_PROVIDERS,
    OAUTH_PROVIDERS,
    begin_oauth_login,
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
    print("┌  Lift setup")
    settings_result = write_settings(
        output_root=output_root,
        default_seed=default_seed,
        baseline_model=baseline_model,
        nuisance_model=nuisance_model,
        overwrite=overwrite,
    )

    print("│")
    choice = _prompt_choice(
        "◆  Choose how to configure model access:",
        [
            "OAuth login (recommended: ChatGPT Plus/Pro, Claude Pro/Max, Copilot, ...)",
            "API key or custom provider (OpenAI, Anthropic, Google, ...)",
            "Cancel",
        ],
        default=1,
    )

    auth_result: dict[str, Any] | None = None
    if choice == 1:
        auth_result = _interactive_oauth_login()
    elif choice == 2:
        auth_result = _interactive_api_key_login()
    else:
        print("└  Setup cancelled.")
        return {"settings": settings_result, "model_auth": None, "cancelled": True}

    agent_result = _configure_recommended_agent()
    status = model_status()
    print("│")
    print("◇  Ready")
    print(f"│  Model: {status.get('current') or status.get('recommended') or 'not configured'}")
    if agent_result:
        print(f"│  Agent: {agent_result.get('default_agent')}")
    print("└  Lift is ready.")
    return {"settings": settings_result, "model_auth": auth_result, "agent": agent_result}


def _interactive_oauth_login() -> dict[str, Any]:
    bridge = oauth_bridge_report()
    if not bridge["available"]:
        print("│")
        print("◇  OAuth bridge is not installed.")
        print("│  Reinstall with:")
        print("│  curl -fsSL https://raw.githubusercontent.com/Funbucket/lift/main/scripts/install/install.sh | bash")
        print("│")
        return {"status": "bridge_required", "bridge": bridge}

    providers = list(OAUTH_PROVIDERS)
    provider_index = _prompt_choice(
        "◆  Choose OAuth provider:",
        [OAUTH_PROVIDERS[name]["label"] for name in providers],
        default=1,
    )
    provider = providers[provider_index - 1]
    print("│")
    print(f"◇  Starting OAuth login: {provider}")
    return begin_oauth_login(provider)


def _interactive_api_key_login() -> dict[str, Any]:
    providers = list(API_KEY_PROVIDERS)
    provider_index = _prompt_choice(
        "◆  Choose API-key provider:",
        [API_KEY_PROVIDERS[name]["label"] for name in providers],
        default=1,
    )
    provider = providers[provider_index - 1]
    spec = API_KEY_PROVIDERS[provider]
    key = input(f"│  API key or env var [{spec['env_var']}]: ").strip() or spec["env_var"]
    model = input(f"│  Model [{spec['default_model']}]: ").strip() or spec["default_model"]
    return configure_api_key_provider(provider, api_key=key, model=model, make_default=True)


def _configure_recommended_agent() -> dict[str, Any] | None:
    status = agent_status()
    recommended = status.get("recommended")
    if not isinstance(recommended, str):
        return None
    should_set = input(f"│  Set default agent to {recommended}? [Y/n]: ").strip().lower()
    if should_set in {"n", "no"}:
        return None
    return set_default_agent(recommended)


def _prompt_choice(prompt: str, choices: list[str], *, default: int) -> int:
    print(prompt)
    for index, choice in enumerate(choices, start=1):
        marker = "●" if index == default else "○"
        print(f"│  {marker} {index}. {choice}")
    while True:
        raw = input(f"│  Select [{default}]: ").strip()
        if not raw:
            return default
        try:
            selected = int(raw)
        except ValueError:
            print("│  Enter a number from the list.")
            continue
        if 1 <= selected <= len(choices):
            return selected
        print("│  Enter a number from the list.")
