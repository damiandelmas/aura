"""Workspace-local Aura session records.

These records are intentionally small pointers. Aura owns live seat control; the
workspace owns product/unit state and runtime-native context files.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_workdir(value: str | None) -> Path:
    path = Path(value or os.getcwd()).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_dir():
        raise ValueError(f"cwd is not a directory: {path}")
    return path


def resolve_existing_file(value: str | None, *, workdir: Path, label: str) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workdir / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{label} file not found: {path}")
    return path


def infer_context_file(workdir: Path, runtime_spec: dict[str, Any], explicit: str | None = None) -> Path | None:
    explicit_path = resolve_existing_file(explicit, workdir=workdir, label="context")
    if explicit_path:
        return explicit_path
    for candidate in runtime_spec.get("context_candidates") or []:
        path = workdir / candidate
        if path.is_file():
            return path.resolve()
    return None


def infer_native_state_ref(workdir: Path, runtime_spec: dict[str, Any]) -> str | None:
    name = runtime_spec.get("native_state")
    if not name:
        return None
    path = workdir / str(name)
    return str(path) if path.exists() else str(path)


def read_work_prompt(path: Path | None) -> str | None:
    if not path:
        return None
    return path.read_text(encoding="utf-8")


def workspace_session_log(workdir: Path) -> Path:
    return workdir / ".aura" / "state" / "sessions.jsonl"


def append_session_record(workdir: Path, record: dict[str, Any]) -> dict[str, Any]:
    enriched = {
        "timestamp": now_iso(),
        **record,
    }
    path = workspace_session_log(workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, sort_keys=True))
        f.write("\n")
    return enriched


def write_latest_session(workdir: Path, record: dict[str, Any]) -> None:
    path = workdir / ".aura" / "state" / "latest-session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="latest-session-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
