"""Terminal perception helpers for Aura sense/watch.

This module is intentionally pure: callers pass captured text, mechanical
status, terminal state, optional watch evidence, and requested feature names.
It returns structured semantic state without reading or writing terminals.
"""

from __future__ import annotations

from typing import Any

READY_MARKERS = ("READY", "ACK", "idle", "waiting for input")
BUSY_MARKERS = ("BUSY", "running", "processing", "working", "pytest", "Installing", "Building")
ERROR_MARKERS = ("ERROR", "Traceback", "Exception", "FAILED", "failed")
NEEDS_HUMAN_MARKERS = ("needs human", "permission", "approve", "confirm", "trust this", "Proceed?", "[y/N]")
DONE_MARKERS = ("DONE", "COMPLETE", "completed", "succeeded", "8 passed", "passed in")

SUPPORTED_FEATURES = {
    "state",
    "confidence",
    "evidence",
    "next_action",
    "last_visible_line",
    "recent_error",
    "awaiting_approval",
    "blocked_on",
    "received_text",
    "output_changed",
    "stable_count",
    "silence_seconds",
}


def normalize_output(output: str | list[Any] | None) -> str:
    if output is None:
        return ""
    if isinstance(output, list):
        return "\n".join(str(line) for line in output)
    if isinstance(output, str):
        return output
    return str(output)


def normalize_feature_names(features: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if not features:
        return []
    if isinstance(features, str):
        raw = features.split(",")
    else:
        raw = list(features)
    seen: set[str] = set()
    out: list[str] = []
    for feature in raw:
        name = str(feature).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _tail_lines(output: str, n: int = 20) -> list[str]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-n:]


def _hit(tail: list[str], markers: tuple[str, ...]) -> str | None:
    joined = "\n".join(tail).lower()
    for marker in markers:
        if marker.lower() not in joined:
            continue
        for line in reversed(tail):
            if marker.lower() in line.lower():
                return line
    return None


def classify_terminal_state(
    output: str | list[Any] | None,
    mechanical_status: str = "unknown",
    terminal: str = "missing",
    watch: dict | None = None,
) -> dict[str, Any]:
    text = normalize_output(output)
    evidence: list[str] = []
    if terminal == "missing" or mechanical_status in {"dead", "stopped"}:
        return {"state": "unknown", "confidence": 0.55, "evidence": ["terminal is missing or stopped"], "next_action": "inspect"}

    tail = _tail_lines(text)
    if line := _hit(tail, ERROR_MARKERS):
        evidence.append(line)
        state = "error"
        confidence = 0.82
        next_action = "escalate"
    elif line := _hit(tail, NEEDS_HUMAN_MARKERS):
        evidence.append(line)
        state = "needs_human"
        confidence = 0.78
        next_action = "escalate"
    elif line := _hit(tail, BUSY_MARKERS):
        evidence.append(line)
        state = "busy"
        confidence = 0.70
        next_action = "wait"
    elif line := _hit(tail, DONE_MARKERS):
        evidence.append(line)
        state = "done"
        confidence = 0.70
        next_action = "capture"
    elif line := _hit(tail, READY_MARKERS):
        evidence.append(line)
        state = "ready"
        confidence = 0.72
        next_action = "send"
    elif tail:
        evidence.append(tail[-1])
        state = "unknown"
        confidence = 0.45
        next_action = "inspect"
    else:
        evidence.append("no captured output")
        state = "unknown"
        confidence = 0.35
        next_action = "inspect"

    if watch:
        stable_count = int(watch.get("stable_count", 0) or 0)
        if terminal == "alive" and stable_count >= 3 and state in {"busy", "unknown"}:
            state = "stuck"
            confidence = max(confidence, 0.76)
            evidence.append(f"watch output stable for {stable_count} samples")
            next_action = "inspect"

    return {"state": state, "confidence": confidence, "evidence": evidence, "next_action": next_action}


def extract_features(
    output: str | list[Any] | None,
    features: list[str] | tuple[str, ...] | str | None,
    classification: dict[str, Any],
    watch: dict | None = None,
) -> dict[str, Any]:
    requested = normalize_feature_names(features)
    text = normalize_output(output)
    tail = _tail_lines(text)
    recent_error = _hit(tail, ERROR_MARKERS)
    awaiting_approval = _hit(tail, NEEDS_HUMAN_MARKERS)
    received = _hit(tail, ("ACK", "SEEN", "[AURA MESSAGE"))

    values: dict[str, Any] = {}
    for feature in requested:
        if feature == "state":
            values[feature] = classification.get("state")
        elif feature == "confidence":
            values[feature] = classification.get("confidence")
        elif feature == "evidence":
            values[feature] = classification.get("evidence", [])
        elif feature == "next_action":
            values[feature] = classification.get("next_action")
        elif feature == "last_visible_line":
            values[feature] = tail[-1] if tail else None
        elif feature == "recent_error":
            values[feature] = recent_error
        elif feature == "awaiting_approval":
            values[feature] = bool(awaiting_approval)
        elif feature == "blocked_on":
            if awaiting_approval:
                values[feature] = "human_approval"
            elif recent_error:
                values[feature] = "error"
            elif classification.get("state") == "stuck":
                values[feature] = "stable_output"
            else:
                values[feature] = None
        elif feature == "received_text":
            values[feature] = received
        elif feature == "output_changed":
            values[feature] = None if watch is None else watch.get("output_changed")
        elif feature == "stable_count":
            values[feature] = None if watch is None else watch.get("stable_count")
        elif feature == "silence_seconds":
            values[feature] = None if watch is None else watch.get("silence_seconds")
        else:
            values[feature] = {"unsupported": True}
    return values


def perceive_terminal(
    capture: dict,
    request: dict | None = None,
    watch: dict | None = None,
) -> dict[str, Any]:
    request = request or {}
    output = capture.get("output", "")
    classification = classify_terminal_state(
        output,
        mechanical_status=capture.get("mechanical_status") or capture.get("status", "unknown"),
        terminal=capture.get("terminal", "missing"),
        watch=watch,
    )
    features = extract_features(output, request.get("features"), classification, watch=watch)
    return {**classification, "features": features}
