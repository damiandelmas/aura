"""Sense inferred semantic state for a seat."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from commands import check
from lib import seat_schema, state


READY_MARKERS = ("READY", "ACK", "idle", "waiting for input")
BUSY_MARKERS = ("BUSY", "running", "processing", "working", "pytest", "Installing", "Building")
ERROR_MARKERS = ("ERROR", "Traceback", "Exception", "FAILED", "failed")
NEEDS_HUMAN_MARKERS = ("needs human", "permission", "approve", "confirm", "trust this", "Proceed?", "[y/N]")
DONE_MARKERS = ("DONE", "COMPLETE", "completed", "succeeded", "8 passed", "passed in")


def _state_from_output(output: str, mechanical_status: str, terminal: str) -> tuple[str, float, list[str], str]:
    evidence: list[str] = []
    if terminal == "missing" or mechanical_status in {"dead", "stopped"}:
        return "unknown", 0.55, ["terminal is missing or stopped"], "inspect"

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    tail = lines[-20:]
    joined = "\n".join(tail)

    def hit(markers: tuple[str, ...]) -> str | None:
        lowered = joined.lower()
        for marker in markers:
            if marker.lower() in lowered:
                for line in reversed(tail):
                    if marker.lower() in line.lower():
                        return line
        return None

    if line := hit(ERROR_MARKERS):
        evidence.append(line)
        return "error", 0.82, evidence, "escalate"
    if line := hit(NEEDS_HUMAN_MARKERS):
        evidence.append(line)
        return "needs_human", 0.78, evidence, "escalate"
    if line := hit(BUSY_MARKERS):
        evidence.append(line)
        return "busy", 0.70, evidence, "wait"
    if line := hit(DONE_MARKERS):
        evidence.append(line)
        return "done", 0.70, evidence, "capture"
    if line := hit(READY_MARKERS):
        evidence.append(line)
        return "ready", 0.72, evidence, "send"
    if tail:
        evidence.append(tail[-1])
        return "unknown", 0.45, evidence, "inspect"
    return "unknown", 0.35, ["no captured output"], "inspect"


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
    check_args = argparse.Namespace(name=args.name, output=True, lines=lines)
    check_result = check.run(check_args)

    output = check_result.get("output", "") if check_result.get("ok") else ""
    if isinstance(output, list):
        output = "\n".join(str(line) for line in output)
    elif not isinstance(output, str):
        output = str(output)
    mechanical_status = check_result.get("status", "unknown")
    terminal = check_result.get("terminal", "missing")
    state, confidence, evidence, next_action = _state_from_output(output, mechanical_status, terminal)
    watch_latest = _read_watch_latest(args.name)
    watch_source = None
    if watch_latest:
        stable_count = int(watch_latest.get("stable_count", 0) or 0)
        silence_seconds = watch_latest.get("silence_seconds")
        watch_source = {
            "stable_count": stable_count,
            "silence_seconds": silence_seconds,
            "output_changed": watch_latest.get("output_changed"),
        }
        if terminal == "alive" and stable_count >= 3 and state in {"busy", "unknown"}:
            state = "stuck"
            confidence = max(confidence, 0.76)
            evidence.append(f"watch output stable for {stable_count} samples")
            next_action = "inspect"

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
        "state": state,
        "confidence": confidence,
        "summary": _summary_for_state(args.name, state),
        "evidence": evidence,
        "next_action": next_action,
    }
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
