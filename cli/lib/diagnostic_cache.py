"""Shared diagnostic cache freshness metadata."""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone

from lib import state


POSTURE_TTL_ENV = "AURA_POSTURE_TTL_SECONDS"
SENSE_TTL_ENV = "AURA_SENSE_TTL_SECONDS"
DEFAULT_POSTURE_TTL_SECONDS = 120
DEFAULT_SENSE_TTL_SECONDS = 300


def ttl_seconds(env_var: str, default: int) -> int:
    value = os.environ.get(env_var)
    try:
        ttl = int(value) if value is not None else int(default)
    except (TypeError, ValueError):
        ttl = int(default)
    return max(0, ttl)


def posture_ttl_seconds() -> int:
    return ttl_seconds(POSTURE_TTL_ENV, DEFAULT_POSTURE_TTL_SECONDS)


def sense_ttl_seconds() -> int:
    return ttl_seconds(SENSE_TTL_ENV, DEFAULT_SENSE_TTL_SECONDS)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def freshness_metadata(
    *,
    cache_key: str,
    at: str | None,
    ttl_seconds: int,
    checked_at: str | None = None,
) -> dict:
    checked_at = checked_at or now_iso()
    started = _parse_iso(at)
    checked = _parse_iso(checked_at)
    age_seconds = None
    freshness = "unknown"
    if started and checked:
        age_seconds = max(0.0, (checked - started).total_seconds())
        freshness = "fresh" if age_seconds <= ttl_seconds else "stale"

    return {
        "freshness": freshness,
        "stale": freshness == "stale",
        "age_seconds": age_seconds,
        "ttl_seconds": ttl_seconds,
        "cache_owner": "aura",
        "cache_key": cache_key,
        "freshness_checked_at": checked_at,
    }


def capture_state(check_result: dict | None) -> str:
    if not isinstance(check_result, dict):
        return "unavailable"
    terminal = check_result.get("terminal")
    status = check_result.get("status")
    if terminal == "alive" or status in {"alive", "running"}:
        return "live"
    if terminal in {"missing", "dead", "killed"} or status in {"dead", "stopped"}:
        return "dead"
    if check_result.get("ok") is False:
        return "unavailable"
    return "unknown"


def invalidate(
    target: str,
    *,
    reason: str,
    source_command: str,
    caches: tuple[str, ...] = ("posture", "sense", "watch"),
    at: str | None = None,
    evidence: dict | None = None,
) -> dict:
    """Record that Aura-owned diagnostic cache entries are no longer authoritative."""
    record = {
        "schema": "aura.diagnostic_cache_invalidation.v1",
        "type": "diagnostic_cache_invalidation",
        "target": target,
        "at": at or now_iso(),
        "reason": reason,
        "source_command": source_command,
        "cache_owner": "aura",
        "caches": list(caches),
    }
    if evidence:
        record["evidence"] = evidence
    path = state.seat_dir(target) / "diagnostics" / "cache-invalidations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return {**record, "path": str(path)}
