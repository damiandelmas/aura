"""Manage Aura seat identity without moving the running terminal."""

from __future__ import annotations

import json
from pathlib import Path


def _load_role_metadata(role_home: str | None, manifest_path: str | None) -> dict:
    if not role_home and not manifest_path:
        return {}
    path = Path(manifest_path or Path(role_home) / "role.json").expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    role_dir = path.parent
    return {
        "desks_role_home": str(role_dir),
        "desks_role_id": raw.get("role_id"),
        "desks_product": raw.get("product"),
        "desks_unit": raw.get("unit"),
        "desks_manifest": str(path),
        "desks_bootstrap": str((role_dir / raw.get("files", {}).get("bootstrap")).resolve()) if raw.get("files", {}).get("bootstrap") else None,
        "desks_compression": str((role_dir / raw.get("files", {}).get("compression")).resolve()) if raw.get("files", {}).get("compression") else None,
        "desks_memory": str((role_dir / raw.get("files", {}).get("memory")).resolve()) if raw.get("files", {}).get("memory") else None,
    }


def run(args):
    from lib import registry

    action = args.seat_action
    if action == "aliases":
        return {"ok": True, "aliases": registry.read_aliases()}
    if action == "resolve":
        target = registry.get_agent(args.target)
        return {"ok": bool(target), "target": args.target, "record": target, "error": None if target else "seat not found"}
    if action == "rehome":
        try:
            metadata = _load_role_metadata(getattr(args, "role_home", None), getattr(args, "manifest", None))
        except Exception as exc:
            return {"ok": False, "error": f"failed to load role metadata: {exc}"}
        metadata = {key: value for key, value in metadata.items() if value}
        return registry.rehome_agent(
            args.source,
            new_name=getattr(args, "name", None),
            new_fleet=getattr(args, "fleet", None),
            metadata=metadata,
            alias_old=not getattr(args, "no_alias_old", False),
        )
    return {"ok": False, "error": f"unknown seat action: {action}"}
