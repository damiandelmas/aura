"""Durable Aura session ledger and restore planning helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from lib import state


CONFIDENCE_ORDER = {
    "exact": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ledger_path() -> Path:
    return state.state_root() / "registry" / "session-ledger.jsonl"


def append_record(record: dict[str, Any]) -> dict[str, Any]:
    enriched = {
        "schema": "aura.session_ledger.v1",
        "timestamp": now_iso(),
        **record,
    }
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, sort_keys=True))
        f.write("\n")
    return enriched


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


def _confidence_at_least(value: str | None, minimum: str) -> bool:
    return CONFIDENCE_ORDER.get(value or "", 0) >= CONFIDENCE_ORDER[minimum]


def restore_status(row: dict[str, Any], capability: dict[str, Any] | None = None) -> dict[str, Any]:
    capability = capability or {}
    session_id = row.get("session_id") or row.get("runtime_session_id")
    confidence = row.get("runtime_session_confidence")
    supports_resume = bool(capability.get("supports_resume"))
    if not session_id:
        return {
            "restore_ready": False,
            "restore_confidence": confidence,
            "restore_reason": "missing-session-id",
        }
    if not supports_resume:
        return {
            "restore_ready": False,
            "restore_confidence": confidence,
            "restore_reason": "runtime-does-not-support-resume",
        }
    if not _confidence_at_least(confidence, "high"):
        return {
            "restore_ready": False,
            "restore_confidence": confidence,
            "restore_reason": "confidence-below-high",
        }
    return {
        "restore_ready": True,
        "restore_confidence": confidence,
        "restore_reason": "session-id-and-runtime-resume-supported",
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
    parts = ["aura", "spawn", _shell_quote(seat), "--runtime", _shell_quote(runtime)]
    if fleet:
        parts.extend(["--fleet", _shell_quote(fleet)])
    if cwd:
        parts.extend(["--cwd", _shell_quote(cwd)])
    resume_template = capability.get("resume_command")
    if resume_template:
        parts.extend(["--command", _shell_quote(resume_template.format(session_id=session_id))])
    elif runtime in ("claude", "claude-code"):
        parts.extend(["--memory", _shell_quote(session_id)])
    else:
        return None
    return " ".join(parts)


def restore_plan_from_rows(rows: list[dict[str, Any]], capabilities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    plan_rows: list[dict[str, Any]] = []
    for row in rows:
        runtime = row.get("runtime")
        capability = capabilities.get(runtime or "", {})
        status = restore_status(row, capability)
        command = restore_command(row, capability)
        plan_rows.append({
            "seat": row.get("seat") or row.get("name"),
            "fleet": row.get("fleet"),
            "runtime": runtime,
            "terminal": row.get("terminal"),
            "session_id": row.get("session_id") or row.get("runtime_session_id"),
            "runtime_session_confidence": row.get("runtime_session_confidence"),
            "runtime_session_source": row.get("runtime_session_source"),
            "cwd": row.get("cwd") or row.get("workdir"),
            "restore_ready": status["restore_ready"],
            "restore_reason": status["restore_reason"],
            "restore_command": command,
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
