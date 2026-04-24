"""Terminal multiplexer abstraction — tmux-only since 2026-04-14.

Zellij backend was explored (see context/changes/code/260320-1058_zellij-backend-adoption.md)
but abandoned. We run tmux exclusively. The seam here is preserved in case a future
backend returns, but `BACKEND_NAME` is always 'tmux'.

Usage:
    from lib.terminal import backend
    backend.create_window("my-agent", workdir="/path")
    backend.send_keys("my-agent", "hello")
"""

from lib import tmux as backend

# Export all functions from backend
ensure_session = backend.ensure_session
create_window = backend.create_window
send_keys = backend.send_keys
send_text = backend.send_text
capture_output = backend.capture_output
kill_window = backend.kill_window
window_exists = backend.window_exists
list_windows = backend.list_windows

# For introspection
BACKEND_NAME = "tmux"
SESSION_NAME = backend.TMUX_SESSION
FLEET_NAME = SESSION_NAME  # Alias: fleet = tmux session grouping agents
