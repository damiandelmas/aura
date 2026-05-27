"""Quick Aura-managed runtime-profile launches."""

from __future__ import annotations

import argparse
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from commands import spawn
from lib import agent_packages, runtime_bases, runtime_boxes

SUPPORTED_RUNTIMES = {"codex", "omx", "hermes"}

PRESET_SKILLS = {
    "minimal": (),
    "worker": ("aura-view", "aura-report", "aura-queue", "aura-self-bind"),
    "operator": (
        "aura-view",
        "aura-report",
        "aura-queue",
        "aura-self-bind",
        "aura-operations",
        "aura-operator",
    ),
    "debug": ("aura-view", "aura-inspect", "aura-operator"),
}


def _now_minute() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M")


def _shortid() -> str:
    return uuid.uuid4().hex[:6]


def default_fleet() -> str:
    return f"quick-{_now_minute()}"


def generated_profile_name() -> str:
    return f"quick-{_now_minute()}-{_shortid()}"


def generated_seat(runtime: str) -> str:
    return f"{runtime}-{_shortid()}"


def _validate_runtime(runtime: str) -> str:
    runtime = str(runtime or "").strip()
    if runtime not in SUPPORTED_RUNTIMES:
        raise ValueError(f"unsupported quick runtime: {runtime}; expected one of {', '.join(sorted(SUPPORTED_RUNTIMES))}")
    return runtime


def _validate_profile_name(profile: str) -> str:
    return runtime_boxes.validate_logical_segment(profile, label="profile")


def _preset_warning(runtime: str, preset: str | None) -> str | None:
    if not preset:
        return None
    return (
        f"preset {preset!r} recorded only for {runtime}; Aura quick no longer copies "
        "user-global Codex skills/config into runtime profiles"
    )


def _profile_root(runtime: str, profile: str) -> Path:
    if runtime == "codex":
        return runtime_boxes.runtime_profile_root("codex", profile)
    if runtime == "omx":
        return runtime_boxes.runtime_profile_root("omx", profile, legacy_omx=True)
    if runtime == "hermes":
        if profile == "default":
            return (Path.home() / ".hermes").resolve()
        return (Path.home() / ".hermes" / "profiles" / profile).resolve()
    raise ValueError(f"unsupported quick runtime: {runtime}")


def _skill_destination(runtime: str, profile_root: Path) -> Path:
    if runtime in {"codex", "omx"}:
        return profile_root / "codex-home-template" / "skills"
    if runtime == "hermes":
        return profile_root / "skills"
    raise ValueError(f"unsupported quick runtime: {runtime}")


def _ensure_profile_skeleton(runtime: str, profile: str, *, existed: bool) -> Path:
    root = _profile_root(runtime, profile)
    if runtime in {"codex", "omx"}:
        if not existed:
            runtime_bases.create_profile_from_base(runtime, root)
        else:
            # Existing Aura-owned profile templates win; never overwrite them.
            for dirname in runtime_bases.template_names(runtime):
                (root / dirname).mkdir(parents=True, exist_ok=True)
        return root
    if runtime == "hermes":
        if not root.is_dir():
            raise FileNotFoundError(
                f"Hermes profile not found: {root}; create it with 'hermes profile create {profile}'"
            )
        return root
    raise ValueError(f"unsupported quick runtime: {runtime}")


def ensure_profile(runtime: str, profile: str, *, mode: str, preset: str | None = None) -> dict[str, object]:
    """Ensure or validate a runtime profile for quick launch."""

    runtime = _validate_runtime(runtime)
    profile = _validate_profile_name(profile)
    if preset and preset not in PRESET_SKILLS:
        raise ValueError(f"unknown preset: {preset}; expected one of {', '.join(sorted(PRESET_SKILLS))}")
    root = _profile_root(runtime, profile)
    existed = root.exists()
    if mode == "existing" and not root.is_dir():
        raise FileNotFoundError(f"{runtime} profile not found: {root}")
    if mode == "new" and existed:
        raise FileExistsError(f"{runtime} profile already exists: {root}")
    if mode not in {"default", "new", "existing"}:
        raise ValueError(f"unknown profile mode: {mode}")

    root = _ensure_profile_skeleton(runtime, profile, existed=existed)
    warnings = []
    warning = _preset_warning(runtime, preset)
    if warning:
        warnings.append(warning)
    return {
        "runtime": runtime,
        "profile": profile,
        "profile_root": str(root),
        "profile_created": not existed,
        "profile_mode": mode,
        "preset": preset,
        "preset_skills": [],
        "warnings": warnings,
    }


def _resolve_profile(args) -> tuple[str | None, dict[str, object] | None]:
    runtime = _validate_runtime(args.runtime)
    profile_modes = [bool(args.default), args.new is not None, bool(args.profile)]
    if sum(profile_modes) > 1:
        raise ValueError("use only one of --default, --new, or --profile")
    if args.preset and not any(profile_modes):
        raise ValueError("--preset requires --default, --new, or --profile")
    if args.default:
        profile = "default"
        return profile, ensure_profile(runtime, profile, mode="default", preset=args.preset)
    if args.new is not None:
        if runtime == "hermes":
            raise ValueError("Hermes profiles are native; create one with 'hermes profile create NAME'")
        profile = args.new or generated_profile_name()
        return profile, ensure_profile(runtime, profile, mode="new", preset=args.preset)
    if args.profile:
        profile = _validate_profile_name(args.profile)
        return profile, ensure_profile(runtime, profile, mode="existing", preset=args.preset)
    return None, None


def _profile_ref(runtime: str, profile: str | None) -> str | None:
    if not profile:
        return None
    if runtime in {"codex", "omx", "hermes"}:
        return f"{runtime}/{profile}"
    return None


def _quick_agent_alias(runtime: str) -> str:
    return f"quick-{runtime}"


def _quick_agent_address(runtime: str) -> str:
    return f"aura:quick:{runtime}"


def _ensure_quick_agent(
    runtime: str,
    *,
    profile_ref: str | None,
    cwd: str,
    fleet: str,
    seat: str,
) -> dict[str, object] | None:
    """Create or reuse the canonical package-native quick body for a runtime."""

    if runtime not in {"codex", "omx"}:
        return None
    alias = _quick_agent_alias(runtime)
    try:
        record = agent_packages.resolve(alias)
    except FileNotFoundError:
        created = agent_packages.create(
            address=_quick_agent_address(runtime),
            runtime=runtime,
            profile=profile_ref,
            cwd=cwd,
            fleet=fleet,
            seat=seat,
            alias=alias,
        )
        record = dict(created["agent"])
    if record.get("runtime") != runtime:
        raise ValueError(
            f"quick agent alias {alias!r} resolves to runtime {record.get('runtime')!r}, "
            f"expected {runtime!r}"
        )
    return {
        "agent_id": record["agent_id"],
        "address": record["address"],
        "alias": record.get("alias"),
        "root": record["root"],
    }

def attach_to_result(result: dict[str, object]) -> str | None:
    """Attach or switch the current terminal to a quick launch fleet.

    Returns None on success. For non-tmux shells this replaces the current
    process with `tmux attach`, so success does not return until tmux exits.
    """

    fleet = str(result.get("fleet") or "").strip()
    if not fleet:
        return "quick launch result did not include a fleet"

    if os.environ.get("TMUX"):
        completed = subprocess.run(["tmux", "switch-client", "-t", fleet])
        if completed.returncode != 0:
            return f"tmux switch-client failed with exit code {completed.returncode}"
        return None

    try:
        os.execvp("tmux", ["tmux", "attach", "-t", fleet])
    except OSError as exc:
        return f"tmux attach failed: {exc}"
    return None


def _spawn_args(args, *, profile: str | None, quick_agent: dict[str, object] | None) -> argparse.Namespace:
    runtime = _validate_runtime(args.runtime)
    runtime_profile = _profile_ref(runtime, profile)
    omx_profile = None
    boxed = runtime == "codex"
    return argparse.Namespace(
        name=args.seat or generated_seat(runtime),
        fleet=args.fleet or default_fleet(),
        fleet_id=None,
        knowledge=None,
        memory=None,
        resume_session=None,
        fresh=True,
        at=None,
        prompt=args.prompt,
        work=args.work,
        cwd=args.cwd or os.getcwd(),
        context=None,
        wait=args.wait,
        timeout=args.timeout,
        model=args.model,
        as_pane=args.as_pane,
        silent=False,
        runtime=runtime,
        profile=None,
        runtime_profile=runtime_profile,
        boxed=boxed,
        omx_profile=omx_profile,
        launch_command=None,
        identity_provider="aura-agent" if quick_agent else None,
        identity_id=quick_agent.get("agent_id") if quick_agent else None,
        identity_label=quick_agent.get("address") if quick_agent else None,
        fork_session=None,
        _agent_package=quick_agent,
    )


def run(args):
    try:
        profile, profile_meta = _resolve_profile(args)
        runtime = _validate_runtime(args.runtime)
        cwd = args.cwd or os.getcwd()
        fleet = args.fleet or default_fleet()
        seat = args.seat or generated_seat(runtime)
        quick_agent = _ensure_quick_agent(
            runtime,
            profile_ref=_profile_ref(runtime, profile),
            cwd=cwd,
            fleet=fleet,
            seat=seat,
        )
        args_for_spawn = argparse.Namespace(**vars(args))
        args_for_spawn.cwd = cwd
        args_for_spawn.fleet = fleet
        args_for_spawn.seat = seat
        spawn_args = _spawn_args(args_for_spawn, profile=profile, quick_agent=quick_agent)
    except Exception as exc:
        return {"ok": False, "error": "quick-launch-invalid", "detail": str(exc)}

    result = spawn.run(spawn_args)
    if isinstance(result, dict):
        result["quick"] = True
        result["quick_runtime"] = spawn_args.runtime
        result["quick_profile"] = profile
        if quick_agent:
            result["quick_agent_package_id"] = quick_agent.get("agent_id")
            result["quick_agent_package_address"] = quick_agent.get("address")
            result["quick_agent_package_alias"] = quick_agent.get("alias")
            result["quick_agent_package_root"] = quick_agent.get("root")
        if profile_meta:
            result["quick_profile_meta"] = profile_meta
    return result
