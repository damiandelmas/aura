"""Snapshot-delta terminal posture for UI logging."""

from __future__ import annotations

import re


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CLASSIFIER_VERSION = "2026-05-21.snapshot-delta-v1"
VALID_STATES = {"idle", "working", "unknown"}


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def output_to_text(output) -> str:
    if isinstance(output, list):
        return "\n".join(str(line) for line in output)
    if output is None:
        return ""
    return str(output)


def classify_delta(*, previous_hash: str | None, output_hash: str) -> dict:
    """Classify posture from whether terminal output changed since last sample."""
    if not previous_hash:
        return {
            "state": "unknown",
            "confidence": 0.5,
            "explanation": "No previous terminal snapshot exists.",
        }
    if previous_hash != output_hash:
        return {
            "state": "working",
            "confidence": 0.9,
            "explanation": "Terminal output changed since the previous snapshot.",
        }
    return {
        "state": "idle",
        "confidence": 0.85,
        "explanation": "Terminal output did not change since the previous snapshot.",
    }
