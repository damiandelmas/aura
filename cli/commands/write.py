"""Write raw text or keys to a terminal-backed seat."""

from __future__ import annotations

from datetime import datetime, timezone
import time


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_target(target: str, registry, terminal) -> tuple[str, str | None, str | None, dict | None]:
    """Return (window_name, fleet, backend_ref, registry_record)."""
    if target.startswith("tmux:"):
        parts = target.split(":", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            raise ValueError("tmux target must be tmux:FLEET:WINDOW")
        fleet, name = parts[1], parts[2]
        if hasattr(terminal, "configure_session"):
            terminal.configure_session(fleet)
        return name, fleet, f"tmux:{fleet}:{name}", None

    reg_agent = registry.get_agent(target)
    fleet = (reg_agent or {}).get("fleet")
    if fleet and hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)
    backend_ref = None
    if fleet:
        backend_ref = f"tmux:{fleet}:{target}"
    return target, fleet, backend_ref, reg_agent


def _preview(text: str, limit: int = 120) -> str:
    text = text.replace("\n", "\\n").strip()
    return text[:limit]


def _needs_submit_retry(capture: list[str]) -> bool:
    """Detect terminal states where a pasted Codex/agent prompt is queued.

    Codex can occasionally show a message as "to be submitted after next tool
    call" even though Aura sent Enter. In that state a bare Enter submits the
    already-pasted text. Keep this intentionally narrow to avoid double-sending
    legitimate, already-running turns.
    """
    lines = [str(line).lower() for line in (capture or [])]
    joined = "\n".join(lines)
    queued_markers = (
        "messages to be submitted after next tool call",
        "press enter to submit",
        "enter to submit",
    )
    if any(marker in joined for marker in queued_markers):
        return True

    # Codex can leave large pasted prompts rendered as a prompt line:
    #   › [Pasted Content 1024 chars]
    # If no later "Working" line appears, a bare Enter is still required.
    last_pasted_prompt = -1
    last_working = -1
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("› [pasted content", "> [pasted content")):
            last_pasted_prompt = idx
        if "working (" in stripped or "thinking" in stripped:
            last_working = idx
    return last_pasted_prompt > last_working


def _retry_submit(name: str, terminal) -> dict:
    """Retry submit using the same key path as `aura write --keys Enter`.

    libtmux `pane.enter()` is not equivalent to sending a literal Enter key in
    every full-screen TUI state. Codex queued prompts have proven more reliable
    with the literal key path.
    """
    return terminal.send_keys(name, "Enter", enter=False) or {}


def run(args):
    """Write directly to the terminal body behind a seat or backend ref."""
    from lib import delivery, registry, seat_schema, terminal

    sender = getattr(args, "sender", None) or "cli"
    target = args.target
    message = getattr(args, "message", None) or ""
    key_sequence = getattr(args, "keys", None)
    submit = bool(getattr(args, "enter", False))
    lines = int(getattr(args, "lines", 20) or 20)

    if key_sequence and message:
        return {"ok": False, "error": "provide either message text or --keys, not both"}
    if not key_sequence and message == "":
        return {"ok": False, "error": "message text or --keys is required"}

    try:
        name, fleet, backend_ref, reg_agent = _parse_target(target, registry, terminal)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "target": target}

    if not terminal.window_exists(name):
        return {"ok": False, "error": f"window not found: {target}", "target": target, "backend_ref": backend_ref}

    before = None
    if getattr(args, "capture_before", False):
        before = terminal.capture_output(name, lines)

    message_id = delivery.new_message_id()
    created_at = _now_iso()
    body_for_hash = key_sequence if key_sequence is not None else message
    pending = delivery.append_record({
        "schema": "aura.delivery.v1",
        "type": "terminal_write",
        "message_id": message_id,
        "target": target,
        "seat": name,
        "sender": sender,
        "transport": "tmux",
        "backend": "tmux",
        "backend_ref": backend_ref or f"tmux:{getattr(terminal, 'SESSION_NAME', fleet or 'aura')}:{name}",
        "delivery_type": "terminal_key" if key_sequence else "terminal_write",
        "state": "pending",
        "created_at": created_at,
        "body_hash": delivery.body_hash(body_for_hash),
        "bytes": len(body_for_hash.encode("utf-8")),
        "enter": submit,
        "keys": key_sequence,
        "preview": _preview(body_for_hash),
    })

    if key_sequence:
        result = terminal.send_keys(name, key_sequence, enter=False) or {"ok": False, "error": "terminal send_keys failed"}
    else:
        result = terminal.send_text(name, message, submit=submit)

    after = None
    submit_verified = None
    submit_retry = False
    if getattr(args, "capture_after", False):
        after = terminal.capture_output(name, lines)

    if (
        getattr(args, "ensure_submit", False)
        and submit
        and not key_sequence
        and result.get("ok")
    ):
        time.sleep(1.0)
        verify_capture = terminal.capture_output(name, max(lines, 80))
        submit_verified = not _needs_submit_retry(verify_capture)
        if not submit_verified:
            retry = _retry_submit(name, terminal)
            submit_retry = bool(retry.get("ok"))
            time.sleep(1.0)
            verify_capture = terminal.capture_output(name, max(lines, 80))
            submit_verified = not _needs_submit_retry(verify_capture)
            if after is not None:
                after = verify_capture[-lines:]

    state = "delivered" if result.get("ok") else "failed"
    record = delivery.append_record({
        **pending,
        "state": state,
        "updated_at": _now_iso(),
        "terminal_ref": result.get("target") or pending.get("backend_ref"),
        "error": result.get("error"),
        "submitted": result.get("submitted", False),
        "submitted_verified": submit_verified,
        "submit_retry": submit_retry,
        "capture_before_lines": len(before or []),
        "capture_after_lines": len(after or []),
    })

    response = {
        "ok": bool(result.get("ok")),
        "schema": "aura.write.v1",
        "type": "write",
        "message_id": message_id,
        "target": target,
        "name": name,
        "fleet": fleet or (reg_agent or {}).get("fleet"),
        "sender": sender,
        "transport": "tmux",
        "terminal_ref": result.get("target") or pending.get("backend_ref"),
        "backend_ref": pending.get("backend_ref"),
        "state": state,
        "submitted": result.get("submitted", False),
        "submitted_verified": submit_verified,
        "submit_retry": submit_retry,
        "enter": submit,
        "keys": key_sequence,
        "bytes": pending.get("bytes"),
        "record": record,
    }
    if before is not None:
        response["capture_before"] = before
    if after is not None:
        response["capture_after"] = after
    if not result.get("ok"):
        response["error"] = result.get("error", "terminal write failed")
    return seat_schema.enrich(response)
