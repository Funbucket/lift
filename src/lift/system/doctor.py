from __future__ import annotations

import importlib.metadata
import shutil
import sys
from pathlib import Path
from typing import Any

from lift import __version__
from lift.system.agents import agent_status
from lift.system.models import model_status, oauth_bridge_report
from lift.system.paths import ensure_runtime_dirs
from lift.system.pi import pi_runtime_status


REQUIRED_PACKAGES = ("numpy", "pandas", "sklearn", "typer", "yaml")


def doctor_report() -> dict[str, Any]:
    paths = ensure_runtime_dirs()
    dependencies = {
        package: _dependency_status(package)
        for package in REQUIRED_PACKAGES
    }
    pi_runtime = pi_runtime_status()
    bridge = oauth_bridge_report()
    path_errors = list(paths.get("errors", []))
    checks = {
        "python_supported": sys.version_info >= (3, 10),
        "lift_command_on_path": shutil.which("lift") is not None,
        "runtime_dirs_created": not path_errors,
        "outputs_writable": _is_writable(Path(str(paths["outputs"]))),
        "node_available": bool(pi_runtime.get("node")),
        "pi_cli_installed": Path(str(pi_runtime["pi_cli"])).exists(),
        "pi_extension_available": Path(str(pi_runtime["extension"])).exists(),
        "oauth_bridge_installed": bridge.get("available", False),
    }
    python_ok = all(item["available"] for item in dependencies.values())
    core_ok = all(checks[key] for key in (
        "python_supported", "lift_command_on_path", "runtime_dirs_created", "outputs_writable"
    ))
    pi_ok = checks["node_available"] and checks["pi_cli_installed"] and checks["pi_extension_available"]
    status = "ok" if (python_ok and core_ok and pi_ok) else "warning"
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
        "pi_runtime": pi_runtime,
        "oauth_bridge": {
            "available": bridge.get("available", False),
            "source": bridge.get("source"),
            "install_dir": bridge.get("install_dir"),
        },
        "agents": agent_status(),
        "models": model_status(),
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
