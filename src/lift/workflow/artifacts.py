from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    def __init__(self, root: str | Path = "outputs") -> None:
        self.root = Path(root)

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def write_json(self, run_id: str, name: str, payload: dict[str, Any]) -> Path:
        path = self.run_dir(run_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default), encoding="utf-8")
        return path

    def write_markdown(self, run_id: str, name: str, content: str) -> Path:
        path = self.run_dir(run_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def require_run_dir(self, run_id: str) -> Path:
        path = self.run_dir(run_id)
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Run not found: {run_id}")
        return path


def _json_default(value: Any) -> Any:
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    return str(value)
