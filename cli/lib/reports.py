"""Append-only worker report ledger for Aura."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
import uuid

from lib import registry, runtime_session, state


VALID_STATES = {
    "working",
    "blocked",
    "needs_decision",
    "handoff",
    "complete",
    "parked",
    "failed",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_report_id() -> str:
    return f"aura-rpt-{uuid.uuid4().hex[:12]}"


def reports_path() -> Path:
    return state.state_root() / "reports" / "reports.jsonl"


def _env_first(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def infer_context() -> dict[str, Any]:
    runtime = _env_first("AURA_RUNTIME")
    resolved = runtime_session.resolve_current_process(runtime)

    fleet = _env_first("AURA_FLEET", "AURA_TMUX_SESSION") or resolved.get("fleet")
    seat = _env_first("AURA_SEAT", "AURA_AGENT_NAME") or resolved.get("seat")
    runtime = runtime or resolved.get("runtime")

    agent = registry.get_agent(seat, fleet=fleet) if seat else None
    if agent:
        fleet = fleet or agent.get("fleet")
        runtime = runtime or agent.get("runtime")

    session_id = (
        _env_first("CODEX_THREAD_ID", "AURA_RUNTIME_SESSION_ID", "AURA_SESSION_ID", "CLAUDE_SESSION_ID")
        or resolved.get("session_id")
        or (agent or {}).get("session_id")
        or (agent or {}).get("runtime_session_id")
    )

    warnings = []
    if not seat:
        warnings.append("seat-not-inferred")
    if not fleet:
        warnings.append("fleet-not-inferred")
    if not session_id:
        warnings.append("session-id-not-inferred")

    return {
        "seat": seat,
        "fleet": fleet,
        "runtime": runtime,
        "session_id": session_id,
        "runtime_session_id": session_id,
        "runtime_session_source": resolved.get("runtime_session_source"),
        "runtime_session_confidence": resolved.get("runtime_session_confidence"),
        "cwd": os.getcwd(),
        "pane": os.environ.get("TMUX_PANE"),
        "role": {},
        "warnings": warnings,
    }


def append_report(record: dict[str, Any]) -> dict[str, Any]:
    enriched = {
        "schema": "aura.report.v1",
        "report_id": new_report_id(),
        "timestamp": now_iso(),
        **infer_context(),
        **record,
    }
    path = reports_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, sort_keys=True))
        f.write("\n")
    return enriched


def release_queued_messages(report: dict[str, Any]) -> list[dict[str, Any]]:
    from lib import queued_messages

    return queued_messages.release_for_report(report)


def schedule_queued_messages(report: dict[str, Any], *, delay_seconds: float = 1.5) -> list[dict[str, Any]]:
    from lib import queued_messages

    return queued_messages.schedule_for_report(report, delay_seconds=delay_seconds)


def schedule_report_subscriptions(report: dict[str, Any], *, delay_seconds: float = 1.5) -> list[dict[str, Any]]:
    from lib import report_subscriptions

    return report_subscriptions.schedule_for_report(report, delay_seconds=delay_seconds)


def iter_reports(limit: int | None = None) -> list[dict[str, Any]]:
    path = reports_path()
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


def latest_report() -> dict[str, Any] | None:
    rows = iter_reports(limit=1)
    return rows[-1] if rows else None


def find_report(report_id: str) -> dict[str, Any] | None:
    for row in reversed(iter_reports()):
        if row.get("report_id") == report_id:
            return row
    return None
