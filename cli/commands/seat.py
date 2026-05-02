"""Manage Aura seat identity and optional terminal placement."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

FLEX_PACKET_MARKER = "[FLEX PROJECT RETRIEVAL]"


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


def _list_tmux_panes() -> list[dict]:
    result = _run_tmux([
        "list-panes",
        "-a",
        "-F",
        "#{session_name}\t#{window_index}\t#{window_name}\t#{pane_id}\t#{pane_pid}",
    ])
    if result.returncode != 0:
        return []
    panes = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        session, window_index, window_name, pane_id, pane_pid = parts
        try:
            pid = int(pane_pid)
        except ValueError:
            pid = None
        panes.append({
            "session": session,
            "window_index": window_index,
            "window_name": window_name,
            "pane_id": pane_id,
            "pane_pid": pid,
        })
    return panes


def _discovery_matches_record(record: dict, discovery: dict) -> bool:
    if not discovery:
        return False
    expected_session = record.get("runtime_session_id") or record.get("session_id")
    discovered_session = discovery.get("runtime_session_id") or discovery.get("session_id")
    if expected_session and discovered_session and str(expected_session) == str(discovered_session):
        return True
    evidence = discovery.get("runtime_session_evidence") or {}
    launch_id = record.get("aura_launch_id")
    return bool(launch_id and evidence.get("aura_launch_id") == launch_id)


def _discover_pane(record: dict, pane: dict) -> dict:
    from lib import runtime_session

    discovered = runtime_session.discover_from_pane_pid(
        record.get("runtime"),
        pane.get("pane_pid"),
        seat_name=record.get("name") or record.get("seat"),
        launch_id=record.get("aura_launch_id"),
    )
    return discovered or {}


def _verified_move_source(record: dict) -> dict:
    """Resolve the real pane for a seat before moving it.

    Registry pane refs are cached operational state. A rehome with
    --move-terminal is a physical operation, so prefer launch/session evidence
    when it can identify the live pane more accurately than the cached ref.
    """
    source = record.get("pane_ref") or record.get("terminal_ref")
    if not record.get("aura_launch_id") and not (record.get("runtime_session_id") or record.get("session_id")):
        return {"ok": True, "source": source, "refreshed": False}

    stale_source_discovery = {}
    if source:
        source_target = _tmux_target(source)
        info = _run_tmux([
            "display-message",
            "-p",
            "-t",
            source_target,
            "#{session_name}\t#{window_index}\t#{window_name}\t#{pane_id}\t#{pane_pid}",
        ])
        if info.returncode == 0:
            parts = info.stdout.strip().split("\t")
            if len(parts) == 5:
                pane = {
                    "session": parts[0],
                    "window_index": parts[1],
                    "window_name": parts[2],
                    "pane_id": parts[3],
                    "pane_pid": int(parts[4]) if parts[4].isdigit() else None,
                }
                stale_source_discovery = _discover_pane(record, pane)
                if _discovery_matches_record(record, stale_source_discovery):
                    return {"ok": True, "source": source, "refreshed": False, "discovery": stale_source_discovery}

    matches = []
    for pane in _list_tmux_panes():
        discovered = _discover_pane(record, pane)
        if not _discovery_matches_record(record, discovered):
            continue
        matches.append({**pane, "discovery": discovered})

    if len(matches) == 1:
        pane = matches[0]
        return {
            "ok": True,
            "source": f"tmux:{pane['session']}:{pane['pane_id']}",
            "refreshed": True,
            "pane_ref": f"tmux:{pane['session']}:{pane['pane_id']}",
            "pane_pid": pane.get("pane_pid"),
            "discovery": pane.get("discovery"),
            "previous_source": source,
        }
    if len(matches) > 1:
        return {
            "ok": False,
            "error": "multiple tmux panes match seat launch/session evidence; refusing physical move",
            "matches": [
                {
                    "session": pane.get("session"),
                    "window_index": pane.get("window_index"),
                    "window_name": pane.get("window_name"),
                    "pane_id": pane.get("pane_id"),
                    "pane_pid": pane.get("pane_pid"),
                    "runtime_session_id": (pane.get("discovery") or {}).get("runtime_session_id"),
                }
                for pane in matches
            ],
            "previous_source": source,
            "previous_discovery": stale_source_discovery,
        }

    if source:
        return {
            "ok": True,
            "source": source,
            "refreshed": False,
            "warning": "could not verify pane by launch/session evidence; using cached source",
            "previous_discovery": stale_source_discovery,
        }
    return {"ok": False, "error": "seat has no pane_ref or terminal_ref to move"}


def _tmux_target_info(target: str | None) -> dict | None:
    if not target:
        return None
    result = _run_tmux([
        "display-message",
        "-p",
        "-t",
        _tmux_target(target),
        "#{session_name}\t#{window_index}\t#{window_name}\t#{pane_id}\t#{pane_pid}",
    ])
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split("\t")
    if len(parts) != 5:
        return None
    session, window_index, window_name, pane_id, pane_pid = parts
    try:
        pid = int(pane_pid)
    except ValueError:
        pid = None
    return {
        "session": session,
        "window_index": window_index,
        "window_name": window_name,
        "pane_id": pane_id,
        "pane_pid": pid,
    }


def _destination_collision(*, fleet: str, name: str, source_pane_id: str) -> dict | None:
    existing = _tmux_target_info(f"{fleet}:{name}")
    if not existing:
        return None
    if existing.get("pane_id") == source_pane_id:
        return None
    return {
        "ok": False,
        "error": f"target tmux window already exists: {fleet}:{name}",
        "reason": "target-window-exists",
        "target": f"{fleet}:{name}",
        "existing": existing,
        "source_pane_id": source_pane_id,
        "hint": "move or rename the existing window first, or rehome with --index to an explicit free window slot",
    }


def _move_terminal(record: dict, *, fleet: str, name: str, index: str | None) -> dict:
    verified = _verified_move_source(record)
    if not verified.get("ok"):
        return verified
    source = verified.get("source")
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

    collision = _destination_collision(fleet=fleet, name=name, source_pane_id=pane_id)
    if collision:
        return collision

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
        "source_refreshed": verified.get("refreshed", False),
        "previous_pane_ref": verified.get("previous_source"),
        "source_warning": verified.get("warning"),
    }


def _seat_targets(record: dict) -> list[str]:
    seen = set()
    targets = []
    for key in ("pane_ref", "terminal_ref", "backend_ref"):
        value = record.get(key)
        if value and value not in seen:
            seen.add(value)
            targets.append(value)
    return targets


def _flex_project_for_record(record: dict) -> tuple[Path | None, Path | None]:
    manifest_value = record.get("flex_project_manifest")
    root_value = record.get("flex_project_root")
    if manifest_value and root_value:
        manifest = Path(str(manifest_value)).expanduser()
        root = Path(str(root_value)).expanduser()
        if manifest.is_file():
            try:
                return manifest.resolve(), root.resolve()
            except OSError:
                return manifest, root

    from commands import spawn

    workdir = record.get("cwd") or record.get("workdir") or record.get("runtime_session_cwd")
    role_meta = {
        key: record.get(key)
        for key in (
            "desks_role_home",
            "desks_role_id",
            "desks_product",
            "desks_unit",
            "desks_manifest",
            "flex_project_manifest",
            "flex_project_root",
        )
        if record.get(key)
    }
    if workdir:
        return spawn._resolve_launch_flex_project(Path(str(workdir)), role_meta)
    if role_meta:
        return spawn._resolve_launch_flex_project(Path.cwd(), role_meta)
    return None, None


def _packet_session_key(record: dict) -> str | None:
    return (
        record.get("runtime_session_id")
        or record.get("session_id")
        or record.get("source_session_id")
        or record.get("aura_launch_id")
    )


def _packet_registry_match(record: dict, manifest: Path, session_key: str | None) -> dict | None:
    if not record.get("flex_project_packet_delivered"):
        return None
    if str(record.get("flex_project_packet_manifest") or "") != str(manifest):
        return None
    delivered_key = record.get("flex_project_packet_session_key")
    if session_key and delivered_key and str(delivered_key) != str(session_key):
        return None
    return {
        "source": "registry",
        "delivered_at": record.get("flex_project_packet_delivered_at"),
        "session_key": delivered_key,
    }


def _packet_capture_match(terminal, target: str | None, manifest: Path, *, lines: int) -> dict | None:
    if not target or not hasattr(terminal, "capture_output"):
        return None
    try:
        capture = terminal.capture_output(target, lines)
    except Exception:
        return None
    text = "\n".join(str(line) for line in capture or [])
    if FLEX_PACKET_MARKER not in text:
        return None
    if str(manifest) not in text:
        return {
            "source": "terminal-capture",
            "warning": "packet marker found without matching manifest path",
            "capture_lines": len(capture or []),
        }
    return {
        "source": "terminal-capture",
        "capture_lines": len(capture or []),
    }


def _codex_jsonl_candidates(record: dict) -> list[Path]:
    candidates = []
    evidence = record.get("runtime_session_evidence") or {}
    jsonl = evidence.get("jsonl") or record.get("jsonl")
    if jsonl:
        path = Path(str(jsonl)).expanduser()
        if path.is_file():
            candidates.append(path)

    session_id = record.get("runtime_session_id") or record.get("session_id")
    root = Path.home() / ".codex" / "sessions"
    if not session_id or not root.exists():
        return candidates
    try:
        result = subprocess.run(
            ["rg", "-l", str(session_id), str(root), "-g", "*.jsonl"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return candidates
    for line in result.stdout.splitlines():
        path = Path(line.strip())
        if path.is_file() and path not in candidates:
            candidates.append(path)
    return candidates


def _packet_codex_jsonl_match(record: dict, manifest: Path) -> dict | None:
    if record.get("runtime") != "codex":
        return None
    checked = 0
    for path in _codex_jsonl_candidates(record):
        checked += 1
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if FLEX_PACKET_MARKER in line and str(manifest) in line:
                        return {"source": "codex-jsonl", "jsonl": str(path), "checked": checked}
        except OSError:
            continue
    if checked:
        return {"source": "codex-jsonl", "checked": checked, "found": False}
    return None


def _packet_already_present(record: dict, terminal, target: str | None, manifest: Path, *, lines: int) -> dict | None:
    session_key = _packet_session_key(record)
    registry_match = _packet_registry_match(record, manifest, session_key)
    if registry_match:
        return registry_match
    capture_match = _packet_capture_match(terminal, target, manifest, lines=lines)
    if capture_match:
        return capture_match
    jsonl_match = _packet_codex_jsonl_match(record, manifest)
    if jsonl_match and jsonl_match.get("found") is not False:
        return jsonl_match
    return None


def _mark_flex_packet(record: dict, registry, *, manifest: Path, root: Path, source: str, sent: bool) -> dict:
    from lib import delivery

    session_key = _packet_session_key(record)
    now = delivery.now_iso()
    delivered = bool(sent) or bool(record.get("flex_project_packet_delivered"))
    updated = registry.upsert_agent({
        **record,
        "flex_project_manifest": str(manifest),
        "flex_project_root": str(root),
        "flex_project_packet_delivered": delivered,
        "flex_project_packet_delivered_at": now if sent else record.get("flex_project_packet_delivered_at"),
        "flex_project_packet_source": source,
        "flex_project_packet_manifest": str(manifest),
        "flex_project_packet_session_key": session_key,
    })
    return updated


def _inject_flex(args, registry, terminal) -> dict:
    record = registry.get_agent(args.target)
    if not record:
        return {"ok": False, "error": f"seat not found: {args.target}"}
    if registry.is_hidden_agent(record):
        return {"ok": False, "error": "target is hidden/internal; refusing Flex packet injection", "target": args.target}

    fleet = record.get("fleet")
    if fleet and hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)

    target = record.get("pane_ref") or record.get("terminal_ref") or record.get("backend_ref") or args.target
    if not _target_exists(terminal, target):
        return {"ok": False, "error": f"terminal target not found: {target}", "target": args.target}

    manifest, root = _flex_project_for_record(record)
    if not manifest or not root:
        return {
            "ok": False,
            "error": "no Flex project manifest found for seat",
            "target": args.target,
            "cwd": record.get("cwd") or record.get("workdir") or record.get("runtime_session_cwd"),
        }

    from commands import spawn
    from lib import delivery

    packet = spawn._render_flex_project_launch_packet(manifest, root)
    if not packet:
        return {"ok": False, "error": "failed to render Flex project packet", "manifest": str(manifest), "root": str(root)}

    present = None if getattr(args, "force", False) else _packet_already_present(
        record,
        terminal,
        target,
        manifest,
        lines=max(1, int(getattr(args, "capture_lines", 5000) or 5000)),
    )
    if present:
        _mark_flex_packet(record, registry, manifest=manifest, root=root, source=present.get("source", "existing"), sent=False)
        return {
            "ok": True,
            "skipped": True,
            "reason": "flex-project-packet-already-present",
            "target": args.target,
            "terminal_ref": target,
            "manifest": str(manifest),
            "root": str(root),
            "evidence": present,
        }

    if getattr(args, "dry_run", False):
        return {
            "ok": True,
            "dry_run": True,
            "would_send": True,
            "target": args.target,
            "terminal_ref": target,
            "manifest": str(manifest),
            "root": str(root),
            "packet_preview": packet[:240],
        }

    result = terminal.send_text(target, packet, submit=True)
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "tmux send failed"),
            "target": args.target,
            "terminal_ref": target,
            "manifest": str(manifest),
        }

    updated = _mark_flex_packet(record, registry, manifest=manifest, root=root, source="seat.inject-flex", sent=True)
    dedupe_key = f"flex-project-packet:{registry.seat_ref(record.get('fleet'), record.get('name'))}:{manifest}:{_packet_session_key(record) or ''}"
    delivery_record = delivery.new_delivery_record(
        delivery_type="flex_project_packet",
        sender="aura",
        target=registry.seat_ref(record.get("fleet"), record.get("name")),
        payload_hash=delivery.body_hash(packet),
        backend="tmux",
        backend_ref=target,
        dedupe_key=dedupe_key,
        state="delivered",
        terminal_ref=result.get("target"),
        submitted=result.get("submitted", True),
        manifest=str(manifest),
        root=str(root),
    )
    delivery.append_attempt(delivery_record, state="delivered", evidence={"terminal_ref": result.get("target")})
    delivery.append_record(delivery_record)

    return {
        "ok": True,
        "sent": True,
        "target": args.target,
        "terminal_ref": result.get("target") or target,
        "manifest": str(manifest),
        "root": str(root),
        "registry_updated": True,
        "flex_project_packet_delivered_at": updated.get("flex_project_packet_delivered_at"),
    }


def _target_exists(terminal, target: str | None) -> bool:
    if not target:
        return False
    if hasattr(terminal, "target_exists"):
        return bool(terminal.target_exists(target))
    return bool(terminal.window_exists(target))


def _pane_exists_anywhere(pane_ref: str | None) -> bool:
    if not pane_ref:
        return False
    target = _tmux_target(pane_ref)
    if not target.startswith("%"):
        return False
    result = _run_tmux(["display-message", "-p", "-t", target, "#{pane_id}"])
    return result.returncode == 0


def _safe_stale(agent: dict) -> bool:
    status = str(agent.get("status") or "").lower()
    if status in {"dead", "stopped", "cut", "terminated", "exited"}:
        return True
    return bool(agent.get("cut_at") or agent.get("ended_at") or agent.get("terminated_at"))


def _sweep(args, registry, terminal) -> dict:
    include_hidden = bool(getattr(args, "include_hidden", False))
    agents = registry.list_agents(getattr(args, "fleet", None), include_hidden=include_hidden)
    stale = []
    suspect = []
    alive = 0
    for agent in agents:
        fleet = agent.get("fleet")
        if fleet and hasattr(terminal, "configure_session"):
            terminal.configure_session(fleet)
        targets = _seat_targets(agent)
        alive_targets = [target for target in targets if _target_exists(terminal, target)]
        if alive_targets:
            alive += 1
            continue
        row = {
            "seat": agent.get("name"),
            "fleet": fleet,
            "seat_ref": registry.seat_ref(fleet, agent.get("name")),
            "status": agent.get("status"),
            "runtime": agent.get("runtime"),
            "terminal_ref": agent.get("terminal_ref"),
            "backend_ref": agent.get("backend_ref"),
            "pane_ref": agent.get("pane_ref"),
            "checked_targets": targets,
        }
        if _safe_stale(agent):
            stale.append({**row, "reason": "registered-terminal-missing"})
            continue
        pane_exists = _pane_exists_anywhere(agent.get("pane_ref"))
        suspect.append({
            **row,
            "reason": "registered-terminal-unverified",
            "pane_exists_anywhere": pane_exists,
        })

    removed = []
    if getattr(args, "confirm", False):
        for row in stale:
            if registry.remove_agent(row["seat"], fleet=row.get("fleet")):
                removed.append(row["seat_ref"])

    return {
        "ok": True,
        "schema": "aura.seat_sweep.v1",
        "dry_run": not getattr(args, "confirm", False),
        "fleet": getattr(args, "fleet", None),
        "include_hidden": include_hidden,
        "checked": len(agents),
        "alive": alive,
        "stale": stale,
        "stale_count": len(stale),
        "suspect": suspect,
        "suspect_count": len(suspect),
        "removed": removed,
        "removed_count": len(removed),
    }


def run(args):
    from lib import registry

    action = args.seat_action
    if action == "aliases":
        return {"ok": True, "aliases": registry.read_aliases()}
    if action == "resolve":
        target = registry.get_agent(args.target)
        return {"ok": bool(target), "target": args.target, "record": target, "error": None if target else "seat not found"}
    if action == "cut":
        from commands import cut

        result = cut.run(args)
        if result.get("ok"):
            result["seat_cut"] = True
            result["seat"] = result.get("name")
        return result
    if action == "sweep":
        from lib import terminal

        return _sweep(args, registry, terminal)
    if action == "inject-flex":
        from lib import terminal

        return _inject_flex(args, registry, terminal)
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
            if moved.get("source_refreshed"):
                metadata["rehome_source_refreshed"] = True
                metadata["rehome_previous_pane_ref"] = moved.get("previous_pane_ref")
            if moved.get("source_warning"):
                metadata["rehome_source_warning"] = moved.get("source_warning")
        return registry.rehome_agent(
            args.source,
            new_name=getattr(args, "name", None),
            new_fleet=getattr(args, "fleet", None),
            metadata=metadata,
            alias_old=not getattr(args, "no_alias_old", False),
        )
    return {"ok": False, "error": f"unknown seat action: {action}"}
