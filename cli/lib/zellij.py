"""Zellij wrapper for orca session management (hidden from AI).

Drop-in replacement for tmux.py. Same interface, different backend.

Zellij concepts mapping:
- tmux session → zellij session
- tmux window  → zellij tab
- tmux pane    → zellij pane (we use 1 pane per tab for simplicity)
"""

import subprocess
import time
import os
import tempfile

ZELLIJ_SESSION = "orca"


def ensure_session():
    """Create orca session if doesn't exist.

    Returns:
        True if session was created, False if it already existed
    """
    result = subprocess.run(
        ["zellij", "list-sessions"],
        capture_output=True, text=True
    )
    if ZELLIJ_SESSION not in result.stdout:
        # Start detached session
        subprocess.run([
            "zellij", "--session", ZELLIJ_SESSION,
            "options", "--detached"
        ], capture_output=True)
        # Alternative: use zellij attach --create
        subprocess.Popen(
            ["zellij", "attach", "--create", ZELLIJ_SESSION],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        time.sleep(0.5)  # Let session initialize
        return True
    return False


def create_window(name, workdir=None):
    """Create named tab in orca session.

    Args:
        name: Tab name (will also be pane name)
        workdir: Optional working directory

    Returns:
        CompletedProcess result
    """
    # Create new tab with name
    cmd = [
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "new-tab", "--name", name
    ]
    if workdir:
        cmd.extend(["--cwd", workdir])

    return subprocess.run(cmd, capture_output=True)


def send_keys(name, text, enter=True):
    """Send text to tab, optionally followed by Enter.

    Args:
        name: Tab name
        text: Text to send
        enter: If True, send Enter key after text (with delay for Claude)
    """
    # First switch to the tab
    subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "go-to-tab-name", name
    ], capture_output=True)

    # Write characters to focused pane
    subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "write-chars", text
    ], capture_output=True)

    if enter:
        time.sleep(0.3)  # Critical delay for Claude
        subprocess.run([
            "zellij", "--session", ZELLIJ_SESSION,
            "action", "write", "13"  # Enter key (ASCII 13)
        ], capture_output=True)


def capture_output(name, lines=20):
    """Capture last N lines from tab.

    Args:
        name: Tab name
        lines: Number of lines to capture from end

    Returns:
        List of captured lines
    """
    # Switch to tab first
    subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "go-to-tab-name", name
    ], capture_output=True)

    # Dump screen to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        dump_path = f.name

    try:
        result = subprocess.run([
            "zellij", "--session", ZELLIJ_SESSION,
            "action", "dump-screen", dump_path
        ], capture_output=True)

        if result.returncode == 0 and os.path.exists(dump_path):
            with open(dump_path, 'r') as f:
                all_lines = f.read().strip().split('\n')
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    finally:
        if os.path.exists(dump_path):
            os.unlink(dump_path)

    return []


def kill_window(name):
    """Kill tab.

    Args:
        name: Tab name

    Returns:
        CompletedProcess result
    """
    # Switch to tab, then close it
    subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "go-to-tab-name", name
    ], capture_output=True)

    return subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "close-tab"
    ], capture_output=True)


def window_exists(name):
    """Check if tab exists.

    Args:
        name: Tab name

    Returns:
        True if tab exists in session
    """
    # Query tab names via dump-layout and parse
    result = subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "query-tab-names"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        tabs = result.stdout.strip().split('\n')
        return name in tabs

    # Fallback: try to go to tab
    result = subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "go-to-tab-name", name
    ], capture_output=True)
    return result.returncode == 0


def list_windows():
    """List all tabs in session.

    Returns:
        List of tab names
    """
    result = subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "query-tab-names"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        return [t for t in result.stdout.strip().split('\n') if t]
    return []


# --- Zellij-specific features (bonus) ---

def create_floating_pane(name, workdir=None, command=None):
    """Create a floating pane (Zellij exclusive feature).

    Args:
        name: Pane name
        workdir: Working directory
        command: Optional command to run

    Returns:
        CompletedProcess result
    """
    cmd = [
        "zellij", "--session", ZELLIJ_SESSION,
        "run", "--floating", "--name", name
    ]
    if workdir:
        cmd.extend(["--cwd", workdir])
    if command:
        cmd.extend(["--", command])
    else:
        cmd.extend(["--", "bash"])

    return subprocess.run(cmd, capture_output=True)


def toggle_floating():
    """Toggle floating panes visibility."""
    return subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "toggle-floating-panes"
    ], capture_output=True)


def pin_floating_pane():
    """Pin current floating pane (always on top)."""
    return subprocess.run([
        "zellij", "--session", ZELLIJ_SESSION,
        "action", "toggle-pane-pinned"
    ], capture_output=True)
