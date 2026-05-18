"""Durable runtime capsule manifests for Aura-managed runtime homes.

A runtime capsule is the per-launched-body package around native runtime
state.  Profiles/templates stay reusable and must not contain session stores;
capsules retain the native homes that make runtime-native resume possible.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

LAUNCH_MANIFEST = "aura-launch.json"
SESSION_MANIFEST = "runtime-session.json"
LAUNCH_SCHEMA = "aura.runtime_capsule.launch.v1"
SESSION_SCHEMA = "aura.runtime_capsule.session.v1"
ENV_ROOT_KEYS = ("HOME", "CODEX_HOME", "OMX_ROOT", "OMX_TEAM_STATE_ROOT")

_CAPSULE_ROOT_KEYS = (
    "omx_box_root",
    "codex_box_root",
    "runtime_capsule_root",
    "runtime_home",
)
_CODEX_HOME_KEYS = (
    "omx_box_codex_home",
    "codex_box_codex_home",
)
_OMX_ROOT_KEYS = (
    "omx_box_omx_root",
    "omx_box_team_state_root",
)
_LAUNCH_FIELDS = (
    "name",
    "seat",
    "fleet",
    "seat_ref",
    "runtime",
    "profile",
    "command",
    "cwd",
    "workdir",
    "context_file",
    "work_file",
    "aura_launch_id",
    "previous_aura_launch_id",
    "seat_instance_id",
    "source_session_id",
    "runtime_session_mode",
    "isolation",
    "runtime_home",
    "native_state_ref",
    "runtime_profile",
    "runtime_profile_ref",
    "runtime_profile_runtime",
    "runtime_profile_source",
    "terminal_ref",
    "backend_ref",
    "pane_ref",
    "transport",
    "identity_provider",
    "identity_id",
    "identity_label",
    "desks_identity_id",
    "desks_identity_home",
    "desks_profile_id",
    "desks_profile_home",
    "omx_box_root",
    "omx_box_home",
    "omx_box_codex_home",
    "omx_box_omx_root",
    "omx_box_omx_state",
    "omx_box_team_state_root",
    "codex_box_root",
    "codex_box_home",
    "codex_box_codex_home",
    "agent_package_id",
    "agent_package_address",
    "agent_package_alias",
    "agent_package_root",
)
_SESSION_FIELDS = (
    "name",
    "seat",
    "fleet",
    "seat_ref",
    "runtime",
    "cwd",
    "workdir",
    "aura_launch_id",
    "seat_instance_id",
    "source_session_id",
    "runtime_session_mode",
    "session_id",
    "runtime_session_id",
    "runtime_session_source",
    "runtime_session_binding",
    "runtime_session_bind_method",
    "runtime_session_bind_source",
    "runtime_session_bound_at",
    "runtime_session_confidence",
    "runtime_session_evidence",
    "runtime_session_env",
    "runtime_session_cwd",
    "runtime_session_created_at_ms",
    "runtime_session_updated_at_ms",
    "runtime_session_pid",
    "runtime_home",
    "native_state_ref",
    "jsonl",
    "agent_package_id",
    "agent_package_address",
    "agent_package_alias",
    "agent_package_root",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value if v is not None]
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(_json_safe(payload), f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _as_path(value: Any) -> Path | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def capsule_root(record_or_root: dict[str, Any] | str | Path | None) -> Path | None:
    """Resolve an Aura-owned boxed runtime home root, never a profile ref."""

    if record_or_root is None:
        return None
    if isinstance(record_or_root, (str, Path)):
        return _as_path(record_or_root)
    runtime = str(record_or_root.get("runtime") or "").strip().lower()
    if runtime not in {"codex", "omx"}:
        return None
    for key in _CAPSULE_ROOT_KEYS:
        root = _as_path(record_or_root.get(key))
        if root:
            return root
    return None


def codex_home(record_or_root: dict[str, Any] | str | Path | None) -> Path | None:
    if isinstance(record_or_root, dict):
        for key in _CODEX_HOME_KEYS:
            path = _as_path(record_or_root.get(key))
            if path:
                return path
    root = capsule_root(record_or_root)
    return root / "codex-home" if root else None


def omx_root(record_or_root: dict[str, Any] | str | Path | None) -> Path | None:
    if isinstance(record_or_root, dict):
        for key in _OMX_ROOT_KEYS:
            path = _as_path(record_or_root.get(key))
            if path:
                return path
    root = capsule_root(record_or_root)
    return root / "omx-root" if root else None


def ensure_capsule_dirs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "receipts").mkdir(exist_ok=True)
    (root / "artifacts").mkdir(exist_ok=True)


def env_roots_from_env(env: dict[str, Any] | None) -> dict[str, str]:
    if not env:
        return {}
    roots: dict[str, str] = {}
    for key in ENV_ROOT_KEYS:
        value = env.get(key)
        if value is not None and str(value).strip():
            roots[key] = str(value)
    return roots


def boxed_launch_env_from_record(record: dict[str, Any], source_cwd: str) -> dict[str, str]:
    """Rebuild boxed runtime environment from a registry record.

    Restarts must relaunch inside the same native runtime homes that spawn
    created.  This helper intentionally uses only stored capsule metadata; it
    does not call prepare_box because restart must not refresh templates or
    rewrite runtime homes as a side effect.
    """

    runtime = str(record.get("runtime") or "").strip().lower()
    env: dict[str, str] = {}
    if runtime == "codex" and record.get("codex_box_root"):
        home = record.get("codex_box_home")
        codex = record.get("codex_box_codex_home")
        if home:
            env["HOME"] = str(home)
        if codex:
            env["CODEX_HOME"] = str(codex)
        env["AURA_CODEX_BOX"] = str(record["codex_box_root"])
        env["AURA_CODEX_SOURCE_CWD"] = source_cwd
        if record.get("codex_profile"):
            env["AURA_CODEX_PROFILE"] = str(record["codex_profile"])
    elif runtime == "omx" and record.get("omx_box_root"):
        home = record.get("omx_box_home")
        codex = record.get("omx_box_codex_home")
        omx = record.get("omx_box_omx_root")
        team_state = record.get("omx_box_team_state_root")
        if home:
            env["HOME"] = str(home)
        if codex:
            env["CODEX_HOME"] = str(codex)
        if omx:
            env["OMX_ROOT"] = str(omx)
        if team_state:
            env["OMX_TEAM_STATE_ROOT"] = str(team_state)
        env.update({
            "OMX_LAUNCH_POLICY": "direct",
            "OMXBOX_ACTIVE": "1",
            "OMX_AUTO_UPDATE": "0",
            "OMX_NOTIFY_FALLBACK": "0",
            "OMX_SOURCE_CWD": source_cwd,
            "AURA_OMX_BOX": str(record["omx_box_root"]),
        })
        if record.get("omx_profile"):
            env["AURA_OMX_PROFILE"] = str(record["omx_profile"])
        runtime_path = _as_path(record.get("omx_box_runtime"))
        if runtime_path:
            from lib import omx_adapter

            env["PATH"] = omx_adapter.adapter_path_prefix(runtime_path)
    return {key: value for key, value in env.items() if value is not None and str(value).strip()}


def _selected(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {key: record.get(key) for key in fields if record.get(key) is not None}


def write_aura_launch(record: dict[str, Any], *, env_roots: dict[str, Any] | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    root = capsule_root(record)
    if not root:
        return {"ok": False, "reason": "no-capsule-root"}
    ensure_capsule_dirs(root)
    payload = {
        "schema": LAUNCH_SCHEMA,
        "updated_at": now_iso(),
        "capsule_root": str(root),
        **_selected(record, _LAUNCH_FIELDS),
        "env_roots": env_roots_from_env(env_roots),
    }
    if extra:
        payload.update(extra)
    path = root / LAUNCH_MANIFEST
    _atomic_write_json(path, payload)
    return {"ok": True, "capsule_root": str(root), "path": str(path), "schema": LAUNCH_SCHEMA}


def write_runtime_session(record: dict[str, Any], *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    root = capsule_root(record)
    if not root:
        return {"ok": False, "reason": "no-capsule-root"}
    ensure_capsule_dirs(root)
    payload = {
        "schema": SESSION_SCHEMA,
        "updated_at": now_iso(),
        "capsule_root": str(root),
        **_selected(record, _SESSION_FIELDS),
        "codex_home": str(codex_home(record)) if codex_home(record) else None,
        "omx_root": str(omx_root(record)) if omx_root(record) else None,
    }
    if extra:
        payload.update(extra)
    path = root / SESSION_MANIFEST
    _atomic_write_json(path, payload)
    return {"ok": True, "capsule_root": str(root), "path": str(path), "schema": SESSION_SCHEMA}


def capsule_codex_session_roots(record_or_root: dict[str, Any] | str | Path | None) -> list[Path]:
    home = codex_home(record_or_root)
    if not home:
        return []
    sessions = home / "sessions"
    return [sessions] if sessions.exists() else []


def capsule_codex_jsonls(record_or_root: dict[str, Any] | str | Path | None) -> Iterable[Path]:
    for sessions_root in capsule_codex_session_roots(record_or_root):
        yield from sessions_root.rglob("*.jsonl")
