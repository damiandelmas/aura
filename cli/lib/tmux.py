"""Tmux backend for aura.

Preserves the public primitive surface used by spawn / send / check / cut /
resolve / list commands. Keep this module dependency-light because every Aura
command imports it through lib.terminal, including read-only commands like view.
"""

import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

# Fleet name: the tmux session that groups agents working one initiative.
# Set via --fleet flag, AURA_FLEET env, or falls back to AURA_PROJECT/knowledge.
TMUX_SESSION = (os.environ.get("AURA_FLEET")
                or os.environ.get("AURA_TMUX_SESSION")
                or os.environ.get("AURA_PROJECT")
                or "aura")


def configure_session(session_name: str | None) -> str:
    """Retarget this process' tmux backend to a fleet session.

    The CLI imports several command modules at startup. Some of those modules
    import terminal/tmux before `spawn --fleet` has a chance to set AURA_FLEET,
    so the module-level TMUX_SESSION can otherwise freeze to the default
    "aura". Keep this mutable so command handlers can explicitly retarget the
    backend after argument parsing.
    """
    global TMUX_SESSION
    if session_name:
        TMUX_SESSION = session_name
    return TMUX_SESSION


def _session():
    """Return current libtmux Session, or None if it doesn't exist."""
    result = _run_tmux(["has-session", "-t", TMUX_SESSION])
    return True if result.returncode == 0 else None


def ensure_session() -> bool:
    """Create fleet session if doesn't exist.

    Returns:
        True if session was created, False if it already existed.
    """
    if _session() is not None:
        return False
    result = _run_tmux(["new-session", "-d", "-s", TMUX_SESSION])
    if result.returncode == 0:
        _apply_index_defaults()
        return True
    if "duplicate session" in (result.stderr or "").lower():
        _apply_index_defaults()
        return False
    return False


def _run_tmux(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def _apply_index_defaults(session_name: str | None = None) -> None:
    """Keep Aura-created tmux fleets on human-friendly 1-based indexes."""
    if os.environ.get("AURA_TMUX_INDEX_DEFAULTS", "1").strip().lower() in {"0", "false", "no", "off"}:
        return
    target = session_name or TMUX_SESSION
    for args in (
        ["set-option", "-t", target, "base-index", "1"],
        ["set-window-option", "-t", target, "pane-base-index", "1"],
        ["set-option", "-t", target, "renumber-windows", "on"],
        ["move-window", "-r", "-t", target],
    ):
        _run_tmux(args)


def _split_ref(ref: str) -> tuple[str, str]:
    """Return (fleet, tmux-subject) for window refs and pane refs."""
    value = str(ref or "")
    if value.startswith("tmux:"):
        value = value[len("tmux:"):]
    if ":" in value and not value.startswith("%"):
        fleet, subject = value.split(":", 1)
        return fleet or TMUX_SESSION, subject
    return TMUX_SESSION, value


def _tmux_target(ref: str) -> str:
    fleet, subject = _split_ref(ref)
    if subject.startswith("%"):
        return subject
    return f"={fleet}:{subject}"


def _backend_ref(ref: str) -> str:
    fleet, subject = _split_ref(ref)
    return f"{fleet}:{subject}"


def _subject(ref: str) -> str:
    return _split_ref(ref)[1]


def _pane_belongs_to_fleet(pane_ref: str, fleet: str) -> bool:
    result = _run_tmux(["display-message", "-p", "-t", pane_ref, "#{session_name}"])
    return result.returncode == 0 and result.stdout.strip() == fleet


def create_window(
    name: str,
    workdir: str | None = None,
    detached: bool = False,
    command: str | None = None,
    env: dict[str, str] | None = None,
    unset_env: list[str] | None = None,
):
    """Create named window in fleet session.

    Args:
        name: Window name
        workdir: Optional working directory for the window
        detached: If True, don't switch focus to the new window (libtmux attach=False).
                  Use when spawning workers from a session a human is attached to.
        unset_env: Environment variables to remove from the launched command.
    """
    def _command_with_env(command_text: str | None) -> str | None:
        if not command_text:
            return None
        env_parts = []
        if unset_env:
            env_parts.append("env")
            for key in unset_env:
                env_parts.extend(["-u", shlex.quote(str(key))])
        if env:
            env_parts.extend(f"{key}={shlex.quote(str(value))}" for key, value in env.items())
        env_prefix = " ".join(env_parts) + " " if env_parts else ""
        return env_prefix + command_text

    def _tmux_env_args() -> list[str]:
        # The shell prefix below affects only the launched command.  tmux panes
        # that the runtime creates later (for example OMX HUD splits) inherit
        # the tmux session/window environment instead, so mirror explicit Aura
        # launch env through tmux -e as well.
        if not env:
            return []
        tmux_env: list[str] = []
        for key, value in env.items():
            tmux_env.extend(["-e", f"{key}={value}"])
        return tmux_env

    # Keys whose values from the positive env dict should be pushed into the
    # session environment so that runtime-created child panes (OMX HUD splits,
    # etc.) inherit the CORRECT body home rather than whatever the tmux server
    # inherited from the spawning process.
    _BODY_HOME_KEYS = (
        "CODEX_HOME",
        "OMX_ROOT",
        "OMX_TEAM_STATE_ROOT",
    )

    def _scrub_session_env() -> None:
        """Remove stale identity vars from the tmux SESSION environment.

        This is belt-and-suspenders alongside the per-command ``env -u`` prefix:
        panes the runtime later creates (e.g. OMX HUD splits) inherit the tmux
        *session* environment, not the command prefix, so we must also scrub
        and re-set the relevant keys at the session level.

        Only called when env or unset_env is non-empty (i.e. an identity-aware
        spawn path), so legacy no-env windows are untouched.
        """
        if not env and not unset_env:
            return
        # Unset every key the caller asked to scrub.
        if unset_env:
            for key in unset_env:
                _run_tmux(["set-environment", "-t", TMUX_SESSION, "-u", key])
        # Re-set the body-home keys that were explicitly provided in env so
        # that child panes pick up the CORRECT values, not inherited stale ones.
        if env:
            for key in _BODY_HOME_KEYS:
                if key in env:
                    _run_tmux(["set-environment", "-t", TMUX_SESSION, key, env[key]])

    def _create_initial_session(command_text: str | None = None):
        args = ["new-session", "-d", "-s", TMUX_SESSION, "-n", name, *_tmux_env_args()]
        if workdir:
            args.extend(["-c", workdir])
        if command_text:
            args.append(command_text)
        return _run_tmux(args)

    def _new_window(command_text: str | None = None):
        args = ["new-window", "-t", TMUX_SESSION, "-n", name, *_tmux_env_args()]
        if detached:
            args.append("-d")
        if workdir:
            args.extend(["-c", workdir])
        if command_text:
            args.append(command_text)
        return _run_tmux(args)

    command_text = _command_with_env(command)
    sess = _session()
    if sess is None:
        result = _create_initial_session(command_text)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "duplicate session" in stderr.lower():
                _apply_index_defaults()
                _scrub_session_env()
                result = _new_window(command_text)
            if result.returncode != 0:
                return {"ok": False, "error": result.stderr.strip() or "tmux new-session failed", "name": name}
        else:
            _apply_index_defaults()
            _scrub_session_env()
        pane = pane_id(name)
        return {
            "ok": True,
            "name": name,
            "target": _backend_ref(name),
            "pane_id": pane,
            "pane_ref": f"{TMUX_SESSION}:{pane}" if pane else None,
        }

    _apply_index_defaults()
    _scrub_session_env()
    result = _new_window(command_text)
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip() or "tmux new-window failed", "name": name}
    pane = pane_id(name)
    return {
        "ok": True,
        "name": name,
        "target": _backend_ref(name),
        "pane_id": pane,
        "pane_ref": f"{TMUX_SESSION}:{pane}" if pane else None,
    }


def respawn_pane(
    target: str,
    workdir: str | None = None,
    command: str | None = None,
    env: dict[str, str] | None = None,
    unset_env: list[str] | None = None,
):
    """Replace the process in an existing pane while preserving the pane id."""
    if not target_exists(target):
        return {"ok": False, "error": f"target does not exist: {target}"}
    if not command:
        return {"ok": False, "error": "command is required"}
    args = ["respawn-pane", "-k", "-t", _tmux_target(target)]
    if workdir:
        args.extend(["-c", workdir])
    env_parts = []
    if unset_env:
        env_parts.append("env")
        for key in unset_env:
            env_parts.extend(["-u", shlex.quote(str(key))])
    if env:
        env_parts.extend(f"{key}={shlex.quote(str(value))}" for key, value in env.items())
    env_prefix = " ".join(env_parts) + " " if env_parts else ""
    args.append(env_prefix + command)
    result = _run_tmux(args)
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip() or "tmux respawn-pane failed"}
    pane = pane_id(target)
    return {
        "ok": True,
        "target": _backend_ref(target),
        "pane_id": pane,
        "pane_ref": f"{_split_ref(target)[0]}:{pane}" if pane else None,
        "respawned_viewport": True,
    }


def _window(name: str):
    """Return a named window in the current fleet session, or None."""
    result = _run_tmux(["list-windows", "-t", TMUX_SESSION, "-F", "#{window_name}"])
    if result.returncode != 0:
        return None
    return name if name in result.stdout.splitlines() else None


def _target(name: str) -> str:
    return _backend_ref(name)


def target_exists(ref: str) -> bool:
    """Check whether a tmux window or pane target exists."""
    fleet, subject = _split_ref(ref)
    if not subject:
        return False
    if subject.startswith("%"):
        return _pane_belongs_to_fleet(subject, fleet)
    result = _run_tmux(["list-windows", "-t", fleet, "-F", "#{window_name}"])
    if result.returncode != 0:
        return False
    return subject in {line.strip() for line in result.stdout.splitlines() if line.strip()}


def pane_id(ref: str) -> str | None:
    """Return the active pane id for a window/pane target."""
    if not target_exists(ref):
        return None
    result = _run_tmux(["display-message", "-p", "-t", _tmux_target(ref), "#{pane_id}"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def pane_pid(ref: str) -> int | None:
    """Return active pane pid for a window/pane target."""
    if not target_exists(ref):
        return None
    result = _run_tmux(["display-message", "-p", "-t", _tmux_target(ref), "#{pane_pid}"])
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except (TypeError, ValueError):
        return None


def target_window(ref: str) -> str | None:
    if not target_exists(ref):
        return None
    result = _run_tmux(["display-message", "-p", "-t", _tmux_target(ref), "#{window_name}"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def set_pane_title(ref: str, title: str) -> bool:
    result = _run_tmux(["select-pane", "-t", _tmux_target(ref), "-T", title])
    return result.returncode == 0


def send_keys(name: str, text: str, enter: bool = True):
    """Send text to window, optionally followed by Enter.

    Kept for legacy call sites. New multiline/message delivery should use
    send_text(), which uses tmux buffers instead of shell/key quoting.
    """
    if not target_exists(name):
        return None
    target = _tmux_target(name)
    if text:
        result = _run_tmux(["send-keys", "-t", target, text])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "tmux send-keys failed", "target": _target(name)}
    if enter:
        time.sleep(0.3)  # Critical delay for agent CLIs
        result = _run_tmux(["send-keys", "-t", target, "Enter"])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "tmux enter failed", "target": _target(name)}
    return {"ok": True, "target": _target(name), "submitted": enter}


def _submit_delay_seconds(default: float = 0.75) -> float:
    raw = os.environ.get("AURA_TMUX_SUBMIT_DELAY_SECONDS")
    if raw is None:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default


def send_text(name: str, text: str, submit: bool = True, submit_key: str = "Enter") -> dict:
    """Paste text into a tmux window safely, optionally submitting it.

    Uses tmux load-buffer + paste-buffer so multiline prompts and message
    envelopes are not mangled by shell quoting or libtmux send-keys behavior.
    """
    if not target_exists(name):
        return {"ok": False, "error": f"tmux target not found: {name}", "name": _subject(name)}

    Path("/tmp/aura/messages").mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="aura-msg-", suffix=".txt", dir="/tmp/aura/messages")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)

        buffer_name = f"aura-{Path(path).stem}"
        load = subprocess.run(
            ["tmux", "load-buffer", "-b", buffer_name, path],
            capture_output=True,
            text=True,
        )
        if load.returncode != 0:
            return {"ok": False, "error": load.stderr.strip() or "tmux load-buffer failed", "name": name}

        paste = subprocess.run(
            ["tmux", "paste-buffer", "-p", "-t", _tmux_target(name), "-b", buffer_name],
            capture_output=True,
            text=True,
        )
        if paste.returncode != 0:
            return {"ok": False, "error": paste.stderr.strip() or "tmux paste-buffer failed", "name": name}

        submitted = False
        delay_seconds = 0.0
        if submit:
            delay_seconds = _submit_delay_seconds()
            if delay_seconds:
                time.sleep(delay_seconds)
            key = "Enter" if submit_key in ("Enter", "") else submit_key
            submit_result = subprocess.run(
                ["tmux", "send-keys", "-t", _tmux_target(name), key],
                capture_output=True,
                text=True,
            )
            if submit_result.returncode != 0:
                return {"ok": False, "error": submit_result.stderr.strip() or "tmux submit failed", "name": _subject(name)}
            submitted = True

        return {
            "ok": True,
            "name": _subject(name),
            "target": _target(name),
            "pane_id": pane_id(name),
            "bytes": len(text.encode("utf-8")),
            "submitted": submitted,
            "submit_delay_seconds": delay_seconds,
        }
    finally:
        subprocess.run(
            ["tmux", "delete-buffer", "-b", buffer_name],
            capture_output=True,
            text=True,
        )
        try:
            os.unlink(path)
        except OSError:
            pass


def capture_output(name: str, lines: int = 20, ansi: bool = False) -> list[str]:
    """Capture last N lines from a window or pane target."""
    if not target_exists(name):
        return []
    args = ["capture-pane", "-p", "-t", _tmux_target(name), "-S", f"-{int(lines)}"]
    if ansi:
        args.insert(1, "-e")
    result = _run_tmux(args)
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def kill_window(name: str):
    """Kill a window target, or a pane when passed a pane ref."""
    fleet, subject = _split_ref(name)
    if subject.startswith("%"):
        # Belt-and-suspenders: verify the pane actually belongs to the expected
        # fleet before killing to prevent cross-fleet kills on stale pane ids.
        if not _pane_belongs_to_fleet(subject, fleet):
            return
        _run_tmux(["kill-pane", "-t", subject])
        return
    if not target_exists(name):
        return
    _run_tmux(["kill-window", "-t", f"={fleet}:{subject}"])


def window_exists(name: str) -> bool:
    """Compatibility wrapper: check if a window or pane target exists."""
    return target_exists(name)


def list_windows() -> list[str]:
    """List all window names in fleet session."""
    result = _run_tmux(["list-windows", "-t", TMUX_SESSION, "-F", "#{window_name}"])
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]
