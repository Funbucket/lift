from __future__ import annotations

from pathlib import Path
from typing import Any


SKILL_MARKDOWN = """# Lift

Use Lift when analyzing campaign incrementality, uplift, treatment/control campaign data, budget constrained targeting, ROI constrained targeting, or target export decisions.

## Workflow

1. Run `lift doctor` to verify the local runtime.
2. Run `lift inspect <dataset>` to infer schema and validation issues.
3. Run `lift analyze <dataset> --budget <amount> --min-roi <roi>` to create artifacts.
4. Run `lift report <run-id>` to read the generated report.
5. Run `lift export-targets <run-id> --budget <amount> --min-roi <roi>` when a target CSV is needed.

## Rules

- Do not invent incremental ROI, AUCC, CPiA, target counts, or trust ratings.
- Read Lift artifacts from the returned `run_dir` before summarizing results.
- Treat `trust_level` of `low` or `blocked` as a warning against direct campaign execution.
- Explain observational, overlap, imbalance, and leakage warnings clearly.
- Keep user data local and use the installed `lift` CLI.

## Useful Commands

```bash
lift doctor
lift quickstart
lift inspect data.csv
lift analyze data.csv --budget 1000000 --min-roi 1.5
lift outputs
lift report <run-id>
lift export-targets <run-id> --budget 1000000 --min-roi 1.5
```
"""


def install_skill(*, target: str, project_root: str | None = None, overwrite: bool = False) -> dict[str, Any]:
    skill_dir = _target_dir(target, project_root)
    skill_path = skill_dir / "SKILL.md"
    if skill_path.exists() and not overwrite:
        return {"target": target, "skill_path": str(skill_path), "created": False}
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(SKILL_MARKDOWN, encoding="utf-8")
    return {"target": target, "skill_path": str(skill_path), "created": True}


def _target_dir(target: str, project_root: str | None) -> Path:
    if target == "codex":
        return Path.home() / ".codex" / "skills" / "lift"
    if target == "repo":
        root = Path(project_root).expanduser() if project_root else Path.cwd()
        return root / ".agents" / "skills" / "lift"
    raise ValueError("target must be one of: codex, repo")
