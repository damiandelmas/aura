"""Spawn new agent."""

import time
import os


def run(args):
    """Spawn a new agent."""
    from lib import mesh, tmux

    # Ensure tmux session exists
    tmux.ensure_session()

    # Check if window already exists
    if tmux.window_exists(args.name):
        return {"ok": False, "error": f"agent already exists: {args.name}"}

    # Create window
    workdir = os.getcwd()
    tmux.create_window(args.name, workdir)

    # Build aura.py command
    aura_wrapper = "/home/axp/projects/aura/main/wrapper/aura.py"
    cmd_parts = ["python3", aura_wrapper, "--name", args.name]

    if args.memory:
        cmd_parts.extend(["-r", args.memory])

    if args.slice:
        cmd_parts.extend(["--at", str(args.slice)])

    if args.knowledge:
        cmd_parts.extend(["--from", args.knowledge])

    cmd_parts.append("--dangerously-skip-permissions")

    cmd = " ".join(cmd_parts)

    # Send command to tmux
    time.sleep(0.5)
    tmux.send_keys(args.name, cmd, enter=True)

    # If --wait or --prompt, poll for registration
    if args.wait or args.prompt:
        timeout = args.timeout
        start = time.time()
        registered = False

        while time.time() - start < timeout:
            if mesh.agent_registered(args.name):
                registered = True
                break
            time.sleep(0.5)

        if not registered:
            return {"ok": False, "error": "timeout waiting for registration", "name": args.name}

        # Send prompt if specified
        if args.prompt:
            time.sleep(1)  # Extra wait for Claude to be ready
            mesh.send_message(args.name, args.prompt)
            return {"ok": True, "name": args.name, "registered": True, "prompt_sent": True}

    return {"ok": True, "name": args.name, "spawned": True}
