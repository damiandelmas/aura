"""Manage Aura seat identity and optional terminal placement."""

from __future__ import annotations

import json
import subprocess
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


def _tmux_target(ref: str) -> str:
    value = str(ref or "")
    if value.startswith("tmux:"):
        value = value[len("tmux:"):]
    if value.startswith("%"):
        return value
    return value


def _run_tmux(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def _move_terminal(record: dict, *, fleet: str, name: str, index: str | None) -> dict:
    source = record.get("pane_ref") or record.get("terminal_ref")
    if not source:
        return {"ok": False, "error": "seat has no pane_ref or terminal_ref to move"}

    source_target = _tmux_target(source)
    info = _run_tmux([
        "display-message",
        "-p",
        "-t",
        source_target,
        "#{session_name}:#{window_index}:#{pane_id}",
    ])
    if info.returncode != 0:
        return {"ok": False, "error": info.stderr.strip() or f"tmux target not found: {source}"}

    current_fleet, current_index, pane_id = info.stdout.strip().split(":", 2)
    session = _run_tmux(["has-session", "-t", fleet])
    if session.returncode != 0:
        return {"ok": False, "error": f"tmux session not found: {fleet}"}

    destination = f"{fleet}:{index}" if index is not None else f"{fleet}:"
    if current_fleet != fleet or (index is not None and current_index != str(index)):
        move = _run_tmux(["move-window", "-s", f"{current_fleet}:{current_index}", "-t", destination])
        if move.returncode != 0:
            return {"ok": False, "error": move.stderr.strip() or "tmux move-window failed"}

    rename_target = pane_id
    rename = _run_tmux(["rename-window", "-t", rename_target, name])
    if rename.returncode != 0:
        return {"ok": False, "error": rename.stderr.strip() or "tmux rename-window failed"}

    final = _run_tmux([
        "display-message",
        "-p",
        "-t",
        pane_id,
        "#{session_name}:#{window_index}:#{window_name}:#{pane_id}",
    ])
    if final.returncode != 0:
        return {"ok": False, "error": final.stderr.strip() or "tmux final target verification failed"}
    final_fleet, final_index, final_name, final_pane = final.stdout.strip().split(":", 3)
    return {
        "ok": True,
        "fleet": final_fleet,
        "index": final_index,
        "name": final_name,
        "pane_id": final_pane,
        "pane_ref": f"tmux:{final_fleet}:{final_pane}",
        "terminal_ref": f"{final_fleet}:{final_name}",
        "backend_ref": f"{final_fleet}:{final_name}",
        "physical_fleet": final_fleet,
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
        if getattr(args, "index", None) is not None and not getattr(args, "move_terminal", False):
            return {"ok": False, "error": "--index requires --move-terminal"}
        if getattr(args, "move_terminal", False):
            existing = registry.get_agent(args.source)
            if not existing:
                return {"ok": False, "error": f"agent not found: {args.source}"}
            target_name = getattr(args, "name", None) or existing.get("name")
            target_fleet = getattr(args, "fleet", None) or existing.get("fleet")
            moved = _move_terminal(
                existing,
                fleet=target_fleet,
                name=target_name,
                index=getattr(args, "index", None),
            )
            if not moved.get("ok"):
                return moved
            metadata.update({
                "terminal_ref": moved["terminal_ref"],
                "backend_ref": moved["backend_ref"],
                "pane_ref": moved["pane_ref"],
                "physical_fleet": moved["physical_fleet"],
            })
        return registry.rehome_agent(
            args.source,
            new_name=getattr(args, "name", None),
            new_fleet=getattr(args, "fleet", None),
            metadata=metadata,
            alias_old=not getattr(args, "no_alias_old", False),
        )
    return {"ok": False, "error": f"unknown seat action: {action}"}
