"""Tmux wrapper for aura session management (hidden from AI)."""

import os
import subprocess
import time

# Session name from env, knowledge session, or default
# Set AURA_TMUX_SESSION or pass --knowledge to aura spawn
TMUX_SESSION = os.environ.get("AURA_TMUX_SESSION") or os.environ.get("AURA_PROJECT") or "aura"


def ensure_session():
    """Create orca session if doesn't exist.

    Returns:
        True if session was created, False if it already existed
    """
    result = subprocess.run(
        ["tmux", "has-session", "-t", TMUX_SESSION],
        capture_output=True
    )
    if result.returncode != 0:
        subprocess.run(["tmux", "new-session", "-d", "-s", TMUX_SESSION])
        return True
    return False


def create_window(name, workdir=None):
    """Create named window in orca session.

    Args:
        name: Window name
        workdir: Optional working directory for the window

    Returns:
        CompletedProcess result
    """
    cmd = ["tmux", "new-window", "-t", TMUX_SESSION, "-n", name]
    if workdir:
        cmd.extend(["-c", workdir])
    return subprocess.run(cmd, capture_output=True)


def send_keys(name, text, enter=True):
    """Send text to window, optionally followed by Enter.

    Args:
        name: Window name
        text: Text to send
        enter: If True, send Enter key after text (with delay for Claude)
    """
    target = f"{TMUX_SESSION}:{name}"
    subprocess.run(["tmux", "send-keys", "-t", target, text])
    if enter:
        time.sleep(0.3)  # Critical delay for Claude
        subprocess.run(["tmux", "send-keys", "-t", target, "Enter"])


def capture_output(name, lines=20):
    """Capture last N lines from window.

    Args:
        name: Window name
        lines: Number of lines to capture from end

    Returns:
        List of captured lines
    """
    target = f"{TMUX_SESSION}:{name}"
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", target, "-p"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        all_lines = result.stdout.strip().split('\n')
        return all_lines[-lines:] if len(all_lines) > lines else all_lines
    return []


def kill_window(name):
    """Kill window.

    Args:
        name: Window name

    Returns:
        CompletedProcess result
    """
    target = f"{TMUX_SESSION}:{name}"
    return subprocess.run(["tmux", "kill-window", "-t", target], capture_output=True)


def window_exists(name):
    """Check if window exists.

    Args:
        name: Window name

    Returns:
        True if window exists in session
    """
    target = f"{TMUX_SESSION}:{name}"
    result = subprocess.run(
        ["tmux", "list-windows", "-t", TMUX_SESSION, "-F", "#{window_name}"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        windows = result.stdout.strip().split('\n')
        return name in windows
    return False


def list_windows():
    """List all windows in session.

    Returns:
        List of window names
    """
    result = subprocess.run(
        ["tmux", "list-windows", "-t", TMUX_SESSION, "-F", "#{window_name}"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return [w for w in result.stdout.strip().split('\n') if w]
    return []
