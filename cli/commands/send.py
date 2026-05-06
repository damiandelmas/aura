"""Send message to agent."""

import os
import threading


def _is_current_seat(target: str, record: dict | None) -> bool:
    fleet = os.environ.get("AURA_FLEET")
    seat = os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")
    if seat and target in {seat, f"{fleet}:{seat}" if fleet else ""}:
        return True

    record = record or {}
    if seat and record.get("name") == seat and (not fleet or record.get("fleet") == fleet):
        return True

    current_session = os.environ.get("AURA_RUNTIME_SESSION_ID") or os.environ.get("CODEX_THREAD_ID") or os.environ.get("CLAUDE_SESSION_ID")
    if current_session and current_session in {
        record.get("runtime_session_id"),
        record.get("session_id"),
        record.get("source_session_id"),
    }:
        return True

    tmux_pane = os.environ.get("TMUX_PANE")
    pane_ref = str(record.get("pane_ref") or "")
    if tmux_pane and pane_ref.endswith(f":{tmux_pane}"):
        return True

    return False


def run(args):
    """Send message to agent."""
    from lib import delivery, identity, mesh, registry, terminal

    nudge = getattr(args, 'nudge', False)
    sender = identity.sender(getattr(args, "sender", None))
    reg_agent = registry.get_agent(args.target)
    if _is_current_seat(args.target, reg_agent) and not getattr(args, "force", False):
        return {
            "ok": False,
            "blocked": True,
            "reason": "target-is-current-seat",
            "error": "refusing to paste an Aura message into the current seat; use the conversation directly or pass --force",
            "target": args.target,
            "current": {
                "fleet": os.environ.get("AURA_FLEET"),
                "seat": os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME"),
                "runtime_session_id": os.environ.get("AURA_RUNTIME_SESSION_ID") or os.environ.get("CODEX_THREAD_ID") or os.environ.get("CLAUDE_SESSION_ID"),
                "tmux_pane": os.environ.get("TMUX_PANE"),
            },
        }
    if reg_agent and registry.is_hidden_agent(reg_agent) and not getattr(args, "allow_hidden", False):
        return {
            "ok": False,
            "blocked": True,
            "reason": "target-hidden",
            "error": "target is hidden/internal; use an explicit operator path or --allow-hidden",
            "target": args.target,
        }
    if args.target.startswith("tmux:"):
        parts = args.target.split(":", 2)
        if len(parts) == 3 and registry.is_hidden_fleet(parts[1]) and not getattr(args, "allow_hidden", False):
            return {
                "ok": False,
                "blocked": True,
                "reason": "target-hidden",
                "error": "target is hidden/internal; use an explicit operator path or --allow-hidden",
                "target": args.target,
            }
    if (reg_agent or {}).get("fleet") and hasattr(terminal, "configure_session"):
        terminal.configure_session(reg_agent.get("fleet"))
    elif ":" in args.target and not args.target.startswith("tmux:") and hasattr(terminal, "configure_session"):
        terminal.configure_session(args.target.split(":", 1)[0])
    terminal_target = (reg_agent or {}).get("pane_ref") or (reg_agent or {}).get("terminal_ref") or args.target
    target_exists = terminal.target_exists(terminal_target) if hasattr(terminal, "target_exists") else terminal.window_exists(terminal_target)

    # --nudge: send a literal Enter key as a delivery kick.
    if nudge:
        if target_exists:
            result = terminal.send_keys(terminal_target, "Enter", enter=False) or {}
            return {"ok": True, "nudged": True, "name": args.target, "terminal_ref": result.get("target")}
        return {"error": f"window not found: {args.target}"}

    transport = getattr(args, 'transport', 'auto') or 'auto'
    if transport == 'auto':
        transport = 'tmux' if target_exists else 'mesh'

    if transport == 'tmux':
        return _send_tmux(args, terminal, delivery, terminal_target=terminal_target, sender=sender)

    # Legacy mesh path remains available for wrapper-managed Claude sessions.
    mode = args.mode
    if mode == "auto":
        discovery = mesh.discover()
        agent = next(
            (a for a in discovery.get("agents", []) if a.get("name") == args.target),
            None
        )
        status = (agent or {}).get("status", "idle")
        mode = "queue" if status == "busy" else "immediate"

    result = mesh.send_message(args.target, args.message, sender, mode)

    if result.get("ok"):
        _confirm_delivery_async(args.target, args.message, sender)

        return {
            "ok": True,
            "queued": True,
            "transport": "mesh",
            "message_id": result.get("message_id", "")
        }
    return result


def _send_tmux(args, terminal, delivery, terminal_target=None, sender=None):
    from lib import identity

    sender = identity.sender(sender if sender is not None else getattr(args, "sender", None))
    body = args.message or ""
    terminal_target = terminal_target or args.target
    dedupe_key = getattr(args, 'dedupe_key', None) or delivery.default_dedupe_key(args.target, sender, body)

    if not getattr(args, 'force', False):
        previous = delivery.has_successful_dedupe(args.target, dedupe_key)
        if previous:
            record = delivery.new_delivery_record(
                delivery_type="semantic_send",
                sender=sender,
                target=args.target,
                backend="tmux",
                dedupe_key=dedupe_key,
                state="skipped_duplicate",
                previous_message_id=previous,
                transport="tmux",
            )
            delivery.append_attempt(record, state="skipped_duplicate", evidence={"previous_message_id": previous})
            record = delivery.append_record(record)
            return {"ok": True, "skipped": True, "reason": "duplicate", "previous_message_id": previous, "record": record}

    blocker = None
    if getattr(args, "defer_if_busy", False):
        from lib import terminal_submit

        preflight_capture = terminal.capture_output(terminal_target, 80)
        blocker = terminal_submit.delivery_blocker(preflight_capture)
    if blocker:
        record = delivery.new_delivery_record(
            delivery_type="semantic_send",
            sender=sender,
            target=args.target,
            backend="tmux",
            backend_ref=terminal_target,
            dedupe_key=dedupe_key,
            state="blocked",
            transport="tmux",
            error=blocker,
            capture_before_lines=len(preflight_capture),
        )
        delivery.append_attempt(record, state="blocked", evidence={
            "blocker": blocker,
            "preflight_capture_lines": len(preflight_capture),
        })
        record = delivery.append_record(record)
        deferred_record = None
        if getattr(args, "defer_if_busy", False) and blocker in {"target-busy", "target-input-queued"}:
            deferred_record = _create_deferred_delivery(
                args,
                body=body,
                sender=sender,
                dedupe_key=dedupe_key,
                blocked_reason=blocker,
                blocked_message_id=record.get("message_id"),
            )
        return {
            "ok": bool(deferred_record),
            "blocked": True,
            "deferred": bool(deferred_record),
            "reason": blocker,
            "error": f"target not ready for paste: {blocker}",
            "record": record,
            "deferred_record": deferred_record,
        }

    message_id = delivery.new_message_id()
    sent_at = delivery.now_iso()
    envelope = delivery.render_envelope(message_id, sender, body, sent_at=sent_at)

    pending = delivery.new_delivery_record(
        delivery_type="semantic_send",
        sender=sender,
        target=args.target,
        payload_hash=delivery.body_hash(body),
        backend="tmux",
        backend_ref=terminal_target,
        dedupe_key=dedupe_key,
        message_id=message_id,
        transport="tmux",
        state="pending",
    )
    pending["created_at"] = sent_at
    pending["updated_at"] = sent_at
    delivery.append_attempt(pending, state="pending", evidence={"body_hash": delivery.body_hash(body)})
    delivery.append_record(pending)

    result = terminal.send_text(terminal_target, envelope, submit=True)
    submit_verified = None
    submit_retry = None
    verify_reason = None

    state = "attempted" if result.get("ok") else "failed"
    delivery.append_attempt(pending, state="attempted", evidence={
        "paste_ok": bool(result.get("ok")),
        "terminal_ref": result.get("target"),
        "bytes": result.get("bytes"),
        "submitted": result.get("submitted", False),
        "submitted_verified": submit_verified,
        "submit_verify_reason": verify_reason,
        "submit_retry": submit_retry,
        "error": result.get("error"),
    })
    record = delivery.append_final_record(
        pending,
        state=state,
        terminal_ref=result.get("target"),
        error=result.get("error"),
        bytes=result.get("bytes"),
        submitted=result.get("submitted", False),
        submitted_verified=submit_verified,
        submit_verify_reason=verify_reason,
        submit_retry=submit_retry,
    )

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "tmux send failed"), "message_id": message_id, "record": record}

    response = {
        "ok": True,
        "transport": "tmux",
        "message_id": message_id,
        "target": args.target,
        "terminal_ref": result.get("target"),
        "state": state,
        "submitted": result.get("submitted", False),
        "submitted_verified": submit_verified,
        "submit_verify_reason": verify_reason,
        "submit_retry": submit_retry,
        "record": record,
    }
    return response


def _create_deferred_delivery(args, *, body, sender, dedupe_key, blocked_reason, blocked_message_id=None):
    from lib import deferred

    ttl_seconds = deferred.parse_duration(getattr(args, "defer_ttl", None), default=900)
    retry_seconds = deferred.parse_duration(getattr(args, "defer_retry_every", None), default=15)
    deferred_record = deferred.create(
        target=args.target,
        message=body,
        sender=sender,
        dedupe_key=dedupe_key,
        transport="tmux",
        retry_every_seconds=retry_seconds,
        ttl_seconds=ttl_seconds,
        blocked_reason=blocked_reason,
        blocked_message_id=blocked_message_id,
    )
    if not getattr(args, "no_deferred_daemon", False):
        deferred_record["daemon"] = deferred.spawn_daemon(deferred_record["deferred_id"])
    return deferred_record


def _confirm_delivery_async(target, message, sender):
    """Background thread: poll flex for 10s to verify message appeared in agent's JSONL."""
    t = threading.Thread(
        target=_confirm_delivery,
        args=(target, message, sender),
        daemon=True
    )
    t.start()


def _confirm_delivery(target, message, sender, timeout=10, interval=2):
    """Poll flex claude_code cell to verify message was processed by agent.

    Looks for the @sender: prefix in user_prompt messages for the agent's session.
    If not found within timeout, sends warning back to sender via mesh.
    """
    import time

    try:
        from flex.registry import resolve_cell
        from flex.core import open_cell, run_sql
    except ImportError:
        return  # flex not available, skip confirmation

    from lib import mesh

    # Get agent's session_id from mesh
    discovery = mesh.discover()
    if not discovery.get("ok"):
        return

    agent = next((a for a in discovery.get("agents", []) if a["name"] == target), None)
    if not agent or not agent.get("session_id"):
        return

    session_id = agent["session_id"]
    if not session_id or len(session_id) < 8:
        return

    # Resolve flex cell
    cell_path = resolve_cell("claude_code")
    if not cell_path:
        return

    # Use first 50 chars of message as search fingerprint
    fingerprint = message[:50].replace("'", "''")
    prefix = f"@{sender}:"

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(interval)
        try:
            conn = open_cell(str(cell_path))
            rows = run_sql(conn, """
                SELECT 1 FROM _raw_chunks c
                JOIN _edges_source e ON c.id = e.chunk_id
                JOIN _raw_sources s ON e.source_id = s.id
                WHERE s.id LIKE ? AND c.content LIKE ? AND c.content LIKE ?
                LIMIT 1
            """, (f"{session_id[:8]}%", f"%{prefix}%", f"%{fingerprint}%"))
            conn.close()

            if rows:
                return  # confirmed — message appeared in JSONL
        except Exception:
            pass  # flex query failed, keep trying

    # Timeout — message not confirmed. Warn sender.
    warning = (
        f"[aura] Message to {target} may not have been delivered after {timeout}s. "
        f"Try: aura send {target} \"\" --nudge"
    )

    # Send warning back to sender (if sender is a mesh agent, not CLI)
    if sender != "cli":
        mesh.send_message(sender, warning, "aura")
    else:
        # For CLI sender, write to stderr (they may have moved on)
        import sys
        sys.stderr.write(f"\033[33m{warning}\033[0m\n")
        sys.stderr.flush()
