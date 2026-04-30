"""Write raw text or keys to a terminal-backed seat."""

from __future__ import annotations

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_target(target: str, registry, terminal) -> tuple[str, str, str | None, str | None, dict | None]:
    """Return (seat_name, terminal_target, fleet, backend_ref, registry_record)."""
    if target.startswith("tmux:"):
        parts = target.split(":", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            raise ValueError("tmux target must be tmux:FLEET:WINDOW_OR_%PANE")
        fleet, subject = parts[1], parts[2]
        if hasattr(terminal, "configure_session"):
            terminal.configure_session(fleet)
        return subject, target, fleet, f"tmux:{fleet}:{subject}", None

    reg_agent = registry.get_agent(target)
    fleet = (reg_agent or {}).get("fleet")
    if fleet and hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)
    terminal_target = (reg_agent or {}).get("pane_ref") or (reg_agent or {}).get("terminal_ref") or target
    backend_ref = (reg_agent or {}).get("pane_ref") or None
    if not backend_ref and fleet:
        backend_ref = f"tmux:{fleet}:{target}"
    return target, terminal_target, fleet, backend_ref, reg_agent


def _target_exists(terminal, target: str) -> bool:
    return terminal.target_exists(target) if hasattr(terminal, "target_exists") else terminal.window_exists(target)


def _preview(text: str, limit: int = 120) -> str:
    text = text.replace("\n", "\\n").strip()
    return text[:limit]


def _needs_submit_retry(capture: list[str]) -> bool:
    from lib.terminal_submit import needs_submit_retry

    return needs_submit_retry(capture)


def _retry_submit(name: str, terminal) -> dict:
    from lib.terminal_submit import retry_submit

    return retry_submit(name, terminal)


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
        name, terminal_target, fleet, backend_ref, reg_agent = _parse_target(target, registry, terminal)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "target": target}

    if (registry.is_hidden_agent(reg_agent) or registry.is_hidden_fleet(fleet)) and not getattr(args, "allow_hidden", False):
        return {
            "ok": False,
            "blocked": True,
            "reason": "target-hidden",
            "error": "target is hidden/internal; use an explicit operator path or --allow-hidden",
            "target": target,
            "name": name,
            "fleet": fleet,
            "backend_ref": backend_ref,
        }

    if not _target_exists(terminal, terminal_target):
        return {"ok": False, "error": f"window not found: {target}", "target": target, "backend_ref": backend_ref}

    if getattr(args, "ensure_submit", False) and submit and not key_sequence:
        from lib import terminal_submit

        preflight_capture = terminal.capture_output(terminal_target, max(lines, 80))
        blocker = terminal_submit.delivery_blocker(preflight_capture)
        if blocker:
            record = delivery.new_delivery_record(
                delivery_type="terminal_write",
                sender=sender,
                target=target,
                backend="tmux",
                backend_ref=backend_ref or f"tmux:{getattr(terminal, 'SESSION_NAME', fleet or 'aura')}:{name}",
                state="blocked",
                seat=name,
                transport="tmux",
                error=blocker,
                enter=submit,
                keys=key_sequence,
                capture_before_lines=len(preflight_capture),
            )
            delivery.append_attempt(record, state="blocked", evidence={
                "blocker": blocker,
                "preflight_capture_lines": len(preflight_capture),
            })
            record = delivery.append_record(record)
            return seat_schema.enrich({
                "ok": False,
                "schema": "aura.write.v1",
                "type": "write",
                "blocked": True,
                "reason": blocker,
                "error": f"target not ready for paste: {blocker}",
                "target": target,
                "name": name,
                "fleet": fleet or (reg_agent or {}).get("fleet"),
                "sender": sender,
                "transport": "tmux",
                "backend_ref": record.get("backend_ref"),
                "state": "blocked",
                "submitted": False,
                "submitted_verified": False,
                "submit_retry": False,
                "record": record,
            })

    before = None
    if getattr(args, "capture_before", False):
        before = terminal.capture_output(terminal_target, lines)

    message_id = delivery.new_message_id()
    created_at = _now_iso()
    body_for_hash = key_sequence if key_sequence is not None else message
    pending = delivery.new_delivery_record(
        delivery_type="terminal_key" if key_sequence else "terminal_write",
        sender=sender,
        target=target,
        payload_hash=delivery.body_hash(body_for_hash),
        backend="tmux",
        backend_ref=backend_ref or f"tmux:{getattr(terminal, 'SESSION_NAME', fleet or 'aura')}:{name}",
        message_id=message_id,
        state="pending",
        seat=name,
        transport="tmux",
        bytes=len(body_for_hash.encode("utf-8")),
        enter=submit,
        keys=key_sequence,
        preview=_preview(body_for_hash),
    )
    pending["created_at"] = created_at
    pending["updated_at"] = created_at
    delivery.append_attempt(pending, state="pending", evidence={
        "body_hash": delivery.body_hash(body_for_hash),
        "bytes": pending.get("bytes"),
        "enter": submit,
        "keys": key_sequence,
    })
    delivery.append_record(pending)

    if key_sequence:
        result = terminal.send_keys(terminal_target, key_sequence, enter=False) or {"ok": False, "error": "terminal send_keys failed"}
    else:
        result = terminal.send_text(terminal_target, message, submit=submit)

    after = None
    submit_verified = None
    submit_retry = False
    verify_reason = None
    if getattr(args, "capture_after", False):
        after = terminal.capture_output(terminal_target, lines)

    if (
        getattr(args, "ensure_submit", False)
        and submit
        and not key_sequence
        and result.get("ok")
    ):
        from lib.terminal_submit import verify_submit

        verify = verify_submit(terminal, terminal_target, message_id=message_id, lines=lines)
        submit_verified = verify["submitted_verified"]
        submit_retry = verify["submit_retry"]
        verify_reason = verify.get("verify_reason")
        if after is not None:
            after = verify["capture"][-lines:]

    state = "delivered" if result.get("ok") and submit_verified is not False else "failed"
    delivery.append_attempt(pending, state="attempted", evidence={
        "write_ok": bool(result.get("ok")),
        "terminal_ref": result.get("target") or pending.get("backend_ref"),
        "submitted": result.get("submitted", False),
        "submitted_verified": submit_verified,
        "submit_verify_reason": verify_reason,
        "submit_retry": submit_retry,
        "capture_before_lines": len(before or []),
        "capture_after_lines": len(after or []),
        "error": result.get("error"),
    })
    record = delivery.append_final_record(
        pending,
        state=state,
        terminal_ref=result.get("target") or pending.get("backend_ref"),
        error=result.get("error"),
        submitted=result.get("submitted", False),
        submitted_verified=submit_verified,
        submit_verify_reason=verify_reason,
        submit_retry=submit_retry,
        capture_before_lines=len(before or []),
        capture_after_lines=len(after or []),
    )

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
        "submit_verify_reason": verify_reason,
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
