"""Portable delivery records for terminal-backed aura sends."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DELIVERY_LOG = Path(os.environ.get("AURA_DELIVERY_LOG", "/tmp/aura/deliveries.jsonl"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_message_id() -> str:
    return f"aura-msg-{uuid.uuid4().hex[:12]}"


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


def append_record(record: dict) -> dict:
    DELIVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DELIVERY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def iter_records(limit: int | None = None):
    if not DELIVERY_LOG.exists():
        return []
    lines = DELIVERY_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    if limit is not None:
        lines = lines[-limit:]
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def has_successful_dedupe(target: str, dedupe_key: str) -> str | None:
    for record in reversed(iter_records()):
        if record.get("target") != target:
            continue
        if record.get("dedupe_key") != dedupe_key:
            continue
        if record.get("state") in {"delivered", "attempted"}:
            return record.get("message_id")
    return None
