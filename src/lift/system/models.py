from __future__ import annotations

import json
import os
from typing import Any

from lift.system.paths import auth_path, settings_path


API_KEY_PROVIDERS = {
    "openai": {
        "label": "OpenAI Platform API",
        "env_var": "OPENAI_API_KEY",
        "default_model": "gpt-5.4",
    },
    "anthropic": {
        "label": "Anthropic API",
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-5",
    },
    "google": {
        "label": "Google Gemini API",
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-pro",
    },
}

OAUTH_PROVIDERS = {
    "openai-codex": {
        "label": "OpenAI Codex / ChatGPT OAuth",
        "bridge": "pi-auth",
    },
    "anthropic-claude": {
        "label": "Claude OAuth",
        "bridge": "pi-auth",
    },
    "github-copilot": {
        "label": "GitHub Copilot OAuth",
        "bridge": "pi-auth",
    },
}


def model_status() -> dict[str, Any]:
    settings = _read_json(settings_path())
    auth = _read_json(auth_path())
    providers = {
        name: _api_key_provider_status(name, spec, auth)
        for name, spec in API_KEY_PROVIDERS.items()
    }
    oauth = {
        name: _oauth_provider_status(name, spec, auth)
        for name, spec in OAUTH_PROVIDERS.items()
    }
    current = _current_model(settings)
    available = _available_models(providers)
    if current and current not in available:
        available.insert(0, current)
    return {
        "current": current,
        "recommended": current or (available[0] if available else None),
        "api_key_providers": providers,
        "oauth_providers": oauth,
        "oauth_bridge": _oauth_bridge_status(),
        "available_models": available,
    }


def configure_api_key_provider(
    provider: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    make_default: bool = True,
) -> dict[str, Any]:
    if provider not in API_KEY_PROVIDERS:
        raise ValueError(f"unknown API-key provider: {provider}")

    spec = API_KEY_PROVIDERS[provider]
    auth = _read_json(auth_path())
    auth.setdefault("providers", {})
    auth["providers"][provider] = {
        "type": "api_key",
        "key": api_key or spec["env_var"],
    }
    _write_json(auth_path(), auth)

    selected_model = model or str(spec["default_model"])
    if make_default:
        _set_default_model(provider, selected_model)

    return {
        "provider": provider,
        "auth_path": str(auth_path()),
        "model": selected_model,
        "default": make_default,
    }


def begin_oauth_login(provider: str) -> dict[str, Any]:
    if provider not in OAUTH_PROVIDERS:
        raise ValueError(f"unknown OAuth provider: {provider}")

    bridge = _oauth_bridge_status()
    if not bridge["available"]:
        return {
            "provider": provider,
            "status": "bridge_required",
            "message": (
                "OAuth login requires a Pi-compatible auth bridge. "
                "Use API-key auth now, or install the bridge before retrying."
            ),
            "bridge": bridge,
        }

    return {
        "provider": provider,
        "status": "bridge_available",
        "message": "OAuth bridge detection is ready; login execution will be wired in the bridge phase.",
        "bridge": bridge,
    }


def set_default_model(spec: str) -> dict[str, Any]:
    provider, model = _split_model_spec(spec)
    _set_default_model(provider, model)
    return {"current": f"{provider}/{model}", "settings_path": str(settings_path())}


def _api_key_provider_status(name: str, spec: dict[str, str], auth: dict[str, Any]) -> dict[str, Any]:
    provider_auth = auth.get("providers", {}).get(name, {})
    key = provider_auth.get("key") if isinstance(provider_auth, dict) else None
    env_var = spec["env_var"]
    env_present = bool(os.environ.get(env_var))
    configured = isinstance(key, str) and bool(key)
    usable = env_present or (configured and key != env_var)
    return {
        "label": spec["label"],
        "auth_type": "api_key",
        "env_var": env_var,
        "env_present": env_present,
        "configured": configured,
        "available": usable,
        "models": [spec["default_model"]],
    }


def _oauth_provider_status(name: str, spec: dict[str, str], auth: dict[str, Any]) -> dict[str, Any]:
    provider_auth = auth.get("providers", {}).get(name, {})
    configured = isinstance(provider_auth, dict) and provider_auth.get("type") == "oauth"
    return {
        "label": spec["label"],
        "auth_type": "oauth",
        "configured": configured,
        "available": configured,
        "bridge": spec["bridge"],
    }


def _oauth_bridge_status() -> dict[str, Any]:
    bridge = os.environ.get("LIFT_OAUTH_BRIDGE")
    return {
        "available": bool(bridge),
        "command": bridge,
        "kind": "pi-auth",
    }


def _available_models(providers: dict[str, dict[str, Any]]) -> list[str]:
    models: list[str] = []
    for provider, status in providers.items():
        if status["available"]:
            models.extend(f"{provider}/{model}" for model in status["models"])
    return models


def _current_model(settings: dict[str, Any]) -> str | None:
    provider = settings.get("default_provider")
    model = settings.get("default_model")
    if isinstance(provider, str) and isinstance(model, str):
        return f"{provider}/{model}"
    return None


def _set_default_model(provider: str, model: str) -> None:
    settings = _read_json(settings_path())
    settings["default_provider"] = provider
    settings["default_model"] = model
    _write_json(settings_path(), settings)


def _split_model_spec(spec: str) -> tuple[str, str]:
    separator = "/" if "/" in spec else ":" if ":" in spec else None
    if not separator:
        raise ValueError("model spec must look like provider/model or provider:model")
    provider, model = spec.split(separator, 1)
    if not provider or not model:
        raise ValueError("model spec must look like provider/model or provider:model")
    return provider, model


def _read_json(path: Any) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Any, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
