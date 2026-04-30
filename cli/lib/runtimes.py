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
    "openclaw": {
        "command": "openclaw",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "capabilities": {
            "supports_resume": False,
            "session_id_source": "unknown",
        },
    },
    "claude-code": {
        "command": "claude --dangerously-skip-permissions",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "context_candidates": ["CLAUDE.md", "AGENTS.md"],
        "capabilities": {
            "supports_resume": True,
            "session_id_source": "claude-jsonl-or-env",
        },
    },
    "claude": {
        "alias_for": "claude-code",
    },
    "hermes": {
        "command": "hermes -p {profile}",
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
            "session_id_source": "codex-state-or-resume-argv",
            "resume_command": "codex --dangerously-bypass-approvals-and-sandbox resume {session_id}",
        },
    },
    "omx": {
        "command": "omx",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "native_state": ".omx",
        "context_candidates": ["AGENTS.md"],
        "capabilities": {
            "supports_resume": False,
            "session_id_source": "native-state",
        },
    },
    "opencode": {
        "command": "opencode",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "capabilities": {
            "supports_resume": False,
            "session_id_source": "unknown",
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


def build_command(runtime: str, spec: dict, *, name: str, profile: str | None = None,
                  model: str | None = None, command_override: str | None = None) -> str:
    if command_override:
        return command_override

    profile = profile or name
    command = spec["command"].format(
        name=shlex.quote(name),
        profile=shlex.quote(profile),
    )

    if runtime == "claude-code" and model:
        command = f"{command} --model {shlex.quote(model)}"

    return command


def build_resume_command(runtime: str, session_id: str) -> str:
    resolved, spec = resolve_runtime(runtime)
    resume_template = (spec.get("capabilities") or {}).get("resume_command")
    if not resume_template:
        raise ValueError(f"runtime does not support native resume: {resolved}")
    return resume_template.format(session_id=shlex.quote(session_id))


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
