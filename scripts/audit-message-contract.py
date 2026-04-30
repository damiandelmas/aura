#!/usr/bin/env python3
"""Audit active skill docs that teach Aura messaging without the message contract."""

from __future__ import annotations

from pathlib import Path
import sys


ROOTS = [
    Path.home() / ".codex" / "skills",
    Path("/home/axp/projects/flexgraph/chatbot/.codex/skills"),
]

MESSAGE_PATTERNS = (
    "aura send",
    "aura broadcast",
    "aura discord send",
)

CONTRACT_PATTERNS = (
    "message-contract.md",
    "aura-send-message",
)

SKIP_PARTS = {
    "runs",
    "__pycache__",
}

TEXT_SUFFIXES = {".md", ".sh", ".jsonl"}


def active_skill_file(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    parts = set(path.parts)
    if SKIP_PARTS & parts:
        return False
    return True


def needs_contract(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    lower = text.lower()
    mentions_message = any(pattern in lower for pattern in MESSAGE_PATTERNS)
    mentions_contract = any(pattern in text for pattern in CONTRACT_PATTERNS)
    return mentions_message and not mentions_contract


def main() -> int:
    offenders: list[Path] = []
    for root in ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and active_skill_file(path) and needs_contract(path):
                offenders.append(path)
    for path in offenders:
        print(path)
    if offenders:
        print(f"message contract audit failed: {len(offenders)} active files", file=sys.stderr)
        return 1
    print("message contract audit ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
