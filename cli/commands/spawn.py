"""Spawn new agent."""

import os
import sys
import time

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))


def run(args):
    """Spawn a new agent."""
    # Set project/session name from knowledge BEFORE importing terminal
    # This affects which tmux session agents are spawned into
    if args.knowledge:
        os.environ["AURA_PROJECT"] = args.knowledge

    from lib import mesh, terminal

    # Ensure mesh daemon is running
    mesh.ensure_running()

    # Ensure terminal session exists
    terminal.ensure_session()

    # Check if window already exists
    if terminal.window_exists(args.name):
        return {"ok": False, "error": f"agent already exists: {args.name}"}

    # Determine working directory
    workdir = os.getcwd()
    full_session_id = None

    # If resuming a session, find it and extract workdir
    if args.memory:
        try:
            from jsonl import find_jsonl, extract_workdir, slice_at

            jsonl_path = find_jsonl(args.memory)
            if jsonl_path:
                # Extract original working directory BEFORE any slicing
                session_workdir = extract_workdir(jsonl_path)
                if session_workdir and os.path.isdir(session_workdir):
                    workdir = session_workdir

                # If slicing, do it HERE so we can symlink the result
                # --at is preferred, --slice is legacy fallback
                slice_ref = getattr(args, 'at', None) or getattr(args, 'slice', None)
                if slice_ref:
                    new_session_id = slice_at(jsonl_path, slice_ref)
                    # Update jsonl_path to point to sliced file
                    jsonl_path = jsonl_path.parent / f"{new_session_id}.jsonl"
                    full_session_id = new_session_id
                else:
                    full_session_id = jsonl_path.stem

                # Handle cross-project resume with symlink (for original OR sliced)
                _ensure_session_accessible(jsonl_path, workdir)
            else:
                return {"ok": False, "error": f"session not found: {args.memory}"}
        except ImportError:
            # jsonl lib not available, use partial ID
            full_session_id = args.memory

    # Create window in the correct working directory
    terminal.create_window(args.name, workdir)

    # Build aura.py command
    aura_wrapper = "/home/axp/projects/aura/main/wrapper/aura.py"
    cmd_parts = ["python3", aura_wrapper, "--name", args.name]

    if args.memory:
        # Use full session ID if we found it (may be sliced session)
        session_id = full_session_id or args.memory
        cmd_parts.extend(["-r", session_id])
        # Note: --slice is handled above in spawn.py, not passed to aura.py

    if args.knowledge:
        cmd_parts.extend(["--from", args.knowledge])

    cmd_parts.append("--dangerously-skip-permissions")

    cmd = " ".join(cmd_parts)

    # Send command to terminal
    time.sleep(0.5)
    terminal.send_keys(args.name, cmd, enter=True)

    # If --wait or --prompt, poll for registration
    if args.wait or args.prompt:
        timeout = args.timeout
        start = time.time()
        registered = False
        mesh_available = True

        # Check if mesh is running before waiting
        mesh_check = mesh.discover()
        if mesh_check.get("error"):
            mesh_available = False

        if mesh_available:
            while time.time() - start < timeout:
                if mesh.agent_registered(args.name):
                    registered = True
                    break
                time.sleep(0.5)

            if not registered:
                return {"ok": False, "error": "timeout waiting for registration", "name": args.name}

        # Send prompt if specified
        if args.prompt:
            # Longer wait for Claude to be fully ready (hooks, rendering, etc.)
            time.sleep(2)

            if mesh_available:
                result = mesh.send_message(args.name, args.prompt)
                if not result.get("error"):
                    return {"ok": True, "name": args.name, "registered": True, "prompt_sent": True}

            # Mesh unavailable or send failed - fall back to direct terminal with delay scaling
            # Delay formula from aura.py: handles long prompts (up to 5KB+)
            prompt_bytes = len(args.prompt.encode('utf-8'))
            delay = min(2.0, max(0.3, prompt_bytes / 2500))
            terminal.send_keys(args.name, args.prompt)
            time.sleep(delay)
            terminal.send_keys(args.name, "", enter=True)
            return {"ok": True, "name": args.name, "prompt_sent": True, "fallback": terminal.BACKEND_NAME}

    return {"ok": True, "name": args.name, "spawned": True}


def _ensure_session_accessible(jsonl_path, target_workdir):
    """Create symlink if session is from different project.

    Claude Code stores sessions in project-specific directories.
    To resume a session from a different project, we need a symlink.
    """
    from pathlib import Path

    claude_dir = Path.home() / ".claude/projects"

    # Encode target workdir to Claude's directory format
    # /home/axp/projects/foo -> -home-axp-projects-foo
    encoded = target_workdir.replace("/", "-")
    if not encoded.startswith("-"):
        encoded = "-" + encoded

    target_claude_dir = claude_dir / encoded
    target_claude_dir.mkdir(parents=True, exist_ok=True)

    # Check if session is from a different project
    if jsonl_path.parent != target_claude_dir:
        symlink_path = target_claude_dir / jsonl_path.name

        # Remove existing symlink if present
        if symlink_path.is_symlink():
            symlink_path.unlink()

        # Create symlink only if file doesn't exist
        if not symlink_path.exists():
            symlink_path.symlink_to(jsonl_path)
