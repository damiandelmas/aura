"""Mesh socket client for agent communication."""

import os
import socket
import json
import subprocess
import time

MESH_SOCKET = "/tmp/aura/mesh.sock"
MESH_DAEMON = "/home/axp/projects/aura/main/mesh/mesh.py"


def ensure_running():
    """Start mesh daemon if not running.

    Returns:
        True if mesh is now running
    """
    # Check if already running
    result = discover()
    if not result.get("error"):
        return True

    # Check if process exists
    try:
        output = subprocess.check_output(["pgrep", "-f", "mesh/mesh.py"], stderr=subprocess.DEVNULL)
        if output.strip():
            # Process exists but socket not ready, wait a bit
            time.sleep(0.5)
            return not discover().get("error")
    except subprocess.CalledProcessError:
        pass

    # Start daemon
    subprocess.Popen(
        ["python3", MESH_DAEMON],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    time.sleep(0.5)
    return not discover().get("error")


def request(cmd: dict) -> dict:
    """Send command to mesh, return response.

    Args:
        cmd: Command dict to send

    Returns:
        Response dict from mesh, or error dict if failed
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(MESH_SOCKET)
        sock.send(json.dumps(cmd).encode())
        # Drain until mesh closes; single recv(8192) silently truncated large
        # responses (receive-with-big-DMs). 260416 bug.
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
        response = b"".join(chunks).decode()
        return json.loads(response)
    except FileNotFoundError:
        return {"error": "mesh not running", "hint": "start mesh daemon first"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if sock:
            sock.close()


def discover():
    """List all registered agents.

    Returns:
        Dict with 'ok' and 'agents' keys, or error dict
    """
    return request({"action": "discover"})


def send_message(target, message, sender="cli", mode=None):
    """Send message to agent.

    Args:
        target: Target agent name
        message: Message content
        sender: Sender name (default: "cli")
        mode: Optional delivery mode

    Returns:
        Response dict from mesh
    """
    cmd = {"action": "send", "from": sender, "to": target, "content": message}
    if mode:
        cmd["delivery_mode"] = mode
    return request(cmd)


def unregister(name):
    """Unregister agent from mesh.

    Args:
        name: Agent name to unregister

    Returns:
        Response dict from mesh
    """
    return request({"action": "unregister", "name": name})


def set_mode(name, mode):
    """Set agent delivery mode.

    Args:
        name: Agent name
        mode: Delivery mode to set

    Returns:
        Response dict from mesh
    """
    return request({"action": "set_mode", "name": name, "mode": mode})


def agent_registered(name):
    """Check if agent is registered.

    Args:
        name: Agent name to check

    Returns:
        True if agent is registered in mesh
    """
    result = discover()
    if result.get("ok") and result.get("agents"):
        return any(a.get("name") == name for a in result["agents"])
    return False
