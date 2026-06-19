"""aura notes — query the annotation ledger.

  list   filter/scan the margin notes (newest first)
  show   one note + re-resolve its anchored message, with a content-drift check

Drift is checked against the on-disk transcript (full content, same content-sha
the anchor was minted with), so it is faithful; Flex is the fallback content
source when the transcript is no longer local.
"""

from __future__ import annotations

from lib import notes, result_anchor


def _matches(n, args) -> bool:
    target = getattr(args, "target", None)
    if target and n["target"] != target:
        return False
    session = getattr(args, "session", None)
    if session:
        sid = n["session_id"] or ""
        if sid != session and not sid.startswith(session):
            return False
    grep = getattr(args, "grep", None)
    if grep:
        hay = f"{n['note']} {n.get('selected_text') or ''}".lower()
        if grep.lower() not in hay:
            return False
    if getattr(args, "with_note", False) and not n["has_note"]:
        return False
    return True


def _list(args) -> dict:
    rows = [n for n in notes.all_normalized() if _matches(n, args)]
    rows.sort(key=lambda n: n.get("ts") or "", reverse=True)  # newest first
    limit = getattr(args, "limit", None)
    if limit:
        rows = rows[: int(limit)]
    out = []
    for n in rows:
        r = dict(n)
        sel = r.pop("selected_text", None)
        r["selected_preview"] = ((sel or "").replace("\n", " ")[:100]) or None
        out.append(r)
    return {"ok": True, "count": len(out), "notes": out}


def _resolve_message(sid: str, pos: int, stored_sha: str | None) -> dict:
    """Re-resolve the anchored message: transcript-faithful, Flex fallback."""
    row = {"runtime_session_id": sid}
    path = result_anchor.discover_transcript(row, str(sid))
    if path:
        cur = next((r for r in result_anchor.transcript_rows(path) if r["position"] == pos), None)
        if cur:
            cur_sha = result_anchor.content_sha(cur["content"])
            return {
                "source": "transcript",
                "path": str(path),
                "type": cur["type"],
                "stored_sha8": (stored_sha or "")[:8] or None,
                "current_sha8": cur_sha[:8],
                "drift": (stored_sha is not None and cur_sha != stored_sha),
                "content": cur["content"],
            }
        return {"source": "transcript", "path": str(path), "found": False,
                "reason": f"position {pos} not in transcript (compacted/rewritten?)"}
    # transcript gone — fall back to Flex (content may be truncated, so no hard drift)
    resolved = result_anchor.resolve(f"{sid}_{pos}")
    if resolved:
        return {"source": "flex", "cell": resolved.get("cell"), "type": resolved.get("type"),
                "drift": None, "drift_note": "Flex content may be truncated; sha not compared",
                "content": resolved.get("content")}
    return {"resolved": False, "reason": "transcript not on disk and not indexed in Flex (live-edge lag)"}


def _show(args) -> dict:
    anchor = getattr(args, "anchor", None)
    index = getattr(args, "index", None)
    if anchor:
        cid = result_anchor.to_chunk_id(anchor)
        rec = next((n for n in notes.all_normalized() if n["flex_chunk_id"] == cid), None)
        if not rec:
            # no stored note for this anchor — still resolve the message
            rec = {"index": None, "note": None, "anchor": anchor, "flex_chunk_id": cid,
                   "content_sha256": None}
            sid_pos = (cid or "").rsplit("_", 1)
            rec["session_id"] = sid_pos[0] if len(sid_pos) == 2 else None
            rec["position"] = int(sid_pos[1]) if len(sid_pos) == 2 and sid_pos[1].isdigit() else None
    elif index is not None:
        rec = notes.get(int(index))
        if not rec:
            return {"ok": False, "error": f"no annotation at index {index}"}
    else:
        return {"ok": False, "error": "pass an annotation index or --anchor"}

    resolution = None
    if rec.get("session_id") and rec.get("position") is not None:
        resolution = _resolve_message(rec["session_id"], rec["position"], rec.get("content_sha256"))
    return {"ok": True, "note": rec, "resolution": resolution}


def run(args):
    action = getattr(args, "notes_action", None)
    if action == "list":
        return _list(args)
    if action == "show":
        return _show(args)
    return {"ok": False, "error": f"unknown notes action: {action}"}
