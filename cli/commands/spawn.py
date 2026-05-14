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
    from lib import registry, runtimes, workspace_state

    if getattr(args, 'prompt', None) and getattr(args, 'work', None):
        return result_fn({"ok": False, "error": "use either --prompt or --work, not both", "name": args.name})

    requested_runtime = getattr(args, 'runtime', None)
    if not requested_runtime and getattr(args, 'launch_command', None):
        requested_runtime = "command"
    runtime, spec = runtimes.resolve_runtime(requested_runtime)
    resume_session = getattr(args, 'resume_session', None)
    launch_command = getattr(args, 'launch_command', None)
    workdir_path = workspace_state.resolve_workdir(getattr(args, 'cwd', None))
    workdir = str(workdir_path)
    if resume_session:
        if launch_command:
            return result_fn({"ok": False, "error": "use either --resume-session or --command, not both", "name": args.name})
        try:
            launch_command = runtimes.build_resume_command(runtime, resume_session, cwd=workdir)
        except ValueError as exc:
            return result_fn({"ok": False, "error": str(exc), "name": args.name})
    role_meta = dict(getattr(args, "_role_manifest_meta", None) or {})
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
        if identity_provider_arg == "desks":
            role_meta["desks_identity_id"] = identity_id_arg
    try:
        desks_runtime_profiles = _validated_desks_runtime_profiles(role_meta.get("desks_runtime_profiles"))
    except ValueError as exc:
        return result_fn({
            "ok": False,
            "error": "invalid-desks-runtime-profile",
            "detail": str(exc),
            "name": args.name,
            "runtime": runtime,
        })
    if desks_runtime_profiles:
        role_meta["desks_runtime_profiles"] = desks_runtime_profiles
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
    profile_source = getattr(args, "_profile_source", None) or ("cli" if raw_profile else None)
    explicit_cli_profile = bool(raw_profile and profile_source == "cli")
    desks_runtime_profile_ref = None
    if (
        not runtime_profile
        and not explicit_cli_profile
        and not explicit_omx_profile
        and runtime in desks_runtime_profiles
    ):
        desks_runtime_profile_ref = desks_runtime_profiles[runtime]
        _, runtime_profile, runtime_profile_ref = _normalize_runtime_profile_ref(
            desks_runtime_profile_ref,
            expected_runtime=runtime,
        )
        runtime_profile_source = "desks"
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
    profile = raw_profile or args.name
    omx_profile = None
    codex_profile = None
    if runtime == "omx":
        if explicit_omx_profile:
            omx_profile = explicit_omx_profile
            runtime_profile_source = "cli-omx-profile"
        elif runtime_profile:
            omx_profile = runtime_profile
        elif raw_profile and profile_source != "manifest-default":
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
            **({"desks_runtime_profile_ref": desks_runtime_profile_ref} if desks_runtime_profile_ref else {}),
        }
    recorded_profile = profile if runtime == "hermes" else omx_profile if runtime == "omx" else codex_profile if runtime == "codex" else None
    command = runtimes.build_command(
        runtime,
        spec,
        name=args.name,
        profile=profile,
        model=getattr(args, 'model', None),
        command_override=launch_command,
    )
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
    seat_instance_id = registry.new_seat_instance_id()

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
    flex_manifest, flex_root = _resolve_launch_flex_project(workdir_path, role_meta)
    flex_meta = {}
    if flex_manifest and flex_root:
        flex_meta = {
            "flex_project_manifest": str(flex_manifest),
            "flex_project_root": str(flex_root),
        }

    if role_meta:
        launch_env.update(_desks_launch_env(role_meta))
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
    if runtime == "omx":
        try:
            from lib import omx as omx_lib

            omx_box = omx_lib.prepare_box(
                fleet=fleet,
                seat=args.name,
                source_cwd=workdir,
                profile=omx_profile,
            )
            launch_env.update(omx_box.launch_env(workdir))
            omx_box_meta = omx_box.metadata()
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
            )
            launch_env.update(codex_box.launch_env(workdir))
            codex_box_meta = codex_box.metadata()
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
    has_identity_binding = bool(role_meta.get("identity_id") or role_meta.get("desks_identity_id"))
    identity_clear_keys = []
    if not has_identity_binding:
        identity_clear_keys = [
            "identity_provider",
            "identity_id",
            "identity_label",
            "identity_bound_at",
            "identity_bind_source",
            "identity_bind_confidence",
            "desks_identity_id",
            "desks_current_name",
            "desks_identity_home",
            "desks_memory_home",
            "desks_profile_id",
            "desks_profile_home",
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
        "source_session_id": resume_session,
        "runtime_session_mode": "native-resume" if resume_session else None,
        "isolation": "shared-native-thread" if resume_session and runtime == "codex" else None,
        "terminal_ref": launch.get("target"),
        "backend_ref": launch.get("target"),
        "pane_ref": pane_ref,
        "physical_fleet": fleet,
        "transport": "tmux",
        "status": "starting",
        "registered": True,
        **flex_meta,
        **runtime_profile_meta,
        **omx_box_meta,
        **codex_box_meta,
        **role_meta,
        **process_meta,
        **session_meta,
    })
    if resume_session:
        try:
            from lib import desks_sessions

            identity_provider = registered.get("identity_provider") or ("desks" if registered.get("desks_identity_id") else None)
            identity_id = registered.get("identity_id") or registered.get("desks_identity_id") or role_meta.get("identity_id") or role_meta.get("desks_identity_id")
            desks_sessions.append_identity_session(
                identity_id if identity_provider == "desks" else None,
                resume_session,
            )
        except Exception:
            pass
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
            "source_session_id": resume_session,
            "runtime_session_mode": "native-resume" if resume_session else None,
            "isolation": "shared-native-thread" if resume_session and runtime == "codex" else None,
            "cwd": workdir,
            "workdir": workdir,
            "context_file": str(context_path) if context_path else None,
            "work_file": str(work_path) if work_path else None,
            "runtime_home": runtime_home,
            "native_state_ref": native_state_ref,
            "terminal_ref": launch.get("target"),
            "pane_ref": pane_ref,
            "status": "starting",
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
        "source_session_id": resume_session,
        "runtime_session_mode": "native-resume" if resume_session else None,
        "isolation": "shared-native-thread" if resume_session and runtime == "codex" else None,
        "terminal_ref": launch.get("target"),
        "backend_ref": launch.get("target"),
        "pane_ref": pane_ref,
        "status": "starting",
        "registered": True,
        "fleet": fleet,
        "trace_cell": registered.get("trace_cell"),
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
    if _should_send_codex_startup_handshake(runtime=runtime, resume_session=resume_session):
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

    if prompt_text:
        flex_packet = _render_flex_project_launch_packet(flex_manifest, flex_root)
        prompt_result = terminal.send_text(
            args.name,
            _augment_runtime_prompt(
                runtime,
                prompt_text,
                fleet=fleet,
                seat=args.name,
                launch_id=launch_id,
                flex_packet=flex_packet,
            ),
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
        elif runtime == "codex" and hasattr(terminal, "send_keys"):
            prompt_delivery["submit_retry"] = _retry_codex_prompt_submit(
                terminal=terminal,
                target=prompt_target,
                seat=args.name,
                launch_id=launch_id,
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
    _record_workspace_spawn(workdir_path, result, runtime=runtime)
    return result_fn({k: v for k, v in result.items() if v is not None})


def _should_send_codex_startup_handshake(*, runtime: str, resume_session: str | None) -> bool:
    if runtime != "codex" or resume_session:
        return False
    value = os.environ.get("AURA_CODEX_STARTUP_HANDSHAKE", "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


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
    if runtime == "hermes" and profile:
        return str(Path.home() / ".hermes" / "profiles" / profile)
    return None


def _normalize_runtime_profile_ref(ref: str, *, expected_runtime: str | None = None) -> tuple[str, str, str]:
    """Normalize an Aura runtime-profile ref like ``codex/dev``.

    This is deliberately separate from filesystem path construction so refs do
    not accidentally become nested path fragments such as codex/codex/dev.
    """

    raw = str(ref or "").strip()
    if not raw:
        raise ValueError("runtime profile ref is required")
    parts = [part.strip() for part in raw.split("/") if part.strip()]
    if len(parts) != 2:
        raise ValueError("runtime profile ref must use <runtime>/<profile>, e.g. codex/dev")
    runtime, profile = parts
    if "/" in profile or not profile:
        raise ValueError("runtime profile name must be a single path segment")
    if expected_runtime and runtime != expected_runtime:
        raise ValueError(f"runtime profile {raw!r} is for {runtime}, not selected runtime {expected_runtime}")
    return runtime, profile, f"{runtime}/{profile}"


def _validated_desks_runtime_profiles(value) -> dict[str, str]:
    """Return canonical runtime profile refs from Desks metadata."""

    if not value:
        return {}
    if not isinstance(value, dict):
        raise ValueError("desks runtime_profiles must be an object")
    normalized: dict[str, str] = {}
    for runtime, ref in value.items():
        runtime_key = str(runtime or "").strip()
        if not runtime_key:
            raise ValueError("desks runtime_profiles contains an empty runtime key")
        raw_ref = str(ref or "").strip()
        if not raw_ref:
            raise ValueError(f"desks runtime_profiles.{runtime_key} is empty")
        if "/" in raw_ref:
            _, _, canonical = _normalize_runtime_profile_ref(raw_ref, expected_runtime=runtime_key)
        else:
            _, _, canonical = _normalize_runtime_profile_ref(f"{runtime_key}/{raw_ref}", expected_runtime=runtime_key)
        normalized[runtime_key] = canonical
    return normalized


def _desks_profile_metadata(manifest: dict) -> dict:
    role_home = manifest["role_home"]
    identity_path = role_home / "identity.json"
    if identity_path.is_file() and role_home.parent.name == "identities":
        try:
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            identity = {}
        if isinstance(identity, dict):
            identity_id = identity.get("identity_id") or role_home.name
            meta = {
                "identity_provider": "desks",
                "identity_id": identity_id,
                "identity_label": identity.get("current_name"),
                "identity_bind_source": "desks-launch",
                "identity_bind_confidence": "explicit",
                "desks_identity_id": identity_id,
                "desks_identity_home": str(role_home),
                "desks_memory_home": str(role_home / "memory"),
                "desks_current_name": identity.get("current_name"),
            }
            if isinstance(identity.get("runtime_profiles"), dict):
                meta["desks_runtime_profiles"] = dict(identity["runtime_profiles"])
            return meta
        return {}

    profile_dir = role_home
    profile_path = profile_dir / "profile.json"
    if not profile_path.is_file():
        return {}
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(profile, dict):
        return {}

    profile_id = profile.get("profile_id")
    identity_id = profile.get("identity_id")
    meta = {
        "identity_provider": "desks" if identity_id else None,
        "identity_id": identity_id,
        "identity_bind_source": "desks-launch" if identity_id else None,
        "identity_bind_confidence": "explicit" if identity_id else None,
        "desks_profile_id": profile_id,
        "desks_profile_home": str(profile_dir),
        "desks_identity_id": identity_id,
    }
    if isinstance(profile.get("runtime_profiles"), dict):
        meta["desks_runtime_profiles"] = dict(profile["runtime_profiles"])
    if identity_id and profile_dir.parent.name == "profiles":
        desks_root = profile_dir.parent.parent
        identity_home = desks_root / "identities" / str(identity_id)
        meta.update({
            "desks_identity_home": str(identity_home),
            "desks_memory_home": str(identity_home / "memory"),
        })
        identity_path = identity_home / "identity.json"
        if identity_path.is_file():
            try:
                identity = json.loads(identity_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                identity = {}
            if isinstance(identity, dict):
                meta["desks_current_name"] = identity.get("current_name")
                meta["identity_label"] = identity.get("current_name")
                if isinstance(identity.get("runtime_profiles"), dict) and "desks_runtime_profiles" not in meta:
                    meta["desks_runtime_profiles"] = dict(identity["runtime_profiles"])
    return {key: value for key, value in meta.items() if value}


def _role_metadata_from_manifest(manifest: dict) -> dict:
    files = manifest.get("files") or {}
    bootstrap = files.get("bootstrap")
    meta = {
        "desks_role_home": str(manifest["role_home"]),
        "desks_role_id": manifest["role_id"],
        "desks_product": manifest["product"],
        "desks_unit": manifest["unit"],
        "desks_manifest": str(manifest["manifest_path"]),
        "desks_bootstrap": str(bootstrap) if bootstrap else None,
        "desks_compression": str(files.get("compression")) if files.get("compression") else None,
        "desks_memory": str(files.get("memory")) if files.get("memory") else None,
        "desks_default_seat": manifest.get("seat"),
        "desks_default_fleet": manifest.get("fleet"),
        "flex_project_manifest": str(manifest["flex_project_manifest"]) if manifest.get("flex_project_manifest") else None,
        "flex_project_root": str(manifest["flex_project_root"]) if manifest.get("flex_project_root") else None,
    }
    profile_meta = _desks_profile_metadata(manifest)
    runtime_profiles = {}
    if isinstance(profile_meta.get("desks_runtime_profiles"), dict):
        runtime_profiles.update(profile_meta["desks_runtime_profiles"])
    if isinstance(manifest.get("runtime_profiles"), dict):
        runtime_profiles.update(manifest["runtime_profiles"])
    meta.update(profile_meta)
    if runtime_profiles:
        meta["desks_runtime_profiles"] = runtime_profiles
    return {key: value for key, value in meta.items() if value}


def _desks_launch_env(role_meta: dict) -> dict:
    if not role_meta:
        return {}
    mappings = {
        "ROLE_HOME": "desks_role_home",
        "ROLE_ID": "desks_role_id",
        "PRODUCT": "desks_product",
        "UNIT": "desks_unit",
        "MANIFEST": "desks_manifest",
        "IDENTITY_ID": "desks_identity_id",
        "GENERIC_IDENTITY_PROVIDER": "identity_provider",
        "GENERIC_IDENTITY_ID": "identity_id",
        "PROFILE_ID": "desks_profile_id",
        "CURRENT_NAME": "desks_current_name",
        "IDENTITY_HOME": "desks_identity_home",
        "PROFILE_HOME": "desks_profile_home",
        "MEMORY_HOME": "desks_memory_home",
        "DEFAULT_SEAT": "desks_default_seat",
        "DEFAULT_FLEET": "desks_default_fleet",
    }
    env = {}
    for env_suffix, meta_key in mappings.items():
        value = role_meta.get(meta_key, "")
        env[f"DESKS_{env_suffix}"] = value
        env[f"AURA_DESKS_{env_suffix}"] = value
    if role_meta.get("desks_runtime_profiles"):
        value = json.dumps(role_meta["desks_runtime_profiles"], sort_keys=True)
        env["DESKS_RUNTIME_PROFILES"] = value
        env["AURA_DESKS_RUNTIME_PROFILES"] = value
    return env


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

    args.name = getattr(args, "name", None) or seat
    args.fleet = getattr(args, "fleet", None) or fleet
    args.cwd = str(workspace_root)
    args.runtime = getattr(args, "runtime", None) or manifest.get("runtime") or "codex"
    if not getattr(args, "resume_session", None):
        args.prompt = "\n".join([
            f"Read {bootstrap} and follow it.",
            f"Use {manifest['role_home']} as your Desks role home.",
        ])
    if not getattr(args, "context", None) and manifest["files"].get("agents"):
        args.context = str(manifest["files"]["agents"])
    if not getattr(args, "profile", None):
        manifest_profile = manifest.get("profile")
        args.profile = manifest_profile or seat
        args._profile_source = "manifest" if manifest_profile else "manifest-default"
    else:
        args._profile_source = getattr(args, "_profile_source", None) or "cli"
    args._role_manifest_meta = _role_metadata_from_manifest(manifest)
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
    files = dict(files)
    if files.get("compaction") and not files.get("compression"):
        files["compression"] = files["compaction"]
    raw["files"] = files

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

    flex_project_manifest, flex_project_root = _resolve_flex_project(raw, workspace_root)

    return {
        **raw,
        "manifest_path": manifest_path,
        "role_home": role_home,
        "workspace_root": workspace_root,
        "files": resolved_files,
        "flex_project_manifest": flex_project_manifest,
        "flex_project_root": flex_project_root,
    }


def _resolve_flex_project(raw: dict, workspace_root: Path) -> tuple[Path | None, Path | None]:
    manifest_value = raw.get("flex_project_manifest")
    root_value = raw.get("flex_project_root")

    def resolve_under_workspace(value: str) -> Path:
        path = Path(str(value)).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (workspace_root / path).resolve()

    if manifest_value:
        manifest = resolve_under_workspace(str(manifest_value))
        if not manifest.is_file():
            raise ValueError(f"manifest flex_project_manifest not found: {manifest}")
        return manifest, manifest.parent.parent

    if root_value:
        root = resolve_under_workspace(str(root_value))
        manifest = root / ".flex" / "project.yaml"
        if not manifest.is_file():
            raise ValueError(f"manifest flex_project_root missing .flex/project.yaml: {root}")
        return manifest, root

    candidates = [
        workspace_root / ".flex" / "project.yaml",
        workspace_root / "context" / ".flex" / "project.yaml",
    ]
    for manifest in candidates:
        if manifest.is_file():
            return manifest.resolve(), manifest.parent.parent.resolve()
    return None, None


def _resolve_launch_flex_project(workdir_path: Path, role_meta: dict | None = None) -> tuple[Path | None, Path | None]:
    role_meta = role_meta or {}
    manifest_value = role_meta.get("flex_project_manifest")
    root_value = role_meta.get("flex_project_root")
    if manifest_value:
        manifest = Path(str(manifest_value)).expanduser().resolve()
        root = Path(str(root_value)).expanduser().resolve() if root_value else manifest.parent.parent.resolve()
        if manifest.is_file():
            return manifest, root
    if root_value:
        root = Path(str(root_value)).expanduser().resolve()
        manifest = root / ".flex" / "project.yaml"
        if manifest.is_file():
            return manifest.resolve(), root

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
    if runtime != "codex":
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
    if runtime != "codex" or not resume_session or not target or not hasattr(terminal, "capture_output"):
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
        possible_matches = session_info.get("runtime_session_possible_matches") if session_info else None
        if possible_matches:
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

            found = sessions_cmd._codex_session_from_nonce(launch_id, expected_cwd=workdir)
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
                    "desks_session_recorded": bound.get("desks_session_recorded"),
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
            "desks_role_home": result.get("desks_role_home"),
            "desks_role_id": result.get("desks_role_id"),
            "desks_product": result.get("desks_product"),
            "desks_unit": result.get("desks_unit"),
            "desks_manifest": result.get("desks_manifest"),
            "desks_bootstrap": result.get("desks_bootstrap"),
            "desks_compression": result.get("desks_compression"),
            "desks_memory": result.get("desks_memory"),
            "desks_runtime_profiles": result.get("desks_runtime_profiles"),
            "desks_runtime_profile_ref": result.get("desks_runtime_profile_ref"),
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
