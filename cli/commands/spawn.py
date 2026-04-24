"""Spawn new agent."""

import os
import subprocess
import sys
import time

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))


def _candidate_identities():
    """Best-effort identities for the current spawning seat."""
    import re

    def _normalize(ident: str) -> str:
        return re.sub(r"-\d+$", "", ident or "")

    candidates = []
    if os.environ.get("AURA_AGENT_NAME"):
        candidates.append(os.environ["AURA_AGENT_NAME"])
    pane = os.environ.get("TMUX_PANE")
    if pane:
        for fmt in ("#W", "#S"):
            try:
                r = subprocess.run(
                    ["tmux", "display-message", "-p", "-t", pane, fmt],
                    capture_output=True, text=True
                )
                if r.returncode == 0 and r.stdout.strip():
                    candidates.append(r.stdout.strip())
            except Exception:
                pass

    deduped = []
    seen = set()
    for candidate in candidates:
        normalized = _normalize(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _infer_parent_from_caller():
    candidates = _candidate_identities()
    return candidates[0] if candidates else None


def _infer_fleet_from_caller():
    """Route workers based on normalized manager/leader identities."""
    for ident in _candidate_identities():
        if ident.startswith("pm-"):
            return f"{ident[3:]}-workers"
        if ident.endswith("-manager-project"):
            product = ident[: -len("-manager-project")]
            return f"{product}-workers"
        if "-leader-" in ident:
            product, lane = ident.split("-leader-", 1)
            return f"{product}-{lane}-workers"
        if ident.endswith("-leader") and ident.count("-") >= 2:
            base = ident[: -len("-leader")]
            return f"{base}-workers"
    return None


def run(args):
    """Spawn a new agent."""
    # Determine fleet name BEFORE importing terminal (it reads env at import time)
    # Priority: --fleet flag > caller-derived default.
    fleet = getattr(args, 'fleet', None) or _infer_fleet_from_caller()
    if fleet:
        os.environ["AURA_FLEET"] = fleet
        os.environ["AURA_PROJECT"] = fleet

    from lib import mesh, terminal

    def _result(base: dict) -> dict:
        """Add fleet/attach info to every spawn result."""
        fleet_name = terminal.SESSION_NAME
        name = base.get("name", args.name)
        base["fleet"] = fleet_name
        base["attach"] = f"tmux attach -t {fleet_name}" if terminal.BACKEND_NAME == "tmux" else f"zellij attach {fleet_name}"
        base["window"] = f"{fleet_name}:{name}"
        return base

    # Ensure terminal session exists; this is the baseline substrate for both
    # generic runtimes and the legacy Claude wrapper path.
    terminal.ensure_session()

    # Check if window already exists
    if terminal.window_exists(args.name):
        return {"ok": False, "error": f"agent already exists: {args.name}"}

    if getattr(args, 'runtime', None) or getattr(args, 'launch_command', None):
        return _spawn_terminal_runtime(args, terminal, _result)

    # Legacy Claude-wrapper path still uses mesh lifecycle hooks.
    mesh.ensure_running()

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
                # --at is preferred, --slice is legacy fallback.
                # --clone (without --at) means "fork at tail": compute line count
                # and use it as the slice ref, so the clone gets an isolated JSONL.
                slice_ref = getattr(args, 'at', None) or getattr(args, 'slice', None)
                if not slice_ref and getattr(args, 'clone', False):
                    try:
                        with open(jsonl_path, 'r') as _f:
                            tail_line = sum(1 for _ in _f)
                        if tail_line > 0:
                            slice_ref = f"L{tail_line}"
                    except Exception:
                        pass
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

    # Inject Claude Code lifecycle hooks into <workdir>/.claude/settings.json
    # so the new agent auto-reports AGENT_STARTED / AGENT_STOPPED via aura mesh.
    # Picasso-steal from octogent. Idempotent.
    try:
        from lib import hooks
        hook_result = hooks.inject(workdir, emit_lifecycle=not getattr(args, 'silent', False))
    except Exception:
        hook_result = None

    # Create window in the correct working directory
    # --as-pane → detached new-window so we don't steal focus from a human-watched session
    terminal.create_window(args.name, workdir, detached=getattr(args, 'as_pane', False))

    # Build aura.py command
    aura_wrapper = "/home/axp/projects/aura/main/wrapper/aura.py"
    parent_name = _infer_parent_from_caller()
    env_parts = []
    if parent_name:
        env_parts.append(f"AURA_PARENT={parent_name!r}")
    cmd_parts = env_parts + ["python3", aura_wrapper, "--name", args.name]

    if args.memory:
        # Use full session ID if we found it (may be sliced session)
        session_id = full_session_id or args.memory
        cmd_parts.extend(["-r", session_id])
        # Note: --slice is handled above in spawn.py, not passed to aura.py

    if args.knowledge:
        cmd_parts.extend(["--from", args.knowledge])

    cmd_parts.append("--dangerously-skip-permissions")

    # Pass --model through to Claude if specified.
    # NOTE: the bare alias 'opus' resolves to the 200K-context Opus 4.6, NOT the 1M variant.
    # For the 1M variant, pass the full model ID 'claude-opus-4-6[1m]' (brackets quoted).
    # Omitting --model falls back to the user's configured default (typically 1M opus).
    model = getattr(args, 'model', None)
    if model:
        # Shell-quote values with brackets so the shell doesn't interpret them as glob chars.
        if any(c in model for c in "[]"):
            cmd_parts.extend(["--model", f"'{model}'"])
        else:
            cmd_parts.extend(["--model", model])

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
                return _result({"ok": False, "error": "timeout waiting for registration", "name": args.name})

        # Send prompt if specified
        if args.prompt:
            # Brief wait — wrapper gates message injection on Claude readiness
            time.sleep(1)

            if mesh_available:
                result = mesh.send_message(args.name, args.prompt)
                if not result.get("error"):
                    return _result({"ok": True, "name": args.name, "registered": True, "prompt_sent": True})

            # Mesh unavailable or send failed - fall back to direct terminal with delay scaling
            # Delay formula from aura.py: handles long prompts (up to 5KB+)
            prompt_bytes = len(args.prompt.encode('utf-8'))
            delay = min(2.0, max(0.3, prompt_bytes / 2500))
            terminal.send_keys(args.name, args.prompt)
            time.sleep(delay)
            terminal.send_keys(args.name, "", enter=True)
            return _result({"ok": True, "name": args.name, "prompt_sent": True, "fallback": terminal.BACKEND_NAME})

    result = {"ok": True, "name": args.name, "spawned": True}
    if hook_result:
        result["hooks"] = hook_result
    return _result(result)


def _spawn_terminal_runtime(args, terminal, result_fn):
    """Spawn a generic terminal-backed runtime without Claude wrapper coupling."""
    from lib import runtimes

    runtime, spec = runtimes.resolve_runtime(getattr(args, 'runtime', None) or "claude-code")
    profile = getattr(args, 'profile', None) or args.name
    command = runtimes.build_command(
        runtime,
        spec,
        name=args.name,
        profile=profile,
        model=getattr(args, 'model', None),
        command_override=getattr(args, 'launch_command', None),
    )
    workdir = os.getcwd()

    terminal.create_window(args.name, workdir, detached=getattr(args, 'as_pane', False))
    time.sleep(0.3)
    launch = terminal.send_text(args.name, command, submit=True)
    if not launch.get("ok"):
        return result_fn({"ok": False, "error": launch.get("error", "launch failed"), "name": args.name})

    result = {
        "ok": True,
        "name": args.name,
        "spawned": True,
        "runtime": runtime,
        "profile": profile if runtime == "hermes" else None,
        "command": command,
        "workdir": workdir,
        "terminal_ref": launch.get("target"),
        "status": "starting",
    }

    if getattr(args, 'prompt', None):
        time.sleep(1)
        prompt_result = terminal.send_text(args.name, args.prompt, submit=True)
        result["prompt_sent"] = bool(prompt_result.get("ok"))
        if not prompt_result.get("ok"):
            result["prompt_error"] = prompt_result.get("error")

    return result_fn({k: v for k, v in result.items() if v is not None})


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
