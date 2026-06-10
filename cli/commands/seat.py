"""Manage Aura seat identity and optional terminal placement."""

from __future__ import annotations

import argparse
import re
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

FLEX_PACKET_MARKER = "[FLEX PROJECT RETRIEVAL]"


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
        "#{session_name}\t#{window_index}\t#{window_name}\t#{pane_index}\t#{pane_id}\t#{pane_pid}\t#{pane_current_command}\t#{pane_current_path}",
    ])
    if result.returncode != 0:
        return []
    panes = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        # Pad with empty strings for backwards compatibility with older tmux outputs.
        while len(parts) < 8:
            parts.append("")
        session, window_index, window_name, pane_index, pane_id, pane_pid, pane_current_command, pane_current_path = parts[:8]
        try:
            pid = int(pane_pid)
        except ValueError:
            pid = None
        panes.append({
            "session": session,
            "window_index": window_index,
            "window_name": window_name,
            "pane_index": pane_index,
            "pane_id": pane_id,
            "pane_pid": pid,
            "pane_current_command": pane_current_command,
            "pane_current_path": pane_current_path,
        })
    return panes


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
    matches = [
        pane for pane in _list_tmux_panes()
        if pane.get("session") == fleet and pane.get("window_name") == name
    ]
    if not matches:
        return None
    if len(matches) == 1 and matches[0].get("pane_id") == source_pane_id:
        return None
    return {
        "ok": False,
        "error": f"target tmux window already exists: {fleet}:{name}",
        "reason": "target-window-exists",
        "target": f"{fleet}:{name}",
        "existing": matches[0] if len(matches) == 1 else None,
        "matches": matches,
        "source_pane_id": source_pane_id,
        "hint": "move or rename the existing window first, or choose an explicit free window slot",
    }


def _fleet_windows_by_exact_name(fleet: str) -> dict[str, list[dict]]:
    windows: dict[str, dict] = {}
    for pane in _list_tmux_panes():
        if pane.get("session") != fleet:
            continue
        window_index = pane.get("window_index")
        if window_index is None or window_index in windows:
            continue
        windows[str(window_index)] = pane
    grouped: dict[str, list[dict]] = {}
    for pane in windows.values():
        grouped.setdefault(str(pane.get("window_name") or ""), []).append(pane)
    return grouped


def _order(args) -> dict:
    fleet = getattr(args, "fleet", None)
    seats = list(getattr(args, "seats", None) or [])
    if not fleet:
        return {"ok": False, "error": "fleet-required"}
    if not seats:
        return {"ok": False, "error": "seats-required"}

    grouped = _fleet_windows_by_exact_name(fleet)
    selected = []
    missing = []
    ambiguous = []
    for seat in seats:
        matches = grouped.get(seat) or []
        if not matches:
            missing.append(seat)
            continue
        if len(matches) > 1:
            ambiguous.append({
                "seat": seat,
                "matches": [
                    {
                        "window_index": pane.get("window_index"),
                        "pane_id": pane.get("pane_id"),
                    }
                    for pane in matches
                ],
            })
            continue
        selected.append(matches[0])
    if missing or ambiguous:
        return {
            "ok": False,
            "error": "fleet-order-unresolved",
            "fleet": fleet,
            "missing": missing,
            "ambiguous": ambiguous,
            "detail": "all requested seats must match exactly one tmux window name",
        }

    slots = sorted(int(pane["window_index"]) for pane in selected)
    plan = [
        {
            "seat": seat,
            "from_index": str(selected[index].get("window_index")),
            "to_index": str(slots[index]),
            "pane_id": selected[index].get("pane_id"),
        }
        for index, seat in enumerate(seats)
    ]
    if getattr(args, "dry_run", False):
        return {
            "ok": True,
            "schema": "aura.seat_order.v1",
            "dry_run": True,
            "fleet": fleet,
            "plan": plan,
        }

    swaps = []
    for desired in plan:
        grouped = _fleet_windows_by_exact_name(fleet)
        current_matches = grouped.get(desired["seat"]) or []
        if len(current_matches) != 1:
            return {
                "ok": False,
                "error": "fleet-order-changed-during-apply",
                "fleet": fleet,
                "seat": desired["seat"],
            }
        current_index = str(current_matches[0].get("window_index"))
        target_index = str(desired["to_index"])
        if current_index == target_index:
            continue
        swap = _run_tmux(["swap-window", "-s", f"{fleet}:{current_index}", "-t", f"{fleet}:{target_index}"])
        if swap.returncode != 0:
            return {"ok": False, "error": swap.stderr.strip() or "tmux swap-window failed", "fleet": fleet, "plan": plan, "swaps": swaps}
        swaps.append({"seat": desired["seat"], "from_index": current_index, "to_index": target_index})
    return {
        "ok": True,
        "schema": "aura.seat_order.v1",
        "dry_run": False,
        "fleet": fleet,
        "plan": plan,
        "swaps": swaps,
        "swapped_count": len(swaps),
    }


def _rename_terminal_exact(record: dict, *, fleet: str, name: str) -> dict:
    """Rename exactly the registered live seat window.

    A routine seat rename is a topology label change, not repair. It must not
    rediscover a pane from runtime/session evidence and must not move windows
    between fleets. Repair/adopt/bind commands are the explicit escape hatches.
    """
    source = record.get("pane_ref")
    if not source:
        return {
            "ok": False,
            "error": "rename-source-pane-missing",
            "detail": "seat rename requires an exact registered pane_ref",
        }

    source_target = _tmux_target(source)
    info = _run_tmux([
        "display-message",
        "-p",
        "-t",
        source_target,
        "#{session_name}:#{window_index}:#{window_name}:#{pane_id}",
    ])
    if info.returncode != 0:
        return {
            "ok": False,
            "error": "rename-source-pane-missing",
            "detail": info.stderr.strip() or f"tmux target not found: {source}",
            "pane_ref": source,
        }

    current_fleet, current_index, current_name, pane_id = info.stdout.strip().split(":", 3)
    session = _run_tmux(["has-session", "-t", fleet])
    if session.returncode != 0:
        return {"ok": False, "error": f"tmux session not found: {fleet}"}
    if current_fleet != fleet:
        return {
            "ok": False,
            "error": "rename-source-fleet-mismatch",
            "reason": "source-fleet-mismatch",
            "expected_fleet": fleet,
            "actual_fleet": current_fleet,
            "pane_ref": source,
            "pane_id": pane_id,
            "window_name": current_name,
        }

    collision = _destination_collision(fleet=fleet, name=name, source_pane_id=pane_id)
    if collision:
        return collision

    rename = _run_tmux(["rename-window", "-t", pane_id, name])
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
    if final_fleet != fleet or final_pane != pane_id or final_name != name:
        return {
            "ok": False,
            "error": "rename-final-verification-failed",
            "expected": {"fleet": fleet, "name": name, "pane_id": pane_id},
            "actual": {"fleet": final_fleet, "name": final_name, "pane_id": final_pane},
        }
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
    if workdir:
        return spawn._resolve_launch_flex_project(Path(str(workdir)))
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

    now = delivery.now_iso()
    updated = registry.upsert_agent({
        **record,
        "flex_project_manifest": str(manifest),
        "flex_project_root": str(root),
    })
    updated["flex_project_packet_delivered_at"] = now if sent else record.get("flex_project_packet_delivered_at")
    updated["flex_project_packet_source"] = source
    updated["flex_project_packet_manifest"] = str(manifest)
    updated["flex_project_packet_session_key"] = _packet_session_key(record)
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
    meta = {
        key: record.get(key)
        for key in (
            "identity_provider",
            "identity_id",
            "identity_label",
            "identity_bound_at",
            "identity_bind_source",
            "identity_bind_confidence",
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
    fresh_session = bool(getattr(args, "fresh_session", False))
    should_rebuild_command = fresh_session and runtime != "command"
    if should_rebuild_command or not command:
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
            if should_rebuild_command:
                return {
                    "ok": False,
                    "phase": "build_plan",
                    "error": f"cannot reconstruct fresh launch command: {exc}",
                }
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

    resume_session_id = None
    if not fresh_session:
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

    if runtime == "claude-code" and command and "--session-id" in str(command):
        # A replayed --session-id is never valid: a fresh start with a used id
        # refuses ("already in use"), and resume rides claude-r, which never
        # carries the flag. Strip it; a fresh session gets its id from the hook.
        command = re.sub(r"\s--session-id\s+\S+", "", str(command))

    prompt = getattr(args, "prompt", None) or role_prompt
    return {
        "ok": True,
        "runtime": runtime,
        "command": command,
        "cwd": str(cwd_path),
        "role_meta": role_meta,
        "prompt": prompt,
        "resume_session_id": resume_session_id,
        "fresh_session": fresh_session,
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


def _restart_record_is_package_agent(record: dict) -> bool:
    if record.get("agent_package_id") or record.get("package_agent_id"):
        return True
    for key in (
        "agent_package_root",
        "package_root",
        "codex_package_root",
        "runtime_home",
        "runtime_capsule_root",
        "codex_box_root",
    ):
        value = record.get(key)
        if not value:
            continue
        try:
            root = Path(str(value)).expanduser()
            manifest = root / "manifest.json"
        except (TypeError, ValueError):
            continue
        if manifest.exists():
            return True
    return False


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
        "seat_instance_id": record.get("seat_instance_id"),
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
    seat_instance_id = registry.new_seat_instance_id()
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
    role_meta = dict(plan.get("role_meta") or {})
    carried_identity = {
        key: record.get(key)
        for key in (
            "identity_provider",
            "identity_id",
            "identity_label",
            "identity_bound_at",
            "identity_bind_source",
            "identity_bind_confidence",
        )
        if record.get(key) is not None
    }
    identity_carried_forward = bool(carried_identity)
    if identity_carried_forward:
        role_meta.update(carried_identity)
    if role_meta:
        if role_meta.get("identity_provider"):
            launch_env["AURA_IDENTITY_PROVIDER"] = str(role_meta["identity_provider"])
        if role_meta.get("identity_id"):
            launch_env["AURA_IDENTITY_ID"] = str(role_meta["identity_id"])
        if role_meta.get("identity_label"):
            launch_env["AURA_IDENTITY_LABEL"] = str(role_meta["identity_label"])
    if role_meta.get("flex_project_manifest"):
        launch_env["FLEX_PROJECT_MANIFEST"] = role_meta["flex_project_manifest"]
    if role_meta.get("flex_project_root"):
        launch_env["FLEX_PROJECT_ROOT"] = role_meta["flex_project_root"]
    try:
        from lib import runtime_capsules

        boxed_env = runtime_capsules.boxed_launch_env_from_record(record, plan["cwd"])
        launch_env.update(boxed_env)
    except Exception as exc:
        if record.get("codex_box_root") or record.get("omx_box_root"):
            return {
                "ok": False,
                "schema": "aura.seat_restart.v1",
                "phase": "build_plan",
                "target": args.target,
                "seat_ref": seat_ref,
                "error": f"failed to restore boxed runtime capsule environment: {exc}",
            }

    unset_env = [
        "NO_COLOR",
        "AURA_RUNTIME_SESSION_ID",
        "AURA_SESSION_ID",
        "CODEX_THREAD_ID",
        "CODEX_CI",
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
            "pane_ref": None,
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
    if plan.get("prompt") and hasattr(terminal, "send_text"):
        from commands import spawn

        terminal.send_text(
            new_pane_ref or terminal_ref,
            spawn._augment_runtime_prompt(plan["runtime"], plan["prompt"], fleet=fleet, seat=name, launch_id=launch_id),
            submit=True,
        )

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
        "seat_instance_id": seat_instance_id,
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
    })
    package_agent = _restart_record_is_package_agent(updated)

    capsule_launch = {}
    if not package_agent:
        try:
            from lib import runtime_capsules

            capsule_launch = runtime_capsules.write_aura_launch(updated, env_roots=launch_env)
            if capsule_launch.get("ok"):
                updated = registry.upsert_agent({
                    **updated,
                    "runtime_capsule_ref": capsule_launch.get("capsule_root"),
                    "runtime_capsule_launch": capsule_launch.get("path"),
                })
        except Exception as exc:
            capsule_launch = {"ok": False, "reason": "capsule-launch-write-failed", "error": str(exc)}

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
            if not package_agent:
                try:
                    from lib import runtime_capsules

                    capsule_session = runtime_capsules.write_runtime_session(updated)
                    if capsule_session.get("ok"):
                        updated = registry.upsert_agent({
                            **updated,
                            "runtime_capsule_ref": capsule_session.get("capsule_root"),
                            "runtime_capsule_session": capsule_session.get("path"),
                        })
                except Exception:
                    pass
    except Exception as exc:
        session_observation = {"status": "error", "reason": "session-discovery-error", "error": str(exc)}

    new_pid = terminal.pane_pid(new_pane_ref or terminal_ref) if hasattr(terminal, "pane_pid") else None
    new = {
        "runtime_session_id": updated.get("runtime_session_id"),
        "seat_instance_id": updated.get("seat_instance_id"),
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
            "old_seat_instance_id": old.get("seat_instance_id"),
            "new_seat_instance_id": new.get("seat_instance_id"),
            "identity_carried_forward": identity_carried_forward,
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
                "old_seat_instance_id": old.get("seat_instance_id"),
                "new_seat_instance_id": new.get("seat_instance_id"),
                "identity_carried_forward": identity_carried_forward,
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
            old_seat_instance_id=old.get("seat_instance_id"),
            new_seat_instance_id=new.get("seat_instance_id"),
            identity_carried_forward=identity_carried_forward,
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
        "runtime_capsule_ref": updated.get("runtime_capsule_ref"),
        "runtime_capsule_launch": updated.get("runtime_capsule_launch"),
        "runtime_capsule_session": updated.get("runtime_capsule_session"),
        "warnings": warnings,
    }


def _rollover(args, registry, terminal) -> dict:
    before = registry.get_agent(args.target)
    if not before:
        return {
            "ok": False,
            "schema": "aura.seat_rollover.v1",
            "phase": "resolve_failed",
            "target": args.target,
            "error": "seat not found",
        }

    rollover_id = f"aura-seat-rollover-{uuid.uuid4().hex[:16]}"
    restart_args = argparse.Namespace(**vars(args))
    restart_args.fresh_session = True
    restart_result = _restart(restart_args, registry, terminal)
    reason = getattr(args, "reason", None) or "session rollover"

    if not restart_result.get("ok"):
        return {
            **restart_result,
            "schema": "aura.seat_rollover.v1",
            "rollover_id": rollover_id,
            "reason": reason,
            "restart_error_schema": restart_result.get("schema"),
        }

    if restart_result.get("dry_run"):
        return {
            **restart_result,
            "schema": "aura.seat_rollover.v1",
            "rollover_id": rollover_id,
            "reason": reason,
            "restart_schema": restart_result.get("schema"),
        }

    seat_name = before.get("name") or before.get("seat")
    canonical_ref = registry.seat_ref(before.get("fleet"), seat_name)
    after = registry.get_agent(args.target) or registry.get_agent(canonical_ref) or {}
    updated_after = after
    if after:
        updated_after = registry.upsert_agent({
            **after,
            "last_rollover_id": rollover_id,
            "last_rollover_at": registry.now_iso(),
            "last_rollover_reason": reason,
            "rollover_count": int(before.get("rollover_count") or 0) + 1,
        })

    rollover_event = {}
    rollover_warnings = list(restart_result.get("warnings") or [])
    try:
        from lib import session_ledger

        rollover_event = session_ledger.append_record({
            "event": "seat_rollover",
            "kind": "aura.seat.rollover",
            "rollover_id": rollover_id,
            "restart_id": restart_result.get("restart_id"),
            "target": args.target,
            "seat_ref": restart_result.get("seat_ref"),
            "reason": reason,
            "old_runtime_session_id": (restart_result.get("old") or {}).get("runtime_session_id"),
            "new_runtime_session_id": (restart_result.get("new") or {}).get("runtime_session_id"),
            "old_seat_instance_id": (restart_result.get("old") or {}).get("seat_instance_id"),
            "new_seat_instance_id": (restart_result.get("new") or {}).get("seat_instance_id"),
            "old_pane_ref": (restart_result.get("old") or {}).get("pane_ref"),
            "new_pane_ref": (restart_result.get("new") or {}).get("pane_ref"),
            "actor": "cli",
            "forced": bool(getattr(args, "force", False)),
        })
        session_ledger.append_seat_event(
            event="seat_rollover",
            before=before,
            after=updated_after or after,
            evidence={
                "rollover_id": rollover_id,
                "restart_id": restart_result.get("restart_id"),
                "reason": reason,
                "old": restart_result.get("old"),
                "new": restart_result.get("new"),
                "fresh_session": True,
                "session_observation": restart_result.get("session_observation"),
            },
            source_command="aura seat rollover",
            rollover_id=rollover_id,
            restart_id=restart_result.get("restart_id"),
            old_runtime_session_id=(restart_result.get("old") or {}).get("runtime_session_id"),
            new_runtime_session_id=(restart_result.get("new") or {}).get("runtime_session_id"),
        )
    except Exception as exc:
        rollover_event = {}
        rollover_warnings.append(f"rollover-ledger-write-failed: {exc}")

    return {
        "ok": True,
        "schema": "aura.seat_rollover.v1",
        "target": args.target,
        "seat_ref": restart_result.get("seat_ref"),
        "rollover_id": rollover_id,
        "reason": reason,
        "old": restart_result.get("old"),
        "new": restart_result.get("new"),
        "restart_id": restart_result.get("restart_id"),
        "seat_history_event_id": rollover_event.get("event_id") or rollover_id,
        "restart_event_id": restart_result.get("seat_history_event_id"),
        "session_observation": restart_result.get("session_observation"),
        "runtime_capsule_ref": restart_result.get("runtime_capsule_ref"),
        "runtime_capsule_launch": restart_result.get("runtime_capsule_launch"),
        "runtime_capsule_session": restart_result.get("runtime_capsule_session"),
        "warnings": rollover_warnings,
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


ADOPTION_RESET_FIELDS = {
    # A reused fleet:seat address is a new live incarnation unless an operator
    # explicitly binds it. Do not inherit identity/session continuity from a
    # stale current projection at the same routing address.
    "identity_provider": None,
    "identity_id": None,
    "identity_label": None,
    "identity_bound_at": None,
    "identity_bind_source": None,
    "identity_bind_confidence": None,
    "runtime_session_id": None,
    "session_id": None,
    "source_session_id": None,
    "runtime_session_binding": "unbound",
    "runtime_session_bind_method": None,
    "runtime_session_bind_source": None,
    "runtime_session_confidence": None,
    "runtime_session_source": None,
    "runtime_session_evidence": None,
    "runtime_session_pid": None,
    "runtime_session_mode": None,
    "isolation": None,
}


ADOPTION_SESSION_RESET_KEYS = {
    "runtime_session_id",
    "session_id",
    "source_session_id",
    "runtime_session_binding",
    "runtime_session_bind_method",
    "runtime_session_bind_source",
    "runtime_session_confidence",
    "runtime_session_source",
    "runtime_session_evidence",
    "runtime_session_pid",
    "runtime_session_mode",
    "isolation",
}


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

    expected_instance_id = getattr(args, "expect_seat_instance_id", None)
    current_instance_id = record.get("seat_instance_id")
    if expected_instance_id and current_instance_id != expected_instance_id:
        return {
            "ok": False,
            "error": "seat-instance-id-mismatch",
            "target": target,
            "expected_seat_instance_id": expected_instance_id,
            "actual_seat_instance_id": current_instance_id,
        }

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

    next_record["name"] = name
    next_record["seat"] = next_record.get("seat") or name
    next_record["fleet"] = fleet
    next_record["last_seen"] = registry.now_iso()
    updated = registry.replace_agent_record(next_record)

    warnings: list[str] = []
    try:
        from lib import session_ledger

        session_ledger.append_seat_event(
            event="seat_metadata_tagged",
            before=record,
            after=updated,
            evidence={
                "source_command": "aura seat tag",
                "caller": "cli",
                "set_keys": sorted(set_pairs.keys()),
                "unset_keys": sorted(unset_keys),
                "changed_keys": changed_keys,
                "expected_seat_instance_id": expected_instance_id,
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


def _infer_adoption_runtime(pane_command: str | None, pane_argv: list[str] | None = None) -> str:
    cmd = (pane_command or "").lower()
    argv_str = " ".join(pane_argv or []).lower()
    if "codex" in argv_str or "codex" in cmd:
        return "codex"
    if "claude" in argv_str or "claude" in cmd:
        return "claude-code"
    if "hermes" in argv_str:
        return "hermes"
    if cmd in {"bash", "zsh", "sh", "fish", "dash"}:
        return "shell"
    if cmd == "node":
        # bare `node` with no detectable codex/claude argv → assume codex (most
        # common manual launch). Operators who care should pass --runtime.
        return "codex"
    return "command"


def _validate_explicit_adoption_pane(pane_ref: str, fleet: str) -> dict:
    target = _tmux_target(pane_ref)
    declared_fleet = None
    if str(pane_ref).startswith("tmux:"):
        value = str(pane_ref)[len("tmux:"):]
        if ":" in value:
            declared_fleet, subject = value.split(":", 1)
            if subject.startswith("%"):
                target = subject
    if declared_fleet and declared_fleet != fleet:
        return {
            "ok": False,
            "error": "not-a-fleet-pane",
            "detail": f"--pane declares session {declared_fleet!r}, expected {fleet!r}",
        }
    if not target.startswith("%"):
        return {"ok": False, "error": "not-a-fleet-pane",
                "detail": "--pane must be a tmux pane id ref like tmux:<fleet>:%<id>"}
    info = _run_tmux([
        "display-message", "-p", "-t", target,
        "#{session_name}\t#{window_index}\t#{window_name}\t#{pane_index}\t#{pane_id}\t#{pane_pid}\t#{pane_current_command}\t#{pane_current_path}",
    ])
    if info.returncode != 0:
        return {"ok": False, "error": "pane-not-found",
                "detail": info.stderr.strip() or f"tmux pane not found: {pane_ref}"}
    parts = info.stdout.strip().split("\t")
    while len(parts) < 8:
        parts.append("")
    session, window_index, window_name, pane_index, pane_id, pane_pid, pane_current_command, pane_current_path = parts[:8]
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
        "pane_index": pane_index,
        "pane_id": pane_id,
        "pane_pid": pid,
        "pane_current_command": pane_current_command,
        "pane_current_path": pane_current_path,
    }
    return {"ok": True, "pane": pane, "discovered_by": "explicit"}


def _normalize_adoption_target(target: str) -> tuple[str | None, str | None, dict | None]:
    if not target or target.count(":") != 1 or target.startswith(":") or target.endswith(":"):
        return None, None, {
            "ok": False,
            "error": "empty-target",
            "detail": "target must be FLEET:SEAT",
        }
    fleet, seat = target.split(":", 1)
    return fleet, seat, None


def _runtime_session_fields(runtime: str, pane: dict, seat: str) -> dict:
    try:
        from lib import runtime_session

        discovered = runtime_session.discover_from_pane_pid(
            runtime,
            pane.get("pane_pid"),
            seat_name=seat,
            launch_id=None,
        )
        if not discovered:
            return {}
        return runtime_session.mark_binding(discovered)
    except Exception:
        return {}


def _rename_adopted_window(*, fleet: str, seat: str, pane: dict) -> dict:
    pane_id = pane.get("pane_id")
    if not pane_id:
        return {"ok": False, "error": "missing-pane-id"}
    collision = _destination_collision(fleet=fleet, name=seat, source_pane_id=pane_id)
    if collision:
        return collision
    rename = _run_tmux(["rename-window", "-t", pane_id, seat])
    if rename.returncode != 0:
        return {"ok": False, "error": rename.stderr.strip() or "tmux rename-window failed"}
    return {
        "ok": True,
        "terminal_ref": f"{fleet}:{seat}",
        "backend_ref": f"{fleet}:{seat}",
        "renamed_window": True,
    }


def _adopt_pane_as_seat(
    *,
    target: str,
    pane: dict,
    registry,
    runtime_arg: str | None = None,
    cwd_arg: str | None = None,
    discovered_by: str | None = None,
    source_command: str = "aura seat adopt",
    registered_via: str = "adopt",
    rename_window: bool = False,
    adoption_source: str | None = None,
    identity_provider: str | None = None,
    identity_id: str | None = None,
    identity_label: str | None = None,
) -> dict:
    fleet, seat, error = _normalize_adoption_target(target)
    if error:
        return error

    existing = registry.get_agent(target)
    if existing:
        return {
            "ok": False,
            "error": "already-registered",
            "detail": f"registry already has a row for {target!r}; cut or sweep first",
            "record": existing,
        }

    if pane.get("session") != fleet:
        return {
            "ok": False,
            "error": "not-a-fleet-pane",
            "detail": f"pane belongs to session {pane.get('session')!r}, expected {fleet!r}",
            "target": target,
        }

    pane_id = pane.get("pane_id")
    pane_command = pane.get("pane_current_command") or pane.get("command") or ""
    runtime_inferred = False
    if runtime_arg:
        runtime = runtime_arg
    else:
        runtime = _infer_adoption_runtime(pane_command)
        runtime_inferred = True

    if cwd_arg == "auto":
        cwd = pane.get("pane_current_path") or pane.get("cwd") or ""
    else:
        cwd = cwd_arg or pane.get("pane_current_path") or pane.get("cwd") or ""

    pane_ref = f"tmux:{fleet}:{pane_id}"
    terminal_ref = pane_ref
    backend_ref = pane_ref
    rename_result = None
    if rename_window:
        rename_result = _rename_adopted_window(fleet=fleet, seat=seat, pane=pane)
        if not rename_result.get("ok"):
            return {"target": target, **rename_result}
        terminal_ref = rename_result["terminal_ref"]
        backend_ref = rename_result["backend_ref"]

    now = registry.now_iso()
    session_fields = _runtime_session_fields(runtime, pane, seat)
    bound = bool(session_fields.get("runtime_session_binding") == "bound" and session_fields.get("runtime_session_id"))
    record = {
        "name": seat,
        "seat": seat,
        "fleet": fleet,
        "runtime": runtime,
        "backend": "tmux",
        "backend_ref": backend_ref,
        "terminal_ref": terminal_ref,
        "seat_ref": f"{fleet}:{seat}",
        "pane_ref": pane_ref,
        "status": "unknown",
        "registered": True,
        "delivery_mode": "immediate",
        "kind": "terminal",
        "cwd": cwd,
        "workdir": cwd,
        "transport": "tmux",
        "created_at": now,
        "last_seen": now,
        "registered_via": registered_via,
        "registered_at": now,
        "registered_pane_pid": pane.get("pane_pid"),
        "registered_pane_command": pane_command,
        "runtime_session_id": None,
        "runtime_session_binding": "unbound",
        "runtime_session_bind_method": None,
        "aura_launch_id": None,
        "adoption_id": f"adopt_{uuid.uuid4().hex[:12]}",
        "adoption_source": adoption_source,
        "seat_instance_id": registry.new_seat_instance_id(),
        **session_fields,
    }
    if not bound:
        record["runtime_session_id"] = None
        record["session_id"] = None
        record["runtime_session_binding"] = "unbound"
    if identity_provider and identity_id:
        record.update({
            "identity_provider": identity_provider,
            "identity_id": identity_id,
            "identity_label": identity_label,
            "identity_bound_at": now,
            "identity_bind_source": source_command,
            "identity_bind_confidence": "explicit",
        })

    inserted = registry.upsert_agent(record)
    try:
        data = registry.read_registry()
        key = registry._key(fleet, seat)
        stored = dict(data.get(key, inserted))
        stored.update(record)
        for reset_key, reset_value in ADOPTION_RESET_FIELDS.items():
            if reset_key in {"identity_provider", "identity_id", "identity_label"} and identity_provider and identity_id:
                continue
            if bound and reset_key in ADOPTION_SESSION_RESET_KEYS:
                continue
            if reset_value is None:
                stored.pop(reset_key, None)
            else:
                stored[reset_key] = reset_value
        if not bound:
            stored["runtime_session_id"] = None
            stored.pop("session_id", None)
            stored["runtime_session_binding"] = "unbound"
            stored["runtime_session_bind_method"] = None
        if identity_provider and identity_id:
            stored.update({
                "identity_provider": identity_provider,
                "identity_id": identity_id,
                "identity_label": identity_label,
                "identity_bound_at": now,
                "identity_bind_source": source_command,
                "identity_bind_confidence": "explicit",
            })
        inserted = registry.replace_agent_record(stored)
    except Exception:
        pass

    provenance = {
        "discovered_by": discovered_by,
        "pane_ref": record["pane_ref"],
        "pane_pid": pane.get("pane_pid"),
        "pane_command": pane_command,
        "pane_cwd": pane.get("pane_current_path") or pane.get("cwd"),
        "runtime": runtime,
        "runtime_inferred": runtime_inferred,
        "registered_at": now,
        "adoption_source": adoption_source,
        "rename_window": bool(rename_window),
    }

    try:
        from lib import session_ledger

        session_ledger.append_seat_event(
            event="seat_adopted",
            before=None,
            after=inserted,
            evidence={
                "source_command": source_command,
                "pane_ref": record["pane_ref"],
                "pane_pid": pane.get("pane_pid"),
                "pane_command": pane_command,
                "pane_cwd": pane.get("pane_current_path") or pane.get("cwd"),
                "discovered_by": discovered_by,
                "runtime": runtime,
                "runtime_inferred": runtime_inferred,
                "runtime_session_binding": inserted.get("runtime_session_binding"),
                "adoption_source": adoption_source,
                "rename_window": bool(rename_window),
            },
            source_command=source_command,
        )
    except Exception:
        pass

    response = {
        "ok": True,
        "action": "adopt",
        "target": target,
        "record": inserted,
        "provenance": provenance,
    }
    response.update({
        "pane_ref": inserted.get("pane_ref"),
        "seat_instance_id": inserted.get("seat_instance_id"),
        "managed_state": f"adopted_{'bound' if inserted.get('runtime_session_binding') == 'bound' else 'unbound'}",
        "runtime": inserted.get("runtime"),
        "cwd": inserted.get("cwd"),
        "runtime_session_binding": inserted.get("runtime_session_binding"),
        "runtime_session_id": inserted.get("runtime_session_id"),
    })
    if inserted.get("runtime_session_binding") != "bound" and inserted.get("runtime") != "shell":
        response["next_command"] = f"aura sessions bind-current --target {target} --runtime {runtime}"
    if rename_result:
        response["rename_window"] = rename_result
    return response


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
            after = {
                **(before or row),
                "status": "swept_removed",
                "terminal_state": "terminal",
                "restore_suppressed": True,
                "swept_removed_at": registry.now_iso(),
                "sweep_reason": row.get("reason"),
            }
            try:
                from lib import session_ledger

                session_ledger.append_seat_event(
                    event="seat_swept_removed",
                    before=before or row,
                    after=after,
                    evidence=row,
                    source_command="aura seat sweep",
                )
            except Exception:
                pass
            if registry.remove_agent(row["seat"], fleet=row.get("fleet")):
                removed.append(row["seat_ref"])
                try:
                    from lib import diagnostic_cache

                    diagnostic_cache.invalidate(
                        row["seat_ref"],
                        reason="seat-swept-removed",
                        source_command="aura seat sweep",
                        evidence={"sweep_reason": row.get("reason")},
                    )
                except Exception:
                    pass

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


def _audit(args, registry, terminal) -> dict:
    include_hidden = bool(getattr(args, "include_hidden", False))
    agents = registry.list_agents(getattr(args, "fleet", None), include_hidden=include_hidden)
    rows = []
    risk_counts: dict[str, int] = {}
    for agent in agents:
        fleet = agent.get("fleet")
        if fleet and hasattr(terminal, "configure_session"):
            terminal.configure_session(fleet)
        targets = _seat_targets(agent)
        alive_targets = [target for target in targets if _target_exists(terminal, target)]
        pane_exists = _pane_exists_anywhere(agent.get("pane_ref"))
        has_identity = bool(
            agent.get("identity_provider")
            or agent.get("identity_id")
            or agent.get("identity_label")
        )
        risk_flags = []
        if not alive_targets:
            risk_flags.append("missing-pane")
        if not alive_targets and not pane_exists:
            risk_flags.append("dead-process")
        if has_identity and not alive_targets:
            risk_flags.append("identity-on-dead-row")
        if not agent.get("seat_instance_id"):
            risk_flags.append("missing-seat-instance-id")
        if not agent.get("runtime_session_id") and agent.get("runtime") not in ("shell", "command"):
            risk_flags.append("runtime-session-missing")
        seat = agent.get("name") or agent.get("seat")
        expected_ref = registry.seat_ref(fleet, seat)
        if (agent.get("seat_ref") and agent.get("seat_ref") != expected_ref) or (
            agent.get("terminal_ref") and agent.get("terminal_ref") not in targets
        ):
            risk_flags.append("reused-address-suspected")
        for flag in risk_flags:
            risk_counts[flag] = risk_counts.get(flag, 0) + 1
        if "dead-process" in risk_flags:
            suggested_action = "archive-or-restore"
        elif "missing-pane" in risk_flags:
            suggested_action = "inspect-or-adopt"
        elif "missing-seat-instance-id" in risk_flags:
            suggested_action = "restart-or-repair-current-projection"
        else:
            suggested_action = "none"
        rows.append({
            "seat": seat,
            "fleet": fleet,
            "seat_ref": expected_ref,
            "status": agent.get("status"),
            "runtime": agent.get("runtime"),
            "terminal_ref": agent.get("terminal_ref"),
            "backend_ref": agent.get("backend_ref"),
            "pane_ref": agent.get("pane_ref"),
            "checked_targets": targets,
            "alive_targets": alive_targets,
            "pane_exists_anywhere": pane_exists,
            "runtime_session_id": agent.get("runtime_session_id"),
            "seat_instance_id": agent.get("seat_instance_id"),
            "identity_provider": agent.get("identity_provider"),
            "identity_id": agent.get("identity_id"),
            "identity_label": agent.get("identity_label"),
            "last_seen": agent.get("last_seen"),
            "risk_flags": risk_flags,
            "suggested_action": suggested_action,
        })

    risky = [row for row in rows if row["risk_flags"]]
    return {
        "ok": True,
        "schema": "aura.seat_audit.v1",
        "read_only": True,
        "fleet": getattr(args, "fleet", None),
        "include_hidden": include_hidden,
        "checked": len(rows),
        "risky_count": len(risky),
        "risk_counts": risk_counts,
        "rows": rows,
    }


def _archive(args, registry, terminal) -> dict:
    target = getattr(args, "target", None) or ""
    if not target or target.count(":") != 1 or target.startswith(":") or target.endswith(":"):
        return {"ok": False, "error": "empty-target",
                "detail": "target must be FLEET:SEAT"}

    record = registry.get_agent(target)
    if not record:
        return {"ok": False, "error": "seat not found", "target": target}

    fleet = record.get("fleet")
    if fleet and hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)
    targets = _seat_targets(record)
    alive_targets = [ref for ref in targets if _target_exists(terminal, ref)]
    pane_exists = _pane_exists_anywhere(record.get("pane_ref"))
    if (alive_targets or pane_exists) and not getattr(args, "force", False):
        return {
            "ok": False,
            "error": "seat-appears-live",
            "target": target,
            "alive_targets": alive_targets,
            "pane_exists_anywhere": pane_exists,
            "detail": "refusing to archive a current row while its terminal appears live; pass --force only after manual verification",
        }

    now = registry.now_iso()
    reason = getattr(args, "reason", None) or "manual-current-projection-cleanup"
    after = {
        **record,
        "status": "archived",
        "archived_at": now,
        "archive_reason": reason,
        "terminal_state": "historical",
    }
    try:
        from lib import session_ledger

        event = session_ledger.append_seat_event(
            event="seat_archived",
            before=record,
            after=after,
            evidence={
                "source_command": "aura seat archive",
                "reason": reason,
                "checked_targets": targets,
                "alive_targets": alive_targets,
                "pane_exists_anywhere": pane_exists,
                "force": bool(getattr(args, "force", False)),
            },
            source_command="aura seat archive",
        )
    except Exception:
        event = None

    fleet_name, seat_name = registry.split_ref(target)
    removed = registry.remove_agent(seat_name, fleet=fleet_name)
    invalidation = None
    if removed:
        try:
            from lib import diagnostic_cache

            invalidation = diagnostic_cache.invalidate(
                target,
                reason="seat-archived",
                source_command="aura seat archive",
                evidence={"archive_reason": reason},
            )
        except Exception:
            invalidation = None
    return {
        "ok": bool(removed),
        "action": "archive",
        "target": target,
        "removed_current_row": bool(removed),
        "event": "seat_archived",
        "event_id": (event or {}).get("event_id"),
        "reason": reason,
        "historical": True,
        "diagnostic_cache_invalidation": invalidation,
    }


def _quarantine(args, registry, terminal) -> dict:
    target = getattr(args, "target", None) or ""
    if not target or target.count(":") != 1 or target.startswith(":") or target.endswith(":"):
        return {"ok": False, "error": "empty-target",
                "detail": "target must be FLEET:SEAT"}

    record = registry.get_agent(target)
    if not record:
        return {"ok": False, "error": "seat not found", "target": target}

    fleet = record.get("fleet")
    if fleet and hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)
    targets = _seat_targets(record)
    alive_targets = [ref for ref in targets if _target_exists(terminal, ref)]
    pane_exists = _pane_exists_anywhere(record.get("pane_ref"))
    if (alive_targets or pane_exists) and not getattr(args, "force", False):
        return {
            "ok": False,
            "error": "seat-appears-live",
            "target": target,
            "alive_targets": alive_targets,
            "pane_exists_anywhere": pane_exists,
            "detail": "refusing to quarantine a row while its terminal appears live; pass --force only after manual verification",
        }

    now = registry.now_iso()
    reason = getattr(args, "reason", None) or "stale-current-projection-quarantine"
    after = {
        **record,
        "status": "quarantined",
        "quarantined_at": now,
        "quarantine_reason": reason,
        "terminal_state": "terminal",
        "restore_suppressed": True,
    }
    try:
        from lib import session_ledger

        event = session_ledger.append_seat_event(
            event="seat_quarantined",
            before=record,
            after=after,
            evidence={
                "source_command": "aura seat quarantine",
                "reason": reason,
                "checked_targets": targets,
                "alive_targets": alive_targets,
                "pane_exists_anywhere": pane_exists,
                "force": bool(getattr(args, "force", False)),
            },
            source_command="aura seat quarantine",
        )
    except Exception:
        event = None

    updated = registry.replace_agent_record(after)
    try:
        from lib import diagnostic_cache

        invalidation = diagnostic_cache.invalidate(
            target,
            reason="seat-quarantined",
            source_command="aura seat quarantine",
            evidence={"quarantine_reason": reason},
        )
    except Exception:
        invalidation = None
    return {
        "ok": True,
        "action": "quarantine",
        "target": target,
        "event": "seat_quarantined",
        "event_id": (event or {}).get("event_id"),
        "reason": reason,
        "record": updated,
        "hidden_from_live_views": True,
        "diagnostic_cache_invalidation": invalidation,
    }


def _rename(args, registry) -> dict:
    source = getattr(args, "source", None)
    name = getattr(args, "name", None)
    if not source or not name:
        return {"ok": False, "error": "usage", "detail": "rename requires SOURCE and NEW_NAME"}
    if ":" in name:
        return {
            "ok": False,
            "error": "rename-target-must-be-seat-name",
            "detail": "use only the new seat name; rename never changes fleet",
        }
    preflight = registry.rename_preflight(source, new_name=name)
    if not preflight.get("ok"):
        return preflight
    existing = preflight.get("source_record")
    if not existing:
        return {"ok": False, "error": f"agent not found: {source}"}
    fleet = existing.get("fleet")
    current_name = existing.get("name") or existing.get("seat")
    if name == current_name:
        return {"ok": True, "renamed": False, "source": preflight.get("source"), "target": preflight.get("source")}

    renamed_terminal = _rename_terminal_exact(existing, fleet=fleet, name=name)
    if not renamed_terminal.get("ok"):
        return renamed_terminal
    metadata = {
        "terminal_ref": renamed_terminal["terminal_ref"],
        "backend_ref": renamed_terminal["backend_ref"],
        "pane_ref": renamed_terminal["pane_ref"],
        "physical_fleet": renamed_terminal["physical_fleet"],
    }

    result = registry.rename_agent(source, new_name=name, metadata=metadata, alias_old=True)
    if result.get("ok"):
        try:
            from lib import session_ledger

            after = result.get("record")
            session_ledger.append_seat_event(
                event="seat_renamed",
                before=existing,
                after=after,
                evidence={
                    "source": result.get("source"),
                    "target": result.get("target"),
                    "same_fleet": True,
                    "metadata_keys": sorted(metadata.keys()),
                },
                source_command="aura seat rename",
                source_ref=result.get("source"),
                target_ref=result.get("target"),
            )
            if result.get("alias"):
                session_ledger.append_seat_event(
                    event="seat_alias_created",
                    before=existing,
                    after=after,
                    evidence=result.get("alias"),
                    source_command="aura seat rename",
                    source_ref=result["alias"].get("source"),
                    target_ref=result["alias"].get("target"),
                )
        except Exception:
            pass
        result["renamed"] = True
    return result


def _sync_windows(args) -> dict:
    """Re-assert each managed live seat's tmux window name from the registry.

    The seat name is the authority; the window name is its label. One-way,
    idempotent, label-only: never touches rows, panes, or processes.
    """
    from lib import registry, tmux_mirror

    fleet_filter = getattr(args, "fleet", None)
    mirror = tmux_mirror.list_physical_panes()
    if not mirror.get("ok"):
        return {"ok": False, "error": "tmux-mirror-unavailable"}

    panes = [p for p in mirror.get("panes", []) if p.get("pane_id")]
    window_pane_counts: dict = {}
    for p in panes:
        key = (p.get("tmux_session"), p.get("window_id") or p.get("window_index"))
        window_pane_counts[key] = window_pane_counts.get(key, 0) + 1
    pane_window = {}
    for p in panes:
        key = (p.get("tmux_session"), p.get("window_id") or p.get("window_index"))
        # Dashboard tiling is presentation, not identity: a multi-pane window
        # (or the dash window itself) is never relabeled to a seat name.
        if window_pane_counts[key] > 1 or p.get("window_name") == "dashboard":
            continue
        pane_window[p["pane_id"]] = (p.get("window_name"), p.get("tmux_session"))

    renamed: list[dict] = []
    failed: list[dict] = []
    for rec in registry.list_agents(fleet_filter, include_hidden=True):
        seat = rec.get("name") or rec.get("seat")
        fleet = rec.get("fleet")
        pane_ref = str(rec.get("pane_ref") or "")
        if not (seat and fleet and pane_ref.startswith("tmux:")):
            continue
        pane_id = pane_ref.rsplit(":", 1)[-1]
        if pane_id not in pane_window:
            continue
        window_name, tmux_session = pane_window[pane_id]
        if tmux_session != fleet or window_name == seat:
            continue
        result = _run_tmux(["rename-window", "-t", pane_id, seat])
        row = {"target": f"{fleet}:{seat}", "pane": pane_id, "was": window_name}
        if result.returncode == 0:
            renamed.append(row)
        else:
            failed.append({**row, "error": result.stderr.strip()})

    return {
        "ok": not failed,
        "schema": "aura.seat_sync_windows.v1",
        "fleet": fleet_filter,
        "renamed": renamed,
        "failed": failed,
    }


def _gc(args) -> dict:
    """TTL-based auto-archival of CRUFT registry rows.

    Replaces manual ``aura seat sweep`` for the common case of rows that are
    truly orphaned: pane gone, no resumable runtime session, and older than
    *ttl* days.  Resumable lineage is unconditionally KEPT.

    This is an EXPLICIT write command. --confirm is required to perform any
    removal; --dry-run (or the absence of --confirm) only reports.
    """
    from datetime import datetime, timezone
    from lib import registry, tmux_mirror, runtime_session, runtimes

    ttl: int = getattr(args, "ttl", None) or 7
    fleet_filter = getattr(args, "fleet", None)
    dry_run = bool(getattr(args, "dry_run", False))
    confirm = bool(getattr(args, "confirm", False))

    records = registry.list_agents(fleet_filter, include_hidden=True)

    mirror = tmux_mirror.list_physical_panes()
    if not mirror.get("ok"):
        return {
            "ok": False,
            "error": "tmux-mirror-unavailable",
            "detail": mirror.get("error") or "tmux list-panes failed",
        }

    joined = tmux_mirror.join_managed(mirror["panes"], records)
    missing_managed = joined.get("missing_managed", [])

    # Build a logical_ref -> full record map so we can look up the rich row
    # from the compact entries returned by join_managed.
    ref_to_record: dict = {}
    for rec in records:
        seat_name = rec.get("seat") or rec.get("name")
        fleet_name = rec.get("fleet")
        if not seat_name:
            continue
        logical_ref = f"{fleet_name}:{seat_name}" if fleet_name else str(seat_name)
        ref_to_record[logical_ref] = rec

    now = datetime.now(timezone.utc)

    archived: list[dict] = []
    kept: list[dict] = []

    for entry in missing_managed:
        logical_ref = entry.get("logical_ref")
        if not logical_ref:
            continue
        record = ref_to_record.get(logical_ref)
        if not record:
            # Cannot find full record — skip conservatively
            kept.append({"ref": logical_ref, "reason": "record-not-found"})
            continue

        # Resumability requires the runtime to still exist. A row bound to a
        # runtime removed from RUNTIMES (e.g. legacy omx) can never be resumed
        # — resolve_runtime() errors — so its "bound"/fork lineage is false
        # lineage: cruft, not something to protect. Gate the lineage keeps on a
        # present runtime so removed-runtime rows self-clean on the next gc.
        runtime_key = record.get("runtime")
        runtime_present = bool(runtime_key) and runtime_key in runtimes.RUNTIMES

        # KEEP: resumable lineage (only if its runtime still exists)
        if runtime_present and runtime_session.is_bound_session(record):
            kept.append({"ref": logical_ref, "reason": "resumable"})
            continue

        # KEEP: fork-in-progress — carries a source_session_id (fork lineage) even
        # though no child runtime_session_id is bound yet. Never auto-archive it
        # (unless its runtime was removed — a fork child of a deleted runtime is
        # equally unresumable).
        if runtime_present and (
            record.get("runtime_session_binding") == "pending-fork-child"
            or record.get("source_session_id")
        ):
            kept.append({"ref": logical_ref, "reason": "fork-lineage"})
            continue

        # KEEP: already retired / terminal
        if record.get("terminal_state") == "terminal" or record.get("restore_suppressed"):
            kept.append({"ref": logical_ref, "reason": "already-archived"})
            continue

        # ARCHIVE (TTL-exempt): runtime no longer in RUNTIMES. Such a row can
        # never resume (resolve_runtime errors) and can never bind again, so the
        # age grace window serves nothing — archive it on the first gc. This is
        # what makes "runtime removed from code" actually imply "rows clear".
        if not runtime_present:
            archived.append({
                "ref": logical_ref,
                "seat": record.get("seat") or record.get("name"),
                "fleet": record.get("fleet"),
                "age_days": None,
                "created_at": record.get("created_at"),
                "reason": "removed-runtime",
            })
            continue

        # AGE: parse created_at conservatively
        created_at_raw = record.get("created_at")
        if not created_at_raw:
            kept.append({"ref": logical_ref, "reason": "no-created-at"})
            continue
        try:
            created_at = datetime.fromisoformat(str(created_at_raw))
            # Ensure timezone-aware comparison
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            kept.append({"ref": logical_ref, "reason": "no-created-at"})
            continue

        age_days = (now - created_at).days
        if age_days <= ttl:
            kept.append({"ref": logical_ref, "reason": "within-ttl", "age_days": age_days})
            continue

        # ARCHIVE: unbound orphan with a present runtime, older than TTL.
        archived.append({
            "ref": logical_ref,
            "seat": record.get("seat") or record.get("name"),
            "fleet": record.get("fleet"),
            "age_days": age_days,
            "created_at": created_at_raw,
            "reason": "ttl-orphan",
        })

    # Perform removals only when --confirm is set (never on --dry-run or default)
    removed_refs: list[str] = []
    if confirm and not dry_run:
        now_iso = registry.now_iso()
        for row in archived:
            seat_name = row["seat"]
            fleet_name = row["fleet"]
            record = ref_to_record.get(row["ref"])
            if not record:
                continue
            after = {
                **record,
                "terminal_state": "terminal",
                "restore_suppressed": True,
                "archived_at": now_iso,
                "archive_reason": f"{row.get('reason', 'ttl-orphan')}-gc",
            }
            try:
                from lib import session_ledger
                session_ledger.append_seat_event(
                    event="seat_auto_archived",
                    before=record,
                    after=after,
                    source_command="aura seat gc",
                )
            except Exception:
                pass
            if registry.remove_agent(seat_name, fleet=fleet_name):
                removed_refs.append(row["ref"])

        # Single batch invalidation after all removals
        if removed_refs:
            try:
                from lib import diagnostic_cache
                for ref in removed_refs:
                    diagnostic_cache.invalidate(
                        ref,
                        reason="seat-auto-archived-ttl-gc",
                        source_command="aura seat gc",
                        evidence={"ttl_days": ttl},
                    )
            except Exception:
                pass

    return {
        "ok": True,
        "schema": "aura.seat_gc.v1",
        "dry_run": not confirm or dry_run,
        "ttl_days": ttl,
        "fleet": fleet_filter,
        "archived": archived,
        "removed": removed_refs,
        "kept": kept,
        "counts": {
            "scanned": len(records),
            "candidates": len(missing_managed),
            "archived": len(archived),
            "removed": len(removed_refs),
            "kept": len(kept),
        },
    }


def _alias_ls(args, registry):
    """List historical alias ledger rows, schema-tolerant.

    Reads only source/target/reason/created_at (plus optional retired_occupant
    when present). Filters by source/target/fleet. Touches the alias ledger only.
    """
    aliases = registry.read_aliases()
    source_filter = getattr(args, "source", None)
    target_filter = getattr(args, "target", None)
    fleet_filter = getattr(args, "fleet", None)

    rows = []
    for source, record in aliases.items():
        if not isinstance(record, dict):
            continue
        target = record.get("target")
        if source_filter and source != source_filter:
            continue
        if target_filter and target != target_filter:
            continue
        if fleet_filter:
            source_fleet = source.split(":", 1)[0] if ":" in source else None
            target_fleet = str(target).split(":", 1)[0] if target and ":" in str(target) else None
            if fleet_filter not in (source_fleet, target_fleet):
                continue
        row = {
            "source": source,
            "target": target,
            "reason": record.get("reason"),
            "created_at": record.get("created_at"),
        }
        if "retired_occupant" in record:
            row["retired_occupant"] = record.get("retired_occupant")
        rows.append(row)

    rows.sort(key=lambda r: (str(r.get("source") or "")))
    return {"ok": True, "aliases": rows, "count": len(rows)}


def _alias_rm(args, registry):
    """Remove one historical alias by source. Touches the alias ledger only.

    Requires --confirm to write; otherwise returns a dry-run preview.
    """
    source = getattr(args, "source", None)
    if not source:
        return {"ok": False, "error": "source-required", "detail": "seat alias rm requires a source"}

    aliases = registry.read_aliases()
    record = aliases.get(source)
    if not isinstance(record, dict):
        return {"ok": False, "error": "alias-not-found", "source": source}

    preview = {
        "source": source,
        "target": record.get("target"),
        "reason": record.get("reason"),
        "created_at": record.get("created_at"),
    }
    if getattr(args, "dry_run", False) or not getattr(args, "confirm", False):
        return {"ok": True, "dry_run": True, "removed": False, "alias": preview}

    aliases.pop(source, None)
    registry.write_aliases(aliases)
    return {"ok": True, "dry_run": False, "removed": True, "alias": preview}


def _whoami(args, registry) -> dict:
    """Resolve a pane (or this process) to its managed seat identity. Read-only.

    The CLI contract the tmux layer consumes: scripts pass --pane and read the
    JSON (or the pre-rendered `block`) instead of importing registry internals.
    """
    pane_arg = getattr(args, "pane", None)
    pane_ref = None
    if pane_arg:
        value = str(pane_arg)
        if value.startswith("tmux:"):
            pane_ref = value
        elif value.startswith("%"):
            probe = _run_tmux(["display-message", "-p", "-t", value, "#{session_name}"])
            session = (probe.stdout or "").strip()
            if probe.returncode != 0 or not session:
                return {"ok": False, "error": "pane-not-found", "pane": value}
            pane_ref = f"tmux:{session}:{value}"
        else:
            return {
                "ok": False,
                "error": "bad-pane-ref",
                "detail": "expected tmux:SESSION:%N or a bare %N pane id",
                "pane": value,
            }
        row = registry.resolve_occupant(pane_ref=pane_ref)
    else:
        env = os.environ
        pane_id = env.get("TMUX_PANE")
        if pane_id:
            probe = _run_tmux(["display-message", "-p", "-t", pane_id, "#{session_name}"])
            session = (probe.stdout or "").strip()
            if probe.returncode == 0 and session:
                pane_ref = f"tmux:{session}:{pane_id}"
        row = registry.resolve_occupant(
            seat_instance_id=env.get("AURA_SEAT_INSTANCE_ID"),
            aura_launch_id=env.get("AURA_LAUNCH_ID"),
            pane_ref=pane_ref,
        )

    if not row:
        hint = (
            f"aura seat adopt --pane {pane_ref} --as FLEET:SEAT --runtime RUNTIME"
            if pane_ref
            else None
        )
        block_lines = [f"- aura: unmanaged pane {pane_ref or 'unknown'}"]
        if hint:
            block_lines.append(f"  hint: {hint}")
        return {
            "ok": False,
            "error": "unmanaged-pane",
            "pane_ref": pane_ref,
            "hint": hint,
            "block": "\n".join(block_lines),
        }

    target = f"{row.get('fleet')}:{row.get('name') or row.get('seat')}"
    agent = next(
        (str(row.get(k)) for k in ("identity_id", "agent_package_id", "identity") if row.get(k)),
        "",
    )
    lines = [f"- aura: {target}"]
    if agent.startswith("i_"):
        lines.append(f"  agent: {agent}")
    if row.get("seat_instance_id"):
        lines.append(f"  seat_instance: {row['seat_instance_id']}")
    if row.get("runtime_session_id"):
        lines.append(f"  session: {row['runtime_session_id']}")
    elif row.get("aura_launch_id"):
        lines.append(f"  launch: {row['aura_launch_id']}")
    if row.get("runtime"):
        lines.append(f"  runtime: {row['runtime']}")
    if row.get("pane_ref"):
        lines.append(f"  pane: {row['pane_ref']}")
    return {
        "ok": True,
        "target": target,
        "fleet": row.get("fleet"),
        "seat": row.get("name") or row.get("seat"),
        "runtime": row.get("runtime"),
        "seat_instance_id": row.get("seat_instance_id"),
        "runtime_session_id": row.get("runtime_session_id"),
        "aura_launch_id": row.get("aura_launch_id"),
        "agent_package_id": agent if agent.startswith("i_") else None,
        "pane_ref": row.get("pane_ref"),
        "block": "\n".join(lines),
    }


def run(args):
    from lib import registry

    action = args.seat_action
    if action == "aliases":
        return {"ok": True, "aliases": registry.read_aliases()}
    if action == "alias":
        alias_action = getattr(args, "alias_action", None)
        if alias_action == "ls":
            return _alias_ls(args, registry)
        if alias_action == "rm":
            return _alias_rm(args, registry)
        return {"ok": False, "error": f"unknown seat alias action: {alias_action}"}
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
    if action == "audit":
        from lib import terminal

        return _audit(args, registry, terminal)
    if action == "archive":
        from lib import terminal

        return _archive(args, registry, terminal)
    if action == "quarantine":
        from lib import terminal

        return _quarantine(args, registry, terminal)
    if action == "order":
        return _order(args)
    if action == "tag":
        return _tag(args, registry)
    if action == "inject-flex":
        from lib import terminal

        return _inject_flex(args, registry, terminal)
    if action == "restart":
        from lib import terminal

        return _restart(args, registry, terminal)
    if action == "rollover":
        from lib import terminal

        return _rollover(args, registry, terminal)
    if action == "adopt":
        target = getattr(args, "target", None)
        fleet, _, error = _normalize_adoption_target(target)
        if error:
            return error
        pane_ref = getattr(args, "pane", None)
        if not pane_ref:
            return {
                "ok": False,
                "error": "pane-required",
                "detail": "seat adopt requires --pane tmux:<fleet>:%<pane-id>",
            }
        discovery = _validate_explicit_adoption_pane(pane_ref, fleet)
        if not discovery.get("ok"):
            return {"ok": False, **discovery, "target": target}
        return _adopt_pane_as_seat(
            target=target,
            pane=discovery["pane"],
            registry=registry,
            runtime_arg=getattr(args, "runtime", None),
            cwd_arg=getattr(args, "cwd", None),
            discovered_by=discovery.get("discovered_by"),
            source_command="aura seat adopt",
            rename_window=bool(getattr(args, "rename_window", True)) and not bool(getattr(args, "keep_window_name", False)),
            adoption_source="direct-pane",
            identity_provider=getattr(args, "identity_provider", None),
            identity_id=getattr(args, "identity_id", None),
            identity_label=getattr(args, "identity_label", None),
        )
    if action == "rename":
        return _rename(args, registry)
    if action == "gc":
        return _gc(args)
    if action == "sync-windows":
        return _sync_windows(args)
    if action == "whoami":
        return _whoami(args, registry)
    return {"ok": False, "error": f"unknown seat action: {action}"}
