"""Tmux backend for aura — libtmux adapter.

Wraps libtmux as a thin primitive layer. Preserves the public function surface
used by spawn / send / check / cut / resolve / list commands.

Vendor: libtmux (MIT, pinned in requirements). Picasso steal — we adapt, not copy.
"""

import os
import time

import libtmux

# Fleet name: the tmux session that groups agents working one initiative.
# Set via --fleet flag, AURA_FLEET env, or falls back to AURA_PROJECT/knowledge.
TMUX_SESSION = (os.environ.get("AURA_FLEET")
                or os.environ.get("AURA_TMUX_SESSION")
                or os.environ.get("AURA_PROJECT")
                or "aura")


# Module-level server handle, lazy-initialized
_server: libtmux.Server | None = None


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


def create_window(name: str, workdir: str | None = None, detached: bool = False):
    """Create named window in fleet session.

    Args:
        name: Window name
        workdir: Optional working directory for the window
        detached: If True, don't switch focus to the new window (libtmux attach=False).
                  Use when spawning workers from a session a human is attached to.
    """
    sess = _session()
    if sess is None:
        ensure_session()
        sess = _session()
    kwargs = {"window_name": name, "attach": not detached}
    if workdir:
        kwargs["start_directory"] = workdir
    return sess.new_window(**kwargs)


def send_keys(name: str, text: str, enter: bool = True):
    """Send text to window, optionally followed by Enter.

    Args:
        name: Window name
        text: Text to send
        enter: If True, send Enter key after text (with delay for Claude)
    """
    sess = _session()
    if sess is None:
        return
    win = sess.windows.get(window_name=name, default=None)
    if win is None:
        return
    pane = win.active_pane
    pane.send_keys(text, enter=False, suppress_history=False)
    if enter:
        time.sleep(0.3)  # Critical delay for Claude
        pane.enter()


def capture_output(name: str, lines: int = 20) -> list[str]:
    """Capture last N lines from window's active pane."""
    sess = _session()
    if sess is None:
        return []
    win = sess.windows.get(window_name=name, default=None)
    if win is None:
        return []
    pane = win.active_pane
    all_lines = pane.capture_pane()
    if not all_lines:
        return []
    return all_lines[-lines:] if len(all_lines) > lines else all_lines


def kill_window(name: str):
    """Kill window by name."""
    sess = _session()
    if sess is None:
        return
    win = sess.windows.get(window_name=name, default=None)
    if win is None:
        return
    win.kill()


def window_exists(name: str) -> bool:
    """Check if window exists in fleet session."""
    sess = _session()
    if sess is None:
        return False
    return sess.windows.get(window_name=name, default=None) is not None


def list_windows() -> list[str]:
    """List all window names in fleet session."""
    sess = _session()
    if sess is None:
        return []
    return [w.window_name for w in sess.windows if w.window_name]
