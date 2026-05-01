"""Tmux backend for aura — libtmux adapter.

Wraps libtmux as a thin primitive layer. Preserves the public function surface
used by spawn / send / check / cut / resolve / list commands.

Vendor: libtmux (MIT, pinned in requirements). Picasso steal — we adapt, not copy.
"""

import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

import libtmux

# Fleet name: the tmux session that groups agents working one initiative.
# Set via --fleet flag, AURA_FLEET env, or falls back to AURA_PROJECT/knowledge.
TMUX_SESSION = (os.environ.get("AURA_FLEET")
                or os.environ.get("AURA_TMUX_SESSION")
                or os.environ.get("AURA_PROJECT")
                or "aura")


# Module-level server handle, lazy-initialized
_server: libtmux.Server | None = None


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


def _srv() -> libtmux.Server:
    global _server
    if _server is None:
        _server = libtmux.Server()
    return _server


def _session():
    """Return current libtmux Session, or None if it doesn't exist."""
    try:
        return _srv().sessions.get(session_name=TMUX_SESSION)
    except Exception:
        return None


def ensure_session() -> bool:
    """Create fleet session if doesn't exist.

    Returns:
        True if session was created, False if it already existed.
    """
    if _session() is not None:
        return False
    _srv().new_session(session_name=TMUX_SESSION, detach=True)
    return True


def _run_tmux(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


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
    return f"{fleet}:{subject}"


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
    sess = _session()
    if sess is None:
        ensure_session()
        sess = _session()

    if command:
        args = ["new-window", "-t", TMUX_SESSION, "-n", name]
        if detached:
            args.append("-d")
        if workdir:
            args.extend(["-c", workdir])
        env_prefix = ""
        env_parts = []
        if unset_env:
            env_parts.append("env")
            for key in unset_env:
                env_parts.extend(["-u", shlex.quote(str(key))])
        if env:
            env_parts.extend(f"{key}={shlex.quote(str(value))}" for key, value in env.items())
        if env_parts:
            env_prefix = " ".join(env_parts) + " "
        args.append(env_prefix + command)
        result = _run_tmux(args)
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

    kwargs = {"window_name": name, "attach": not detached}
    if workdir:
        kwargs["start_directory"] = workdir
    win = sess.new_window(**kwargs)
    pane = getattr(win.active_pane, "pane_id", None)
    return {
        "ok": True,
        "name": name,
        "target": _backend_ref(name),
        "pane_id": pane,
        "pane_ref": f"{TMUX_SESSION}:{pane}" if pane else None,
        "window": win,
    }


def _window(name: str):
    """Return a named window in the current fleet session, or None."""
    sess = _session()
    if sess is None:
        return None
    return sess.windows.get(window_name=name, default=None)


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
            ["tmux", "paste-buffer", "-t", _tmux_target(name), "-b", buffer_name],
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
        _run_tmux(["kill-pane", "-t", subject])
        return
    if not target_exists(name):
        return
    _run_tmux(["kill-window", "-t", f"{fleet}:{subject}"])


def window_exists(name: str) -> bool:
    """Compatibility wrapper: check if a window or pane target exists."""
    return target_exists(name)


def list_windows() -> list[str]:
    """List all window names in fleet session."""
    sess = _session()
    if sess is None:
        return []
    return [w.window_name for w in sess.windows if w.window_name]
