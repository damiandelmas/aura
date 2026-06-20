"""Society container config — a named JSON package: members + config + resolves_to.

A *society* is the top container above fleet/placement. It holds:
  - members      durable `fleet-id://<id>` pointers (rename-safe; authored by name/glob,
                 pinned to ids at `set` time — a fleet rename never silently adds/drops one)
  - config       a K -> pointer map (values resolve via the seam; literals/op://… pass raw)
  - resolves_to  one opaque pointer, stored + returned RAW

Discipline (v1): stores + resolves ONLY. Does NOT apply config to seats, deref secrets,
or know Runway. ALL pointer resolution routes through `lib.resolve` (the seam); the
`fleet-id` resolver self-registers from `lib.fleets` (imported here).

This is the CONTAINER. The member-set-changed *event* is `lib.membership` — a level
below, sharing no code.
"""

from __future__ import annotations

import fnmatch
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from lib import resolve, fleets, state  # importing fleets self-registers the fleet-id resolver

SCHEMA = "aura.society.v1"


def registry_path() -> Path:
    return state.state_root() / "societies" / "registry.json"


def _read() -> dict[str, Any]:
    path = registry_path()
    if not path.exists():
        return {"schema": SCHEMA, "societies": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": SCHEMA, "societies": {}}
    if not isinstance(data, dict):
        return {"schema": SCHEMA, "societies": {}}
    data.setdefault("schema", SCHEMA)
    if not isinstance(data.get("societies"), dict):
        data["societies"] = {}
    return data


def _write(data: dict[str, Any]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _blank_society() -> dict[str, Any]:
    return {"schema": SCHEMA, "members": [], "config": {}, "resolves_to": None}


def _member_pointer(fleet_id: str) -> str:
    return f"fleet-id://{fleet_id}"


def _name_or_glob_to_ids(pattern: str) -> list[str]:
    """Snapshot a fleet name|id|alias|glob to durable fleet_id(s) at authoring time."""
    rec = fleets.resolve(pattern)
    if rec and rec.get("fleet_id"):
        return [rec["fleet_id"]]
    ids = [f["fleet_id"] for f in fleets.list_fleets()
           if f.get("current_name") and f.get("fleet_id")
           and fnmatch.fnmatch(f["current_name"], pattern)]
    return sorted(set(ids))


# --------------------------------------------------------------------------- verbs


def list_societies() -> dict[str, Any]:
    data = _read()
    rows = [
        {"name": name, "members": len(soc.get("members") or []),
         "has_config": bool(soc.get("config")), "resolves_to": soc.get("resolves_to")}
        for name, soc in sorted(data["societies"].items())
    ]
    return {"ok": True, "schema": "aura.society_list.v1", "total": len(rows), "societies": rows}


def get(name: str) -> dict[str, Any]:
    soc = _read()["societies"].get(name)
    if not soc:
        return {"ok": False, "error": f"society not found: {name}"}
    members = [resolve.resolve(m) for m in (soc.get("members") or [])]  # ids -> current names (+stale)
    return {"ok": True, "schema": "aura.society.get.v1", "name": name,
            "members": members, "config": soc.get("config") or {},
            "resolves_to": soc.get("resolves_to")}


def of(fleet: str) -> dict[str, Any]:
    """Reverse lookup: which societ(ies) own this fleet, by durable id."""
    rec = fleets.resolve(fleet)
    fid = rec.get("fleet_id") if rec else None
    hits = []
    if fid:
        for name, soc in _read()["societies"].items():
            ids = {m.partition("://")[2] for m in (soc.get("members") or [])
                   if isinstance(m, str) and m.startswith("fleet-id://")}
            if fid in ids:
                hits.append(name)
    return {"ok": True, "schema": "aura.society.of.v1", "fleet": fleet,
            "fleet_id": fid, "societies": sorted(hits)}


def resolve_config(name: str, key: str | None = None) -> dict[str, Any]:
    soc = _read()["societies"].get(name)
    if not soc:
        return {"ok": False, "error": f"society not found: {name}"}
    cfg = soc.get("config") or {}
    if key is not None:
        return {"ok": True, "name": name, "key": key, "value": resolve.resolve(cfg.get(key))}
    return {"ok": True, "name": name, "config": resolve.resolve_map(cfg)}


def set_member(name: str, pattern: str) -> dict[str, Any]:
    ids = _name_or_glob_to_ids(pattern)
    if not ids:
        return {"ok": False, "error": f"no fleet matched: {pattern}"}
    data = _read()
    soc = data["societies"].setdefault(name, _blank_society())
    members = set(soc.get("members") or [])
    members.update(_member_pointer(fid) for fid in ids)
    soc["members"] = sorted(members)
    _write(data)
    return {"ok": True, "name": name, "pinned": ids, "members": soc["members"]}


def remove_member(name: str, fleet_id: str) -> dict[str, Any]:
    data = _read()
    soc = data["societies"].get(name)
    if not soc:
        return {"ok": False, "error": f"society not found: {name}"}
    fid = fleet_id.partition("://")[2] if str(fleet_id).startswith("fleet-id://") else fleet_id
    ptr = _member_pointer(fid)
    before = len(soc.get("members") or [])
    soc["members"] = [m for m in (soc.get("members") or []) if m != ptr]
    _write(data)
    return {"ok": True, "name": name, "removed": before - len(soc["members"])}


def set_fields(name: str, *, config: dict[str, str] | None = None,
               resolves_to: str | None = None) -> dict[str, Any]:
    data = _read()
    soc = data["societies"].setdefault(name, _blank_society())
    if config:
        soc.setdefault("config", {})
        soc["config"].update(config)
    if resolves_to is not None:
        soc["resolves_to"] = resolves_to
    _write(data)
    return {"ok": True, "name": name, "config": soc.get("config"), "resolves_to": soc.get("resolves_to")}


def run(args) -> dict[str, Any]:
    action = getattr(args, "society_action", None)
    if action == "list":
        return list_societies()
    if action == "get":
        return get(args.name)
    if action == "of":
        return of(args.fleet)
    if action == "resolve":
        return resolve_config(args.name, getattr(args, "key", None))
    if action == "remove-member":
        return remove_member(args.name, args.fleet_id)
    if action == "set":
        steps: list[dict[str, Any]] = []
        for member in (getattr(args, "member", None) or []):
            steps.append(set_member(args.name, member))
        cfg: dict[str, str] = {}
        for kv in (getattr(args, "config", None) or []):
            if "=" in kv:
                k, v = kv.split("=", 1)
                cfg[k] = v
        if cfg or getattr(args, "resolves_to", None) is not None:
            steps.append(set_fields(args.name, config=cfg or None,
                                    resolves_to=getattr(args, "resolves_to", None)))
        if not steps:
            return {"ok": False, "error": "set requires --member, --config K=V, or --resolves-to"}
        return {"ok": all(s.get("ok") for s in steps), "name": args.name, "steps": steps}
    return {"ok": False, "error": f"unknown society action: {action}"}
