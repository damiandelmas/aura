"""aura anchor — the canonical message-anchor primitive.

One numbering authority: a message's identity is its Flex chunk id,
``session_id_<1-based JSONL line>``. Mint locally (lag-free, agrees with Flex by
construction because the position IS the line number); resolve durably through
Flex's index. The idle-watcher, the tmux right-click resolver, and Flex search are
all clients of this one contract.

  latest   mint a seat's latest-assistant anchor          (local, lag-free)
  resolve  anchor / chunk id -> content via Flex's index  (durable, cross-tool)
  enum     the canonical numbered message list            (position == Flex chunk N)
"""

from __future__ import annotations

from lib import registry, result_anchor


def _row_for(args) -> dict | None:
    """Build the transcript-discovery row from --target (registry) or --session."""
    target = getattr(args, "target", None)
    if target:
        row = registry.resolve_live(target)
        if not row:
            return None
        row = dict(row)
        row.setdefault("seat_ref", target)
        return row
    session = getattr(args, "session", None)
    if session:
        row: dict = {
            "runtime_session_id": session,
            "seat_ref": getattr(args, "seat_ref", None) or "",
        }
        if getattr(args, "transcript", None):
            row["transcript_path"] = args.transcript
        return row
    return None


def run(args):
    action = args.anchor_action

    if action == "latest":
        row = _row_for(args)
        if not row:
            return {"ok": False, "error": "no session: pass --target FLEET:SEAT or --session ID"}
        seat_ref = getattr(args, "seat_ref", None) or row.get("seat_ref")
        anchor = result_anchor.latest_assistant_anchor(row, seat_ref)
        if not anchor:
            return {"ok": False, "error": "no resolvable assistant message for this session",
                    "session_id": row.get("runtime_session_id") or row.get("session_id")}
        return {"ok": True, **anchor}

    if action == "resolve":
        cells = tuple(getattr(args, "cell", None) or ("claude_code", "codex"))
        resolved = result_anchor.resolve(args.anchor, cells=cells)
        if not resolved:
            return {"ok": False, "anchor": args.anchor,
                    "error": "not resolvable (unknown id, or not yet indexed in Flex — the live-edge lag)"}
        return {"ok": True, "resolved": resolved}

    if action == "enum":
        row = _row_for(args)
        if not row:
            return {"ok": False, "error": "no session: pass --target FLEET:SEAT or --session ID"}
        sid = row.get("runtime_session_id") or row.get("session_id")
        path = result_anchor.discover_transcript(row, str(sid)) if sid else None
        if not path:
            return {"ok": False, "error": "transcript not found", "session_id": sid}
        rows = result_anchor.transcript_rows(path)
        limit = getattr(args, "limit", None)
        if limit:
            rows = rows[-int(limit):]
        out = [{
            "position": r["position"],                       # == Flex chunk N (the JSONL line)
            "type": r["type"],
            "flex_chunk_id": f"{sid}_{r['position']}",
            "sha8": result_anchor.content_sha(r["content"])[:8],
            "preview": r["content"][:120].replace("\n", " "),
        } for r in rows]
        return {"ok": True, "session_id": sid, "count": len(out), "rows": out}

    return {"ok": False, "error": f"unknown anchor action: {action}"}
