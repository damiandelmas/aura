"""Spawn new agent."""

import json
import os
import subprocess
import sys
import time
import uuid
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
    manifest_result = _apply_spawn_manifest(args)
    if manifest_result and not manifest_result.get("ok"):
        return manifest_result

    if not getattr(args, 'name', None):
        return {"ok": False, "error": "agent name is required unless --manifest or --role-home supplies a seat"}

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
    resume_session = getattr(args, 'resume_session', None)
    launch_command = getattr(args, 'launch_command', None)
    if resume_session:
        if launch_command:
            return result_fn({"ok": False, "error": "use either --resume-session or --command, not both", "name": args.name})
        try:
            launch_command = runtimes.build_resume_command(runtime, resume_session)
        except ValueError as exc:
            return result_fn({"ok": False, "error": str(exc), "name": args.name})
    profile = getattr(args, 'profile', None) or args.name
    command = runtimes.build_command(
        runtime,
        spec,
        name=args.name,
        profile=profile,
        model=getattr(args, 'model', None),
        command_override=launch_command,
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
    launch_id = f"aura-launch-{uuid.uuid4().hex[:16]}"

    launch_env = {
        "AURA_AGENT_NAME": args.name,
        "AURA_SEAT": args.name,
        "AURA_FLEET": fleet,
        "AURA_RUNTIME": runtime,
        "AURA_LAUNCH_ID": launch_id,
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "FORCE_COLOR": "1",
        "CLICOLOR_FORCE": "1",
    }
    role_meta = getattr(args, "_role_manifest_meta", None) or {}
    if role_meta:
        launch_env.update({
            "AURA_DESKS_ROLE_HOME": role_meta.get("desks_role_home", ""),
            "AURA_DESKS_ROLE_ID": role_meta.get("desks_role_id", ""),
            "AURA_DESKS_PRODUCT": role_meta.get("desks_product", ""),
            "AURA_DESKS_UNIT": role_meta.get("desks_unit", ""),
            "AURA_DESKS_MANIFEST": role_meta.get("desks_manifest", ""),
        })
    try:
        launch = terminal.create_window(
            args.name,
            workdir,
            detached=getattr(args, 'as_pane', False),
            command=command,
            env=launch_env,
            unset_env=[
                "NO_COLOR",
                "AURA_RUNTIME_SESSION_ID",
                "AURA_SESSION_ID",
                "CODEX_THREAD_ID",
                "CLAUDE_SESSION_ID",
            ],
        )
    except TypeError:
        # Compatibility for tests or alternate terminal backends that have not
        # grown direct command launch yet.
        terminal.create_window(args.name, workdir, detached=getattr(args, 'as_pane', False))
        time.sleep(0.3)
        launch = terminal.send_text(args.name, command, submit=True)
    if not launch.get("ok"):
        return result_fn({"ok": False, "error": launch.get("error", "launch failed"), "name": args.name})

    pane_ref = f"tmux:{fleet}:{launch.get('pane_id')}" if launch.get("pane_id") else None
    process_meta = {}
    if pane_ref and hasattr(terminal, "pane_pid"):
        try:
            from lib import runtime_session

            process_meta = runtime_session.process_metadata(terminal.pane_pid(pane_ref))
        except Exception:
            process_meta = {}
    session_meta = {}
    if resume_session:
        session_meta = {
            "session_id": resume_session,
            "runtime_session_id": resume_session,
            "runtime_session_source": "spawn:resume-session",
            "runtime_session_confidence": "exact",
            "runtime_session_evidence": {
                "reason": "aura-spawn-resume-session",
                "resume_session": resume_session,
            },
        }

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
        "aura_launch_id": launch_id,
        "source_session_id": resume_session,
        "runtime_session_mode": "native-resume" if resume_session else None,
        "isolation": "shared-native-thread" if resume_session and runtime == "codex" else None,
        "terminal_ref": launch.get("target"),
        "pane_ref": pane_ref,
        "transport": "tmux",
        "status": "starting",
        "registered": True,
        **role_meta,
        **process_meta,
        **session_meta,
    })
    try:
        from lib import session_ledger

        session_ledger.append_record({
            "event": "spawn",
            "seat": args.name,
            "name": args.name,
            "fleet": fleet,
            "runtime": runtime,
            "profile": profile if runtime == "hermes" else None,
            "command": command,
            "aura_launch_id": launch_id,
            "source_session_id": resume_session,
            "runtime_session_mode": "native-resume" if resume_session else None,
            "isolation": "shared-native-thread" if resume_session and runtime == "codex" else None,
            "cwd": workdir,
            "workdir": workdir,
            "context_file": str(context_path) if context_path else None,
            "work_file": str(work_path) if work_path else None,
            "terminal_ref": launch.get("target"),
            "pane_ref": pane_ref,
            "status": "starting",
            **role_meta,
            **process_meta,
            **session_meta,
        })
    except Exception:
        pass

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
        "aura_launch_id": launch_id,
        "source_session_id": resume_session,
        "runtime_session_mode": "native-resume" if resume_session else None,
        "isolation": "shared-native-thread" if resume_session and runtime == "codex" else None,
        "terminal_ref": launch.get("target"),
        "pane_ref": pane_ref,
        "status": "starting",
        "registered": True,
        "fleet": fleet,
        "trace_cell": registered.get("trace_cell"),
        **role_meta,
        **process_meta,
        **session_meta,
    }

    if prompt_text:
        time.sleep(1)
        prompt_target = pane_ref or launch.get("target") or args.name
        prompt_result = terminal.send_text(
            args.name,
            _augment_runtime_prompt(runtime, prompt_text, fleet=fleet, seat=args.name, launch_id=launch_id),
            submit=True,
        )
        result["prompt_sent"] = bool(prompt_result.get("ok"))
        if not prompt_result.get("ok"):
            result["prompt_error"] = prompt_result.get("error")
        elif runtime == "codex" and hasattr(terminal, "send_keys"):
            result["prompt_submit_retry"] = _retry_codex_prompt_submit(
                terminal=terminal,
                target=prompt_target,
                seat=args.name,
                launch_id=launch_id,
            )

    session_observation = _observe_spawn_session(
        runtime=runtime,
        terminal=terminal,
        target=pane_ref or launch.get("target") or args.name,
        seat=args.name,
        fleet=fleet,
        launch_id=launch_id,
        workdir=workdir,
        terminal_ref=launch.get("target"),
        pane_ref=pane_ref,
        registered=registered,
        existing_session=session_meta,
        timeout=float(os.environ.get("AURA_SPAWN_SESSION_OBSERVE_TIMEOUT", "6.0" if prompt_text else "0.5")),
    )
    if session_observation:
        result["session_observation"] = session_observation
        if session_observation.get("runtime_session_id"):
            session_observation.setdefault("session_id", session_observation["runtime_session_id"])
            session_fields = {
                key: session_observation.get(key)
                for key in (
                    "session_id",
                    "runtime_session_id",
                    "runtime_session_source",
                    "runtime_session_confidence",
                    "runtime_session_evidence",
                    "runtime_session_env",
                    "runtime_session_cwd",
                    "runtime_session_created_at_ms",
                    "runtime_session_updated_at_ms",
                    "runtime_session_pid",
                )
                if session_observation.get(key) is not None
            }
            result.update(session_fields)

    _record_workspace_spawn(workdir_path, result, runtime=runtime)
    return result_fn({k: v for k, v in result.items() if v is not None})


def _runtime_home(runtime: str, profile: str | None) -> str | None:
    if runtime == "hermes" and profile:
        return str(Path.home() / ".hermes" / "profiles" / profile)
    return None


def _apply_spawn_manifest(args) -> dict | None:
    """Apply role manifest defaults to spawn args.

    Aura stays role-naive at runtime. This adapter only consumes a strict launch
    contract and records the role metadata with the spawned seat.
    """
    manifest_arg = getattr(args, "manifest", None)
    role_home_arg = getattr(args, "role_home", None)
    if not manifest_arg and not role_home_arg:
        return None
    if manifest_arg and role_home_arg:
        return {"ok": False, "error": "use either --manifest or --role-home, not both"}

    try:
        manifest = _load_role_manifest(manifest_arg, role_home_arg)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    seat = manifest["seat"]
    fleet = manifest["fleet"]
    workspace_root = manifest["workspace_root"]
    bootstrap = manifest["files"]["bootstrap"]

    if getattr(args, "name", None) and args.name != seat:
        return {"ok": False, "error": f"manifest seat mismatch: name={args.name} manifest={seat}"}
    if getattr(args, "fleet", None) and args.fleet != fleet:
        return {"ok": False, "error": f"manifest fleet mismatch: --fleet={args.fleet} manifest={fleet}"}
    if getattr(args, "cwd", None):
        try:
            requested_cwd = Path(args.cwd).expanduser()
            if not requested_cwd.is_absolute():
                requested_cwd = Path.cwd() / requested_cwd
            requested_cwd = requested_cwd.resolve()
        except OSError:
            requested_cwd = Path(args.cwd)
        if requested_cwd != Path(workspace_root):
            return {"ok": False, "error": f"manifest cwd mismatch: --cwd={requested_cwd} manifest={workspace_root}"}
    if getattr(args, "prompt", None) or getattr(args, "work", None):
        return {"ok": False, "error": "manifest supplies the bootstrap prompt; do not combine with --prompt or --work"}

    args.name = seat
    args.fleet = fleet
    args.cwd = str(workspace_root)
    args.runtime = getattr(args, "runtime", None) or manifest.get("runtime") or "codex"
    args.prompt = "\n".join([
        f"Read {bootstrap} and follow it.",
        f"Use {manifest['role_home']} as your Desks role home.",
    ])
    if not getattr(args, "context", None) and manifest["files"].get("agents"):
        args.context = str(manifest["files"]["agents"])
    if not getattr(args, "profile", None):
        args.profile = manifest.get("profile") or seat
    args._role_manifest_meta = {
        "desks_role_home": str(manifest["role_home"]),
        "desks_role_id": manifest["role_id"],
        "desks_product": manifest["product"],
        "desks_unit": manifest["unit"],
        "desks_manifest": str(manifest["manifest_path"]),
        "desks_bootstrap": str(bootstrap),
        "desks_compression": str(manifest["files"].get("compression")) if manifest["files"].get("compression") else None,
        "desks_memory": str(manifest["files"].get("memory")) if manifest["files"].get("memory") else None,
    }
    args._role_manifest = manifest
    return {"ok": True, "manifest": str(manifest["manifest_path"])}


def _load_role_manifest(manifest_arg: str | None, role_home_arg: str | None) -> dict:
    manifest_path = Path(manifest_arg or Path(role_home_arg) / "role.json").expanduser()
    if not manifest_path.is_absolute():
        manifest_path = Path.cwd() / manifest_path
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_file():
        raise ValueError(f"manifest not found: {manifest_path}")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest is not valid JSON: {manifest_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("manifest must be a JSON object")
    schema = raw.get("schema")
    if schema != "desks.role.v1":
        raise ValueError(f"unsupported manifest schema: {schema!r}")

    required = ("product", "unit", "role_id", "seat", "fleet", "workspace_root", "files")
    missing = [field for field in required if not raw.get(field)]
    if missing:
        raise ValueError(f"manifest missing required field(s): {', '.join(missing)}")
    files = raw.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest files must be an object")

    role_home = manifest_path.parent
    manifest_role_home = raw.get("role_home")
    if manifest_role_home:
        declared = Path(str(manifest_role_home)).expanduser()
        if not declared.is_absolute():
            declared = (role_home / declared).resolve()
        else:
            declared = declared.resolve()
        if declared != role_home:
            raise ValueError(f"manifest role_home mismatch: {declared} != {role_home}")

    workspace_root = Path(str(raw["workspace_root"])).expanduser()
    if not workspace_root.is_absolute():
        workspace_root = (manifest_path.parent / workspace_root).resolve()
    else:
        workspace_root = workspace_root.resolve()
    if not workspace_root.is_dir():
        raise ValueError(f"manifest workspace_root is not a directory: {workspace_root}")

    required_files = ("soul", "agents", "memory", "bootstrap", "compression")
    missing_files = [field for field in required_files if not files.get(field)]
    if missing_files:
        raise ValueError(f"manifest files missing required key(s): {', '.join(missing_files)}")

    resolved_files = {}
    for key, value in files.items():
        if value in (None, ""):
            continue
        path = Path(str(value)).expanduser()
        if path.is_absolute():
            raise ValueError(f"manifest files.{key} must be relative to role_home: {value}")
        resolved = (role_home / path).resolve()
        try:
            resolved.relative_to(role_home)
        except ValueError as exc:
            raise ValueError(f"manifest files.{key} escapes role_home: {value}") from exc
        if key in required_files or key == "sessions":
            if not resolved.is_file():
                raise ValueError(f"manifest files.{key} not found: {resolved}")
        resolved_files[key] = resolved

    return {
        **raw,
        "manifest_path": manifest_path,
        "role_home": role_home,
        "workspace_root": workspace_root,
        "files": resolved_files,
    }


def _augment_runtime_prompt(runtime: str, prompt_text: str, *, fleet: str, seat: str, launch_id: str) -> str:
    if runtime != "codex":
        return prompt_text
    return "\n".join([
        "[AURA SEAT CONTEXT]",
        f"fleet={fleet}",
        f"seat={seat}",
        f"launch_id={launch_id}",
        "[/AURA SEAT CONTEXT]",
        "",
        prompt_text,
    ])


def _confidence_at_least(value: str | None, minimum: str) -> bool:
    order = {"exact": 4, "high": 3, "medium": 2, "low": 1}
    return order.get(value or "", 0) >= order[minimum]


def _retry_codex_prompt_submit(*, terminal, target: str, seat: str, launch_id: str) -> dict:
    """Nudge a freshly pasted Codex spawn prompt until the thread exists.

    Codex can briefly accept a tmux paste before its input widget is ready,
    especially on first-run trust or MCP startup screens. Repeating a literal
    Enter until state-db evidence appears makes spawn prompt delivery
    deterministic without binding the seat manually.
    """
    from lib import runtime_session

    attempts = []
    max_attempts = int(os.environ.get("AURA_CODEX_PROMPT_SUBMIT_RETRIES", "4"))
    for index in range(max(1, max_attempts)):
        time.sleep(0.5 if index == 0 else 1.5)
        retry_result = terminal.send_keys(target, "Enter", enter=False) or {}
        attempts.append(retry_result)
        time.sleep(0.5)
        try:
            session_info = runtime_session.discover_for_target(
                "codex",
                terminal,
                target,
                seat_name=seat,
                launch_id=launch_id,
            )
        except Exception:
            session_info = {}
        if session_info and _confidence_at_least(session_info.get("runtime_session_confidence"), "high"):
            return {
                "ok": True,
                "attempts": len(attempts),
                "results": attempts,
                "session_seen": True,
                "runtime_session_id": session_info.get("runtime_session_id"),
                "runtime_session_confidence": session_info.get("runtime_session_confidence"),
            }
    return {
        "ok": any(result.get("ok") for result in attempts),
        "attempts": len(attempts),
        "results": attempts,
        "session_seen": False,
    }


def _observe_spawn_session(
    *,
    runtime: str,
    terminal,
    target: str | None,
    seat: str,
    fleet: str,
    launch_id: str,
    workdir: str,
    terminal_ref: str | None,
    pane_ref: str | None,
    registered: dict,
    existing_session: dict,
    timeout: float,
) -> dict:
    """Best-effort post-spawn runtime session observation.

    This makes Aura-spawned Codex seats self-describing without requiring the
    agent to run bind-current as a ritual. It only binds evidence at high/exact
    confidence; bind-current remains the repair path for ambiguous sessions.
    """
    if runtime != "codex":
        return {"status": "skipped", "reason": "runtime-not-observed-at-spawn", "runtime": runtime}

    if existing_session.get("runtime_session_id") and _confidence_at_least(
        existing_session.get("runtime_session_confidence"),
        "high",
    ):
        session_id = existing_session.get("runtime_session_id")
        return {
            "status": "already-bound",
            "session_id": session_id,
            "runtime_session_id": session_id,
            "runtime_session_source": existing_session.get("runtime_session_source"),
            "runtime_session_confidence": existing_session.get("runtime_session_confidence"),
            "runtime_session_evidence": existing_session.get("runtime_session_evidence"),
        }

    if not target or not hasattr(terminal, "pane_pid"):
        return {"status": "pending", "reason": "no-pane-target", "runtime": runtime}

    from lib import registry, runtime_session, session_ledger

    deadline = time.time() + max(timeout, 0)
    attempts = 0
    last_session: dict = {}
    while True:
        attempts += 1
        try:
            session_info = runtime_session.discover_for_target(
                runtime,
                terminal,
                target,
                seat_name=seat,
                launch_id=launch_id,
            )
        except Exception as exc:
            return {
                "status": "error",
                "reason": "session-discovery-error",
                "error": str(exc),
                "attempts": attempts,
            }

        if session_info:
            last_session = session_info
            if _confidence_at_least(session_info.get("runtime_session_confidence"), "high"):
                merged = registry.upsert_agent(runtime_session.merge(dict(registered), session_info))
                try:
                    session_ledger.append_record({
                        "event": "session_observed_after_spawn",
                        "seat": seat,
                        "name": seat,
                        "fleet": fleet,
                        "runtime": runtime,
                        "terminal_ref": terminal_ref,
                        "pane_ref": pane_ref,
                        "cwd": merged.get("cwd") or merged.get("workdir") or workdir,
                        "workdir": merged.get("workdir") or workdir,
                        "aura_launch_id": launch_id,
                        "observation_attempts": attempts,
                        **session_info,
                    })
                except Exception:
                    pass
                return {
                    "status": "observed",
                    "attempts": attempts,
                    "session_id": session_info.get("runtime_session_id"),
                    **session_info,
                }

        if time.time() >= deadline:
            break
        time.sleep(0.25)

    pending = {
        "status": "pending",
        "reason": "no-high-confidence-session-evidence",
        "attempts": attempts,
        "runtime": runtime,
    }
    if last_session:
        pending.update({
            "last_runtime_session_id": last_session.get("runtime_session_id"),
            "last_runtime_session_source": last_session.get("runtime_session_source"),
            "last_runtime_session_confidence": last_session.get("runtime_session_confidence"),
            "last_runtime_session_evidence": last_session.get("runtime_session_evidence"),
        })
    return pending


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
            "aura_launch_id": result.get("aura_launch_id"),
            "source_session_id": result.get("source_session_id"),
            "runtime_session_mode": result.get("runtime_session_mode"),
            "isolation": result.get("isolation"),
            "runtime_session_id": result.get("runtime_session_id"),
            "runtime_session_env": result.get("runtime_session_env"),
            "runtime_session_source": result.get("runtime_session_source"),
            "runtime_session_confidence": result.get("runtime_session_confidence"),
            "runtime_session_evidence": result.get("runtime_session_evidence"),
            "runtime_process_pid": result.get("runtime_process_pid"),
            "runtime_process_cwd": result.get("runtime_process_cwd"),
            "runtime_process_started_at_epoch": result.get("runtime_process_started_at_epoch"),
            "runtime_process_argv": result.get("runtime_process_argv"),
            "command": result.get("command"),
            "terminal_ref": result.get("terminal_ref"),
            "pane_ref": result.get("pane_ref"),
            "prompt_sent": result.get("prompt_sent", False),
            "desks_role_home": result.get("desks_role_home"),
            "desks_role_id": result.get("desks_role_id"),
            "desks_product": result.get("desks_product"),
            "desks_unit": result.get("desks_unit"),
            "desks_manifest": result.get("desks_manifest"),
            "desks_bootstrap": result.get("desks_bootstrap"),
            "desks_compression": result.get("desks_compression"),
            "desks_memory": result.get("desks_memory"),
        })
        workspace_state.write_latest_session(workdir, record)
        try:
            from lib import session_ledger

            session_ledger.append_record({
                "event": "workspace_spawn",
                **{k: v for k, v in record.items() if v is not None},
            })
        except Exception:
            pass
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
