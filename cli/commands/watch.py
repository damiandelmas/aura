"""Watch a seat by repeatedly capturing/checking and sensing state."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from commands import check, sense
from lib import seat_schema, state


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _output_to_text(output) -> str:
    if isinstance(output, list):
        return "\n".join(str(line) for line in output)
    if output is None:
        return ""
    return str(output)


def _hash_output(output: str) -> str:
    return hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest()


def _watch_dir(seat: str) -> Path:
    return state.seat_dir(seat) / "watch"


def _latest_path(seat: str) -> Path:
    return _watch_dir(seat) / "latest.json"


def _read_latest(seat: str) -> dict | None:
    path = _latest_path(seat)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_watch_record(seat: str, record: dict) -> None:
    base = _watch_dir(seat)
    base.mkdir(parents=True, exist_ok=True)
    with (base / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    (base / "latest.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seconds_since(iso_timestamp: str | None, now_iso: str) -> float | None:
    if not iso_timestamp:
        return None
    try:
        start = datetime.fromisoformat(iso_timestamp)
        end = datetime.fromisoformat(now_iso)
        return max(0.0, (end - start).total_seconds())
    except ValueError:
        return None


def sample(args) -> dict:
    """Take one watch sample for a seat and persist watch/latest state."""
    lines = getattr(args, "lines", 80)
    now = _now()
    seat = args.name

    check_args = argparse.Namespace(name=seat, output=True, lines=lines)
    check_result = check.run(check_args)
    output = _output_to_text(check_result.get("output", "") if check_result.get("ok") else "")
    output_hash = _hash_output(output)

    previous = _read_latest(seat)
    previous_hash = previous.get("output_hash") if previous else None
    output_changed = previous_hash != output_hash
    stable_count = 0 if output_changed else int(previous.get("stable_count", 0)) + 1
    last_change_at = now if output_changed else previous.get("last_change_at", now)
    silence_seconds = _seconds_since(last_change_at, now)

    sense_record = None
    if not getattr(args, "no_sense", False):
        sense_args = argparse.Namespace(
            name=seat,
            lines=lines,
            question=getattr(args, "question", None),
            features=getattr(args, "features", None),
        )
        sense_record = sense.run(sense_args)

    record = {
        "ok": bool(check_result.get("ok")),
        "schema": "aura.watch.v1",
        "type": "watch",
        "watch_id": f"watch_{now.replace(':', '').replace('-', '').replace('.', '')}_{seat}",
        "seat": seat,
        "name": seat,
        "fleet": check_result.get("fleet"),
        "runtime": check_result.get("runtime"),
        "at": now,
        "source": {
            "capture_lines": lines,
            "mechanical_status": check_result.get("status", "unknown"),
            "terminal": check_result.get("terminal", "missing"),
            "provider": None,
        },
        "output_hash": output_hash,
        "output_changed": output_changed,
        "stable_count": stable_count,
        "last_change_at": last_change_at,
        "silence_seconds": silence_seconds,
        "sense": sense_record,
    }
    if not check_result.get("ok"):
        record["error"] = check_result.get("error")

    record = seat_schema.enrich(record)
    _write_watch_record(seat, record)
    return record


def run(args):
    """Watch a seat once or continuously until interrupted."""
    if getattr(args, "once", False):
        return sample(args)

    interval = max(float(getattr(args, "interval", 5)), 0.1)
    latest = None
    try:
        while True:
            latest = sample(args)
            time.sleep(interval)
    except KeyboardInterrupt:
        if latest is not None:
            latest = dict(latest)
            latest["interrupted"] = True
            return latest
        return {"ok": False, "error": "watch interrupted before first sample", "seat": args.name}
