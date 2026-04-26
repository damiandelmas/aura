"""Runtime launch specs for terminal-backed aura agents."""

from __future__ import annotations

import shlex

RUNTIMES: dict[str, dict] = {
    "command": {
        "command": "{command}",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
    },
    "shell": {
        "command": "bash",
        "graceful_exit": "exit",
        "submit_key": "Enter",
    },
    "openclaw": {
        "command": "openclaw",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
    },
    "claude-code": {
        "command": "claude",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "context_candidates": ["CLAUDE.md", "AGENTS.md"],
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
    },
    "codex": {
        "command": "codex",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "context_candidates": ["AGENTS.md"],
    },
    "omx": {
        "command": "omx",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
        "native_state": ".omx",
        "context_candidates": ["AGENTS.md"],
    },
    "opencode": {
        "command": "opencode",
        "graceful_exit": "/exit",
        "submit_key": "Enter",
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


def graceful_exit(runtime: str | None, default: str = "/exit") -> str:
    """Return a graceful-exit command, falling back for unknown runtimes."""
    try:
        _, spec = resolve_runtime(runtime)
    except ValueError:
        return default
    return spec.get("graceful_exit", "/exit")
