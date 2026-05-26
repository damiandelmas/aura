"""Log dumb terminal posture for UI polling."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from commands import check, list as list_cmd
from lib import diagnostic_cache, seat_schema, state, terminal_posture


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_output(output: str) -> str:
    return hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest()


def _posture_dir(seat: str) -> Path:
    return state.seat_dir(seat) / "posture"


def _latest_path(seat: str) -> Path:
    return _posture_dir(seat) / "latest.json"


def _global_dir() -> Path:
    return state.state_root() / "terminal-posture"


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def _write_seat_record(seat: str, record: dict) -> None:
    base = _posture_dir(seat)
    _append_jsonl(base / "events.jsonl", record)
    _write_json(base / "latest.json", record)


def _target_key(record: dict) -> str:
    fleet = record.get("fleet")
    seat = record.get("seat") or record.get("name")
    return f"{fleet}:{seat}" if fleet and seat else str(seat or record.get("target") or "unknown")


def _write_global_record(record: dict) -> None:
    base = _global_dir()
    _append_jsonl(base / "events.jsonl", record)
    latest_path = base / "latest.json"
    latest = _read_json(latest_path) or {
        "schema": "aura.terminal_posture_latest.v1",
        "type": "terminal_posture_latest",
        "targets": {},
    }
    latest["updated_at"] = record.get("at")
    latest.setdefault("targets", {})[_target_key(record)] = record
    _write_json(latest_path, latest)


def _check_args(name: str, lines: int) -> argparse.Namespace:
    return argparse.Namespace(name=name, output=True, lines=lines, format="text")


def sample(args) -> dict:
    """Capture one seat, classify posture, and persist latest/events records."""
    seat = args.name
    lines = int(getattr(args, "lines", 80) or 80)
    now = _now()

    check_result = check.run(_check_args(seat, lines))
    output = terminal_posture.output_to_text(check_result.get("output") if check_result.get("ok") else "")
    output_hash = _hash_output(output)

    previous = _read_json(_latest_path(seat))
    previous_hash = previous.get("source", {}).get("output_hash") if previous else None
    previous_classifier = previous.get("source", {}).get("classifier_version") if previous else None
    output_changed = previous_hash != output_hash
    classifier_changed = previous_classifier != terminal_posture.CLASSIFIER_VERSION
    posture = terminal_posture.classify_delta(
        previous_hash=previous_hash,
        output_hash=output_hash,
    )

    record = {
        "ok": bool(check_result.get("ok")),
        "schema": "aura.terminal_posture.v1",
        "type": "terminal_posture",
        "posture_id": f"posture_{now.replace(':', '').replace('-', '').replace('.', '')}_{seat}",
        "target": seat,
        "seat": check_result.get("name") or seat,
        "name": check_result.get("name") or seat,
        "fleet": check_result.get("fleet"),
        "runtime": check_result.get("runtime"),
        "at": now,
        "capture_state": diagnostic_cache.capture_state(check_result),
        "source": {
            "capture_lines": lines,
            "mechanical_status": check_result.get("status", "unknown"),
            "terminal": check_result.get("terminal", "missing"),
            "previous_output_hash": previous_hash,
            "output_hash": output_hash,
            "output_changed": output_changed,
            "classifier_version": terminal_posture.CLASSIFIER_VERSION,
            "classifier_changed": classifier_changed,
            "provider": "snapshot_delta",
        },
        "posture": posture,
        "state": posture.get("state", "unknown"),
        "confidence": posture.get("confidence", 0.0),
        "explanation": posture.get("explanation", ""),
        "reused": False,
    }
    record.update(diagnostic_cache.freshness_metadata(
        cache_key=f"posture:{seat}",
        at=now,
        ttl_seconds=diagnostic_cache.posture_ttl_seconds(),
        checked_at=now,
    ))
    if not check_result.get("ok"):
        record["error"] = check_result.get("error")

    record = seat_schema.enrich(record)
    _write_seat_record(seat, record)
    _write_global_record(record)
    return record


def sample_fleet(args) -> dict:
    fleet = getattr(args, "fleet", None)
    inventory = list_cmd.run(argparse.Namespace(fleet=fleet, status=None, mode=None, include_hidden=False))
    rows = inventory.get("rows", inventory) if isinstance(inventory, dict) else inventory
    samples = []
    for row in rows:
        if not row.get("registered"):
            continue
        seat = row.get("seat") or row.get("name")
        if not seat:
            continue
        target = row.get("target") or row.get("seat_ref") or (
            f"{row.get('fleet')}:{seat}" if row.get("fleet") else seat
        )
        samples.append(sample(argparse.Namespace(
            name=target,
            lines=getattr(args, "lines", 80),
        )))

    now = _now()
    summary: dict[str, int] = {}
    for record in samples:
        posture_state = record.get("state", "unknown")
        summary[posture_state] = summary.get(posture_state, 0) + 1
    record = {
        "ok": True,
        "schema": "aura.terminal_posture_fleet.v1",
        "type": "terminal_posture_fleet",
        "posture_id": f"posture_fleet_{now.replace(':', '').replace('-', '').replace('.', '')}_{fleet or 'all'}",
        "fleet": fleet,
        "at": now,
        "count": len(samples),
        "summary": summary,
        "samples": samples,
    }
    if fleet:
        base = state.fleet_dir(fleet) / "posture"
        _append_jsonl(base / "events.jsonl", record)
        _write_json(base / "latest.json", record)
    return record


def run(args) -> dict:
    if getattr(args, "fleet", None):
        return sample_fleet(args)
    if not getattr(args, "name", None):
        return {"ok": False, "error": "posture requires a seat name or --fleet"}
    return sample(args)
