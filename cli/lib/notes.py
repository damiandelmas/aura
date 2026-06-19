"""aura notes — read side of the annotation ledger.

Annotations are margin notes the tmux right-click resolver attaches to an exact
transcript message (``bin/tmux-aura-annotate``). They land append-only in
``~/.aura/notes/annotations.jsonl``, each pinned to a verifiable anchor
(``fleet:seat@session#N`` + ``content_sha256``). This module is the query half:
load, normalize across the legacy/new id formats, and project a stable view.

Resolution + drift checking live in the command, which reuses
``result_anchor`` (the same content-sha contract the anchors were minted with).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

from lib import state


def notes_path() -> Path:
    """The annotation ledger path. Honors AURA_NOTES_LEDGER (the writer's env)."""
    override = os.environ.get("AURA_NOTES_LEDGER")
    if override:
        return Path(override).expanduser()
    return state.state_root() / "notes" / "annotations.jsonl"


def iter_records() -> Iterator[dict[str, Any]]:
    path = notes_path()
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if isinstance(rec, dict):
            yield rec


def _meaningful(note: str | None) -> bool:
    """A note carries content only if printable chars remain.

    Empty annotate clicks capture a stray control byte (e.g. ESC ``\\x1b`` from
    pressing Escape), which whitespace-stripping alone would keep — so strip to
    printable characters before judging.
    """
    return bool("".join(ch for ch in (note or "") if ch.isprintable()).strip())


def _position(rec: dict[str, Any]) -> int | None:
    """The 1-based JSONL line (== Flex chunk N), across record formats.

    Prefers the explicit ``message_position``; else recovers it from a legacy
    ``message_id`` (``<sid>:transcript:N`` or the newer ``<sid>_N``).
    """
    pos = rec.get("message_position")
    if isinstance(pos, int):
        return pos
    mid = str(rec.get("message_id") or "")
    for sep in (":transcript:", "_"):
        if sep in mid:
            tail = mid.rsplit(sep, 1)[-1]
            if tail.isdigit():
                return int(tail)
    return None


def normalized(rec: dict[str, Any], index: int) -> dict[str, Any]:
    """Project a raw record to one format-agnostic shape."""
    sid = rec.get("session_id")
    pos = _position(rec)
    target = rec.get("target")
    have_anchor = bool(sid) and pos is not None
    sha = rec.get("content_sha256")
    return {
        "index": index,
        "ts": rec.get("ts"),
        "target": target,
        "note": rec.get("note") or "",
        "has_note": _meaningful(rec.get("note")),
        "anchor": f"{target or '?'}@{sid}#{pos}" if have_anchor else None,
        "flex_chunk_id": f"{sid}_{pos}" if have_anchor else None,
        "session_id": sid,
        "position": pos,
        "message_type": rec.get("message_type"),
        "content_sha256": sha,
        "sha8": (sha or "")[:8] or None,
        "resolved": rec.get("resolved"),
        "ambiguous": rec.get("ambiguous"),
        "picked": rec.get("picked"),
        "selected_text": rec.get("selected_text"),
        "cwd": rec.get("cwd"),
    }


def all_normalized() -> list[dict[str, Any]]:
    return [normalized(rec, i) for i, rec in enumerate(iter_records(), 1)]


def get(index: int) -> dict[str, Any] | None:
    for n in all_normalized():
        if n["index"] == index:
            return n
    return None
