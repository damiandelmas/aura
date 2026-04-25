"""Watch a seat by repeatedly capturing/checking and sensing state."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from commands import check, list as list_cmd, sense
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


def _write_fleet_watch_record(fleet: str, record: dict) -> None:
    base = state.fleet_dir(fleet) / "watch"
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


def sample_fleet(args) -> dict:
    """Take one watch sample for every listed seat in a fleet."""
    fleet = getattr(args, "fleet", None)
    rows = list_cmd.run(argparse.Namespace(fleet=fleet, status=None, mode=None))
    samples = []
    for row in rows:
        if not row.get("registered"):
            continue
        seat = row.get("seat") or row.get("name")
        if not seat:
            continue
        sample_args = argparse.Namespace(
            name=seat,
            lines=getattr(args, "lines", 80),
            question=getattr(args, "question", None),
            features=getattr(args, "features", None),
            no_sense=getattr(args, "no_sense", False),
        )
        samples.append(sample(sample_args))
    now = _now()
    summary = _summarize_samples(samples)
    record = {
        "ok": True,
        "schema": "aura.watch_fleet.v1",
        "type": "watch_fleet",
        "watch_id": f"watch_fleet_{now.replace(':', '').replace('-', '').replace('.', '')}_{fleet}",
        "fleet": fleet,
        "at": now,
        "count": len(samples),
        "summary": summary,
        "samples": samples,
    }
    if fleet:
        _write_fleet_watch_record(fleet, record)
    return record


def _sample_state(sample_record: dict) -> str:
    if not sample_record.get("ok"):
        return "error"
    sense_record = sample_record.get("sense") or {}
    return sense_record.get("state") or sample_record.get("source", {}).get("mechanical_status") or "unknown"


def _summarize_samples(samples: list[dict]) -> dict:
    summary: dict[str, int] = {}
    for sample_record in samples:
        key = _sample_state(sample_record)
        summary[key] = summary.get(key, 0) + 1
    return summary


def sample_fleet_bounded(args) -> dict:
    """Take a finite number of fleet samples and return the latest plus history."""
    iterations = int(getattr(args, "iterations", 0) or 0)
    if iterations <= 0:
        return {"ok": False, "error": "watch --fleet --iterations requires a positive integer", "fleet": args.fleet}

    interval = max(float(getattr(args, "interval", 5)), 0.0)
    history = []
    latest = None
    for index in range(iterations):
        latest = sample_fleet(args)
        history.append({
            "iteration": index + 1,
            "at": latest.get("at"),
            "count": latest.get("count", 0),
            "summary": latest.get("summary", {}),
        })
        if index < iterations - 1:
            time.sleep(interval)

    latest = dict(latest or {})
    latest["iterations"] = iterations
    latest["history"] = history
    if args.fleet:
        _write_fleet_watch_record(args.fleet, latest)
    return latest


def run(args):
    """Watch a seat once or continuously until interrupted."""
    if getattr(args, "fleet", None):
        if getattr(args, "once", False):
            return sample_fleet(args)
        if getattr(args, "iterations", None):
            return sample_fleet_bounded(args)
        return {"ok": False, "error": "watch --fleet requires --once or --iterations N", "fleet": args.fleet}
    if not getattr(args, "name", None):
        return {"ok": False, "error": "watch requires a seat name or --fleet"}
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
