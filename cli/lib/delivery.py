"""Portable delivery records for terminal-backed aura sends."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from lib import state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_message_id() -> str:
    return f"aura-msg-{uuid.uuid4().hex[:12]}"


def new_delivery_id() -> str:
    return f"aura-delivery-{uuid.uuid4().hex[:12]}"


def body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def default_dedupe_key(target: str, sender: str, body: str) -> str:
    return f"{target}:{sender}:{body_hash(body)}"


def render_envelope(message_id: str, sender: str, body: str, sent_at: str | None = None) -> str:
    sent_at = sent_at or now_iso()
    return (
        f"[AURA MESSAGE id={message_id} from={sender} sent_at={sent_at}]\n"
        f"{body}\n"
        f"[/AURA MESSAGE]"
    )


def delivery_log_path():
    return state.delivery_log_path()


def append_record(record: dict) -> dict:
    log_path = delivery_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def new_delivery_record(
    *,
    delivery_type: str,
    sender: str,
    target: str,
    payload_hash: str | None = None,
    backend: str | None = None,
    backend_ref: str | None = None,
    dedupe_key: str | None = None,
    message_id: str | None = None,
    state: str = "pending",
    **fields: Any,
) -> dict:
    """Build a v2 delivery record without writing it.

    Callers own sequencing. This helper only normalizes shape so send,
    write, events, and sidecars produce comparable evidence.
    """

    now = now_iso()
    delivery_id = fields.pop("delivery_id", None) or new_delivery_id()
    message_id = message_id or fields.pop("message_id", None) or new_message_id()
    record = {
        "schema": "aura.delivery.v2",
        "type": delivery_type,
        "delivery_id": delivery_id,
        "message_id": message_id,
        "delivery_type": delivery_type,
        "sender": sender,
        "target": target,
        "state": state,
        "created_at": now,
        "updated_at": now,
        "attempts": [],
    }
    if payload_hash is not None:
        record["payload_hash"] = payload_hash
        record["body_hash"] = payload_hash
    if backend is not None:
        record["backend"] = backend
    if backend_ref is not None:
        record["backend_ref"] = backend_ref
    if dedupe_key is not None:
        record["dedupe_key"] = dedupe_key
    record.update(fields)
    return record


def append_attempt(record: dict, *, state: str, evidence: dict | None = None) -> dict:
    attempts = list(record.get("attempts") or [])
    attempts.append({
        "at": now_iso(),
        "state": state,
        "evidence": evidence or {},
    })
    record["attempts"] = attempts
    record["updated_at"] = now_iso()
    return record


def finalize_record(record: dict, *, state: str, error: str | None = None, **fields: Any) -> dict:
    record["state"] = state
    record["updated_at"] = now_iso()
    if error is not None:
        record["error"] = error
    record.update(fields)
    return record


def append_final_record(record: dict, *, state: str, error: str | None = None, **fields: Any) -> dict:
    return append_record(finalize_record(record, state=state, error=error, **fields))


def iter_records(limit: int | None = None):
    log_path = delivery_log_path()
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if limit is not None:
        lines = lines[-limit:]
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def recent_records(*, target: str | None = None, limit: int = 50) -> list[dict]:
    records = iter_records()
    if target is not None:
        records = [record for record in records if record.get("target") == target]
    if limit is not None:
        records = records[-limit:]
    return records


def last_state_for_target(target: str) -> dict | None:
    for record in reversed(iter_records()):
        if record.get("target") == target and record.get("state"):
            return record
    return None


def find_by_dedupe_key(dedupe_key: str) -> dict | None:
    for record in reversed(iter_records()):
        if record.get("dedupe_key") == dedupe_key:
            return record
    return None


def has_successful_dedupe(target: str, dedupe_key: str) -> str | None:
    for record in reversed(iter_records()):
        if record.get("target") != target:
            continue
        if record.get("dedupe_key") != dedupe_key:
            continue
        if record.get("state") in {"delivered", "attempted"}:
            return record.get("message_id")
    return None
