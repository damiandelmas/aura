"""Manage Aura seat identity and optional terminal placement."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

FLEX_PACKET_MARKER = "[FLEX PROJECT RETRIEVAL]"


def _load_role_metadata(role_home: str | None, manifest_path: str | None) -> dict:
    if not role_home and not manifest_path:
        return {}
    from commands import spawn

    manifest = spawn._load_role_manifest(manifest_path, role_home)
    return spawn._role_metadata_from_manifest(manifest)


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
        "#{session_name}\t#{window_index}\t#{window_name}\t#{pane_id}\t#{pane_pid}\t#{pane_current_command}\t#{pane_current_path}",
    ])
    if result.returncode != 0:
        return []
    panes = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        # Pad with empty strings for backwards compatibility with older tmux outputs.
        while len(parts) < 7:
            parts.append("")
        session, window_index, window_name, pane_id, pane_pid, pane_current_command, pane_current_path = parts[:7]
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
            "pane_current_command": pane_current_command,
            "pane_current_path": pane_current_path,
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
        return {
            "ok": True,
            "skipped": True,
            "reason": "flex-project-packet-disabled",
            "target": args.target,
            "terminal_ref": target,
            "manifest": str(manifest),
            "root": str(root),
        }

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


def _latest_report_for_record(record: dict) -> dict | None:
    from lib import reports

    fleet = record.get("fleet")
    name = record.get("name") or record.get("seat")
    rows = reports.iter_reports()
    for row in reversed(rows):
        if row.get("seat") != name:
            continue
        if fleet and row.get("fleet") != fleet:
            continue
        return row
    return None


def _restart_handoff_gate(record: dict, *, force: bool) -> dict:
    latest = _latest_report_for_record(record)
    acceptable = {"complete", "parked", "blocked", "handoff", "failed"}
    if latest and latest.get("state") in acceptable:
        return {"ok": True, "latest_report": latest}
    if force:
        reason = "working-report" if latest else "missing-report"
        return {
            "ok": True,
            "forced": True,
            "warning": f"restart forced despite {reason}",
            "latest_report": latest,
        }
    return {
        "ok": False,
        "phase": "handoff_missing",
        "error": "latest report is missing or not at a restart-safe boundary; report first or pass --force",
        "latest_report": latest,
    }


def _restart_role_metadata(args, record: dict) -> tuple[dict, str | None, str | None]:
    manifest_arg = getattr(args, "manifest", None)
    role_home_arg = getattr(args, "role_home", None)
    if manifest_arg and role_home_arg:
        raise ValueError("use either --manifest or --role-home, not both")
    if manifest_arg or role_home_arg:
        from commands import spawn

        manifest = spawn._load_role_manifest(manifest_arg, role_home_arg)
        files = manifest.get("files") or {}
        meta = spawn._role_metadata_from_manifest(manifest)
        prompt = "\n".join([
            f"Read {files.get('bootstrap')} and follow it.",
            f"Use {manifest['role_home']} as your Desks role home.",
        ])
        return meta, str(manifest["workspace_root"]), prompt

    meta = {
        key: record.get(key)
        for key in (
            "desks_role_home",
            "desks_role_id",
            "desks_product",
            "desks_unit",
            "desks_manifest",
            "desks_bootstrap",
            "desks_compression",
            "desks_memory",
            "desks_default_seat",
            "desks_default_fleet",
            "desks_identity_id",
            "desks_profile_id",
            "desks_current_name",
            "desks_identity_home",
            "desks_profile_home",
            "desks_memory_home",
            "flex_project_manifest",
            "flex_project_root",
        )
        if record.get(key)
    }
    return meta, None, None


def _restart_plan(args, record: dict) -> dict:
    runtime = getattr(args, "runtime", None) or record.get("runtime")
    command = record.get("command")
    cwd = getattr(args, "cwd", None) or record.get("cwd") or record.get("workdir") or record.get("runtime_session_cwd")
    if not runtime:
        return {"ok": False, "phase": "build_plan", "error": "seat has no runtime; cannot reconstruct restart command"}
    if runtime == "command" and not command:
        return {"ok": False, "phase": "build_plan", "error": "command runtime has no recorded command; refusing restart"}
    if not command:
        try:
            from lib import runtimes

            resolved, spec = runtimes.resolve_runtime(runtime)
            runtime = resolved
            command = runtimes.build_command(
                runtime,
                spec,
                name=record.get("name"),
                profile=record.get("profile"),
                model=record.get("model"),
            )
        except Exception as exc:
            return {"ok": False, "phase": "build_plan", "error": f"cannot reconstruct launch command: {exc}"}
    if not cwd:
        return {"ok": False, "phase": "build_plan", "error": "seat has no cwd/workdir; refusing restart"}
    cwd_path = Path(str(cwd)).expanduser()
    if not cwd_path.is_absolute():
        cwd_path = Path.cwd() / cwd_path
    try:
        cwd_path = cwd_path.resolve()
    except OSError:
        pass
    if not cwd_path.is_dir():
        return {"ok": False, "phase": "build_plan", "error": f"cwd is not a directory: {cwd_path}"}

    try:
        role_meta, role_cwd, role_prompt = _restart_role_metadata(args, record)
    except Exception as exc:
        return {"ok": False, "phase": "build_plan", "error": f"failed to load role metadata: {exc}"}
    if role_cwd and not getattr(args, "cwd", None):
        cwd_path = Path(role_cwd)

    resume_session_id = record.get("runtime_session_id") or record.get("session_id")
    try:
        from lib import runtimes

        runtime_capabilities = runtimes.capabilities(runtime)
    except Exception:
        runtime_capabilities = {"supports_resume": False}
    if resume_session_id and runtime_capabilities.get("supports_resume"):
        try:
            command = runtimes.build_resume_command(runtime, str(resume_session_id), cwd=str(cwd_path))
        except Exception:
            # Fall back to the recorded launch command if the runtime cannot
            # build a native resume command for this seat.
            pass

    prompt = getattr(args, "prompt", None) or role_prompt
    return {
        "ok": True,
        "runtime": runtime,
        "command": command,
        "cwd": str(cwd_path),
        "role_meta": role_meta,
        "prompt": prompt,
        "resume_session_id": resume_session_id,
    }


def _stop_restart_target(terminal, target: str, *, force: bool) -> dict:
    before = terminal.pane_pid(target) if hasattr(terminal, "pane_pid") else None
    try:
        terminal.kill_window(target)
    except Exception as exc:
        return {"ok": False, "phase": "stop_failed", "error": str(exc), "old_pid": before}
    deadline = time.time() + (0.5 if force else 2.0)
    while time.time() < deadline:
        if not _target_exists(terminal, target):
            return {"ok": True, "old_pid": before, "stopped": True}
        time.sleep(0.1)
    if _target_exists(terminal, target):
        return {"ok": False, "phase": "stop_failed", "error": f"old terminal target still exists: {target}", "old_pid": before}
    return {"ok": True, "old_pid": before, "stopped": True}


def _launch_restart_target(terminal, target: str, name: str, plan: dict, launch_env: dict, unset_env: list[str]) -> dict:
    if hasattr(terminal, "respawn_pane"):
        return terminal.respawn_pane(
            target,
            workdir=plan["cwd"],
            command=plan["command"],
            env=launch_env,
            unset_env=unset_env,
        )
    stop = _stop_restart_target(terminal, target, force=True)
    if not stop.get("ok"):
        return stop
    launch = terminal.create_window(
        name,
        plan["cwd"],
        detached=True,
        command=plan["command"],
        env=launch_env,
        unset_env=unset_env,
    )
    if launch.get("ok"):
        launch["fallback_recreated_viewport"] = True
        launch["old_pid"] = stop.get("old_pid")
    return launch


def _session_fields(session: dict) -> dict:
    fields = {}
    for key in (
        "session_id",
        "runtime_session_id",
        "runtime_session_source",
        "runtime_session_confidence",
        "runtime_session_evidence",
        "runtime_session_env",
        "runtime_session_cwd",
        "runtime_session_created_at_ms",
        "runtime_session_updated_at_ms",
        "runtime_session_pid",
    ):
        if session.get(key) is not None:
            fields[key] = session.get(key)
    return fields


def _restart(args, registry, terminal) -> dict:
    record = registry.get_agent(args.target)
    if not record:
        return {"ok": False, "schema": "aura.seat_restart.v1", "phase": "resolve_failed", "target": args.target, "error": "seat not found"}
    if registry.is_hidden_agent(record):
        return {"ok": False, "schema": "aura.seat_restart.v1", "phase": "resolve_failed", "target": args.target, "error": "target is hidden/internal; refusing restart"}

    fleet = record.get("fleet")
    name = record.get("name") or record.get("seat")
    seat_ref = registry.seat_ref(fleet, name)
    if fleet and hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)

    target = record.get("pane_ref") or record.get("terminal_ref") or record.get("backend_ref")
    if not _target_exists(terminal, target):
        return {
            "ok": False,
            "schema": "aura.seat_restart.v1",
            "phase": "resolve_failed",
            "target": args.target,
            "seat_ref": seat_ref,
            "error": f"terminal target not found: {target}",
        }

    plan = _restart_plan(args, record)
    if not plan.get("ok"):
        return {"ok": False, "schema": "aura.seat_restart.v1", "target": args.target, "seat_ref": seat_ref, **plan}

    gate = _restart_handoff_gate(record, force=bool(getattr(args, "force", False)))
    if not gate.get("ok"):
        return {"ok": False, "schema": "aura.seat_restart.v1", "target": args.target, "seat_ref": seat_ref, **gate}

    old_pid = terminal.pane_pid(target) if hasattr(terminal, "pane_pid") else None
    old = {
        "runtime_session_id": record.get("runtime_session_id") or record.get("session_id"),
        "pid": old_pid,
        "pane_ref": record.get("pane_ref"),
        "terminal_ref": record.get("terminal_ref"),
        "aura_launch_id": record.get("aura_launch_id"),
    }
    restart_id = f"aura-seat-restart-{uuid.uuid4().hex[:16]}"
    dry_run = bool(getattr(args, "dry_run", False))
    if dry_run:
        return {
            "ok": True,
            "schema": "aura.seat_restart.v1",
            "dry_run": True,
            "target": args.target,
            "seat_ref": seat_ref,
            "same_viewport": True,
            "old": old,
            "plan": {k: v for k, v in plan.items() if k not in {"ok", "role_meta", "prompt"}},
            "warnings": [gate["warning"]] if gate.get("warning") else [],
        }

    launch_id = f"aura-launch-{uuid.uuid4().hex[:16]}"
    launch_env = {
        "AURA_AGENT_NAME": name,
        "AURA_SEAT": name,
        "AURA_FLEET": fleet,
        "AURA_RUNTIME": plan["runtime"],
        "AURA_LAUNCH_ID": launch_id,
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "FORCE_COLOR": "1",
        "CLICOLOR_FORCE": "1",
    }
    role_meta = plan.get("role_meta") or {}
    if role_meta:
        from commands import spawn

        launch_env.update(spawn._desks_launch_env(role_meta))
    if role_meta.get("flex_project_manifest"):
        launch_env["FLEX_PROJECT_MANIFEST"] = role_meta["flex_project_manifest"]
    if role_meta.get("flex_project_root"):
        launch_env["FLEX_PROJECT_ROOT"] = role_meta["flex_project_root"]

    unset_env = [
        "NO_COLOR",
        "AURA_RUNTIME_SESSION_ID",
        "AURA_SESSION_ID",
        "CODEX_THREAD_ID",
        "CLAUDE_SESSION_ID",
    ]
    try:
        launch = _launch_restart_target(terminal, target, name, plan, launch_env, unset_env)
    except TypeError:
        launch = {"ok": False, "error": "terminal backend does not support direct command relaunch"}
    if not launch.get("ok"):
        failure_record = registry.upsert_agent({
            **record,
            "name": name,
            "fleet": fleet,
            "status": "restart_failed",
            "restart_last_failure": {
                "restart_id": restart_id,
                "phase": "relaunch_failed",
                "error": launch.get("error", "launch failed"),
                "old": old,
            },
        })
        try:
            from lib import session_ledger

            session_ledger.append_seat_event(
                event="seat_restart_failed",
                before=record,
                after=failure_record,
                evidence={
                    "restart_id": restart_id,
                    "phase": "relaunch_failed",
                    "error": launch.get("error", "launch failed"),
                    "old": old,
                },
                source_command="aura seat restart",
            )
        except Exception:
            pass
        return {
            "ok": False,
            "schema": "aura.seat_restart.v1",
            "phase": "relaunch_failed",
            "target": args.target,
            "seat_ref": seat_ref,
            "old": old,
            "error": launch.get("error", "launch failed"),
            "record_status": failure_record.get("status"),
            "hint": "the old process was stopped but relaunch failed; inspect the tmux fleet and restart or repair manually",
        }

    new_pane_ref = f"tmux:{fleet}:{launch.get('pane_id')}" if launch.get("pane_id") else None
    if launch.get("respawned_viewport"):
        terminal_ref = old.get("terminal_ref") or f"{fleet}:{name}"
    else:
        terminal_ref = launch.get("target") or f"{fleet}:{name}"
    prompt_sent = False
    if plan.get("prompt") and hasattr(terminal, "send_text"):
        from commands import spawn

        prompt_result = terminal.send_text(
            new_pane_ref or terminal_ref,
            spawn._augment_runtime_prompt(plan["runtime"], plan["prompt"], fleet=fleet, seat=name, launch_id=launch_id),
            submit=True,
        )
        prompt_sent = bool(prompt_result.get("ok"))

    process_meta = {}
    if hasattr(terminal, "pane_pid"):
        try:
            from lib import runtime_session

            process_meta = runtime_session.process_metadata(terminal.pane_pid(new_pane_ref or terminal_ref))
        except Exception:
            process_meta = {}

    pending = {
        key: None
        for key in (
            "session_id",
            "runtime_session_id",
            "runtime_session_source",
            "runtime_session_confidence",
            "runtime_session_evidence",
            "runtime_session_env",
            "runtime_session_cwd",
            "runtime_session_created_at_ms",
            "runtime_session_updated_at_ms",
            "runtime_session_pid",
        )
    }
    updated = registry.upsert_agent({
        **record,
        **pending,
        **role_meta,
        **process_meta,
        "name": name,
        "fleet": fleet,
        "seat": name,
        "seat_ref": seat_ref,
        "runtime": plan["runtime"],
        "command": plan["command"],
        "cwd": plan["cwd"],
        "workdir": plan["cwd"],
        "aura_launch_id": launch_id,
        "previous_aura_launch_id": old.get("aura_launch_id"),
        "previous_runtime_session_id": old.get("runtime_session_id"),
        "restart_from_session_id": old.get("runtime_session_id"),
        "restart_id": restart_id,
        "restart_at": registry.now_iso(),
        "restart_count": int(record.get("restart_count") or 0) + 1,
        "terminal_ref": terminal_ref,
        "backend_ref": terminal_ref,
        "pane_ref": new_pane_ref,
        "status": "starting",
        "registered": True,
        "prompt_sent": prompt_sent or record.get("prompt_sent"),
    })

    cwd_choice = None
    try:
        from commands import spawn

        cwd_choice = spawn._resolve_codex_cwd_choice(
            runtime=plan["runtime"],
            resume_session=plan.get("resume_session_id"),
            terminal=terminal,
            target=new_pane_ref or terminal_ref,
            desired_cwd=plan["cwd"],
        )
        if cwd_choice and cwd_choice.get("detected") and cwd_choice.get("selected_path"):
            updated = registry.upsert_agent({
                **updated,
                "cwd_choice": cwd_choice,
            })
    except Exception as exc:
        cwd_choice = {"detected": False, "ok": False, "reason": "cwd-choice-error", "error": str(exc)}

    session_observation = {}
    try:
        from commands import spawn

        session_observation = spawn._observe_spawn_session(
            runtime=plan["runtime"],
            terminal=terminal,
            target=new_pane_ref or terminal_ref,
            seat=name,
            fleet=fleet,
            launch_id=launch_id,
            workdir=plan["cwd"],
            terminal_ref=terminal_ref,
            pane_ref=new_pane_ref,
            registered=updated,
            existing_session={},
            timeout=float(os.environ.get("AURA_RESTART_SESSION_OBSERVE_TIMEOUT", "0.5")),
        )
        if session_observation.get("runtime_session_id"):
            updated = registry.upsert_agent({**updated, **_session_fields(session_observation)})
            try:
                from lib import desks_sessions

                desks_sessions.append_identity_session(
                    updated.get("desks_identity_id") or record.get("desks_identity_id"),
                    session_observation.get("runtime_session_id"),
                )
            except Exception:
                pass
    except Exception as exc:
        session_observation = {"status": "error", "reason": "session-discovery-error", "error": str(exc)}

    new_pid = terminal.pane_pid(new_pane_ref or terminal_ref) if hasattr(terminal, "pane_pid") else None
    new = {
        "runtime_session_id": updated.get("runtime_session_id"),
        "pid": new_pid,
        "pane_ref": new_pane_ref,
        "terminal_ref": terminal_ref,
        "aura_launch_id": launch_id,
    }
    same_viewport = bool(new_pane_ref and new_pane_ref == old.get("pane_ref"))
    warnings = []
    if gate.get("warning"):
        warnings.append(gate["warning"])
    if not new.get("runtime_session_id"):
        warnings.append("session_observation_pending")
    if launch.get("fallback_recreated_viewport"):
        warnings.append("viewport_recreated_fallback")

    lifecycle_event = {}
    try:
        from lib import session_ledger

        lifecycle_event = session_ledger.append_record({
            "event": "seat_restart",
            "kind": "aura.seat.restarted",
            "restart_id": restart_id,
            "seat": name,
            "name": name,
            "fleet": fleet,
            "seat_ref": seat_ref,
            "runtime": plan["runtime"],
            "command": plan["command"],
            "cwd": plan["cwd"],
            "old_runtime_session_id": old.get("runtime_session_id"),
            "new_runtime_session_id": new.get("runtime_session_id"),
            "old_pid": old.get("pid"),
            "new_pid": new.get("pid"),
            "old_pane_ref": old.get("pane_ref"),
            "new_pane_ref": new.get("pane_ref"),
            "terminal_ref": terminal_ref,
            "same_viewport": same_viewport,
            "actor": "cli",
            "forced": bool(getattr(args, "force", False)),
            "aura_launch_id": launch_id,
            "previous_aura_launch_id": old.get("aura_launch_id"),
        })
        session_ledger.append_seat_event(
            event="seat_restarted",
            before=record,
            after=updated,
            evidence={
                "restart_id": restart_id,
                "old_runtime_session_id": old.get("runtime_session_id"),
                "new_runtime_session_id": new.get("runtime_session_id"),
                "old_pid": old.get("pid"),
                "new_pid": new.get("pid"),
                "old_pane_ref": old.get("pane_ref"),
                "new_pane_ref": new.get("pane_ref"),
                "same_viewport": same_viewport,
                "forced": bool(getattr(args, "force", False)),
                "session_observation": session_observation,
                "cwd_choice": cwd_choice,
            },
            source_command="aura seat restart",
            restart_id=restart_id,
            old_runtime_session_id=old.get("runtime_session_id"),
            new_runtime_session_id=new.get("runtime_session_id"),
            old_pid=old.get("pid"),
            new_pid=new.get("pid"),
            old_pane_ref=old.get("pane_ref"),
            new_pane_ref=new.get("pane_ref"),
            same_viewport=same_viewport,
        )
    except Exception:
        lifecycle_event = {}

    return {
        "ok": True,
        "schema": "aura.seat_restart.v1",
        "target": args.target,
        "seat_ref": seat_ref,
        "same_viewport": same_viewport,
        "old": old,
        "new": new,
        "seat_history_event_id": lifecycle_event.get("event_id") or restart_id,
        "restart_id": restart_id,
        "session_observation": session_observation,
        "cwd_choice": cwd_choice,
        "warnings": warnings,
    }


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


def _parse_set_pair(arg: str) -> tuple[str, str] | dict:
    if not arg or "=" not in arg:
        return {"ok": False, "error": "malformed-set-pair", "arg": arg}
    key, value = arg.split("=", 1)
    if not key:
        return {"ok": False, "error": "malformed-set-pair", "arg": arg}
    return key, value


def _tag(args, registry, terminal=None) -> dict:
    from lib.seat_schema import TAG_ALLOWLIST

    target = getattr(args, "target", None) or ""
    if not target or target.count(":") != 1 or target.startswith(":") or target.endswith(":"):
        return {"ok": False, "error": "empty-target",
                "detail": "target must be FLEET:SEAT"}

    record = registry.get_agent(target)
    if not record:
        return {"ok": False, "error": "no-such-seat",
                "detail": f"registry has no row for {target!r}"}

    set_pairs: dict[str, str] = {}
    for raw in getattr(args, "set", None) or []:
        parsed = _parse_set_pair(raw)
        if isinstance(parsed, dict):
            return parsed
        key, value = parsed
        if key not in TAG_ALLOWLIST:
            return {"ok": False, "error": f"key-not-in-allowlist:{key}",
                    "allowlist": sorted(TAG_ALLOWLIST)}
        set_pairs[key] = value

    unset_keys = list(getattr(args, "unset", None) or [])
    for key in unset_keys:
        if key not in TAG_ALLOWLIST:
            return {"ok": False, "error": f"key-not-in-allowlist:{key}",
                    "allowlist": sorted(TAG_ALLOWLIST)}

    keys_to_track = sorted(set(set_pairs.keys()) | set(unset_keys))
    before = {k: record.get(k) for k in keys_to_track}

    next_record = dict(record)
    for key, value in set_pairs.items():
        if value == "":
            next_record.pop(key, None)
        else:
            next_record[key] = value
    for key in unset_keys:
        next_record.pop(key, None)

    after = {k: next_record.get(k) for k in keys_to_track}
    changed_keys = [k for k in keys_to_track if before.get(k) != after.get(k)]

    fleet = next_record.get("fleet") or record.get("fleet")
    name = next_record.get("name") or next_record.get("seat") or record.get("name") or record.get("seat")
    if not fleet or not name:
        return {"ok": False, "error": "registry-row-missing-fleet-or-name",
                "detail": f"existing row for {target!r} lacks fleet/name fields"}

    # Direct read/write rather than upsert_agent, because upsert merges previous
    # keys back in via `{**previous, **record}` — that would defeat unset.
    data = registry.read_registry()
    key = registry._key(fleet, name)
    next_record["name"] = name
    next_record["seat"] = next_record.get("seat") or name
    next_record["fleet"] = fleet
    next_record["seat_ref"] = key
    next_record["last_seen"] = registry.now_iso()
    data[key] = next_record
    registry.write_registry(data)
    updated = next_record

    warnings: list[str] = []
    try:
        from lib import session_ledger

        session_ledger.append_seat_event(
            event="seat_metadata_tagged",
            before=record,
            after=updated,
            evidence={
                "source_command": "aura seat tag",
                "caller": os.environ.get("DESKS_CALLER", "cli"),
                "set_keys": sorted(set_pairs.keys()),
                "unset_keys": sorted(unset_keys),
                "changed_keys": changed_keys,
                "rehome": os.environ.get("DESKS_REHOME") == "true",
                "before": before,
                "after": after,
            },
            source_command="aura seat tag",
        )
    except Exception:
        warnings.append("ledger-append-failed")

    response = {
        "ok": True,
        "action": "tag",
        "target": target,
        "set": sorted(set_pairs.keys()),
        "unset": sorted(unset_keys),
        "changed": changed_keys,
        "record": updated,
    }
    if warnings:
        response["warnings"] = warnings
    return response


_ORPHAN_RUNTIME_CHOICES = {
    "claude-code", "claude", "hermes", "codex", "omx",
    "opencode", "openclaw", "shell", "command",
}


def _infer_orphan_runtime(pane_command: str | None, pane_argv: list[str] | None = None) -> str:
    cmd = (pane_command or "").lower()
    argv_str = " ".join(pane_argv or []).lower()
    if "codex" in argv_str or "codex" in cmd:
        return "codex"
    if "claude" in argv_str or "claude" in cmd:
        return "claude-code"
    if "hermes" in argv_str:
        return "hermes"
    if "omx" in argv_str:
        return "omx"
    if "openclaw" in argv_str:
        return "openclaw"
    if "opencode" in argv_str:
        return "opencode"
    if cmd in {"bash", "zsh", "sh", "fish", "dash"}:
        return "shell"
    if cmd == "node":
        # bare `node` with no detectable codex/claude argv → assume codex (most
        # common manual launch). Operators who care should pass --runtime.
        return "codex"
    return "command"


def _discover_orphan_pane(fleet: str, seat: str, panes: list[dict] | None = None) -> dict:
    if panes is None:
        panes = _list_tmux_panes()
    in_fleet = [p for p in panes if p.get("session") == fleet]
    matches = [p for p in in_fleet if p.get("window_name") == seat]
    if not matches:
        return {"ok": False, "error": "no-pane",
                "detail": f"no tmux pane found for fleet={fleet!r} seat={seat!r}"}
    if len(matches) > 1:
        return {
            "ok": False,
            "error": "ambiguous-pane",
            "detail": f"{len(matches)} windows named {seat!r} in {fleet!r}; pass --pane explicitly",
            "candidates": [
                {
                    "pane_ref": f"tmux:{p['session']}:{p['pane_id']}",
                    "window_index": p.get("window_index"),
                    "pane_pid": p.get("pane_pid"),
                }
                for p in matches
            ],
        }
    return {"ok": True, "pane": matches[0], "discovered_by": "scan"}


def _validate_explicit_orphan_pane(pane_ref: str, fleet: str) -> dict:
    target = _tmux_target(pane_ref)
    if not target.startswith("%"):
        return {"ok": False, "error": "not-a-fleet-pane",
                "detail": "--pane must be a tmux pane id ref like tmux:<fleet>:%<id>"}
    info = _run_tmux([
        "display-message", "-p", "-t", target,
        "#{session_name}\t#{window_index}\t#{window_name}\t#{pane_id}\t#{pane_pid}\t#{pane_current_command}\t#{pane_current_path}",
    ])
    if info.returncode != 0:
        return {"ok": False, "error": "pane-not-found",
                "detail": info.stderr.strip() or f"tmux pane not found: {pane_ref}"}
    parts = info.stdout.strip().split("\t")
    while len(parts) < 7:
        parts.append("")
    session, window_index, window_name, pane_id, pane_pid, pane_current_command, pane_current_path = parts[:7]
    if session != fleet:
        return {
            "ok": False,
            "error": "not-a-fleet-pane",
            "detail": f"--pane resolves to session {session!r}, expected {fleet!r}",
        }
    try:
        pid = int(pane_pid)
    except ValueError:
        pid = None
    pane = {
        "session": session,
        "window_index": window_index,
        "window_name": window_name,
        "pane_id": pane_id,
        "pane_pid": pid,
        "pane_current_command": pane_current_command,
        "pane_current_path": pane_current_path,
    }
    return {"ok": True, "pane": pane, "discovered_by": "explicit"}


def _register_orphan(args, registry, terminal=None, ledger=None) -> dict:
    target = getattr(args, "target", None) or ""
    if not target or target.count(":") != 1 or target.startswith(":") or target.endswith(":"):
        return {"ok": False, "error": "empty-target",
                "detail": "target must be FLEET:SEAT"}
    fleet, seat = target.split(":", 1)

    existing = registry.get_agent(target)
    if existing:
        return {"ok": False, "error": "already-registered",
                "detail": f"registry already has a row for {target!r}; cut or sweep first",
                "record": existing}

    explicit_pane = getattr(args, "pane", None)
    if explicit_pane:
        discovery = _validate_explicit_orphan_pane(explicit_pane, fleet)
    else:
        discovery = _discover_orphan_pane(fleet, seat)

    if not discovery.get("ok"):
        return {"ok": False, **discovery, "target": target}

    pane = discovery["pane"]
    pane_id = pane.get("pane_id")
    pane_command = pane.get("pane_current_command") or ""
    runtime_arg = getattr(args, "runtime", None)
    runtime_inferred = False
    if runtime_arg:
        runtime = runtime_arg
    else:
        runtime = _infer_orphan_runtime(pane_command)
        runtime_inferred = True

    cwd_override = getattr(args, "cwd", None)
    cwd = cwd_override or pane.get("pane_current_path") or ""

    now = registry.now_iso()
    record = {
        "name": seat,
        "seat": seat,
        "fleet": fleet,
        "runtime": runtime,
        "backend": "tmux",
        "backend_ref": f"{fleet}:{seat}",
        "terminal_ref": f"{fleet}:{seat}",
        "seat_ref": f"{fleet}:{seat}",
        "pane_ref": f"tmux:{fleet}:{pane_id}",
        "status": "unknown",
        "registered": True,
        "delivery_mode": "immediate",
        "kind": "terminal",
        "cwd": cwd,
        "workdir": cwd,
        "transport": "tmux",
        "created_at": now,
        "last_seen": now,
        "registered_via": "register-orphan",
        "registered_at": now,
        "registered_pane_pid": pane.get("pane_pid"),
        "registered_pane_command": pane_command,
        "runtime_session_id": None,
        "runtime_session_binding": "unbound",
        "runtime_session_bind_method": None,
        "aura_launch_id": None,
    }
    inserted = registry.upsert_agent(record)

    provenance = {
        "discovered_by": discovery.get("discovered_by"),
        "pane_ref": record["pane_ref"],
        "pane_pid": pane.get("pane_pid"),
        "pane_command": pane_command,
        "pane_cwd": pane.get("pane_current_path"),
        "runtime": runtime,
        "runtime_inferred": runtime_inferred,
        "registered_at": now,
    }

    try:
        from lib import session_ledger

        session_ledger.append_seat_event(
            event="seat_registered_orphan",
            before=None,
            after=inserted,
            evidence={
                "source_command": "aura seat register-orphan",
                "pane_ref": record["pane_ref"],
                "pane_pid": pane.get("pane_pid"),
                "pane_command": pane_command,
                "pane_cwd": pane.get("pane_current_path"),
                "discovered_by": discovery.get("discovered_by"),
                "runtime": runtime,
                "runtime_inferred": runtime_inferred,
            },
            source_command="aura seat register-orphan",
        )
    except Exception:
        # ledger append failures should not block registration; the seat is in.
        pass

    return {
        "ok": True,
        "action": "register-orphan",
        "target": target,
        "record": inserted,
        "provenance": provenance,
    }


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
            before = registry.get_agent(row["seat"], fleet=row.get("fleet"))
            try:
                from lib import session_ledger

                session_ledger.append_seat_event(
                    event="seat_swept_removed",
                    before=before or row,
                    evidence=row,
                    source_command="aura seat sweep",
                )
            except Exception:
                pass
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
    if action == "register-orphan":
        return _register_orphan(args, registry)
    if action == "tag":
        return _tag(args, registry)
    if action == "inject-flex":
        from lib import terminal

        return _inject_flex(args, registry, terminal)
    if action == "restart":
        from lib import terminal

        return _restart(args, registry, terminal)
    if action == "adopt":
        try:
            metadata = _load_role_metadata(getattr(args, "role_home", None), getattr(args, "manifest", None))
        except Exception as exc:
            return {"ok": False, "error": f"failed to load role metadata: {exc}"}
        metadata = {key: value for key, value in metadata.items() if value}
        if not metadata:
            return {"ok": False, "error": "adopt requires --manifest or --role-home"}
        existing = registry.get_agent(args.target)
        if not existing:
            return {"ok": False, "error": f"agent not found: {args.target}"}
        result = registry.rehome_agent(
            args.target,
            metadata=metadata,
            alias_old=False,
        )
        if result.get("ok"):
            try:
                from lib import session_ledger

                session_ledger.append_seat_event(
                    event="seat_role_adopted",
                    before=existing,
                    after=result.get("record"),
                    evidence={
                        "source": result.get("source"),
                        "target": result.get("target"),
                        "metadata_keys": sorted(metadata.keys()),
                    },
                    source_command="aura seat adopt",
                    source_ref=result.get("source"),
                    target_ref=result.get("target"),
                )
            except Exception:
                pass
        return result
    if action == "rehome":
        try:
            metadata = _load_role_metadata(getattr(args, "role_home", None), getattr(args, "manifest", None))
        except Exception as exc:
            return {"ok": False, "error": f"failed to load role metadata: {exc}"}
        metadata = {key: value for key, value in metadata.items() if value}
        if getattr(args, "index", None) is not None and not getattr(args, "move_terminal", False):
            return {"ok": False, "error": "--index requires --move-terminal"}
        existing = registry.get_agent(args.source)
        if getattr(args, "move_terminal", False):
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
        result = registry.rehome_agent(
            args.source,
            new_name=getattr(args, "name", None),
            new_fleet=getattr(args, "fleet", None),
            metadata=metadata,
            alias_old=not getattr(args, "no_alias_old", False),
        )
        if result.get("ok"):
            try:
                from lib import session_ledger

                after = result.get("record")
                event = "seat_role_adopted" if metadata and result.get("source") == result.get("target") else "seat_rehomed"
                session_ledger.append_seat_event(
                    event=event,
                    before=existing,
                    after=after,
                    evidence={
                        "source": result.get("source"),
                        "target": result.get("target"),
                        "move_terminal": bool(getattr(args, "move_terminal", False)),
                        "metadata_keys": sorted(metadata.keys()),
                    },
                    source_command="aura seat rehome",
                    source_ref=result.get("source"),
                    target_ref=result.get("target"),
                )
                if result.get("alias"):
                    session_ledger.append_seat_event(
                        event="seat_alias_created",
                        before=existing,
                        after=after,
                        evidence=result.get("alias"),
                        source_command="aura seat rehome",
                        source_ref=result["alias"].get("source"),
                        target_ref=result["alias"].get("target"),
                    )
            except Exception:
                pass
        return result
    return {"ok": False, "error": f"unknown seat action: {action}"}
