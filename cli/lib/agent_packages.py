"""Minimal package-native Aura agents.

Agent packages are durable runtime bodies under ``~/.aura/agents/i_*``.  They
intentionally stay thinner than the broader Desks/Runway organization model:
the package stores an address, a default runtime/fleet/seat, and native runtime
homes.  Aura still owns launch/control; the package only owns continuity.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import runtime_boxes, runtime_profiles, state


AGENT_SCHEMA = "aura.agent_package.v1"
DESKS_SCHEMA = "aura.agent_package.desks_identity.v1"
INDEX_SCHEMA = "aura.agent_package.index.v1"

SUPPORTED_RUNTIMES = {"codex", "omx"}


def _empty_index() -> dict[str, Any]:
    return {"schema": INDEX_SCHEMA, "agents": {}, "addresses": {}, "aliases": {}}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def agents_root() -> Path:
    return state.state_root() / "agents"


def index_path() -> Path:
    return agents_root() / "index.json"


def new_agent_id() -> str:
    return f"i_{uuid.uuid4().hex[:12]}"


def normalize_address(address: str) -> str:
    raw = str(address or "").strip()
    if not raw:
        raise ValueError("agent address is required")
    parts = [part.strip() for part in raw.split(":")]
    if any(not part for part in parts):
        raise ValueError("agent address cannot contain empty ':' segments")
    if len(parts) < 2:
        raise ValueError("agent address should have at least two ':' segments")
    for part in parts:
        runtime_boxes.validate_logical_segment(part, label="agent address segment")
    return ":".join(parts)


def normalize_runtime(runtime: str) -> str:
    value = runtime_boxes.validate_logical_segment(str(runtime or "").strip(), label="runtime")
    if value not in SUPPORTED_RUNTIMES:
        raise ValueError(f"runtime must be one of: {', '.join(sorted(SUPPORTED_RUNTIMES))}")
    return value


def normalize_profile_ref(profile: str | None, *, runtime: str) -> str | None:
    raw = str(profile or "").strip()
    if not raw:
        return None
    if "/" not in raw:
        raw = f"{runtime}/{raw}"
    return runtime_profiles.normalize_runtime_profile_ref(raw, expected_runtime=runtime).canonical


def default_seat_from_address(address: str) -> str:
    leaf = address.split(":")[-1]
    return runtime_boxes.safe_segment(leaf)


def default_fleet_from_address(address: str) -> str:
    parts = address.split(":")
    if len(parts) >= 2:
        return runtime_boxes.safe_segment("-".join(parts[:2]))
    return "agents"


def package_root(agent_id: str) -> Path:
    if not re.fullmatch(r"i_[A-Za-z0-9_.-]+", str(agent_id or "")):
        raise ValueError("agent id must look like i_<id>")
    return agents_root() / agent_id


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def read_index() -> dict[str, Any]:
    path = index_path()
    if not path.exists():
        return _empty_index()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid agent package index: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid agent package index: {path}: expected object")
    payload.setdefault("schema", INDEX_SCHEMA)
    payload.setdefault("agents", {})
    payload.setdefault("addresses", {})
    payload.setdefault("aliases", {})
    return payload


def write_index(index: dict[str, Any]) -> None:
    index = dict(index)
    index["schema"] = INDEX_SCHEMA
    index["updated_at"] = now_iso()
    _atomic_write_json(index_path(), index)


def _read_agent_json(root: Path) -> dict[str, Any]:
    path = root / "agent.json"
    if not path.exists():
        raise FileNotFoundError(f"agent package missing agent.json: {root}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid agent package: {path}")
    return payload


def resolve(ref: str) -> dict[str, Any]:
    raw = str(ref or "").strip()
    if not raw:
        raise ValueError("agent ref is required")
    index = read_index()
    agent_id = None
    if raw.startswith("i_"):
        agent_id = raw
    elif raw in index.get("addresses", {}):
        agent_id = index["addresses"][raw]
    elif raw in index.get("aliases", {}):
        agent_id = index["aliases"][raw]
    if not agent_id:
        raise FileNotFoundError(f"unknown agent package: {raw}")
    root = package_root(agent_id)
    record = _read_agent_json(root)
    record["agent_id"] = agent_id
    record["root"] = str(root)
    return record


def package_dirs(root: Path) -> dict[str, str]:
    return {
        "root": str(root),
        "home": str(root / "home"),
        "codex_home": str(root / ".codex"),
        "omx_root": str(root),
        "omx_state": str(root / ".omx"),
        "omx_team_state_root": str(root / ".omx" / "state"),
        "desks_home": str(root / ".desks"),
        "receipts": str(root / "receipts"),
        "artifacts": str(root / "artifacts"),
        "runtime": str(root / "runtime"),
    }


def create(
    *,
    address: str,
    runtime: str,
    profile: str | None,
    cwd: str,
    fleet: str | None,
    seat: str | None,
    alias: str | None = None,
) -> dict[str, Any]:
    address = normalize_address(address)
    runtime = normalize_runtime(runtime)
    profile_ref = normalize_profile_ref(profile, runtime=runtime)
    cwd_path = Path(cwd).expanduser().resolve()
    fleet = runtime_boxes.validate_logical_segment(
        fleet or default_fleet_from_address(address),
        label="fleet",
    )
    seat = runtime_boxes.validate_logical_segment(
        seat or default_seat_from_address(address),
        label="seat",
    )
    alias_value = (
        runtime_boxes.validate_logical_segment(alias, label="alias")
        if alias
        else None
    )

    index = read_index()
    existing_id = index.get("addresses", {}).get(address)
    if existing_id:
        raise FileExistsError(f"agent address already exists: {address} -> {existing_id}")
    if alias_value and alias_value in index.get("aliases", {}):
        raise FileExistsError(f"agent alias already exists: {alias_value}")

    agent_id = new_agent_id()
    root = package_root(agent_id)
    dirs = package_dirs(root)
    for path in dirs.values():
        Path(path).mkdir(parents=True, exist_ok=True)

    address_parts = address.split(":")
    role = address_parts[-2]
    position = address_parts[-1]
    desks_identity = {
        "schema": DESKS_SCHEMA,
        "created_at": now_iso(),
        "agent_id": agent_id,
        "address": address,
        "role": role,
        "position": position,
        "fleet": fleet,
        "seat": seat,
        "alias": alias_value,
    }
    _atomic_write_json(root / ".desks" / "identity.json", desks_identity)

    record = {
        "schema": AGENT_SCHEMA,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "agent_id": agent_id,
        "address": address,
        "alias": alias_value,
        "runtime": runtime,
        "profile": profile_ref,
        "cwd": str(cwd_path),
        "fleet": fleet,
        "seat": seat,
        "root": str(root),
        "home": dirs["home"],
        "codex_home": dirs["codex_home"],
        "omx_root": dirs["omx_root"],
        "omx_state": dirs["omx_state"],
        "omx_team_state_root": dirs["omx_team_state_root"],
        "desks_identity": str(root / ".desks" / "identity.json"),
        "spawn_history": [],
    }
    _atomic_write_json(root / "agent.json", record)

    index.setdefault("agents", {})[agent_id] = str(root)
    index.setdefault("addresses", {})[address] = agent_id
    if alias_value:
        index.setdefault("aliases", {})[alias_value] = agent_id
    write_index(index)
    return {"ok": True, "agent": record}


def append_spawn_history(agent_id: str, event: dict[str, Any]) -> dict[str, Any]:
    root = package_root(agent_id)
    record = _read_agent_json(root)
    history = record.setdefault("spawn_history", [])
    history.append({"at": now_iso(), **event})
    record["updated_at"] = now_iso()
    _atomic_write_json(root / "agent.json", record)
    return record


def inspect(ref: str) -> dict[str, Any]:
    record = resolve(ref)
    root = Path(record["root"])
    dirs = package_dirs(root)
    files = {
        "agent_json": str(root / "agent.json"),
        "desks_identity": str(root / ".desks" / "identity.json"),
        "aura_launch": str(root / "aura-launch.json"),
        "runtime_session": str(root / "runtime-session.json"),
    }
    sizes = {}
    for label, path in dirs.items():
        p = Path(path)
        if p.exists() and p.is_dir():
            sizes[label] = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return {
        "ok": True,
        "agent": record,
        "dirs": dirs,
        "files": {key: value for key, value in files.items() if Path(value).exists()},
        "missing_files": {key: value for key, value in files.items() if not Path(value).exists()},
        "sizes": sizes,
    }
