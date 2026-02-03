"""Terminal multiplexer abstraction layer.

Selects backend based on AURA_TERMINAL env var or auto-detection.
Default: tmux (for compatibility)

Usage:
    from lib.terminal import backend
    backend.create_window("my-agent", workdir="/path")
    backend.send_keys("my-agent", "hello")
"""

import os
import subprocess


def detect_backend():
    """Auto-detect which terminal multiplexer to use.

    Priority:
    1. AURA_TERMINAL env var (explicit choice)
    2. Currently running inside zellij → use zellij
    3. Currently running inside tmux → use tmux
    4. Default to tmux
    """
    # Explicit override
    env_backend = os.environ.get("AURA_TERMINAL", "").lower()
    if env_backend in ("zellij", "zj"):
        return "zellij"
    if env_backend in ("tmux", "tm"):
        return "tmux"

    # Auto-detect from environment
    if os.environ.get("ZELLIJ"):
        return "zellij"
    if os.environ.get("TMUX"):
        return "tmux"

    # Check what's available
    zellij_available = subprocess.run(
        ["which", "zellij"], capture_output=True
    ).returncode == 0
    tmux_available = subprocess.run(
        ["which", "tmux"], capture_output=True
    ).returncode == 0

    # Prefer tmux for backwards compatibility
    if tmux_available:
        return "tmux"
    if zellij_available:
        return "zellij"

    raise RuntimeError("No terminal multiplexer found (need tmux or zellij)")


def get_backend():
    """Get the appropriate backend module."""
    backend_name = detect_backend()

    if backend_name == "zellij":
        from lib import zellij as backend
    else:
        from lib import tmux as backend

    return backend


# Module-level backend instance
backend = get_backend()

# Export all functions from backend
ensure_session = backend.ensure_session
create_window = backend.create_window
send_keys = backend.send_keys
capture_output = backend.capture_output
kill_window = backend.kill_window
window_exists = backend.window_exists
list_windows = backend.list_windows

# For introspection
BACKEND_NAME = detect_backend()
