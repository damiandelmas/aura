"""Spawn new agent."""

import os
import shlex
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


def _resolve_package_env(agent_package: dict, runtime: str) -> tuple[dict[str, str], dict[str, str]]:
    if runtime in {"codex", "omx"}:
        return {}, {}
    root = agent_package.get("root")
    env = agent_package.get("env")
    if not root or not isinstance(env, dict):
        return {}, {}
    root_path = Path(str(root)).expanduser().resolve()
    resolved: dict[str, str] = {}
    meta: dict[str, str] = {}
    for key, value in env.items():
        if value is None:
            continue
        value_text = str(value)
        value_path = Path(value_text).expanduser()
        if value_path.is_absolute():
            resolved_value = str(value_path)
        else:
            resolved_value = str((root_path / value_text).resolve())
        resolved[str(key)] = resolved_value
    if runtime == "gajae-code":
        if resolved.get("GJC_CONFIG_DIR"):
            meta["gajae_code_package_gjc_config"] = resolved["GJC_CONFIG_DIR"]
        if resolved.get("GJC_CODING_AGENT_DIR"):
            meta["gajae_code_package_gjc_agent"] = resolved["GJC_CODING_AGENT_DIR"]
    return resolved, meta


def run(args):
    """Spawn a new agent."""
    if not getattr(args, 'name', None):
        return {"ok": False, "error": "agent name is required"}

    if getattr(args, 'prompt', None) and getattr(args, 'work', None):
        return {"ok": False, "error": "use either --prompt or --work, not both"}

    # Determine fleet name BEFORE importing terminal (it reads env at import time)
    # Priority: --fleet flag > caller-derived default.
    fleet_id = getattr(args, 'fleet_id', None)
    fleet = getattr(args, 'fleet', None)
    if fleet_id:
        from lib import fleets as fleets_lib

        resolved_fleet, fleet_record = fleets_lib.resolve_name_or_id(fleet_id)
        if not fleet_record:
            return {"ok": False, "error": f"unknown fleet id: {fleet_id}", "fleet_id": fleet_id}
        fleet = fleet or resolved_fleet
    fleet = fleet or _infer_fleet_from_caller()
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

                # If slicing, do it HERE so we can symlink the result.
                slice_ref = getattr(args, 'at', None)
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
        # Note: --at slicing is handled above in spawn.py, not passed to aura.py

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

    native_prompt_argv = bool(prompt_text and not args.memory)
    if native_prompt_argv:
        cmd_parts.append(shlex.quote(prompt_text))
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

        # Prompt was included in the native Claude argv.  Keep the legacy mesh
        # wait as readiness evidence, but do not send the prompt a second time.
        if prompt_text and native_prompt_argv:
            base = {
                "ok": True,
                "name": args.name,
                "registered": registered if mesh_available else None,
                "prompt_delivery": {
                    "submitted": True,
                    "transport": "runtime-native-argv",
                    "mode": "initial-argument",
                },
                "workdir": workdir,
                "context_file": str(context_path) if context_path else None,
                "work_file": str(work_path) if work_path else None,
            }
            out = _result({k: v for k, v in base.items() if v is not None})
            _record_workspace_spawn(workdir_path, out, runtime="claude-code")
            return out

        # Send prompt if specified and native argv is unavailable.
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
                        "prompt_delivery": {"submitted": True, "transport": "mesh"},
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
                "prompt_delivery": {"submitted": True, "transport": terminal.BACKEND_NAME},
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
    from lib import registry, runtimes, state, workspace_state

    if getattr(args, 'prompt', None) and getattr(args, 'work', None):
        return result_fn({"ok": False, "error": "use either --prompt or --work, not both", "name": args.name})

    requested_runtime = getattr(args, 'runtime', None)
    if not requested_runtime and getattr(args, 'launch_command', None):
        requested_runtime = "command"
    runtime, spec = runtimes.resolve_runtime(requested_runtime)
    resume_session = getattr(args, 'resume_session', None)
    fork_session = getattr(args, 'fork_session', None)
    custom_launch_command = getattr(args, 'launch_command', None)
    launch_command = custom_launch_command
    try:
        workdir_path = workspace_state.resolve_workdir(getattr(args, 'cwd', None))
    except ValueError as exc:
        return result_fn({"ok": False, "error": "cwd-invalid", "detail": str(exc), "name": args.name})
    workdir = str(workdir_path)
    if resume_session and fork_session:
        return result_fn({"ok": False, "error": "use either --resume-session or --fork-session, not both", "name": args.name})
    if resume_session:
        if launch_command:
            return result_fn({"ok": False, "error": "use either --resume-session or --command, not both", "name": args.name})
        try:
            launch_command = runtimes.build_resume_command(runtime, resume_session, cwd=workdir)
        except ValueError as exc:
            return result_fn({"ok": False, "error": str(exc), "name": args.name})
    if fork_session and launch_command:
        return result_fn({"ok": False, "error": "use either --fork-session or --command, not both", "name": args.name})
    role_meta = {}
    agent_package = dict(getattr(args, "_agent_package", None) or {})
    agent_package_meta = {
        "agent_package_id": agent_package.get("agent_id"),
        "agent_package_address": agent_package.get("address"),
        "agent_package_alias": agent_package.get("alias"),
        "agent_package_root": agent_package.get("root"),
    } if agent_package else {}
    identity_provider_arg = getattr(args, "identity_provider", None)
    identity_id_arg = getattr(args, "identity_id", None)
    identity_label_arg = getattr(args, "identity_label", None)
    if identity_provider_arg or identity_id_arg or identity_label_arg:
        if not identity_provider_arg or not identity_id_arg:
            return result_fn({
                "ok": False,
                "error": "identity-provider-and-id-required",
                "detail": "--identity-provider and --identity-id are required when passing spawn identity metadata",
                "name": args.name,
            })
        role_meta.update({
            "identity_provider": identity_provider_arg,
            "identity_id": identity_id_arg,
            "identity_bind_source": "aura-spawn",
            "identity_bind_confidence": "explicit",
        })
        if identity_label_arg:
            role_meta["identity_label"] = identity_label_arg
    raw_profile = getattr(args, 'profile', None)
    explicit_omx_profile = getattr(args, 'omx_profile', None)
    runtime_profile_ref_arg = getattr(args, 'runtime_profile', None)
    boxed_requested = bool(getattr(args, 'boxed', False))
    runtime_profile = None
    runtime_profile_ref = None
    runtime_profile_source = None
    if runtime_profile_ref_arg:
        try:
            ref_runtime, ref_profile, canonical_ref = _normalize_runtime_profile_ref(
                runtime_profile_ref_arg,
                expected_runtime=runtime,
            )
        except ValueError as exc:
            return result_fn({
                "ok": False,
                "error": "invalid-runtime-profile",
                "detail": str(exc),
                "name": args.name,
                "runtime": runtime,
            })
        runtime_profile = ref_profile
        runtime_profile_ref = canonical_ref
        runtime_profile_source = "cli-runtime-profile"
    profile_source = "cli" if raw_profile else None
    if runtime == "omx" and raw_profile and explicit_omx_profile and raw_profile != explicit_omx_profile:
        return result_fn({
            "ok": False,
            "error": "conflicting-omx-profile",
            "detail": "use either --omx-profile or --profile for OMX, not both with different values",
            "name": args.name,
            "runtime": runtime,
        })
    if runtime == "omx" and runtime_profile and explicit_omx_profile and runtime_profile != explicit_omx_profile:
        return result_fn({
            "ok": False,
            "error": "conflicting-omx-profile",
            "detail": "use either --runtime-profile omx/NAME or --omx-profile for OMX, not both with different values",
            "name": args.name,
            "runtime": runtime,
        })
    if runtime == "omx" and runtime_profile and raw_profile and raw_profile != runtime_profile:
        return result_fn({
            "ok": False,
            "error": "conflicting-omx-profile",
            "detail": "use either --runtime-profile omx/NAME or --profile for OMX, not both with different values",
            "name": args.name,
            "runtime": runtime,
        })
    if boxed_requested and runtime not in {"codex", "omx"}:
        return result_fn({
            "ok": False,
            "error": "boxed-runtime-not-supported",
            "detail": f"--boxed is not supported for runtime {runtime}",
            "name": args.name,
            "runtime": runtime,
        })
    profile = None if runtime == "hermes" else raw_profile or args.name
    omx_profile = None
    codex_profile = None
    if runtime == "omx":
        if explicit_omx_profile:
            omx_profile = explicit_omx_profile
            runtime_profile_source = "cli-omx-profile"
        elif runtime_profile:
            omx_profile = runtime_profile
        elif raw_profile:
            omx_profile = raw_profile
            runtime_profile_source = "cli-profile"
        if omx_profile:
            runtime_profile = omx_profile
            runtime_profile_ref = f"omx/{omx_profile}"
    elif runtime == "codex":
        if runtime_profile:
            codex_profile = runtime_profile
        elif runtime_profile_ref_arg:
            codex_profile = runtime_profile
    elif runtime == "hermes":
        if runtime_profile:
            profile = runtime_profile
            profile_source = "cli-runtime-profile"
        elif raw_profile:
            profile = raw_profile
            if not runtime_profile_ref:
                runtime_profile = raw_profile
                runtime_profile_ref = f"hermes/{raw_profile}"
                runtime_profile_source = profile_source or "cli-profile"
        else:
            runtime_profile = "default"
            runtime_profile_ref = "hermes/default"
            runtime_profile_source = runtime_profile_source or "runtime-default"
        hermes_root = _runtime_home(runtime, profile)
        if hermes_root and not Path(hermes_root).is_dir():
            return result_fn({
                "ok": False,
                "error": "runtime-profile-not-found",
                "detail": f"Hermes runtime profile not found: {hermes_root}",
                "name": args.name,
                "runtime": runtime,
                "runtime_profile_ref": runtime_profile_ref,
                "expected_root": hermes_root,
            })
    elif runtime_profile_ref_arg:
        return result_fn({
            "ok": False,
            "error": "runtime-profile-not-supported",
            "detail": f"--runtime-profile is not supported for runtime {runtime}",
            "name": args.name,
            "runtime": runtime,
        })
    if codex_profile:
        runtime_profile = codex_profile
        runtime_profile_ref = f"codex/{codex_profile}"
    runtime_profile_meta = {}
    if runtime_profile and runtime_profile_ref:
        runtime_profile_meta = {
            "runtime_profile": runtime_profile,
            "runtime_profile_ref": runtime_profile_ref,
            "runtime_profile_runtime": runtime,
            "runtime_profile_source": runtime_profile_source or "cli-runtime-profile",
        }
    recorded_profile = profile if runtime == "hermes" else omx_profile if runtime == "omx" else codex_profile if runtime == "codex" else None
    try:
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
    except (OSError, ValueError) as exc:
        return result_fn({"ok": False, "error": "launch-input-invalid", "detail": str(exc), "name": args.name})
    if runtime == "hermes" and prompt_text and not _hermes_startup_prompt_allowed():
        return result_fn({
            "ok": False,
            "error": "hermes-startup-prompt-disabled",
            "detail": "Hermes does not support safe native startup prompt delivery; spawn Hermes without a startup payload and send work after readiness, or set AURA_HERMES_ALLOW_STARTUP_PROMPT=1.",
            "name": args.name,
            "runtime": runtime,
            "prompt_requested": True,
            "work_file": str(work_path) if work_path else None,
        })
    native_state_ref = workspace_state.infer_native_state_ref(workdir_path, spec)
    fleet = getattr(terminal, "SESSION_NAME", None) or registry.current_fleet(default="aura")
    launch_id = f"aura-launch-{uuid.uuid4().hex[:16]}"
    seat_instance_id = registry.new_seat_instance_id()
    flex_manifest, flex_root = _resolve_launch_flex_project(workdir_path)
    flex_packet = _render_flex_project_launch_packet(flex_manifest, flex_root)
    augmented_prompt = _augment_runtime_prompt(
        runtime,
        prompt_text,
        fleet=fleet,
        seat=args.name,
        launch_id=launch_id,
        flex_packet=flex_packet,
    ) if prompt_text else None
    native_initial_prompt_argv = bool(
        augmented_prompt
        and not fork_session
        and not resume_session
        and not launch_command
        and runtimes.supports_initial_prompt_argv(runtime, spec)
    )
    if fork_session:
        try:
            launch_command = runtimes.build_fork_command(runtime, fork_session, prompt=prompt_text, cwd=workdir)
        except ValueError as exc:
            return result_fn({"ok": False, "error": str(exc), "name": args.name})
    command = runtimes.build_command(
        runtime,
        spec,
        name=args.name,
        profile=profile,
        model=getattr(args, 'model', None),
        command_override=launch_command,
        prompt=augmented_prompt if native_initial_prompt_argv else None,
    )

    launch_env = {
        "AURA_AGENT_NAME": args.name,
        "AURA_SEAT": args.name,
        "AURA_FLEET": fleet,
        "AURA_RUNTIME": runtime,
        "AURA_LAUNCH_ID": launch_id,
        "AURA_SEAT_INSTANCE_ID": seat_instance_id,
        "AURA_STATE_DIR": str(state.state_root()),
        "AURA_REGISTRY_PATH": str(state.registry_path()),
        "AURA_SEAT_ALIASES_PATH": str(state.seat_aliases_path()),
        "AURA_FLEETS_PATH": str(state.fleet_registry_path()),
        "AURA_DELIVERY_LOG": str(state.delivery_log_path()),
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "FORCE_COLOR": "1",
        "CLICOLOR_FORCE": "1",
    }
    flex_meta = {}
    if flex_manifest and flex_root:
        flex_meta = {
            "flex_project_manifest": str(flex_manifest),
            "flex_project_root": str(flex_root),
        }

    if agent_package_meta:
        if agent_package_meta.get("agent_package_id"):
            launch_env["AURA_AGENT_PACKAGE_ID"] = str(agent_package_meta["agent_package_id"])
        if agent_package_meta.get("agent_package_root"):
            launch_env["AURA_AGENT_PACKAGE_ROOT"] = str(agent_package_meta["agent_package_root"])
        if agent_package_meta.get("agent_package_address"):
            launch_env["AURA_AGENT_PACKAGE_ADDRESS"] = str(agent_package_meta["agent_package_address"])
        if agent_package_meta.get("agent_package_alias"):
            launch_env["AURA_AGENT_PACKAGE_ALIAS"] = str(agent_package_meta["agent_package_alias"])
    package_env, package_env_meta = _resolve_package_env(agent_package, runtime)
    if package_env:
        launch_env.update(package_env)
    if role_meta:
        if role_meta.get("identity_provider"):
            launch_env["AURA_IDENTITY_PROVIDER"] = str(role_meta["identity_provider"])
        if role_meta.get("identity_id"):
            launch_env["AURA_IDENTITY_ID"] = str(role_meta["identity_id"])
        if role_meta.get("identity_label"):
            launch_env["AURA_IDENTITY_LABEL"] = str(role_meta["identity_label"])
    if flex_meta.get("flex_project_manifest"):
        launch_env["FLEX_PROJECT_MANIFEST"] = flex_meta["flex_project_manifest"]
    if flex_meta.get("flex_project_root"):
        launch_env["FLEX_PROJECT_ROOT"] = flex_meta["flex_project_root"]
    omx_box_meta = {}
    codex_box_meta = {}
    runtime_home = _runtime_home(runtime, profile)
    if agent_package.get("root") and runtime not in {"codex", "omx"}:
        runtime_home = str(Path(str(agent_package["root"])).expanduser().resolve())
        if runtime == "gajae-code":
            native_state_ref = package_env.get("GJC_CONFIG_DIR") or native_state_ref
    if runtime == "omx":
        try:
            from lib import omx as omx_lib

            omx_box = omx_lib.prepare_box(
                fleet=fleet,
                seat=args.name,
                source_cwd=workdir,
                profile=omx_profile,
                root_override=agent_package.get("root"),
                package_layout=bool(agent_package),
            )
            launch_env.update(omx_box.launch_env(workdir))
            omx_box_meta = omx_box.metadata()
            launch_env["AURA_RUNTIME_CAPSULE_REF"] = str(omx_box.root)
            runtime_home = str(omx_box.root)
            native_state_ref = str(omx_box.omx_state)
        except Exception as exc:
            return result_fn({
                "ok": False,
                "error": "omx-box-setup-failed",
                "detail": str(exc),
                "name": args.name,
                "runtime": runtime,
                "cwd": workdir,
                "fleet": fleet,
            })
    if runtime == "codex" and (boxed_requested or codex_profile):
        try:
            from lib import codex as codex_lib

            codex_box = codex_lib.prepare_box(
                fleet=fleet,
                seat=args.name,
                source_cwd=workdir,
                profile=codex_profile,
                root_override=agent_package.get("root"),
                package_layout=bool(agent_package),
            )
            launch_env.update(codex_box.launch_env(workdir))
            codex_box_meta = codex_box.metadata()
            launch_env["AURA_RUNTIME_CAPSULE_REF"] = str(codex_box.root)
            runtime_home = str(codex_box.root)
            native_state_ref = str(codex_box.codex_home)
        except Exception as exc:
            return result_fn({
                "ok": False,
                "error": "codex-box-setup-failed",
                "detail": str(exc),
                "name": args.name,
                "runtime": runtime,
                "cwd": workdir,
                "fleet": fleet,
            })
    spawn_preflight = _spawn_preflight(
        runtime=runtime,
        command=command,
        custom_launch_command=custom_launch_command,
        launch_env=launch_env,
        resume_session=resume_session,
        fork_session=fork_session,
        agent_package_root=agent_package.get("root"),
    )
    if not spawn_preflight.get("ok", False):
        return result_fn({
            "ok": False,
            "error": "spawn-preflight-failed",
            "name": args.name,
            "runtime": runtime,
            "cwd": workdir,
            "spawn_preflight": spawn_preflight,
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
                "CODEX_CI",
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
            "runtime_session_binding": "bound",
            "runtime_session_bind_method": "spawn-resume-session",
            "runtime_session_bind_source": "spawn:resume-session",
            "runtime_session_confidence": "exact",
            "runtime_session_evidence": {
                "reason": "aura-spawn-resume-session",
                "resume_session": resume_session,
            },
        }
    elif fork_session:
        session_meta = {
            "session_id": None,
            "runtime_session_id": None,
            "runtime_session_source": "spawn:fork-session",
            "runtime_session_binding": "pending-fork-child",
            "runtime_session_bind_method": "spawn-fork-session-source",
            "runtime_session_bind_source": "spawn:fork-session",
            "runtime_session_confidence": "source-exact-child-pending",
            "runtime_session_evidence": {
                "reason": "aura-spawn-fork-session",
                "source_session_id": fork_session,
            },
        }
    else:
        # upsert_agent merges with any previous row for the same fleet:seat.
        # A fresh spawn must clear old runtime-session evidence from that row.
        session_meta = {
            "session_id": None,
            "runtime_session_id": None,
            "runtime_session_source": None,
            "runtime_session_binding": "unbound",
            "runtime_session_bind_method": None,
            "runtime_session_bind_source": None,
            "runtime_session_confidence": None,
            "runtime_session_evidence": None,
            "runtime_session_env": None,
            "runtime_session_cwd": None,
            "runtime_session_created_at_ms": None,
            "runtime_session_updated_at_ms": None,
            "runtime_session_pid": None,
        }
    session_clear_keys = [key for key, value in session_meta.items() if value is None]
    has_identity_binding = bool(role_meta.get("identity_id"))
    identity_clear_keys = []
    if not has_identity_binding:
        identity_clear_keys = [
            "identity_provider",
            "identity_id",
            "identity_label",
            "identity_bound_at",
            "identity_bind_source",
            "identity_bind_confidence",
        ]
    elif role_meta.get("identity_id") and not role_meta.get("identity_bound_at"):
        role_meta = {**role_meta, "identity_bound_at": registry.now_iso()}

    registered = registry.upsert_agent({
        "name": args.name,
        "fleet": fleet,
        "runtime": runtime,
        "profile": recorded_profile,
        "command": command,
        "workdir": workdir,
        "cwd": workdir,
        "context_file": str(context_path) if context_path else None,
        "work_file": str(work_path) if work_path else None,
        "runtime_home": runtime_home,
        "native_state_ref": native_state_ref,
        "aura_launch_id": launch_id,
        "seat_instance_id": seat_instance_id,
        "source_session_id": fork_session or resume_session,
        "runtime_session_mode": "native-fork" if fork_session else "native-resume" if resume_session else None,
        "isolation": "forked-native-thread" if fork_session and runtime == "codex" else "shared-native-thread" if resume_session and runtime == "codex" else None,
        "terminal_ref": launch.get("target"),
        "backend_ref": launch.get("target"),
        "pane_ref": pane_ref,
        "physical_fleet": fleet,
        "transport": "tmux",
        "status": "starting",
        "registered": True,
        **agent_package_meta,
        **package_env_meta,
        **flex_meta,
        **runtime_profile_meta,
        **omx_box_meta,
        **codex_box_meta,
        **role_meta,
        **process_meta,
        **session_meta,
    })
    if session_clear_keys or identity_clear_keys:
        try:
            def clear_fields(current):
                stored = dict(current or registered)
                for clear_key in [*session_clear_keys, *identity_clear_keys]:
                    stored.pop(clear_key, None)
                return stored

            stored = registry.update_agent_record(args.name, fleet, clear_fields)
            registered = stored
        except Exception:
            pass

    capsule_launch = {}
    if not agent_package:
        try:
            from lib import runtime_capsules

            capsule_launch = runtime_capsules.write_aura_launch(registered, env_roots=launch_env)
            if capsule_launch.get("ok"):
                registered = registry.upsert_agent({
                    **registered,
                    "runtime_capsule_ref": capsule_launch.get("capsule_root"),
                    "runtime_capsule_launch": capsule_launch.get("path"),
                })
        except Exception as exc:
            capsule_launch = {"ok": False, "reason": "capsule-launch-write-failed", "error": str(exc)}

    try:
        from lib import session_ledger

        session_ledger.append_record({
            "event": "spawn",
            "seat": args.name,
            "name": args.name,
            "fleet": fleet,
            "runtime": runtime,
            "profile": recorded_profile,
            "command": command,
            "aura_launch_id": launch_id,
            "seat_instance_id": seat_instance_id,
            "source_session_id": fork_session or resume_session,
            "runtime_session_mode": "native-fork" if fork_session else "native-resume" if resume_session else None,
            "isolation": "forked-native-thread" if fork_session and runtime == "codex" else "shared-native-thread" if resume_session and runtime == "codex" else None,
            "cwd": workdir,
            "workdir": workdir,
            "context_file": str(context_path) if context_path else None,
            "work_file": str(work_path) if work_path else None,
            "runtime_home": runtime_home,
            "native_state_ref": native_state_ref,
            "terminal_ref": launch.get("target"),
            "pane_ref": pane_ref,
            "status": "starting",
            **agent_package_meta,
            **package_env_meta,
            **flex_meta,
            **runtime_profile_meta,
            **omx_box_meta,
            **codex_box_meta,
            **role_meta,
            **process_meta,
            **session_meta,
        })
        session_ledger.append_seat_event(
            event="seat_spawned",
            after=registered,
            evidence={
                "terminal_ref": launch.get("target"),
                "pane_ref": pane_ref,
                "resume_session": resume_session,
                "fork_session": fork_session,
                "prompt_requested": bool(prompt_text),
            },
            source_command="aura spawn",
        )
    except Exception:
        pass

    result = {
        "ok": True,
        "name": args.name,
        "spawned": True,
        "runtime": runtime,
        "profile": recorded_profile,
        "command": command,
        "workdir": workdir,
        "cwd": workdir,
        "context_file": str(context_path) if context_path else None,
        "work_file": str(work_path) if work_path else None,
        "runtime_home": runtime_home,
        "native_state_ref": native_state_ref,
        "aura_launch_id": launch_id,
        "seat_instance_id": seat_instance_id,
        "source_session_id": fork_session or resume_session,
        "runtime_session_mode": "native-fork" if fork_session else "native-resume" if resume_session else None,
        "isolation": "forked-native-thread" if fork_session and runtime == "codex" else "shared-native-thread" if resume_session and runtime == "codex" else None,
        "terminal_ref": launch.get("target"),
        "backend_ref": launch.get("target"),
        "pane_ref": pane_ref,
        "status": "starting",
        "registered": True,
        **agent_package_meta,
        **package_env_meta,
        **({"spawn_preflight": spawn_preflight} if spawn_preflight.get("warnings") else {}),
        "fleet": fleet,
        "trace_cell": registered.get("trace_cell"),
        "runtime_capsule_ref": registered.get("runtime_capsule_ref"),
        "runtime_capsule_launch": registered.get("runtime_capsule_launch"),
        **flex_meta,
        **runtime_profile_meta,
        **omx_box_meta,
        **codex_box_meta,
        **role_meta,
        **process_meta,
        **session_meta,
    }

    prompt_target = pane_ref or launch.get("target") or args.name
    observation_session = session_meta
    if _should_send_codex_startup_handshake(runtime=runtime, resume_session=resume_session, fork_session=fork_session):
        time.sleep(float(os.environ.get("AURA_CODEX_STARTUP_HANDSHAKE_DELAY", "1.0")))
        handshake_result = _send_codex_startup_handshake(
            terminal=terminal,
            target=args.name,
            prompt_target=prompt_target,
            seat=args.name,
            fleet=fleet,
            launch_id=launch_id,
        )
        result["startup_handshake"] = handshake_result
        if handshake_result.get("sent"):
            readiness = _wait_for_hook_bound_session(
                fleet=fleet,
                seat=args.name,
                timeout=float(os.environ.get("AURA_CODEX_STARTUP_READY_TIMEOUT", "10.0")),
            )
        else:
            readiness = {
                "ready": False,
                "reason": handshake_result.get("reason") or handshake_result.get("error") or "startup-handshake-not-sent",
                "runtime_session_binding": "unbound",
            }
        result["startup_readiness"] = readiness
        result["ready"] = bool(readiness.get("ready"))
        result["ready_reason"] = readiness.get("reason")
        if readiness.get("runtime_session_id"):
            observation_session = registry.get_agent(args.name, fleet=fleet) or observation_session
            result.update({
                key: readiness.get(key)
                for key in (
                    "session_id",
                    "runtime_session_id",
                    "runtime_session_source",
                    "runtime_session_binding",
                    "runtime_session_bind_method",
                    "runtime_session_bind_source",
                    "runtime_session_confidence",
                    "runtime_session_evidence",
                    "runtime_session_cwd",
                )
                if readiness.get(key) is not None
            })

    if prompt_text and fork_session:
        result["prompt_delivery"] = {
            "submitted": True,
            "transport": "runtime-native-argv",
            "mode": "fork-argument",
        }
    elif prompt_text and native_initial_prompt_argv:
        prompt_delivery = {
            "submitted": True,
            "transport": "runtime-native-argv",
            "mode": "initial-argument",
        }
        if flex_packet and flex_manifest and flex_root:
            prompt_delivery["flex_project_packet_included"] = True
            prompt_delivery["flex_project_packet_manifest"] = str(flex_manifest)
        result["prompt_delivery"] = prompt_delivery
    elif prompt_text:
        prompt_result = terminal.send_text(
            args.name,
            augmented_prompt,
            submit=True,
        )
        prompt_delivery = {
            "submitted": bool(prompt_result.get("ok")),
            "transport": getattr(terminal, "BACKEND_NAME", "tmux"),
        }
        if prompt_result.get("ok") and flex_packet and flex_manifest and flex_root:
            try:
                prompt_delivery["flex_project_packet_included"] = True
                prompt_delivery["flex_project_packet_manifest"] = str(flex_manifest)
            except Exception:
                pass
        if not prompt_result.get("ok"):
            result["prompt_error"] = prompt_result.get("error")
        elif runtime in {"codex", "omx"} and hasattr(terminal, "send_keys"):
            prompt_delivery["submit_retry"] = _retry_codex_prompt_submit(
                terminal=terminal,
                target=prompt_target,
                seat=args.name,
                launch_id=launch_id,
                prompt_text=augmented_prompt,
            )
        result["prompt_delivery"] = prompt_delivery

    cwd_choice = _resolve_codex_cwd_choice(
        runtime=runtime,
        resume_session=resume_session,
        terminal=terminal,
        target=pane_ref or launch.get("target") or args.name,
        desired_cwd=workdir,
    )
    if cwd_choice:
        result["cwd_choice"] = cwd_choice
        if cwd_choice.get("detected") and cwd_choice.get("selected_path"):
            registry.upsert_agent({
                **registry.get_agent(args.name, fleet=fleet),
                "name": args.name,
                "fleet": fleet,
                "cwd_choice": cwd_choice,
            })

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
        existing_session=observation_session,
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
                    "runtime_session_binding",
                    "runtime_session_bind_method",
                    "runtime_session_bind_source",
                    "runtime_session_bound_at",
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
            try:
                from lib import session_ledger

                observed_after = {
                    **registered,
                    **session_fields,
                    "name": args.name,
                    "fleet": fleet,
                    "runtime": runtime,
                    "cwd": workdir,
                }
                session_ledger.append_seat_event(
                    event="session_observed",
                    before=registered,
                    after=observed_after,
                    evidence=session_observation.get("runtime_session_evidence") or session_observation,
                    source_command="aura spawn",
                )
            except Exception:
                pass
            if not agent_package:
                try:
                    from lib import runtime_capsules

                    capsule_session = runtime_capsules.write_runtime_session(observed_after)
                    if capsule_session.get("ok"):
                        result["runtime_capsule_session"] = capsule_session.get("path")
                        registry.upsert_agent({
                            **observed_after,
                            "runtime_capsule_ref": capsule_session.get("capsule_root"),
                            "runtime_capsule_session": capsule_session.get("path"),
                        })
                except Exception as exc:
                    result["runtime_capsule_session_warning"] = str(exc)
        readiness = _runtime_session_readiness(runtime=runtime, observation=session_observation)
        if readiness:
            result["runtime_session_ready"] = readiness["runtime_session_ready"]
            result["runtime_session_ready_reason"] = readiness["runtime_session_ready_reason"]
            if "ready" not in result or (readiness["ready"] and not result.get("ready")):
                result["ready"] = readiness["ready"]
                result["ready_reason"] = readiness["ready_reason"]
            try:
                current = registry.get_agent(args.name, fleet=fleet) or registered
                registry.upsert_agent({
                    **current,
                    "name": args.name,
                    "fleet": fleet,
                    "runtime_session_ready": readiness["runtime_session_ready"],
                    "runtime_session_ready_reason": readiness["runtime_session_ready_reason"],
                })
            except Exception:
                pass
    _record_workspace_spawn(workdir_path, result, runtime=runtime)
    return result_fn({k: v for k, v in result.items() if v is not None})


def _runtime_session_readiness(*, runtime: str, observation: dict | None) -> dict | None:
    if runtime not in {"codex", "omx"} or not observation:
        return None
    status = observation.get("status")
    session_id = observation.get("runtime_session_id") or observation.get("session_id")
    if session_id or status in {"observed", "already-bound"}:
        return {
            "ready": True,
            "ready_reason": "runtime-session-bound",
            "runtime_session_ready": True,
            "runtime_session_ready_reason": "runtime-session-bound",
        }
    reason = observation.get("reason") or status or "runtime-session-binding-pending"
    return {
        "ready": False,
        "ready_reason": reason,
        "runtime_session_ready": False,
        "runtime_session_ready_reason": reason,
    }


def _should_send_codex_startup_handshake(*, runtime: str, resume_session: str | None, fork_session: str | None = None) -> bool:
    if runtime not in {"codex", "omx"} or resume_session or fork_session:
        return False
    value = os.environ.get("AURA_CODEX_STARTUP_HANDSHAKE", "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _spawn_preflight(
    *,
    runtime: str,
    command: str,
    custom_launch_command: str | None,
    launch_env: dict,
    resume_session: str | None,
    fork_session: str | None,
    agent_package_root: str | None = None,
) -> dict:
    del command
    warnings: list[str] = []
    errors: list[dict] = []
    inline_env: dict[str, str] = {}
    parse_warning = None

    if runtime in {"codex", "omx"} and custom_launch_command:
        try:
            parts = shlex.split(custom_launch_command)
        except ValueError as exc:
            parts = []
            parse_warning = f"custom-command-parse-warning: {exc}"
            warnings.append("custom-command-parse-warning")
        executable_index = 0
        for index, part in enumerate(parts):
            if "=" not in part or part.startswith("="):
                executable_index = index
                break
            key, value = part.split("=", 1)
            if not key or any(char in key for char in "/ \t"):
                executable_index = index
                break
            inline_env[key] = value
        else:
            executable_index = len(parts)
        argv = parts[executable_index:]
        if _custom_command_is_manual_resume(runtime, argv) and not resume_session and not fork_session:
            errors.append({
                "code": "manual-resume-command-without-resume-session",
                "detail": "Use --resume-session so Aura can bind the runtime session exactly.",
            })
        for key in ("CODEX_HOME", "OMX_ROOT", "OMX_TEAM_STATE_ROOT"):
            if key not in inline_env or key not in launch_env:
                continue
            if str(inline_env[key]) != str(launch_env[key]):
                errors.append({
                    "code": "runtime-home-conflict",
                    "env": key,
                    "command_value": inline_env[key],
                    "launch_env_value": str(launch_env[key]),
                })
        warning = f"custom-{runtime}-command-may-remain-unbound"
        if warning not in warnings:
            warnings.append(warning)

    package_runtime_hygiene = []
    if agent_package_root:
        try:
            from lib import runtime_hygiene

            package_runtime_hygiene = runtime_hygiene.package_runtime_findings(
                agent_package_root,
                runtime=runtime,
            )
            for finding in runtime_hygiene.severe_findings(package_runtime_hygiene):
                errors.append({
                    "code": "package-runtime-home-contamination",
                    "finding": finding,
                })
        except Exception as exc:
            errors.append({
                "code": "package-runtime-hygiene-check-failed",
                "detail": str(exc),
            })

    result = {
        "ok": not errors,
        "warnings": warnings,
        "errors": errors,
    }
    if inline_env:
        result["inline_env"] = inline_env
    if parse_warning:
        result["parse_warning"] = parse_warning
    if package_runtime_hygiene:
        result["package_runtime_hygiene"] = package_runtime_hygiene
    return result


def _hermes_startup_prompt_allowed() -> bool:
    return os.environ.get("AURA_HERMES_ALLOW_STARTUP_PROMPT", "").strip().lower() in {"1", "true", "yes", "on"}


def _custom_command_is_manual_resume(runtime: str, argv: list[str]) -> bool:
    if len(argv) < 3:
        return False
    executable = Path(argv[0]).name
    if runtime == "codex" and executable == "codex":
        return "resume" in argv[1:]
    if runtime == "omx" and executable == "omx":
        return "resume" in argv[1:]
    return False


def _startup_handshake_text(*, fleet: str, seat: str) -> str:
    return (
        "[AURA STARTUP]\n"
        f"Target: {fleet}:{seat}\n"
        "This is a startup handshake. Let Codex hooks bind your Aura runtime session and inject ambient context.\n"
        "Do not begin task work from this message. Reply only with your Aura target from ambient context.\n"
        "[/AURA STARTUP]"
    )


def _send_codex_startup_handshake(
    *,
    terminal,
    target: str,
    prompt_target: str | None,
    seat: str,
    fleet: str,
    launch_id: str,
) -> dict:
    if not hasattr(terminal, "send_text"):
        return {
            "sent": False,
            "submitted": False,
            "target": target,
            "reason": "terminal-send-text-unavailable",
        }
    text = _startup_handshake_text(fleet=fleet, seat=seat)
    result = terminal.send_text(target, text, submit=True) or {}
    packet = {
        "sent": bool(result.get("ok")),
        "submitted": bool(result.get("ok")),
        "transport": getattr(terminal, "BACKEND_NAME", "tmux"),
        "target": target,
    }
    if not result.get("ok"):
        packet["error"] = result.get("error") or "startup-handshake-send-failed"
        return packet
    if prompt_target and hasattr(terminal, "send_keys"):
        packet["submit_retry"] = _retry_codex_prompt_submit(
            terminal=terminal,
            target=prompt_target,
            seat=seat,
            launch_id=launch_id,
        )
    return packet


def _wait_for_hook_bound_session(*, fleet: str, seat: str, timeout: float) -> dict:
    from lib import registry, runtime_session

    deadline = time.time() + max(timeout, 0)
    attempts = 0
    last = {}
    while True:
        attempts += 1
        row = registry.get_agent(seat, fleet=fleet) or {}
        last = row
        if runtime_session.is_bound_session(row):
            session_id = row.get("runtime_session_id") or row.get("session_id")
            return {
                "ready": True,
                "reason": "hook-bound",
                "attempts": attempts,
                "session_id": session_id,
                "runtime_session_id": session_id,
                "runtime_session_source": row.get("runtime_session_source"),
                "runtime_session_binding": row.get("runtime_session_binding"),
                "runtime_session_bind_method": row.get("runtime_session_bind_method"),
                "runtime_session_bind_source": row.get("runtime_session_bind_source"),
                "runtime_session_confidence": row.get("runtime_session_confidence"),
                "runtime_session_evidence": row.get("runtime_session_evidence"),
                "runtime_session_cwd": row.get("runtime_session_cwd"),
            }
        if time.time() >= deadline:
            break
        time.sleep(0.25)
    return {
        "ready": False,
        "reason": "started_unbound",
        "attempts": attempts,
        "runtime_session_binding": (last or {}).get("runtime_session_binding") or "unbound",
    }


def _runtime_home(runtime: str, profile: str | None) -> str | None:
    if runtime == "hermes":
        if not profile or profile == "default":
            return str(Path.home() / ".hermes")
        return str(Path.home() / ".hermes" / "profiles" / profile)
    return None


def _normalize_runtime_profile_ref(ref: str, *, expected_runtime: str | None = None) -> tuple[str, str, str]:
    """Normalize an Aura runtime-profile ref like ``codex/dev``.

    This is deliberately separate from filesystem path construction so refs do
    not accidentally become nested path fragments such as codex/codex/dev.
    """

    from lib import runtime_profiles

    normalized = runtime_profiles.normalize_runtime_profile_ref(
        ref,
        expected_runtime=expected_runtime,
    )
    return normalized.runtime, normalized.profile, normalized.canonical


def _resolve_launch_flex_project(workdir_path: Path) -> tuple[Path | None, Path | None]:
    try:
        start = workdir_path.expanduser().resolve()
    except OSError:
        start = workdir_path.expanduser()
    for candidate in [start, *start.parents]:
        manifest = candidate / ".flex" / "project.yaml"
        if manifest.is_file():
            return manifest.resolve(), candidate.resolve()
    return None, None


def _render_flex_project_launch_packet(manifest: Path | None, root: Path | None) -> str | None:
    return None


def _augment_runtime_prompt(
    runtime: str,
    prompt_text: str,
    *,
    fleet: str,
    seat: str,
    launch_id: str,
    flex_packet: str | None = None,
) -> str:
    del fleet, seat, launch_id
    if runtime not in {"codex", "omx"}:
        return prompt_text
    lines = []
    if flex_packet:
        lines.extend([flex_packet, ""])
    lines.append(prompt_text)
    return "\n".join(lines)


def _codex_cwd_choice_from_capture(capture: list[str], desired_cwd: str | None) -> dict | None:
    lines = [str(line) for line in capture or []]
    if not any("Choose working directory to resume this session" in line for line in lines):
        return None
    options = []
    for line in lines:
        stripped = line.strip()
        if ". Use " not in stripped or "(" not in stripped or ")" not in stripped:
            continue
        number, rest = stripped.split(".", 1)
        if not number.strip().isdigit():
            continue
        path = rest.rsplit("(", 1)[-1].rsplit(")", 1)[0]
        label = rest.split("(", 1)[0].strip()
        options.append({
            "number": number.strip(),
            "label": label,
            "path": path,
        })
    selected = None
    current_option = next((
        option for option in options
        if "current directory" in option.get("label", "").lower()
    ), None)
    if desired_cwd:
        try:
            desired = str(Path(desired_cwd).expanduser().resolve())
        except OSError:
            desired = str(desired_cwd)
        if current_option and current_option.get("path") == desired:
            selected = current_option
        elif current_option:
            selected = current_option
        else:
            selected = next((option for option in options if option.get("path") == desired), None)
    if not selected and current_option:
        selected = current_option
    if not selected:
        selected = next((option for option in options if option.get("number") == "2"), None)
    if not selected and options:
        selected = options[0]
    return {
        "detected": True,
        "options": options,
        "selected": selected,
        "selection_policy": "codex-current-directory",
    }


def _resolve_codex_cwd_choice(*, runtime: str, resume_session: str | None, terminal, target: str | None, desired_cwd: str | None) -> dict | None:
    if runtime not in {"codex", "omx"} or not resume_session or not target or not hasattr(terminal, "capture_output"):
        return None
    attempts = int(os.environ.get("AURA_CODEX_CWD_CHOICE_ATTEMPTS", "8"))
    for index in range(max(1, attempts)):
        time.sleep(0.25 if index else 0.75)
        capture = terminal.capture_output(target, 80)
        choice = _codex_cwd_choice_from_capture(capture, desired_cwd)
        if not choice:
            continue
        selected = choice.get("selected")
        if not selected:
            return {**choice, "ok": False, "reason": "no-selectable-option"}
        if not hasattr(terminal, "send_keys"):
            return {**choice, "ok": False, "reason": "terminal-send-keys-unavailable"}
        send_attempts = []
        max_send_attempts = int(os.environ.get("AURA_CODEX_CWD_CHOICE_SEND_ATTEMPTS", "4"))
        verify_attempts = int(os.environ.get("AURA_CODEX_CWD_CHOICE_VERIFY_ATTEMPTS", "4"))
        verified = False
        result = {}
        for send_index in range(max(1, max_send_attempts)):
            result = terminal.send_keys(target, selected["number"], enter=True) or {}
            verify_checks = []
            for verify_index in range(max(1, verify_attempts)):
                time.sleep(0.75 if verify_index == 0 else 0.75)
                verify_capture = terminal.capture_output(target, 80)
                prompt_present = _codex_cwd_choice_from_capture(verify_capture, desired_cwd) is not None
                verified = not prompt_present
                verify_checks.append({
                    "verified": verified,
                    "prompt_present": prompt_present,
                })
                if verified:
                    break
            send_attempts.append({
                "ok": bool(result.get("ok")),
                "target": result.get("target"),
                "verified": verified,
                "verify_checks": verify_checks,
            })
            if verified:
                break
        return {
            **choice,
            "ok": bool(result.get("ok")) and verified,
            "selected_number": selected["number"],
            "selected_path": selected.get("path"),
            "selected_label": selected.get("label"),
            "send_result": result,
            "send_attempts": send_attempts,
            "verified": verified,
        }
    return {"detected": False, "ok": True}


def _retry_codex_prompt_submit(*, terminal, target: str, seat: str, launch_id: str, prompt_text: str | None = None) -> dict:
    """Nudge a freshly pasted Codex spawn prompt until the thread exists.

    Codex can briefly accept a tmux paste before its input widget is ready,
    especially on first-run trust or MCP startup screens. Repeating a literal
    Enter until state-db evidence appears makes spawn prompt delivery
    deterministic without binding the seat manually.
    """
    from lib import runtime_session, terminal_submit

    attempts = []
    max_attempts = int(os.environ.get("AURA_CODEX_PROMPT_SUBMIT_RETRIES", "4"))
    repasted = False
    for index in range(max(1, max_attempts)):
        time.sleep(0.5 if index == 0 else 1.5)
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
        possible_matches = session_info.get("runtime_session_possible_matches") if session_info else None
        diagnostics = session_info.get("runtime_session_diagnostics") or {}
        if runtime_session.is_bound_session(session_info) or (
            possible_matches and diagnostics.get("confidence") == "exact"
        ):
            return {
                "ok": True,
                "attempts": len(attempts),
                "results": attempts,
                "session_seen": True,
                "runtime_session_binding": session_info.get("runtime_session_binding"),
                "runtime_session_source": session_info.get("runtime_session_source"),
                "runtime_session_diagnostics": session_info.get("runtime_session_diagnostics"),
                "runtime_session_possible_matches": possible_matches,
            }
        capture = []
        if hasattr(terminal, "capture_output"):
            try:
                capture = terminal.capture_output(target, 160) or []
            except Exception:
                capture = []
        prompt_prefix = str(prompt_text or "").splitlines()[0][:80]
        prompt_visible = bool(prompt_prefix) and any(
            line.strip().startswith(("› ", "❯ ")) and prompt_prefix in line
            for line in (str(raw) for raw in capture)
        )
        codex_tui_visible = any("OpenAI Codex" in str(line) for line in capture)
        idle_prompt_visible = any(str(line).strip().startswith(("› ", "❯ ")) for line in capture)
        default_prompt_visible = any(
            marker in str(line)
            for line in capture
            for marker in ("› Implement {feature}", "❯ Implement {feature}", "› Explain this codebase")
        )
        if capture and not terminal_submit.needs_submit_retry(capture):
            if (
                index
                and prompt_text
                and not prompt_visible
                and not repasted
                and hasattr(terminal, "send_text")
                and (default_prompt_visible or (codex_tui_visible and idle_prompt_visible))
            ):
                clear_result = terminal.send_keys(target, "C-u", enter=False) or {}
                retry_result = terminal.send_text(target, prompt_text, submit=True) or {}
                retry_result = {"clear": clear_result, "reason": "startup-prompt-not-in-composer", **retry_result}
                repasted = True
            else:
                retry_result = {
                    "ok": True,
                    "target": target,
                    "submitted": False,
                    "reason": "no-queued-input",
                }
        else:
            retry_result = terminal.send_keys(target, "Enter", enter=False) or {}
        attempts.append(retry_result)
        time.sleep(0.5)
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

    This makes Aura-spawned Codex-backed seats self-describing without requiring
    the agent to run bind-current as a ritual. It only binds evidence at
    high/exact confidence; bind-current remains the repair path for ambiguous
    sessions.
    """
    if runtime not in {"codex", "omx"}:
        return {"status": "skipped", "reason": "runtime-not-observed-at-spawn", "runtime": runtime}

    from lib import runtime_session

    if runtime_session.is_bound_session(existing_session):
        session_id = existing_session.get("runtime_session_id")
        return {
            "status": "already-bound",
            "session_id": session_id,
            "runtime_session_id": session_id,
            "runtime_session_source": existing_session.get("runtime_session_source"),
            "runtime_session_binding": existing_session.get("runtime_session_binding"),
            "runtime_session_bind_method": existing_session.get("runtime_session_bind_method"),
            "runtime_session_bind_source": existing_session.get("runtime_session_bind_source"),
            "runtime_session_confidence": existing_session.get("runtime_session_confidence"),
            "runtime_session_evidence": existing_session.get("runtime_session_evidence"),
        }

    if not target or not hasattr(terminal, "pane_pid"):
        return {"status": "pending", "reason": "no-pane-target", "runtime": runtime}

    from lib import registry, session_ledger

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
            if runtime_session.is_bound_session(session_info):
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

    # Fresh Codex starts have no trustworthy argv resume evidence, but Aura
    # injects the launch id into the first prompt. Once Codex writes that prompt
    # to its JSONL, the launch id is an explicit nonce and can bind exactly.
    if launch_id:
        try:
            from commands import sessions as sessions_cmd

            found = sessions_cmd._codex_session_from_nonce(launch_id, expected_cwd=workdir, record=registered)
            if found.get("ok") and found.get("session_id"):
                evidence = {
                    "reason": "codex-jsonl-nonce",
                    "nonce": launch_id,
                    "jsonl": found.get("jsonl"),
                    "matches": found.get("matches"),
                    "bound_after_spawn": True,
                }
                bound = sessions_cmd._bind_registry_session(
                    fleet=fleet,
                    seat=seat,
                    previous=registered,
                    session_id=found["session_id"],
                    source="codex-jsonl:nonce",
                    confidence="exact",
                    evidence=evidence,
                    cwd=found.get("cwd") or workdir,
                    event="session_bound_nonce",
                    extra={
                        "jsonl": found.get("jsonl"),
                        "cwd": found.get("cwd") or workdir,
                    },
                )
                return {
                    "status": "observed",
                    "attempts": attempts,
                    "session_id": found["session_id"],
                    "runtime_session_id": found["session_id"],
                    "runtime_session_source": "codex-jsonl:nonce",
                    "runtime_session_binding": "bound",
                    "runtime_session_bind_method": runtime_session.binding_method_for_source("codex-jsonl:nonce"),
                    "runtime_session_bind_source": "codex-jsonl:nonce",
                    "runtime_session_confidence": "exact",
                    "runtime_session_evidence": evidence,
                    "runtime_session_cwd": found.get("cwd") or workdir,
                }
        except Exception as exc:
            last_session = {
                **(last_session or {}),
                "runtime_session_diagnostics": {
                    "nonce_bind_error": str(exc),
                },
            }

    pending = {
        "status": "pending",
        "reason": "no-high-confidence-session-evidence",
        "attempts": attempts,
        "runtime": runtime,
    }
    if last_session:
        pending.update({
            "last_runtime_session_source": last_session.get("runtime_session_source"),
            "last_runtime_session_binding": last_session.get("runtime_session_binding"),
            "last_runtime_session_diagnostics": last_session.get("runtime_session_diagnostics"),
            "last_runtime_session_possible_matches": last_session.get("runtime_session_possible_matches"),
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
            "runtime_profile": result.get("runtime_profile"),
            "runtime_profile_ref": result.get("runtime_profile_ref"),
            "runtime_profile_runtime": result.get("runtime_profile_runtime"),
            "runtime_profile_source": result.get("runtime_profile_source"),
            "aura_launch_id": result.get("aura_launch_id"),
            "source_session_id": result.get("source_session_id"),
            "runtime_session_mode": result.get("runtime_session_mode"),
            "isolation": result.get("isolation"),
            "runtime_session_id": result.get("runtime_session_id"),
            "runtime_session_env": result.get("runtime_session_env"),
            "runtime_session_source": result.get("runtime_session_source"),
            "runtime_session_binding": result.get("runtime_session_binding"),
            "runtime_session_bind_method": result.get("runtime_session_bind_method"),
            "runtime_session_bind_source": result.get("runtime_session_bind_source"),
            "runtime_session_confidence": result.get("runtime_session_confidence"),
            "runtime_session_evidence": result.get("runtime_session_evidence"),
            "runtime_process_pid": result.get("runtime_process_pid"),
            "runtime_process_cwd": result.get("runtime_process_cwd"),
            "runtime_process_started_at_epoch": result.get("runtime_process_started_at_epoch"),
            "runtime_process_argv": result.get("runtime_process_argv"),
            "command": result.get("command"),
            "terminal_ref": result.get("terminal_ref"),
            "pane_ref": result.get("pane_ref"),
            "flex_project_manifest": result.get("flex_project_manifest"),
            "flex_project_root": result.get("flex_project_root"),
            "omx_isolation": result.get("omx_isolation"),
            "omx_package_root": result.get("omx_package_root"),
            "omx_package_codex_home": result.get("omx_package_codex_home"),
            "omx_package_omx_root": result.get("omx_package_omx_root"),
            "omx_package_omx_state": result.get("omx_package_omx_state"),
            "omx_package_team_state_root": result.get("omx_package_team_state_root"),
            "omx_runtime_base_source": result.get("omx_runtime_base_source"),
            "omx_runtime_base_root": result.get("omx_runtime_base_root"),
            "omx_runtime_base_applied": result.get("omx_runtime_base_applied"),
            "omx_runtime_base_templates_applied": result.get("omx_runtime_base_templates_applied"),
            "omx_setup_ran": result.get("omx_setup_ran"),
            "omx_setup_skipped": result.get("omx_setup_skipped"),
            "omx_auth_seeded": result.get("omx_auth_seeded"),
            "omx_config_seeded": result.get("omx_config_seeded"),
            "omx_source_cwd_trusted": result.get("omx_source_cwd_trusted"),
            "omx_box_root": result.get("omx_box_root"),
            "omx_box_home": result.get("omx_box_home"),
            "omx_box_codex_home": result.get("omx_box_codex_home"),
            "omx_box_omx_root": result.get("omx_box_omx_root"),
            "omx_box_omx_state": result.get("omx_box_omx_state"),
            "omx_box_team_state_root": result.get("omx_box_team_state_root"),
            "omx_box_runtime": result.get("omx_box_runtime"),
            "omx_box_setup_ran": result.get("omx_box_setup_ran"),
            "omx_box_setup_skipped": result.get("omx_box_setup_skipped"),
            "omx_box_auth_seeded": result.get("omx_box_auth_seeded"),
            "omx_box_config_seeded": result.get("omx_box_config_seeded"),
            "omx_profile": result.get("omx_profile"),
            "omx_profile_root": result.get("omx_profile_root"),
            "omx_profile_applied": result.get("omx_profile_applied"),
            "omx_profile_templates_applied": result.get("omx_profile_templates_applied"),
            "codex_isolation": result.get("codex_isolation"),
            "codex_package_root": result.get("codex_package_root"),
            "codex_package_codex_home": result.get("codex_package_codex_home"),
            "codex_runtime_base_source": result.get("codex_runtime_base_source"),
            "codex_runtime_base_root": result.get("codex_runtime_base_root"),
            "codex_runtime_base_applied": result.get("codex_runtime_base_applied"),
            "codex_runtime_base_templates_applied": result.get("codex_runtime_base_templates_applied"),
            "codex_auth_seeded": result.get("codex_auth_seeded"),
            "codex_config_seeded": result.get("codex_config_seeded"),
            "codex_source_cwd_trusted": result.get("codex_source_cwd_trusted"),
            "codex_box_root": result.get("codex_box_root"),
            "codex_box_home": result.get("codex_box_home"),
            "codex_box_codex_home": result.get("codex_box_codex_home"),
            "codex_box_runtime": result.get("codex_box_runtime"),
            "codex_box_auth_seeded": result.get("codex_box_auth_seeded"),
            "codex_box_config_seeded": result.get("codex_box_config_seeded"),
            "codex_profile": result.get("codex_profile"),
            "codex_profile_root": result.get("codex_profile_root"),
            "codex_profile_applied": result.get("codex_profile_applied"),
            "codex_profile_templates_applied": result.get("codex_profile_templates_applied"),
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
