"""Send message to agent."""

import threading


def run(args):
    """Send message to agent."""
    from lib import mesh

    nudge = getattr(args, 'nudge', False)

    # --nudge: just send Enter via tmux as a delivery kick
    if nudge:
        from lib import terminal
        if terminal.window_exists(args.target):
            terminal.send_keys(args.target, "", enter=True)
            return {"ok": True, "nudged": True, "name": args.target}
        return {"error": f"window not found: {args.target}"}

    # --mode auto: resolve at send-time from target's current status
    # idle → immediate (deliver now), busy → queue (wait for them to finish)
    mode = args.mode
    if mode == "auto":
        discovery = mesh.discover()
        agent = next(
            (a for a in discovery.get("agents", []) if a.get("name") == args.target),
            None
        )
        status = (agent or {}).get("status", "idle")
        mode = "queue" if status == "busy" else "immediate"

    result = mesh.send_message(args.target, args.message, args.sender, mode)

    if result.get("ok"):
        # Fire background delivery confirmation via flex
        sender = args.sender or "cli"
        _confirm_delivery_async(args.target, args.message, sender)

        return {
            "ok": True,
            "queued": True,
            "message_id": result.get("message_id", "")
        }
    return result


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
