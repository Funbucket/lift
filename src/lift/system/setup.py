from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lift import __version__
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
