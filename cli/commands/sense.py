"""Sense inferred semantic state for a seat."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from commands import check
from lib import seat_schema, state, terminal_perception


def _state_from_output(output: str, mechanical_status: str, terminal: str) -> tuple[str, float, list[str], str]:
    """Compatibility wrapper around terminal_perception classification."""
    result = terminal_perception.classify_terminal_state(output, mechanical_status, terminal)
    return result["state"], result["confidence"], result["evidence"], result["next_action"]


def _root_dir() -> Path:
    return state.state_root()


def _write_sense_record(seat: str, record: dict) -> None:
    base = state.seat_dir(seat) / "sense"
    base.mkdir(parents=True, exist_ok=True)
    events = base / "events.jsonl"
    with events.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    (base / "latest.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_watch_latest(seat: str) -> dict | None:
    path = state.seat_dir(seat) / "watch" / "latest.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def run(args):
    """Return a compact semantic sense record for a seat."""
    lines = getattr(args, "lines", 80)
    question = getattr(args, "question", None) or "What is this seat doing and what should Aura do next?"
    requested_features = terminal_perception.normalize_feature_names(getattr(args, "features", None))
    check_args = argparse.Namespace(name=args.name, output=True, lines=lines)
    check_result = check.run(check_args)

    output = terminal_perception.normalize_output(check_result.get("output", "") if check_result.get("ok") else "")
    mechanical_status = check_result.get("status", "unknown")
    terminal = check_result.get("terminal", "missing")
    watch_latest = _read_watch_latest(args.name)
    watch_source = None
    if watch_latest:
        watch_source = {
            "stable_count": int(watch_latest.get("stable_count", 0) or 0),
            "silence_seconds": watch_latest.get("silence_seconds"),
            "output_changed": watch_latest.get("output_changed"),
        }

    perception = terminal_perception.perceive_terminal(
        {"output": output, "mechanical_status": mechanical_status, "terminal": terminal},
        {"question": question, "features": requested_features},
        watch=watch_source,
    )

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "ok": True,
        "schema": "aura.sense.v1",
        "type": "sense",
        "sense_id": f"sense_{now.replace(':', '').replace('-', '').replace('.', '')}_{args.name}",
        "seat": args.name,
        "name": args.name,
        "fleet": check_result.get("fleet"),
        "runtime": check_result.get("runtime"),
        "at": now,
        "source": {
            "capture_lines": lines,
            "mechanical_status": mechanical_status,
            "terminal": terminal,
            "provider": None,
            "watch": watch_source,
        },
        "question": question,
        "state": perception.get("state"),
        "confidence": perception.get("confidence"),
        "summary": _summary_for_state(args.name, perception.get("state", "unknown")),
        "evidence": perception.get("evidence", []),
        "next_action": perception.get("next_action"),
    }
    if requested_features:
        record["features"] = perception.get("features", {})
    if not check_result.get("ok"):
        record["ok"] = False
        record["error"] = check_result.get("error")
    record = seat_schema.enrich(record)
    _write_sense_record(args.name, record)
    return record


def _summary_for_state(seat: str, state: str) -> str:
    summaries = {
        "ready": f"{seat} appears ready for input.",
        "busy": f"{seat} appears to be working.",
        "stuck": f"{seat} may be stuck.",
        "done": f"{seat} appears to have completed work.",
        "needs_human": f"{seat} appears to need human input or approval.",
        "error": f"{seat} appears to have hit an error.",
        "unknown": f"{seat} state is unclear from available signals.",
    }
    return summaries.get(state, summaries["unknown"])
