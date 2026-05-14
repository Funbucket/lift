from __future__ import annotations

import json
import os
from pathlib import Path


def lift_home() -> Path:
    return Path(os.environ.get("LIFT_HOME", Path.home() / ".lift")).expanduser()


def default_output_root() -> str:
    if "LIFT_OUTPUT_ROOT" in os.environ:
        return str(Path(os.environ["LIFT_OUTPUT_ROOT"]).expanduser())
    settings = _read_settings()
    if "output_root" in settings:
        return str(Path(str(settings["output_root"])).expanduser())
    return str((lift_home() / "outputs").expanduser())


def settings_path() -> Path:
    return lift_home() / "settings.json"


def ensure_runtime_dirs() -> dict[str, str | list[str]]:
    home = lift_home()
    outputs = Path(default_output_root())
    config = home / "config"
    sessions = home / "sessions"
    errors: list[str] = []
    for path in (home, outputs, config, sessions):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    return {
        "home": str(home),
        "outputs": str(outputs),
        "config": str(config),
        "sessions": str(sessions),
        "errors": errors,
    }


def _read_settings() -> dict[str, object]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
