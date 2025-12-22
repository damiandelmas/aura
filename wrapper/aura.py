#!/usr/bin/env python3
"""
aura - Thin PTY wrapper for Claude Code with external control handles.

Provides traction (hooks) for external processes to control Claude:
- Control socket for signals (refresh, fork, stop, status)
- Telemetry emission
- Lifecycle management (restart without losing session)

Delegates actual operations to memory/orca CLIs.

Usage:
    aura                      # Fresh Claude session
    aura -r SESSION_ID        # Resume session
    aura --socket /tmp/x.sock # Custom control socket path
"""

import os
import sys
import pty
import json
import select
import signal
import socket
import threading
import subprocess
from pathlib import Path
from datetime import datetime

# === CONFIG ===
CLAUDE_BIN = "claude"
SOCKET_DIR = Path("/tmp/aura")
MESH_SOCKET = Path("/tmp/aura/mesh.sock")
MEMORY_CLI = "memory"  # TODO: actual path when exists
ORCA_CLI = "orca"      # TODO: actual path when exists

# Paths to actual scripts (until CLI exists)
REFRESH_SCRIPT = Path.home() / "projects/claude-code/invocation/skills/active/refresh/scripts/external_refresh.py"
SPAWN_SCRIPT = Path.home() / "projects/fleet/hangar/code/orca/main/primitives/spawn/async-tmux-state.sh"


def mesh_request(cmd: dict) -> dict | None:
    """Send request to mesh daemon."""
    if not MESH_SOCKET.exists():
        return None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(MESH_SOCKET))
        sock.send(json.dumps(cmd).encode('utf-8'))
        response = sock.recv(8192).decode('utf-8')
        sock.close()
        return json.loads(response)
    except:
        return None


class Aura:
    """Thin wrapper around Claude with control handles."""

    def __init__(self, claude_args: list[str] = None, socket_path: str = None, name: str = None):
        self.claude_args = claude_args or []
        self.session_id = self._extract_session_id()
        self.socket_path = socket_path or self._default_socket_path()
        self.name = name or self._default_name()

        self.master_fd = None
        self.child_pid = None
        self.running = False
        self.control_socket = None
        self.control_thread = None
        self.message_queue: list[str] = []  # Pending messages to inject
        self.mesh_connected = False

    def _extract_session_id(self) -> str | None:
        """Extract session ID from args if resuming."""
        if "-r" in self.claude_args:
            idx = self.claude_args.index("-r")
            if idx + 1 < len(self.claude_args):
                return self.claude_args[idx + 1]
        return None

    def _default_socket_path(self) -> str:
        """Generate socket path."""
        SOCKET_DIR.mkdir(exist_ok=True)
        sid = self.session_id or f"new-{os.getpid()}"
        return str(SOCKET_DIR / f"{sid[:8]}.sock")

    def _default_name(self) -> str:
        """Generate agent name."""
        if self.session_id:
            return f"agent-{self.session_id[:8]}"
        return f"agent-{os.getpid()}"

    # === MESH INTEGRATION ===

    def mesh_register(self):
        """Register with mesh daemon."""
        result = mesh_request({
            "action": "register",
            "name": self.name,
            "session_id": self.session_id or "",
            "socket_path": self.socket_path
        })
        if result and result.get("ok"):
            self.mesh_connected = True
            self._emit("mesh_registered", {"name": self.name})

    def mesh_unregister(self):
        """Unregister from mesh daemon."""
        if self.mesh_connected:
            mesh_request({"action": "unregister", "name": self.name})
            self.mesh_connected = False

    def mesh_heartbeat(self, status: str = "idle"):
        """Send heartbeat to mesh."""
        if self.mesh_connected:
            mesh_request({"action": "heartbeat", "name": self.name, "status": status})

    def mesh_poll_messages(self):
        """Poll mesh for pending messages."""
        if not self.mesh_connected:
            return

        result = mesh_request({"action": "receive", "name": self.name})
        if result and result.get("messages"):
            for msg in result["messages"]:
                from_agent = msg.get("from_agent", "unknown")
                content = msg.get("content", "")
                formatted = f"<system-reminder>\nMessage from @{from_agent}:\n{content}\n</system-reminder>\n"
                self.message_queue.append(formatted)
                self._emit("message_received", {"from": from_agent})

    def mesh_send(self, to_agent: str, content: str) -> dict:
        """Send message to another agent via mesh."""
        return mesh_request({
            "action": "send",
            "from": self.name,
            "to": to_agent,
            "content": content
        }) or {"error": "mesh unavailable"}

    # === LIFECYCLE ===

    def start_claude(self):
        """Spawn Claude in PTY."""
        pid, fd = pty.fork()

        if pid == 0:
            # Child - exec claude
            cmd = [CLAUDE_BIN] + self.claude_args
            os.execvp(cmd[0], cmd)
        else:
            # Parent
            self.child_pid = pid
            self.master_fd = fd
            self.running = True
            self._emit("started", {"pid": pid, "session": self.session_id})

    def stop_claude(self, graceful=True):
        """Stop Claude subprocess."""
        if not self.child_pid:
            return

        try:
            sig = signal.SIGTERM if graceful else signal.SIGKILL
            os.kill(self.child_pid, sig)
            os.waitpid(self.child_pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass

        self._emit("stopped", {"pid": self.child_pid})
        self.child_pid = None
        self.master_fd = None

    def restart_claude(self):
        """Restart Claude, preserving session."""
        self.stop_claude()

        # Ensure resume flag if we have session
        if self.session_id and "-r" not in self.claude_args:
            self.claude_args = ["-r", self.session_id] + self.claude_args

        self.start_claude()
        self._emit("restarted", {"session": self.session_id})

    # === CONTROL SOCKET ===

    def start_control_socket(self):
        """Start Unix socket for control signals."""
        # Clean up old socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        self.control_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.control_socket.bind(self.socket_path)
        self.control_socket.listen(1)
        self.control_socket.setblocking(False)

        self._emit("socket_ready", {"path": self.socket_path})

    def handle_control_message(self, msg: str) -> str:
        """Handle control message, return response."""
        try:
            cmd = json.loads(msg)
        except json.JSONDecodeError:
            cmd = {"action": msg.strip()}

        action = cmd.get("action", "")

        if action == "refresh":
            return self._do_refresh(cmd)
        elif action == "fork":
            return self._do_fork(cmd)
        elif action == "stop":
            return self._do_stop(cmd)
        elif action == "status":
            return self._do_status(cmd)
        elif action == "restart":
            return self._do_restart(cmd)
        elif action == "send":
            return self._do_send_message(cmd)
        elif action == "inject":
            return self._do_inject(cmd)
        else:
            return json.dumps({"error": f"unknown action: {action}"})

    def check_control_socket(self):
        """Non-blocking check for control messages."""
        if not self.control_socket:
            return

        try:
            conn, _ = self.control_socket.accept()
            conn.setblocking(True)
            data = conn.recv(4096).decode('utf-8')
            if data:
                response = self.handle_control_message(data)
                conn.send(response.encode('utf-8'))
            conn.close()
        except BlockingIOError:
            pass  # No connection waiting

    # === DELEGATED OPERATIONS ===

    def _do_refresh(self, cmd: dict) -> str:
        """Delegate refresh to memory CLI."""
        self._emit("refresh_start", {})

        self.stop_claude()

        # Call memory.edit.conversation.refresh
        # TODO: use memory CLI when it exists
        if REFRESH_SCRIPT.exists():
            result = subprocess.run(
                ["python3", str(REFRESH_SCRIPT), self.session_id[:8] if self.session_id else ""],
                capture_output=True, text=True
            )
            self._emit("refresh_done", {"stdout": result.stdout[-500:]})

        self.start_claude()
        return json.dumps({"ok": True, "action": "refresh"})

    def _do_fork(self, cmd: dict) -> str:
        """Delegate fork to orca."""
        name = cmd.get("name", f"fork-{datetime.now().strftime('%H%M%S')}")
        at = cmd.get("at")  # message number to slice at

        self._emit("fork_start", {"name": name, "at": at})

        # Call orca.spawn with inherit
        # TODO: use orca CLI when it exists
        if SPAWN_SCRIPT.exists() and self.session_id:
            spawn_cmd = [str(SPAWN_SCRIPT), self.session_id, "--name", name]
            if at:
                spawn_cmd.extend(["--at", str(at)])
            result = subprocess.run(spawn_cmd, capture_output=True, text=True)
            self._emit("fork_done", {"name": name, "stdout": result.stdout[-500:]})
            return json.dumps({"ok": True, "action": "fork", "name": name})

        return json.dumps({"error": "fork not available"})

    def _do_stop(self, cmd: dict) -> str:
        """Stop Claude."""
        self.stop_claude()
        self.running = False
        return json.dumps({"ok": True, "action": "stop"})

    def _do_restart(self, cmd: dict) -> str:
        """Restart Claude."""
        self.restart_claude()
        return json.dumps({"ok": True, "action": "restart"})

    def _do_status(self, cmd: dict) -> str:
        """Return status."""
        return json.dumps({
            "ok": True,
            "action": "status",
            "name": self.name,
            "session": self.session_id,
            "pid": self.child_pid,
            "running": self.running,
            "socket": self.socket_path,
            "mesh_connected": self.mesh_connected,
            "pending_messages": len(self.message_queue)
        })

    def _do_send_message(self, cmd: dict) -> str:
        """Send message to another agent via mesh."""
        to_agent = cmd.get("to")
        content = cmd.get("content") or cmd.get("text")

        if not to_agent or not content:
            return json.dumps({"error": "need 'to' and 'content'"})

        result = self.mesh_send(to_agent, content)
        return json.dumps(result or {"ok": True, "action": "send"})

    def _do_inject(self, cmd: dict) -> str:
        """Inject text into message queue (will be sent with next user input)."""
        text = cmd.get("text") or cmd.get("content")
        if not text:
            return json.dumps({"error": "need 'text'"})

        self.message_queue.append(text)
        self._emit("injected", {"length": len(text)})
        return json.dumps({"ok": True, "action": "inject", "queued": len(self.message_queue)})

    # === TELEMETRY ===

    def _emit(self, event: str, data: dict):
        """Emit telemetry event (for now, just stderr)."""
        msg = json.dumps({"event": event, "ts": datetime.now().isoformat(), **data})
        sys.stderr.write(f"\033[36m[aura]\033[0m {event}\n")
        sys.stderr.flush()
        # TODO: emit to telemetry sink (file, socket, etc.)

    # === MAIN LOOP ===

    def run(self):
        """Main event loop - proxy PTY + handle control signals."""
        self.start_claude()
        self.start_control_socket()
        self.mesh_register()

        # Print info
        sys.stderr.write(f"\033[36m[aura]\033[0m Name: {self.name}\n")
        sys.stderr.write(f"\033[36m[aura]\033[0m Control: {self.socket_path}\n")
        sys.stderr.write(f"\033[36m[aura]\033[0m Mesh: {'connected' if self.mesh_connected else 'offline'}\n")
        sys.stderr.flush()

        import tty
        import termios
        old_settings = termios.tcgetattr(sys.stdin)

        input_buffer = b""  # Buffer to detect Enter key
        poll_counter = 0

        try:
            tty.setraw(sys.stdin.fileno())

            while self.running:
                # Check control socket
                self.check_control_socket()

                # Poll mesh for messages (every ~10 iterations = ~1 second)
                poll_counter += 1
                if poll_counter >= 10:
                    poll_counter = 0
                    self.mesh_poll_messages()
                    self.mesh_heartbeat("idle" if not input_buffer else "busy")

                if not self.master_fd:
                    break

                # Wait for I/O
                rlist, _, _ = select.select([sys.stdin, self.master_fd], [], [], 0.1)

                for fd in rlist:
                    if fd == sys.stdin:
                        # User input
                        data = os.read(sys.stdin.fileno(), 1024)
                        if not data:
                            self.running = False
                            break

                        # Check for Enter key - inject queued messages
                        if b'\r' in data or b'\n' in data:
                            if self.message_queue:
                                # Inject messages before user's input
                                for msg in self.message_queue:
                                    os.write(self.master_fd, msg.encode('utf-8'))
                                    os.write(self.master_fd, b'\n')
                                self.message_queue = []
                                self._emit("messages_injected", {})

                        os.write(self.master_fd, data)
                        input_buffer = b""  # Reset on send

                    elif fd == self.master_fd:
                        # Claude output → User
                        try:
                            data = os.read(self.master_fd, 1024)
                            if data:
                                os.write(sys.stdout.fileno(), data)
                            else:
                                self.running = False
                        except OSError:
                            self.running = False

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            self.mesh_unregister()
            self.stop_claude()
            if self.control_socket:
                self.control_socket.close()
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="aura - Claude Code wrapper with control handles")
    parser.add_argument("-r", "--resume", metavar="SESSION", help="Resume session")
    parser.add_argument("-n", "--name", metavar="NAME", help="Agent name for mesh")
    parser.add_argument("--socket", metavar="PATH", help="Control socket path")
    parser.add_argument("--dangerously-skip-permissions", action="store_true", default=True)
    args, extra = parser.parse_known_args()

    claude_args = extra
    if args.resume:
        claude_args = ["-r", args.resume] + claude_args
    if args.dangerously_skip_permissions:
        if "--dangerously-skip-permissions" not in claude_args:
            claude_args.append("--dangerously-skip-permissions")

    wrapper = Aura(claude_args, args.socket, args.name)
    wrapper.run()


if __name__ == "__main__":
    main()
