"""Spawn new agent."""

import os
import subprocess
import sys
import time
from pathlib import Path

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
    if getattr(args, 'prompt', None) and getattr(args, 'work', None):
        return {"ok": False, "error": "use either --prompt or --work, not both"}

    # Determine fleet name BEFORE importing terminal (it reads env at import time)
    # Priority: --fleet flag > caller-derived default.
    fleet = getattr(args, 'fleet', None) or _infer_fleet_from_caller()
    if fleet:
        os.environ["AURA_FLEET"] = fleet
        os.environ["AURA_PROJECT"] = fleet

    from lib import mesh, terminal
    if fleet and hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)

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
    from lib import runtimes, workspace_state

    workdir = str(workspace_state.resolve_workdir(getattr(args, 'cwd', None)))
    full_session_id = None

    # If resuming a session, find it and extract workdir
    if args.memory and not getattr(args, 'cwd', None):
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

    _, legacy_spec = runtimes.resolve_runtime("claude-code")
    workdir_path = Path(workdir).resolve()
    context_path = workspace_state.infer_context_file(
        workdir_path,
        legacy_spec,
        getattr(args, 'context', None),
    )
    work_path = workspace_state.resolve_existing_file(
        getattr(args, 'work', None),
        workdir=workdir_path,
        label="work",
    )
    prompt_text = workspace_state.read_work_prompt(work_path) or getattr(args, 'prompt', None)

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
    if args.wait or prompt_text:
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
        if prompt_text:
            # Brief wait — wrapper gates message injection on Claude readiness
            time.sleep(1)

            if mesh_available:
                result = mesh.send_message(args.name, prompt_text)
                if not result.get("error"):
                    base = {
                        "ok": True,
                        "name": args.name,
                        "registered": True,
                        "prompt_sent": True,
                        "workdir": workdir,
                        "context_file": str(context_path) if context_path else None,
                        "work_file": str(work_path) if work_path else None,
                    }
                    out = _result({k: v for k, v in base.items() if v is not None})
                    _record_workspace_spawn(workdir_path, out, runtime="claude-code")
                    return out

            # Mesh unavailable or send failed - fall back to direct terminal with delay scaling
            # Delay formula from aura.py: handles long prompts (up to 5KB+)
            prompt_bytes = len(prompt_text.encode('utf-8'))
            delay = min(2.0, max(0.3, prompt_bytes / 2500))
            terminal.send_keys(args.name, prompt_text)
            time.sleep(delay)
            terminal.send_keys(args.name, "", enter=True)
            base = {
                "ok": True,
                "name": args.name,
                "prompt_sent": True,
                "fallback": terminal.BACKEND_NAME,
                "workdir": workdir,
                "context_file": str(context_path) if context_path else None,
                "work_file": str(work_path) if work_path else None,
            }
            out = _result({k: v for k, v in base.items() if v is not None})
            _record_workspace_spawn(workdir_path, out, runtime="claude-code")
            return out

    result = {
        "ok": True,
        "name": args.name,
        "spawned": True,
        "workdir": workdir,
        "context_file": str(context_path) if context_path else None,
        "work_file": str(work_path) if work_path else None,
    }
    if hook_result:
        result["hooks"] = hook_result
    out = _result({k: v for k, v in result.items() if v is not None})
    _record_workspace_spawn(workdir_path, out, runtime="claude-code")
    return out


def _spawn_terminal_runtime(args, terminal, result_fn):
    """Spawn a generic terminal-backed runtime without Claude wrapper coupling."""
    from lib import registry, runtimes, workspace_state

    if getattr(args, 'prompt', None) and getattr(args, 'work', None):
        return result_fn({"ok": False, "error": "use either --prompt or --work, not both", "name": args.name})

    requested_runtime = getattr(args, 'runtime', None)
    if not requested_runtime and getattr(args, 'launch_command', None):
        requested_runtime = "command"
    runtime, spec = runtimes.resolve_runtime(requested_runtime)
    profile = getattr(args, 'profile', None) or args.name
    command = runtimes.build_command(
        runtime,
        spec,
        name=args.name,
        profile=profile,
        model=getattr(args, 'model', None),
        command_override=getattr(args, 'launch_command', None),
    )
    workdir_path = workspace_state.resolve_workdir(getattr(args, 'cwd', None))
    workdir = str(workdir_path)
    context_path = workspace_state.infer_context_file(
        workdir_path,
        spec,
        getattr(args, 'context', None),
    )
    work_path = workspace_state.resolve_existing_file(
        getattr(args, 'work', None),
        workdir=workdir_path,
        label="work",
    )
    prompt_text = workspace_state.read_work_prompt(work_path) or getattr(args, 'prompt', None)
    native_state_ref = workspace_state.infer_native_state_ref(workdir_path, spec)
    fleet = getattr(terminal, "SESSION_NAME", None) or registry.current_fleet(default="aura")

    launch_env = {
        "AURA_AGENT_NAME": args.name,
        "AURA_SEAT": args.name,
        "AURA_FLEET": fleet,
        "AURA_RUNTIME": runtime,
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "FORCE_COLOR": "1",
        "CLICOLOR_FORCE": "1",
    }
    try:
        launch = terminal.create_window(
            args.name,
            workdir,
            detached=getattr(args, 'as_pane', False),
            command=command,
            env=launch_env,
            unset_env=["NO_COLOR"],
        )
    except TypeError:
        # Compatibility for tests or alternate terminal backends that have not
        # grown direct command launch yet.
        terminal.create_window(args.name, workdir, detached=getattr(args, 'as_pane', False))
        time.sleep(0.3)
        launch = terminal.send_text(args.name, command, submit=True)
    if not launch.get("ok"):
        return result_fn({"ok": False, "error": launch.get("error", "launch failed"), "name": args.name})

    registered = registry.upsert_agent({
        "name": args.name,
        "fleet": fleet,
        "runtime": runtime,
        "profile": profile if runtime == "hermes" else None,
        "command": command,
        "workdir": workdir,
        "cwd": workdir,
        "context_file": str(context_path) if context_path else None,
        "work_file": str(work_path) if work_path else None,
        "runtime_home": _runtime_home(runtime, profile),
        "native_state_ref": native_state_ref,
        "terminal_ref": launch.get("target"),
        "pane_ref": f"tmux:{fleet}:{launch.get('pane_id')}" if launch.get("pane_id") else None,
        "transport": "tmux",
        "status": "starting",
        "registered": True,
    })

    result = {
        "ok": True,
        "name": args.name,
        "spawned": True,
        "runtime": runtime,
        "profile": profile if runtime == "hermes" else None,
        "command": command,
        "workdir": workdir,
        "cwd": workdir,
        "context_file": str(context_path) if context_path else None,
        "work_file": str(work_path) if work_path else None,
        "runtime_home": _runtime_home(runtime, profile),
        "native_state_ref": native_state_ref,
        "terminal_ref": launch.get("target"),
        "pane_ref": f"tmux:{fleet}:{launch.get('pane_id')}" if launch.get("pane_id") else None,
        "status": "starting",
        "registered": True,
        "fleet": fleet,
        "trace_cell": registered.get("trace_cell"),
    }

    if prompt_text:
        time.sleep(1)
        prompt_result = terminal.send_text(args.name, prompt_text, submit=True)
        result["prompt_sent"] = bool(prompt_result.get("ok"))
        if not prompt_result.get("ok"):
            result["prompt_error"] = prompt_result.get("error")

    _record_workspace_spawn(workdir_path, result, runtime=runtime)
    return result_fn({k: v for k, v in result.items() if v is not None})


def _runtime_home(runtime: str, profile: str | None) -> str | None:
    if runtime == "hermes" and profile:
        return str(Path.home() / ".hermes" / "profiles" / profile)
    return None


def _record_workspace_spawn(workdir: Path, result: dict, *, runtime: str) -> None:
    try:
        from lib import workspace_state

        record = workspace_state.append_session_record(workdir, {
            "event": "spawn",
            "seat": result.get("name"),
            "name": result.get("name"),
            "fleet": result.get("fleet"),
            "runtime": runtime,
            "cwd": result.get("cwd") or result.get("workdir"),
            "workdir": result.get("workdir"),
            "context_file": result.get("context_file"),
            "work_file": result.get("work_file"),
            "profile": result.get("profile"),
            "runtime_home": result.get("runtime_home"),
            "native_state_ref": result.get("native_state_ref"),
            "runtime_session_id": result.get("runtime_session_id"),
            "runtime_session_env": result.get("runtime_session_env"),
            "command": result.get("command"),
            "terminal_ref": result.get("terminal_ref"),
            "pane_ref": result.get("pane_ref"),
            "prompt_sent": result.get("prompt_sent", False),
        })
        workspace_state.write_latest_session(workdir, record)
    except Exception as exc:
        result["workspace_state_error"] = str(exc)


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
