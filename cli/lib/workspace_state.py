"""Aura workspace session records.

These records are intentionally small pointers. Aura owns live seat control; the
workspace owns product/unit state and runtime-native context files.
"""

from __future__ import annotations

import json
import os
import hashlib
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import state


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


def workspace_key(workdir: Path) -> str:
    root = workdir.resolve()
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", root.name).strip(".-") or "workspace"
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def workspace_state_dir(workdir: Path) -> Path:
    return state.state_root() / "workspaces" / workspace_key(workdir)


def legacy_workspace_state_dir(workdir: Path) -> Path:
    return workdir / ".aura" / "state"


def workspace_session_log(workdir: Path) -> Path:
    return workspace_state_dir(workdir) / "sessions.jsonl"


def legacy_workspace_session_log(workdir: Path) -> Path:
    return legacy_workspace_state_dir(workdir) / "sessions.jsonl"


def latest_session_path(workdir: Path) -> Path:
    return workspace_state_dir(workdir) / "latest-session.json"


def legacy_latest_session_path(workdir: Path) -> Path:
    return legacy_workspace_state_dir(workdir) / "latest-session.json"


def workspace_metadata_path(workdir: Path) -> Path:
    return workspace_state_dir(workdir) / "workspace.json"


def _write_workspace_metadata(workdir: Path) -> None:
    path = workspace_metadata_path(workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "aura.workspace_state.v1",
        "workspace_key": workspace_key(workdir),
        "workspace_root": str(workdir.resolve()),
        "updated_at": now_iso(),
    }
    _atomic_write_json(path, data)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True))
        f.write("\n")


def _best_effort_legacy_append(workdir: Path, record: dict[str, Any]) -> None:
    try:
        _append_jsonl(legacy_workspace_session_log(workdir), record)
    except OSError:
        pass


def _best_effort_legacy_latest(workdir: Path, record: dict[str, Any]) -> None:
    try:
        _atomic_write_json(legacy_latest_session_path(workdir), record)
    except OSError:
        pass


def append_session_record(workdir: Path, record: dict[str, Any]) -> dict[str, Any]:
    enriched = {
        "timestamp": now_iso(),
        "workspace_key": workspace_key(workdir),
        "workspace_root": str(workdir.resolve()),
        **record,
    }
    path = workspace_session_log(workdir)
    _write_workspace_metadata(workdir)
    _append_jsonl(path, enriched)
    _best_effort_legacy_append(workdir, enriched)
    return enriched


def write_latest_session(workdir: Path, record: dict[str, Any]) -> None:
    path = latest_session_path(workdir)
    _write_workspace_metadata(workdir)
    _atomic_write_json(path, record)
    _best_effort_legacy_latest(workdir, record)
