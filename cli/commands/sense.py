"""Sense inferred semantic state for a seat."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from commands import check
from lib import local_llm, seat_schema, state, terminal_perception, terminal_semantic_sense


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


def _sense_mode(args) -> str:
    mode = getattr(args, "sense_mode", None) or os.environ.get("AURA_SENSE_MODE", "auto")
    mode = str(mode).strip().lower()
    if mode not in {"auto", "llm", "heuristic"}:
        return "auto"
    return mode


def _model(args) -> str:
    return (
        getattr(args, "model", None)
        or os.environ.get("AURA_SENSE_MODEL")
        or local_llm.DEFAULT_OLLAMA_MODEL
    )


def _ollama_host(args) -> str:
    return (
        getattr(args, "ollama_host", None)
        or os.environ.get("AURA_OLLAMA_HOST")
        or local_llm.DEFAULT_OLLAMA_HOST
    )


def _llm_timeout(args) -> float:
    value = getattr(args, "llm_timeout", None) or os.environ.get("AURA_SENSE_TIMEOUT") or 8.0
    try:
        return max(0.1, float(value))
    except (TypeError, ValueError):
        return 8.0


def _perceive(capture: dict, request: dict, watch: dict | None, args) -> tuple[dict, dict]:
    heuristic = terminal_perception.perceive_terminal(capture, request, watch=watch)
    mode = _sense_mode(args)
    metadata = {
        "backend": "heuristic",
        "mode": mode,
        "fallback_used": False,
        "llm": None,
    }
    if mode == "heuristic":
        return heuristic, metadata

    model = _model(args)
    host = _ollama_host(args)
    timeout = _llm_timeout(args)
    metadata["llm"] = {"provider": "ollama", "model": model, "host": host, "timeout": timeout}
    try:
        perception = terminal_semantic_sense.perceive_terminal(
            capture,
            request,
            watch=watch,
            model=model,
            host=host,
            timeout=timeout,
        )
        metadata["backend"] = "llm"
        return perception, metadata
    except Exception as exc:
        metadata["llm_error"] = str(exc)
        if mode == "llm":
            raise
        metadata["fallback_used"] = True
        return heuristic, metadata


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

    capture = {"output": output, "mechanical_status": mechanical_status, "terminal": terminal}
    request = {"question": question, "features": requested_features}
    try:
        perception, sense_metadata = _perceive(capture, request, watch_source, args)
    except Exception as exc:
        perception = {
            "state": "error",
            "confidence": 0.0,
            "summary": "LLM sense failed.",
            "evidence": [str(exc)],
            "next_action": "escalate",
            "features": {},
        }
        sense_metadata = {
            "backend": "llm",
            "mode": _sense_mode(args),
            "fallback_used": False,
            "llm": {
                "provider": "ollama",
                "model": _model(args),
                "host": _ollama_host(args),
                "timeout": _llm_timeout(args),
            },
            "llm_error": str(exc),
        }

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
            "provider": sense_metadata.get("backend"),
            "sense_backend": sense_metadata.get("backend"),
            "sense_mode": sense_metadata.get("mode"),
            "fallback_used": sense_metadata.get("fallback_used"),
            "llm": sense_metadata.get("llm"),
            "watch": watch_source,
        },
        "question": question,
        "state": perception.get("state"),
        "confidence": perception.get("confidence"),
        "summary": perception.get("summary") or _summary_for_state(args.name, perception.get("state", "unknown")),
        "evidence": perception.get("evidence", []),
        "next_action": perception.get("next_action"),
    }
    if sense_metadata.get("llm_error"):
        record["source"]["llm_error"] = sense_metadata["llm_error"]
        if sense_metadata.get("mode") == "llm":
            record["ok"] = False
            record["error"] = sense_metadata["llm_error"]
    if requested_features:
        record["features"] = perception.get("features", {})
    for key in ("role", "current_task", "last_meaningful_event", "blockers"):
        if key in perception:
            record[key] = perception.get(key)
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
