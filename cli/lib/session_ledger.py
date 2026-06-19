"""Durable Aura session ledger and restore planning helpers."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
import uuid

from lib import runtime_session, state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_event_id() -> str:
    return f"aura-seat-history-{uuid.uuid4().hex[:12]}"


def new_fleet_event_id() -> str:
    return f"aura-fleet-history-{uuid.uuid4().hex[:12]}"


def ledger_path() -> Path:
    return state.state_root() / "registry" / "session-ledger.jsonl"


def ledger_lock_path() -> Path:
    path = ledger_path()
    return path.with_name(f"{path.name}.lock")


# Write-path cap so the ledger can never regrow into the 459 MB OOM source that
# took down every event daemon. Appends are flock-serialized; once the file
# crosses AURA_LEDGER_MAX_BYTES a streaming, projection-equivalent compaction
# runs (see compact_ledger). The cap lives on the write path exactly like the
# registry-writes.log cap, so it is self-maintaining and needs no cron.
_DEFAULT_LEDGER_MAX_BYTES = 64 * 1024 * 1024   # 64 MiB
_DEFAULT_LEDGER_KEEP_TAIL = 2000               # recent lines always retained
_DEFAULT_LEDGER_ARCHIVE_KEEP = 5               # compressed archives retained

# Events whose ORDER and presence drive project_latest_from_ledger's alias map
# and terminal-state flags. They are rare and always retained verbatim so a
# compacted ledger projects identically to the full one.
_LINEAGE_EVENTS = {"seat_rehomed", "seat_renamed", "seat_alias_created"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw:
        try:
            value = int(raw)
            if value >= 0:
                return value
        except ValueError:
            pass
    return default


def _ledger_max_bytes() -> int:
    return _env_int("AURA_LEDGER_MAX_BYTES", _DEFAULT_LEDGER_MAX_BYTES)


def _ledger_keep_tail() -> int:
    return _env_int("AURA_LEDGER_KEEP_TAIL", _DEFAULT_LEDGER_KEEP_TAIL)


def _ledger_archive_keep() -> int:
    return _env_int("AURA_LEDGER_ARCHIVE_KEEP", _DEFAULT_LEDGER_ARCHIVE_KEEP)


@contextmanager
def _ledger_lock():
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_lock_path()
    with open(lock_path, "a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _append_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Single flock-serialized append chokepoint for every ledger writer.

    All three append helpers funnel through here so the write-path cap and the
    lock live in exactly one place. The cap check runs after the lock is
    released; compaction is memory-bounded so it can never re-trigger the OOM.
    """
    line = json.dumps(payload, sort_keys=True)
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock():
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")
    _maybe_compact()
    return payload


def _maybe_compact() -> None:
    try:
        if ledger_path().stat().st_size <= _ledger_max_bytes():
            return
    except OSError:
        return
    try:
        compact_ledger()
    except Exception:
        # Maintenance is best-effort: a compaction failure must never break the
        # append that just succeeded (the row is already durably on disk).
        pass


def append_record(record: dict[str, Any]) -> dict[str, Any]:
    enriched = {
        "schema": "aura.session_ledger.v1",
        "timestamp": now_iso(),
        **record,
    }
    return _append_payload(enriched)


def seat_ref(fleet: str | None, seat: str | None) -> str | None:
    if not seat:
        return None
    return f"{fleet}:{seat}" if fleet else str(seat)


SNAPSHOT_FIELDS = (
    "name",
    "seat",
    "fleet",
    "fleet_id",
    "seat_ref",
    "seat_instance_id",
    "runtime",
    "command",
    "cwd",
    "workdir",
    "runtime_session_cwd",
    "aura_launch_id",
    "previous_aura_launch_id",
    "session_id",
    "runtime_session_id",
    "runtime_session_source",
    "runtime_session_binding",
    "runtime_session_bind_method",
    "runtime_session_bind_source",
    "runtime_session_bound_at",
    "runtime_session_confidence",
    "runtime_session_evidence",
    "runtime_session_diagnostics",
    "runtime_session_possible_matches",
    "runtime_session_env",
    "runtime_session_created_at_ms",
    "runtime_session_updated_at_ms",
    "runtime_session_pid",
    "source_session_id",
    "previous_runtime_session_id",
    "restart_from_session_id",
    "terminal_ref",
    "backend_ref",
    "pane_ref",
    "runtime_process_pid",
    "runtime_process_cwd",
    "runtime_process_started_at_epoch",
    "runtime_process_argv",
    "status",
    "identity_provider",
    "identity_id",
    "identity_label",
    "agent_package_id",
    "agent_package_address",
    "agent_package_alias",
    "agent_package_root",
    "codex_package_root",
    "codex_package_codex_home",
    "omx_package_root",
    "omx_package_codex_home",
    "omx_package_omx_root",
    "omx_package_omx_state",
    "omx_package_team_state_root",
    "runtime_home",
    "codex_box_root",
    "codex_box_codex_home",
    "omx_box_root",
    "omx_box_codex_home",
    "omx_box_omx_root",
    "omx_box_team_state_root",
    "flex_project_manifest",
    "flex_project_root",
)


def snapshot_seat(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    snap = {key: record.get(key) for key in SNAPSHOT_FIELDS if record.get(key) is not None}
    seat = snap.get("seat") or snap.get("name")
    fleet = snap.get("fleet")
    if seat:
        snap["seat"] = seat
        snap["name"] = snap.get("name") or seat
    if seat and not snap.get("seat_ref"):
        snap["seat_ref"] = seat_ref(fleet, seat)
    if not snap.get("cwd"):
        cwd = snap.get("runtime_session_cwd") or snap.get("workdir")
        if cwd:
            snap["cwd"] = cwd
    if runtime_session.is_bound_session(snap) and not snap.get("session_id") and snap.get("runtime_session_id"):
        snap["session_id"] = snap["runtime_session_id"]
    if snap.get("runtime_session_binding") != "unbound" and not snap.get("runtime_session_id") and snap.get("session_id"):
        snap["runtime_session_id"] = snap["session_id"]
    return snap


def _first_present(*records: dict[str, Any] | None, key: str) -> Any:
    for record in records:
        if record and record.get(key) is not None:
            return record.get(key)
    return None


def append_seat_event(
    *,
    event: str,
    seat: str | None = None,
    fleet: str | None = None,
    runtime: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    actor: str = "cli",
    source_command: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    before_snap = snapshot_seat(before)
    after_snap = snapshot_seat(after)
    seat = seat or _first_present(after_snap, before_snap, key="seat") or _first_present(after_snap, before_snap, key="name")
    fleet = fleet or _first_present(after_snap, before_snap, key="fleet")
    fleet_id = _first_present(after_snap, before_snap, key="fleet_id")
    runtime = runtime or _first_present(after_snap, before_snap, key="runtime")
    if fleet and not fleet_id:
        try:
            from lib import fleets

            fleet_record = fleets.ensure_fleet(fleet)
            fleet_id = (fleet_record or {}).get("fleet_id")
        except Exception:
            fleet_id = None
    cwd = _first_present(after_snap, before_snap, key="cwd")
    session_id = _first_present(after_snap, before_snap, key="session_id") or _first_present(after_snap, before_snap, key="runtime_session_id")
    runtime_session_id = _first_present(after_snap, before_snap, key="runtime_session_id") or session_id
    launch_id = _first_present(after_snap, before_snap, key="aura_launch_id")
    seat_instance_id = _first_present(after_snap, before_snap, key="seat_instance_id")
    identity_provider = _first_present(after_snap, before_snap, key="identity_provider")
    identity_id = _first_present(after_snap, before_snap, key="identity_id")
    identity_label = _first_present(after_snap, before_snap, key="identity_label")
    record = {
        "schema": "aura.seat_history.v1",
        "event_id": new_event_id(),
        "timestamp": now_iso(),
        "event": event,
        "seat": seat,
        "name": seat,
        "fleet": fleet,
        "fleet_id": fleet_id,
        "seat_ref": seat_ref(fleet, seat),
        "runtime": runtime,
        "cwd": cwd,
        "session_id": session_id,
        "runtime_session_id": runtime_session_id,
        "runtime_session_binding": _first_present(after_snap, before_snap, key="runtime_session_binding"),
        "runtime_session_bind_method": _first_present(after_snap, before_snap, key="runtime_session_bind_method"),
        "runtime_session_bind_source": _first_present(after_snap, before_snap, key="runtime_session_bind_source"),
        "runtime_session_confidence": _first_present(after_snap, before_snap, key="runtime_session_confidence"),
        "runtime_session_source": _first_present(after_snap, before_snap, key="runtime_session_source"),
        "aura_launch_id": launch_id,
        "seat_instance_id": seat_instance_id,
        "identity_provider": identity_provider,
        "identity_id": identity_id,
        "identity_label": identity_label,
        "actor": actor,
        "source_command": source_command,
        "before": before_snap,
        "after": after_snap,
        "evidence": evidence or {},
        **{key: value for key, value in extra.items() if value is not None},
    }
    clean = {key: value for key, value in record.items() if value is not None}
    return _append_payload(clean)


def append_fleet_event(
    *,
    event: str,
    fleet: str | None = None,
    fleet_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    movement_kind: str | None = None,
    subject: str | None = None,
    reason: str | None = None,
    actor: str = "cli",
    source_command: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Append a fleet-level movement/history event.

    Seat events remain the per-runtime lifecycle ledger. Fleet events record the
    topological movement itself so operators can see one durable event for a
    rename/rehome operation without reconstructing it from every affected seat.
    """
    before = dict(before or {})
    after = dict(after or {})
    fleet = fleet or after.get("current_name") or after.get("fleet") or before.get("current_name") or before.get("fleet")
    fleet_id = fleet_id or after.get("fleet_id") or before.get("fleet_id")
    record = {
        "schema": "aura.fleet_history.v1",
        "event_id": new_fleet_event_id(),
        "timestamp": now_iso(),
        "event": event,
        "movement_kind": movement_kind,
        "subject": subject or fleet,
        "fleet": fleet,
        "fleet_id": fleet_id,
        "actor": actor,
        "source_command": source_command,
        "reason": reason,
        "before": before or None,
        "after": after or None,
        "evidence": evidence or {},
        **{key: value for key, value in extra.items() if value is not None},
    }
    clean = {key: value for key, value in record.items() if value is not None}
    return _append_payload(clean)


def iter_records(limit: int | None = None) -> list[dict[str, Any]]:
    path = ledger_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    if limit is not None:
        return rows[-int(limit):]
    return rows


def read_ledger(limit: int | None = None) -> list[dict[str, Any]]:
    """Compatibility reader for commands that need global session history."""
    return iter_records(limit=limit)


def keeper_thread_ids() -> set[str]:
    root = state.state_root() / "keeper-jobs"
    if not root.is_dir():
        return set()
    ids: set[str] = set()
    for result_path in root.glob("memory.*/result.json"):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for key in ("thread_id", "keeper_thread_id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                ids.add(value.strip())
    return ids


def is_keeper_thread_id(session_id: Any, keeper_ids: set[str] | None = None) -> bool:
    ids = keeper_thread_ids() if keeper_ids is None else keeper_ids
    return isinstance(session_id, str) and session_id in ids


def is_keeper_thread_row(row: dict[str, Any]) -> bool:
    session_id = row.get("session_id") or row.get("runtime_session_id")
    return is_keeper_thread_id(session_id)


def _row_refs(row: dict[str, Any]) -> set[str]:
    refs = set()
    for key in ("seat_ref", "source_ref", "target_ref"):
        if row.get(key):
            refs.add(str(row[key]))
    for key in ("before", "after"):
        value = row.get(key)
        if isinstance(value, dict) and value.get("seat_ref"):
            refs.add(str(value["seat_ref"]))
    fleet = row.get("fleet")
    seat = row.get("seat") or row.get("name")
    ref = seat_ref(fleet, seat)
    if ref:
        refs.add(ref)
    return refs


def seat_history_for_target(target: str, *, limit: int | None = None, follow_aliases: bool = True) -> list[dict[str, Any]]:
    rows = iter_records()
    wanted = {target}
    if ":" not in target:
        wanted.update(ref for row in rows for ref in _row_refs(row) if ref.endswith(f":{target}"))
    changed = True
    while follow_aliases and changed:
        changed = False
        for row in rows:
            if row.get("event") not in {"seat_rehomed", "seat_renamed", "seat_alias_created"}:
                continue
            refs = _row_refs(row)
            if refs & wanted and not refs <= wanted:
                wanted.update(refs)
                changed = True
    filtered = [row for row in rows if _row_refs(row) & wanted]
    if limit is not None:
        return filtered[-int(limit):]
    return filtered


TERMINAL_EVENTS = {"seat_cut", "seat_swept_removed", "seat_archived"}


def _state_from_row(row: dict[str, Any]) -> dict[str, Any]:
    after = row.get("after") if isinstance(row.get("after"), dict) else None
    before = row.get("before") if isinstance(row.get("before"), dict) else None
    base = snapshot_seat(after) or snapshot_seat(row) or snapshot_seat(before) or {}
    base.update({
        "latest_event": row.get("event"),
        "latest_event_id": row.get("event_id"),
        "latest_event_at": row.get("timestamp"),
    })
    return base


def project_latest_from_ledger(*, fleet: str | None = None) -> list[dict[str, Any]]:
    projections: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for row in iter_records():
        schema = row.get("schema")
        event = row.get("event")
        if schema in {"aura.seat_history.v1", "aura.seat_lineage.v1"}:
            before = row.get("before") if isinstance(row.get("before"), dict) else None
            after = row.get("after") if isinstance(row.get("after"), dict) else None
            current_ref = row.get("seat_ref") or (after or {}).get("seat_ref") or (before or {}).get("seat_ref")
            if event in {"seat_rehomed", "seat_renamed"}:
                old_ref = (before or {}).get("seat_ref") or row.get("source_ref")
                new_ref = (after or {}).get("seat_ref") or row.get("target_ref") or current_ref
                if old_ref and new_ref and old_ref in projections:
                    projections.pop(str(old_ref), None)
                if old_ref and new_ref:
                    aliases[str(old_ref)] = str(new_ref)
                current_ref = new_ref
            if event == "seat_alias_created":
                source = row.get("source_ref") or (before or {}).get("seat_ref")
                target = row.get("target_ref") or (after or {}).get("seat_ref") or current_ref
                if source and target:
                    aliases[str(source)] = str(target)
                continue
            if not current_ref:
                continue
            state = _state_from_row(row)
            if event in TERMINAL_EVENTS:
                state["terminal_state"] = "terminal"
                state["restore_suppressed"] = True
            elif event == "seat_restart_failed":
                state["repair_needed"] = True
            projections[str(current_ref)] = state
            continue

        # Compatibility fallback for older rows. Prefer explicit seat-history rows
        # when they exist, but keep old spawn/bind rows useful for recovery.
        if schema != "aura.session_ledger.v1":
            continue
        seat = row.get("seat") or row.get("name")
        ref = seat_ref(row.get("fleet"), seat)
        if not ref:
            continue
        if ref in projections and projections[ref].get("latest_event_id"):
            continue
        state = snapshot_seat(row) or {}
        state.update({
            "latest_event": row.get("event"),
            "latest_event_at": row.get("timestamp"),
        })
        projections[ref] = state

    resolved: dict[str, dict[str, Any]] = {}
    for ref, state in projections.items():
        target = aliases.get(ref, ref)
        if target != ref and target in projections:
            continue
        resolved[target] = state
    rows = list(resolved.values())
    if fleet:
        rows = [row for row in rows if row.get("fleet") == fleet]
    return sorted(rows, key=lambda row: (row.get("fleet") or "", row.get("seat") or row.get("name") or ""))


def restore_status(
    row: dict[str, Any],
    capability: dict[str, Any] | None = None,
    *,
    keeper_ids: set[str] | None = None,
) -> dict[str, Any]:
    capability = capability or {}
    if row.get("restore_suppressed") or row.get("terminal_state") == "terminal":
        return {
            "restore_ready": False,
            "restore_reason": "latest-seat-state-is-terminal",
        }
    binding = runtime_session.mark_binding(dict(row))
    session_id = binding.get("session_id") or binding.get("runtime_session_id")
    if is_keeper_thread_id(session_id, keeper_ids=keeper_ids):
        return {
            "restore_ready": False,
            "restore_reason": "keeper-worker-session",
        }
    supports_resume = bool(capability.get("supports_resume"))
    if not session_id and binding.get("runtime_session_possible_matches"):
        return {
            "restore_ready": False,
            "restore_reason": "runtime-session-unbound",
        }
    if not session_id:
        return {
            "restore_ready": False,
            "restore_reason": "missing-session-id",
        }
    if not runtime_session.is_bound_session(binding):
        return {
            "restore_ready": False,
            "restore_reason": "runtime-session-unbound",
        }
    if not supports_resume:
        return {
            "restore_ready": False,
            "restore_reason": "runtime-does-not-support-resume",
        }
    return {
        "restore_ready": True,
        "restore_reason": "bound-session-id-and-runtime-resume-supported",
    }


def _package_restore_ref(row: dict[str, Any]) -> str | None:
    return (
        row.get("agent_package_address")
        or row.get("agent_package_alias")
        or row.get("agent_package_id")
    )


def restore_evidence(row: dict[str, Any]) -> dict[str, Any]:
    """Rank the evidence source a restore command would rely on."""
    package_root = (
        row.get("agent_package_root")
        or row.get("codex_package_root")
        or row.get("omx_package_root")
    )
    if _package_restore_ref(row) and package_root:
        return {
            "restore_evidence_source": "package-local-runtime-state",
            "restore_evidence_rank": 100,
            "restore_command_kind": "agent-spawn-resume",
        }
    if _package_restore_ref(row):
        return {
            "restore_evidence_source": "package-registry-row-missing-root",
            "restore_evidence_rank": 90,
            "restore_command_kind": "agent-spawn-resume",
            "restore_warning": "package-root-missing-from-restore-row",
        }
    if row.get("restore_launch_history_recovered") or row.get("runtime_session_source") == "codex-jsonl:nonce":
        return {
            "restore_evidence_source": "launch-history-codex-jsonl",
            "restore_evidence_rank": 80,
            "restore_command_kind": "spawn-resume",
        }
    if row.get("runtime_home") or row.get("codex_box_root") or row.get("omx_box_root"):
        return {
            "restore_evidence_source": "legacy-capsule-runtime-state",
            "restore_evidence_rank": 70,
            "restore_command_kind": "spawn-resume",
        }
    if row.get("terminal") == "alive" and row.get("runtime_session_binding") == "bound":
        return {
            "restore_evidence_source": "live-registry-binding",
            "restore_evidence_rank": 60,
            "restore_command_kind": "spawn-resume",
        }
    if row.get("latest_event") or row.get("latest_event_id"):
        return {
            "restore_evidence_source": "session-ledger-projection",
            "restore_evidence_rank": 50,
            "restore_command_kind": "spawn-resume",
        }
    if row.get("runtime_session_source"):
        return {
            "restore_evidence_source": "runtime-session-observation",
            "restore_evidence_rank": 40,
            "restore_command_kind": "spawn-resume",
        }
    return {
        "restore_evidence_source": "unranked",
        "restore_evidence_rank": 0,
        "restore_command_kind": "none",
    }


def _shell_quote(value: Any) -> str:
    import shlex

    return shlex.quote(str(value))


def restore_command(row: dict[str, Any], capability: dict[str, Any] | None = None) -> str | None:
    capability = capability or {}
    status = restore_status(row, capability)
    if not status["restore_ready"]:
        return None
    seat = row.get("seat") or row.get("name")
    fleet = row.get("fleet")
    runtime = row.get("runtime")
    cwd = row.get("cwd") or row.get("workdir")
    session_id = row.get("session_id") or row.get("runtime_session_id")
    if not seat or not runtime or not session_id:
        return None
    package_ref = _package_restore_ref(row)
    if package_ref:
        parts = ["aura", "agent", "spawn", _shell_quote(package_ref)]
        if fleet:
            parts.extend(["--fleet", _shell_quote(fleet)])
        parts.extend(["--seat", _shell_quote(seat)])
        if cwd:
            parts.extend(["--cwd", _shell_quote(cwd)])
        parts.extend(["--resume-session", _shell_quote(session_id), "--as-pane", "--wait"])
        return " ".join(parts)

    parts = ["aura", "spawn", _shell_quote(seat), "--runtime", _shell_quote(runtime)]
    if fleet:
        parts.extend(["--fleet", _shell_quote(fleet)])
    if cwd:
        parts.extend(["--cwd", _shell_quote(cwd)])
    parts.extend(["--resume-session", _shell_quote(session_id), "--as-pane", "--wait"])
    return " ".join(parts)


def restore_plan_from_rows(rows: list[dict[str, Any]], capabilities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    plan_rows: list[dict[str, Any]] = []
    for row in rows:
        runtime = row.get("runtime")
        capability = capabilities.get(runtime or "", {})
        status = restore_status(row, capability)
        command = restore_command(row, capability)
        evidence = restore_evidence(row)
        warnings = list(row.get("warnings") or [])
        if evidence.get("restore_warning") and evidence["restore_warning"] not in warnings:
            warnings.append(evidence["restore_warning"])
        plan_rows.append({
            "seat": row.get("seat") or row.get("name"),
            "fleet": row.get("fleet"),
            "runtime": runtime,
            "terminal": row.get("terminal"),
            "session_id": row.get("session_id") or row.get("runtime_session_id"),
            "runtime_session_binding": row.get("runtime_session_binding"),
            "runtime_session_bind_method": row.get("runtime_session_bind_method"),
            "runtime_session_bind_source": row.get("runtime_session_bind_source"),
            "runtime_session_confidence": row.get("runtime_session_confidence"),
            "runtime_session_source": row.get("runtime_session_source"),
            "runtime_session_evidence": row.get("runtime_session_evidence"),
            "runtime_session_jsonl": row.get("runtime_session_jsonl") or row.get("jsonl"),
            "runtime_session_timestamp": row.get("runtime_session_timestamp"),
            "cwd": row.get("runtime_session_cwd") or row.get("cwd") or row.get("workdir"),
            "restore_ready": status["restore_ready"],
            "restore_reason": status["restore_reason"],
            "restore_evidence_source": evidence["restore_evidence_source"],
            "restore_evidence_rank": evidence["restore_evidence_rank"],
            "restore_command_kind": evidence["restore_command_kind"],
            "restore_launch_history_error": row.get("restore_launch_history_error"),
            "restore_command": command,
            "latest_event": row.get("latest_event"),
            "latest_event_id": row.get("latest_event_id"),
            "latest_event_at": row.get("latest_event_at"),
            "identity_provider": row.get("identity_provider"),
            "identity_id": row.get("identity_id"),
            "identity_label": row.get("identity_label"),
            "agent_package_id": row.get("agent_package_id"),
            "agent_package_address": row.get("agent_package_address"),
            "agent_package_alias": row.get("agent_package_alias"),
            "agent_package_root": row.get("agent_package_root"),
            "runtime_home": row.get("runtime_home"),
            "warnings": warnings,
        })
    ready = [row for row in plan_rows if row["restore_ready"]]
    review = [row for row in plan_rows if not row["restore_ready"]]
    return {
        "ok": True,
        "schema": "aura.restore_plan.v1",
        "dry_run": True,
        "total": len(plan_rows),
        "restore_ready": len(ready),
        "needs_review": len(review),
        "rows": plan_rows,
    }


# --------------------------------------------------------------------------- #
# Compaction — bound the append-only ledger without breaking resume.          #
# --------------------------------------------------------------------------- #
#
# project_latest_from_ledger (the resume/continuity consumer) folds the ledger
# to the latest state per seat_ref, applying the alias map built from lineage
# events and the terminal/repair flags. Its output therefore depends ONLY on:
#   * every lineage event (rename/rehome/alias) — in order,
#   * every terminal event (cut/swept/archived),
#   * the latest row per (schema, ref) — for both seat-history and the
#     session_ledger.v1 compatibility rows,
#   * the latest row per fleet (for fleet_history rows).
# Compaction keeps exactly those, plus a recent tail, IN ORIGINAL ORDER, so the
# projection — and thus every restore plan and binding lookup — is identical to
# the full ledger. History-display commands (sessions all / seat-history) see
# fewer intermediate rows; the full file is preserved in a compressed archive.


def _compaction_key(row: dict[str, Any]) -> tuple[str, str] | None:
    """The (schema, ref) key project_latest_from_ledger folds a row onto."""
    schema = row.get("schema")
    before = row.get("before") if isinstance(row.get("before"), dict) else None
    after = row.get("after") if isinstance(row.get("after"), dict) else None
    if schema == "aura.fleet_history.v1":
        fleet = (
            row.get("fleet")
            or (after or {}).get("fleet")
            or (before or {}).get("fleet")
        )
        return ("fleet", str(fleet)) if fleet else None
    ref = row.get("seat_ref") or (after or {}).get("seat_ref") or (before or {}).get("seat_ref")
    if not ref:
        seat = row.get("seat") or row.get("name")
        ref = seat_ref(row.get("fleet"), seat)
    if not ref:
        return None
    return (str(schema or "seat"), str(ref))


def _archive_ledger(path: Path) -> Path:
    """Stream-gzip the current ledger to a timestamped archive (memory-safe)."""
    archive_dir = path.parent / "_ledger-archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_dir / f"{path.name}.{stamp}.gz"
    fd, tmp = tempfile.mkstemp(prefix=".arch-", suffix=".gz", dir=str(archive_dir))
    os.close(fd)
    try:
        with path.open("rb") as src, gzip.open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        os.replace(tmp, archive_path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    return archive_path


def _prune_archives() -> None:
    keep = _ledger_archive_keep()
    archive_dir = ledger_path().parent / "_ledger-archives"
    if not archive_dir.is_dir():
        return
    files = sorted(archive_dir.glob(f"{ledger_path().name}.*.gz"))
    drop = files[:-keep] if keep > 0 else files
    for old in drop:
        try:
            old.unlink()
        except OSError:
            pass


def compact_ledger(*, force: bool = False, archive: bool = True) -> dict[str, Any]:
    """Fold the ledger to its projection-relevant subset, atomically.

    Memory-bounded: two streaming passes, never the whole file in memory. The
    original is preserved as a compressed archive before the atomic swap, so an
    interrupted compaction leaves the live ledger untouched.
    """
    path = ledger_path()
    if not path.exists():
        return {"ok": True, "compacted": False, "reason": "no-ledger"}
    with _ledger_lock():
        try:
            size_before = path.stat().st_size
        except OSError:
            return {"ok": True, "compacted": False, "reason": "stat-failed"}
        if not force and size_before <= _ledger_max_bytes():
            return {"ok": True, "compacted": False, "reason": "under-cap", "size": size_before}

        # Pass 1: decide which line indices to keep.
        keep: set[int] = set()
        last_for_key: dict[tuple[str, str], int] = {}
        total = 0
        with path.open(encoding="utf-8") as f:
            for idx, line in enumerate(f):
                total = idx + 1
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                event = row.get("event")
                if event in _LINEAGE_EVENTS or event in TERMINAL_EVENTS:
                    keep.add(idx)
                key = _compaction_key(row)
                if key is not None:
                    last_for_key[key] = idx
        keep.update(last_for_key.values())
        tail = _ledger_keep_tail()
        if tail > 0 and total > 0:
            keep.update(range(max(0, total - tail), total))

        # Pass 2: write the kept lines, in order, to a temp file.
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".session-ledger-", suffix=".jsonl", dir=str(path.parent))
        kept = 0
        archive_path: Path | None = None
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out, path.open(encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    if idx in keep:
                        if not line.endswith("\n"):
                            line = line + "\n"
                        out.write(line)
                        kept += 1
                out.flush()
                os.fsync(out.fileno())
            if archive:
                archive_path = _archive_ledger(path)
            os.replace(tmp, path)
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
        try:
            size_after = path.stat().st_size
        except OSError:
            size_after = None
        if archive:
            _prune_archives()
    return {
        "ok": True,
        "compacted": True,
        "lines_before": total,
        "lines_after": kept,
        "size_before": size_before,
        "size_after": size_after,
        "archive": str(archive_path) if archive_path else None,
    }
