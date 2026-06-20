"""Stable Aura fleet identity registry.

Fleet ids are lineage handles for groups of live seats. They are deliberately
thin: Aura keeps the stable id, mutable current name, aliases, and current tmux
session name. Product/unit/role meaning belongs outside this layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import tempfile
import uuid
from typing import Any

from lib import state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fleets_path():
    return state.fleet_registry_path()


def new_fleet_id() -> str:
    return f"f_{uuid.uuid4().hex[:8]}"


def read_fleets() -> dict[str, dict[str, Any]]:
    path = fleets_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    return {}


def write_fleets(data: dict[str, dict[str, Any]]) -> None:
    path = fleets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="fleets-", suffix=".json", dir=str(path.parent))
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


def _matches(record: dict[str, Any], ref: str) -> bool:
    return (
        record.get("fleet_id") == ref
        or record.get("current_name") == ref
        or record.get("tmux_session") == ref
        or ref in (record.get("aliases") or [])
    )


def resolve(ref: str | None) -> dict[str, Any] | None:
    if not ref:
        return None
    ref = str(ref)
    data = read_fleets()
    direct = data.get(ref)
    if direct:
        return direct
    for record in data.values():
        if _matches(record, ref):
            return record
    return None


def ensure_fleet(name: str | None, *, tmux_session: str | None = None) -> dict[str, Any] | None:
    if not name:
        return None
    name = str(name)
    existing = resolve(name)
    data = read_fleets()
    timestamp = now_iso()
    if existing:
        fleet_id = existing["fleet_id"]
        updated = {
            **existing,
            "current_name": existing.get("current_name") or name,
            "tmux_session": tmux_session or existing.get("tmux_session") or name,
            "last_seen_at": timestamp,
        }
        data[fleet_id] = updated
        write_fleets(data)
        return updated

    fleet_id = new_fleet_id()
    record = {
        "schema": "aura.fleet.v1",
        "fleet_id": fleet_id,
        "current_name": name,
        "aliases": [],
        "tmux_session": tmux_session or name,
        "created_at": timestamp,
        "last_seen_at": timestamp,
    }
    data[fleet_id] = record
    write_fleets(data)
    return record


def ensure_many(names: list[str]) -> list[dict[str, Any]]:
    records = []
    for name in sorted({str(name) for name in names if name}):
        record = ensure_fleet(name)
        if record:
            records.append(record)
    return records


def resolve_name_or_id(ref: str | None) -> tuple[str | None, dict[str, Any] | None]:
    record = resolve(ref)
    if record:
        return record.get("current_name"), record
    return (str(ref) if ref else None), None


def list_fleets() -> list[dict[str, Any]]:
    return sorted(read_fleets().values(), key=lambda row: row.get("current_name") or row.get("fleet_id") or "")


# --- resolver-seam registration -------------------------------------------------
# The `fleet-id` resolver: durable fleet_id -> CURRENT name (rename-safe). Lives here
# (the fleet/registry module) and self-registers; resolve.py stays pure dispatch.
def _resolve_fleet_id(fid: str, ctx: dict | None = None) -> dict[str, Any]:
    record = resolve(fid)
    if record:
        return {"fleet_id": record.get("fleet_id") or fid,
                "name": record.get("current_name"), "status": "live"}
    return {"fleet_id": fid, "name": None, "status": "stale"}  # dead id, never dropped


try:
    from lib import resolve as _resolve_seam

    _resolve_seam.register("fleet-id", _resolve_fleet_id)
except Exception:  # noqa: BLE001 - registration is best-effort; seam stays usable
    pass
