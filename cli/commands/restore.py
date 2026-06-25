"""`aura restore` — reconnect the fleet from the flight recorder timeline.

Reconstructs the live fleet at a point in time (now, or `--at T`) from the flight store and
produces (dry-run) or runs (`--execute`) the spawn-resume commands that reconnect each seat to
the session it ACTUALLY had then. The session id comes from the recorded frame — the born-bound,
authoritative value — not a reconstructed observe-ledger guess (the original incident's root cause).

Restore replays through Aura's own gated spawn/bind path; the flight store is only the read model
of what was live.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from lib import flight, runtimes, seat_status, session_ledger


# --------------------------------------------------------------------------- pure helpers

_TS_FMT = "%Y-%m-%dT%H:%M:%S.%f+00:00"


def _normalize_at(at: str | None) -> str:
    """Canonical UTC iso matching the recorder's format, so reconstruct's lexicographic
    `ts <= at` compare is chronological. None -> now; naive -> assume UTC."""
    if at is None or str(at).strip() == "":
        dt = datetime.now(timezone.utc)
    else:
        dt = datetime.fromisoformat(str(at).strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(_TS_FMT)


def _frame_to_restore_row(fs: dict[str, Any]) -> dict[str, Any]:
    """A flight frame tuple -> the row shape restore_plan_from_rows consumes."""
    sid = fs.get("session_id")
    return {
        "seat": fs.get("seat"),
        "fleet": fs.get("fleet"),
        "runtime": fs.get("runtime"),
        "session_id": sid,
        "runtime_session_id": sid,
        "runtime_session_binding": "bound" if sid else "unbound",
        "cwd": fs.get("cwd"),
        "seat_instance_id": fs.get("seat_instance_id"),
        "terminal": fs.get("target"),
    }


def _plan(at: str) -> dict[str, Any]:
    from commands import sessions as sessions_cmd

    recon = flight.reconstruct(at)
    rows = [_frame_to_restore_row(s) for s in recon.get("seats", [])]
    plan = session_ledger.restore_plan_from_rows(rows, runtimes.capability_map())
    plan = {**plan, "source": "flight-snapshot", "reconstructed_at": recon.get("ts"), "requested_at": at}
    return sessions_cmd._add_restore_reconciliation(plan)


# --------------------------------------------------------------------------- IO (monkeypatchable)

def _live_targets() -> set[str]:
    try:
        return {
            row.get("target")
            for row in seat_status.list_seat_statuses(include_hidden=False)
            if row.get("liveness") == "alive" and row.get("target")
        }
    except Exception:  # noqa: BLE001 — degrade to "nothing known live" rather than crash restore
        return set()


def _run_command(cmd: str) -> tuple[bool, str]:
    import subprocess

    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    tail = (proc.stdout or proc.stderr or "")[-400:]
    return proc.returncode == 0, tail


# --------------------------------------------------------------------------- command

def run(args):
    at = _normalize_at(getattr(args, "at", None))
    plan = _plan(at)

    if not getattr(args, "execute", False):
        return plan  # dry-run is the default

    live = _live_targets()
    seen_sessions: set[str] = set()
    results: list[dict[str, Any]] = []
    executed = skipped = failed = 0
    for row in plan.get("rows", []):
        target = f"{row.get('fleet')}:{row.get('seat')}"
        cmd = row.get("restore_command")
        if not row.get("restore_ready") or not cmd:
            skipped += 1
            results.append({"target": target, "skipped": row.get("restore_reason") or "not-restore-ready"})
            continue
        if target in live:
            skipped += 1
            results.append({"target": target, "skipped": "already-live"})
            continue
        # Two seats must never resume the SAME session — that forks one mind into two
        # (the incident class, in a different shape). Restore at most one per session id.
        sid = row.get("session_id") or row.get("runtime_session_id")
        if sid and sid in seen_sessions:
            skipped += 1
            results.append({"target": target, "skipped": "duplicate-session-id"})
            continue
        if sid:
            seen_sessions.add(sid)
        ok, tail = _run_command(cmd)
        if ok:
            executed += 1
        else:
            failed += 1
        results.append({"target": target, "ok": ok, "stdout_tail": tail})

    return {
        "ok": failed == 0,
        "source": "flight-snapshot",
        "reconstructed_at": plan.get("reconstructed_at"),
        "requested_at": at,
        "executed": executed,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
