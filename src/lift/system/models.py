from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Any

from lift.system.paths import auth_path, lift_home, settings_path


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
    available = _available_models(providers, oauth)
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


def oauth_bridge_report() -> dict[str, Any]:
    status = _oauth_bridge_status()
    return {
        **status,
        "bundled_script": str(_bundled_bridge_path()),
        "installed_script": str(_installed_bridge_path()),
        "install_dir": str(_installed_bridge_dir()),
        "node": shutil.which("node"),
        "npm": shutil.which("npm"),
        "npm_package": "@mariozechner/pi-coding-agent",
        "install_env": "LIFT_INSTALL_OAUTH_BRIDGE=1",
    }


def bundled_oauth_bridge_path() -> str:
    return str(_bundled_bridge_path())


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

    return _run_oauth_bridge(provider, bridge)


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
    models = provider_auth.get("models", []) if isinstance(provider_auth, dict) else []
    if not isinstance(models, list):
        models = []
    return {
        "label": spec["label"],
        "auth_type": "oauth",
        "configured": configured,
        "available": configured,
        "bridge": spec["bridge"],
        "models": [str(model) for model in models],
    }


def _oauth_bridge_status() -> dict[str, Any]:
    env_bridge = os.environ.get("LIFT_OAUTH_BRIDGE")
    if env_bridge:
        return {
            "available": True,
            "command": env_bridge,
            "kind": "pi-auth",
            "source": "env",
        }

    installed = _installed_bridge_path()
    installed_dependency = _installed_bridge_dir() / "node_modules" / "@mariozechner" / "pi-coding-agent"
    if installed.exists() and installed_dependency.exists() and shutil.which("node"):
        return {
            "available": True,
            "command": f"node {shlex.quote(str(installed))}",
            "kind": "pi-auth",
            "source": "installed",
        }

    return {
        "available": False,
        "command": env_bridge,
        "kind": "pi-auth",
        "source": None,
    }


def _run_oauth_bridge(provider: str, bridge: dict[str, Any]) -> dict[str, Any]:
    command = str(bridge.get("command") or "").strip()
    if not command:
        raise ValueError("OAuth bridge command is empty")

    args = [
        *shlex.split(command),
        "login",
        provider,
        "--auth-path",
        str(auth_path()),
        "--settings-path",
        str(settings_path()),
    ]
    timeout = int(os.environ.get("LIFT_OAUTH_TIMEOUT_SECONDS", "900"))
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "provider": provider,
            "status": "bridge_failed",
            "message": str(exc),
            "bridge": bridge,
        }

    payload = _json_object(result.stdout)
    if result.returncode != 0:
        if payload is not None:
            payload.setdefault("provider", provider)
            payload.setdefault("bridge", bridge)
            payload.setdefault("returncode", result.returncode)
            return payload
        return {
            "provider": provider,
            "status": "bridge_failed",
            "message": (result.stderr or result.stdout).strip(),
            "returncode": result.returncode,
            "bridge": bridge,
        }

    if payload is None:
        return {
            "provider": provider,
            "status": "bridge_failed",
            "message": "OAuth bridge did not return JSON on stdout.",
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "bridge": bridge,
        }

    status = str(payload.get("status", "")).lower()
    if status not in {"ok", "success", "authenticated", "logged_in"}:
        payload.setdefault("provider", provider)
        payload.setdefault("bridge", bridge)
        return payload

    models = payload.get("models", [])
    if isinstance(models, str):
        models = [models]
    if not isinstance(models, list):
        models = []
    default_model = payload.get("default_model") or payload.get("model")
    if default_model is None and models:
        default_model = models[0]

    auth = _read_json(auth_path())
    auth.setdefault("providers", {})
    auth["providers"][provider] = {
        "type": "oauth",
        "bridge": bridge.get("kind"),
        "models": [str(model) for model in models],
    }
    _write_json(auth_path(), auth)

    if default_model:
        _set_default_model(provider, str(default_model))

    return {
        "provider": provider,
        "status": "ok",
        "auth_path": str(auth_path()),
        "model": str(default_model) if default_model else None,
        "models": [str(model) for model in models],
        "bridge": bridge,
    }


def _available_models(
    providers: dict[str, dict[str, Any]],
    oauth_providers: dict[str, dict[str, Any]],
) -> list[str]:
    models: list[str] = []
    for provider, status in providers.items():
        if status["available"]:
            models.extend(f"{provider}/{model}" for model in status["models"])
    for provider, status in oauth_providers.items():
        if status["available"]:
            models.extend(f"{provider}/{model}" for model in status["models"])
    return models


def _json_object(value: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _bundled_bridge_path() -> Path:
    resource = files("lift.oauth").joinpath("pi_auth_bridge.mjs")
    return Path(str(resource))


def _installed_bridge_dir() -> Path:
    return lift_home() / "oauth-bridge"


def _installed_bridge_path() -> Path:
    return _installed_bridge_dir() / "pi_auth_bridge.mjs"


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
