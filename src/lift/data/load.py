from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


def load_csv(path: str | Path) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    with dataset_path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_mapping(path: str | Path) -> dict[str, Any]:
    input_path = Path(path)
    text = input_path.read_text(encoding="utf-8")
    if input_path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text) or {}
    else:
        payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Config must be a mapping: {input_path}")
    return payload


def dataset_fingerprint(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
