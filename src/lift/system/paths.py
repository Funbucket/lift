from __future__ import annotations

import os
from pathlib import Path


def lift_home() -> Path:
    return Path(os.environ.get("LIFT_HOME", Path.home() / ".lift")).expanduser()


def default_output_root() -> str:
    return str(Path(os.environ.get("LIFT_OUTPUT_ROOT", lift_home() / "outputs")).expanduser())


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
