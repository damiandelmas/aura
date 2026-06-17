"""Latest-assistant result anchor — a citation pointer resolved from OUTSIDE the seat.

The idle-edge watcher can optionally stamp this on its report so a result pointer
rides the bus for chaining / provenance / honest-checkmark — recovering the one
capability the sensed-completion path otherwise drops, with NONE of the rejected
machinery (no Stop hook, no task token, no settle-race).

Why the idle-edge is a *better* anchor trigger than a Stop hook: by the time the
pane is debounce-idle, the seat's final message is already flushed to disk, so
reading the transcript from outside the seat sidesteps the flush-timing bug a hook
had to "settle" for. The anchor stays demoted to a memory/citation primitive — it is
never the done-signal; completion is sensed, the result is merely referenced.

Runtime-agnostic: reads the session transcript JSONL (codex ``response_item``
events; claude-code ``user``/``assistant`` events) and returns the last assistant
message's position + content sha. Read-only; never mutates anything.

The position is **Flex's chunk number** — the 1-based line index of the record in
the session JSONL — because that is exactly how Flex keys a message:
``chunk_id = f"{session_id}_{line_num}"`` (claude_code/compile/worker.py) and the
same for codex. So the anchor IS a Flex chunk id by construction: mint it locally by
line number (the index lags, so we can't query Flex at mint time, but the rule is
just the line number and can't drift), and resolve it later by handing the id back
to Flex (`flex core search`). One identity across the watcher, the click resolver,
and the search substrate.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


def content_sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _codex_text(payload: dict) -> tuple[str | None, str]:
    if payload.get("type") != "message":
        return None, ""
    role = payload.get("role")
    parts = []
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"output_text", "input_text"}:
                parts.append(str(item.get("text") or ""))
    text = "\n".join(p for p in parts if p).strip()
    if not text:
        return None, ""
    if role == "assistant":
        return "assistant", text
    if role == "user":
        return "user_prompt", text
    return str(role or "message"), text


def _claude_text(event: dict) -> tuple[str | None, str]:
    row_type = event.get("type")
    if row_type not in {"user", "assistant"} or event.get("isSidechain"):
        return None, ""
    content = (event.get("message") or {}).get("content")
    parts = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
    text = "\n".join(p for p in parts if p).strip()
    if not text:
        return None, ""
    return ("assistant" if row_type == "assistant" else "user_prompt"), text


def transcript_rows(path: Path) -> list[dict[str, Any]]:
    """Content-bearing rows, each tagged with its 1-based JSONL line number.

    ``position`` is the absolute line number (every line counts, blanks and
    unparseable lines included), matching Flex's ``enumerate(lines, 1)`` so the
    position equals Flex's chunk number for that record.
    """
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, 1):  # 1-based line number == Flex chunk N
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "response_item":
                    row_type, text = _codex_text(event.get("payload") or {})
                else:
                    row_type, text = _claude_text(event)
                if not row_type or not text:
                    continue
                rows.append({"position": line_no, "type": row_type, "content": text})
    except OSError:
        return []
    return rows


def discover_transcript(row: dict[str, Any], session_id: str) -> Path | None:
    """Find the session transcript: a direct path on the row, else codex/claude layouts."""
    evidence = row.get("runtime_session_evidence")
    if isinstance(evidence, dict) and evidence.get("transcript_path"):
        direct = Path(str(evidence["transcript_path"])).expanduser()
        if direct.exists():
            return direct
    for key in ("transcript_path", "runtime_transcript_path"):
        if row.get(key):
            direct = Path(str(row[key])).expanduser()
            if direct.exists():
                return direct
    if not session_id:
        return None

    roots: list[Path] = []
    for key in ("codex_package_codex_home", "native_state_ref", "runtime_home"):
        if row.get(key):
            roots.append(Path(str(row[key])).expanduser())
    roots.append(Path.home() / ".codex")
    roots.append(Path.home() / ".claude")

    matches: list[Path] = []
    for root in roots:
        sessions = root / "sessions"  # codex: sessions/**/*<sid>*.jsonl
        if sessions.exists():
            try:
                matches.extend(sessions.glob(f"**/*{session_id}*.jsonl"))
            except OSError:
                pass
        projects = root / "projects"  # claude-code: projects/<cwd>/<sid>.jsonl
        if projects.exists():
            try:
                matches.extend(projects.glob(f"*/{session_id}.jsonl"))
            except OSError:
                pass
    if not matches:
        return None
    matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return matches[0]


def latest_assistant_anchor(row: dict[str, Any] | None, seat_ref: str | None = None) -> dict[str, Any] | None:
    """Resolve the seat's last assistant message to a verifiable anchor, or None.

    Returns ``{session_id, position, sha256, message_id, anchor}`` where ``anchor`` is
    the ``<seat_ref>@<session>#<N> sha:<8>`` citation string. Best-effort: any missing
    session / transcript / assistant row yields None (the watcher just omits the field).
    """
    if not row:
        return None
    session_id = row.get("runtime_session_id") or row.get("session_id")
    if not session_id:
        return None
    path = discover_transcript(row, str(session_id))
    if not path:
        return None
    rows = transcript_rows(path)
    last = next((r for r in reversed(rows) if r["type"] == "assistant"), None)
    if not last:
        return None
    sha = content_sha(last["content"])
    n = last["position"]                       # the JSONL line number == Flex chunk N
    chunk_id = f"{session_id}_{n}"             # the Flex chunk id, by construction
    ref = seat_ref or row.get("seat_ref") or ""
    return {
        "session_id": str(session_id),
        "position": n,
        "sha256": sha,
        "flex_chunk_id": chunk_id,
        "message_id": chunk_id,
        "anchor": f"{ref}@{session_id}#{n} sha:{sha[:8]}",
    }


# --------------------------------------------------------------------------
# Resolve — hand the anchor (a Flex chunk id) back to Flex's index.
# --------------------------------------------------------------------------

# Resolution only needs session + line number; the sha suffix (a drift check) is
# parsed permissively so any trailing `sha:...` form still yields the chunk id.
_ANCHOR_RE = re.compile(r"^(?P<seat>.*?)@(?P<session>[^#\s]+)#(?P<n>\d+)(?:\s+sha:(?P<sha>\S+))?\s*$")
_CHUNK_ID_RE = re.compile(r"^[A-Za-z0-9:_.-]+$")


def to_chunk_id(anchor_or_id: str) -> str | None:
    """Accept an anchor string or a raw chunk id; return the Flex chunk id."""
    value = (anchor_or_id or "").strip()
    m = _ANCHOR_RE.match(value)
    if m:
        return f"{m.group('session')}_{m.group('n')}"
    return value if _CHUNK_ID_RE.match(value) else None


def _flex_bin() -> list[str]:
    override = os.environ.get("FLEX_BIN")
    if override:
        return override.split()
    venv = Path("/home/axp/projects/flexsearch/main/venv/bin/flex")
    return [str(venv)] if venv.exists() else ["flex"]


def resolve(anchor_or_id: str, *, cells: tuple[str, ...] = ("claude_code", "codex")) -> dict[str, Any] | None:
    """Resolve an anchor / Flex chunk id to its content via Flex's index.

    The anchor IS a Flex chunk id (``session_<line>``), so resolution is a Flex
    lookup, not a re-derivation. Best-effort: returns ``None`` if Flex is
    unavailable or the chunk is not yet indexed (the index lags the live edge).
    """
    chunk_id = to_chunk_id(anchor_or_id)
    if not chunk_id:
        return None
    query = f"SELECT id, type, position, substr(content,1,4000) AS content FROM messages WHERE id = '{chunk_id}'"
    for cell in cells:
        try:
            proc = subprocess.run(
                [*_flex_bin(), "core", "search", "--cell", cell, "--json", query],
                text=True, capture_output=True, timeout=30,
            )
        except Exception:
            continue
        if proc.returncode != 0:
            continue
        try:
            data = json.loads(proc.stdout)
        except Exception:
            continue
        if isinstance(data, list) and data:
            row = dict(data[0])
            row["cell"] = cell
            row["flex_chunk_id"] = chunk_id
            return row
    return None
