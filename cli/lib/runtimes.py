"""Runtime launch specs for terminal-backed aura agents."""

from __future__ import annotations

import shlex

RUNTIMES: dict[str, dict] = {
    "command": {
        "command": "{command}",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "capabilities": {
            "supports_resume": False,
            "session_id_source": "none",
        },
    },
    "shell": {
        "command": "bash",
        "graceful_exit": "exit",
        "submit_key": "Enter",
        "capabilities": {
            "supports_resume": False,
            "session_id_source": "none",
        },
    },
    "claude-code": {
        "command": "claude --dangerously-skip-permissions",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "context_candidates": ["CLAUDE.md", "AGENTS.md"],
        "capabilities": {
            "supports_resume": True,
            "supports_initial_prompt_argv": True,
            "session_id_source": "claude-jsonl-or-env",
        },
    },
    "claude": {
        "alias_for": "claude-code",
    },
    "hermes": {
        "command": "hermes",
        "profile_command": "hermes -p {profile}",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "native_state": ".hermes",
        "context_candidates": [".hermes.md", "HERMES.md", "AGENTS.md"],
        "capabilities": {
            "supports_resume": False,
            "session_id_source": "native-state",
        },
    },
    "codex": {
        "command": "codex --dangerously-bypass-approvals-and-sandbox",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "context_candidates": ["AGENTS.md"],
        "capabilities": {
            "supports_resume": True,
            "supports_fork": True,
            "supports_initial_prompt_argv": True,
            "session_id_source": "codex-state-or-resume-argv",
            "resume_command": "codex --dangerously-bypass-approvals-and-sandbox resume {session_id}",
            "fork_command": "codex --dangerously-bypass-approvals-and-sandbox fork {session_id}{prompt_arg}",
        },
    },
    "gajae-code": {
        "command": "gjc",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "native_state": ".gjc",
        "context_candidates": ["AGENTS.md"],
        "capabilities": {
            "supports_resume": False,
            "supports_fork": False,
            "session_id_source": "package-gjc-state",
        },
    },
}


def resolve_runtime(runtime: str | None) -> tuple[str, dict]:
    key = runtime or "claude-code"
    if key not in RUNTIMES:
        known = ", ".join(sorted(RUNTIMES))
        raise ValueError(f"unknown runtime: {key} (known: {known})")
    spec = dict(RUNTIMES[key])
    if "alias_for" in spec:
        key = spec["alias_for"]
        spec = dict(RUNTIMES[key])
    return key, spec


def supports_initial_prompt_argv(runtime: str, spec: dict | None = None) -> bool:
    resolved_spec = spec
    if resolved_spec is None:
        try:
            _, resolved_spec = resolve_runtime(runtime)
        except ValueError:
            return False
    return bool((resolved_spec.get("capabilities") or {}).get("supports_initial_prompt_argv"))


def build_command(runtime: str, spec: dict, *, name: str, profile: str | None = None,
                  model: str | None = None, command_override: str | None = None,
                  prompt: str | None = None) -> str:
    if command_override:
        return command_override

    if runtime == "hermes" and (not profile or profile == "default"):
        command_template = spec["command"]
        profile_for_template = ""
    else:
        profile_for_template = profile or name
        command_template = spec.get("profile_command") if profile else None
        command_template = command_template or spec["command"]
    command = command_template.format(
        name=shlex.quote(name),
        profile=shlex.quote(profile_for_template),
    )

    if runtime == "claude-code" and model:
        command = f"{command} --model {shlex.quote(model)}"

    if prompt and supports_initial_prompt_argv(runtime, spec):
        command = f"{command} {shlex.quote(prompt)}"

    return command


def build_resume_command(runtime: str, session_id: str, *, cwd: str | None = None) -> str:
    resolved, spec = resolve_runtime(runtime)
    resume_template = (spec.get("capabilities") or {}).get("resume_command")
    if not resume_template:
        raise ValueError(f"runtime does not support native resume: {resolved}")
    cwd_arg = f" --cd {shlex.quote(cwd)}" if cwd else ""
    command = resume_template.format(
        session_id=shlex.quote(session_id),
        cwd_arg=cwd_arg,
    )
    if resolved == "codex" and cwd and "{cwd_arg}" not in resume_template:
        return command.replace("codex ", f"codex --cd {shlex.quote(cwd)} ", 1)
    return command


def build_fork_command(runtime: str, session_id: str, *, prompt: str | None = None, cwd: str | None = None) -> str:
    resolved, spec = resolve_runtime(runtime)
    fork_template = (spec.get("capabilities") or {}).get("fork_command")
    if not fork_template:
        raise ValueError(f"runtime does not support native fork: {resolved}")
    prompt_arg = f" {shlex.quote(prompt)}" if prompt else ""
    command = fork_template.format(
        session_id=shlex.quote(session_id),
        prompt_arg=prompt_arg,
    )
    if resolved == "codex" and cwd:
        return command.replace("codex ", f"codex --cd {shlex.quote(cwd)} ", 1)
    return command


def graceful_exit(runtime: str | None, default: str = "/exit") -> str:
    """Return a graceful-exit command, falling back for unknown runtimes."""
    try:
        _, spec = resolve_runtime(runtime)
    except ValueError:
        return default
    return spec.get("graceful_exit", "/exit")


def capabilities(runtime: str | None) -> dict:
    try:
        resolved, spec = resolve_runtime(runtime)
    except ValueError:
        return {
            "runtime": runtime,
            "supports_resume": False,
            "session_id_source": "unknown",
        }
    return {
        "runtime": resolved,
        **dict(spec.get("capabilities") or {}),
    }


def capability_map() -> dict[str, dict]:
    return {key: capabilities(key) for key in RUNTIMES if "alias_for" not in RUNTIMES[key]}
