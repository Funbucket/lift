from __future__ import annotations

import importlib.metadata
import shutil
import sys
from pathlib import Path
from typing import Any

from lift import __version__
from lift.system.paths import ensure_runtime_dirs


REQUIRED_PACKAGES = ("numpy", "pandas", "sklearn", "typer", "yaml")


def doctor_report() -> dict[str, Any]:
    paths = ensure_runtime_dirs()
    dependencies = {
        package: _dependency_status(package)
        for package in REQUIRED_PACKAGES
    }
    path_errors = list(paths.get("errors", []))
    checks = {
        "python_supported": sys.version_info >= (3, 10),
        "lift_command_on_path": shutil.which("lift") is not None,
        "runtime_dirs_created": not path_errors,
        "outputs_writable": _is_writable(Path(str(paths["outputs"]))),
    }
    status = "ok" if all(checks.values()) and all(item["available"] for item in dependencies.values()) else "warning"
    return {
        "status": status,
        "lift_version": __version__,
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "supported": checks["python_supported"],
        },
        "paths": paths,
        "path_errors": path_errors,
        "checks": checks,
        "dependencies": dependencies,
        "fractional_uplift_runtime_dependency": False,
    }


def _dependency_status(package: str) -> dict[str, Any]:
    distribution = "scikit-learn" if package == "sklearn" else "pyyaml" if package == "yaml" else package
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return {"available": False, "version": None}
    return {"available": True, "version": version}


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".lift_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False
