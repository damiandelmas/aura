"""Mesh socket client for agent communication."""

import socket
import json

MESH_SOCKET = "/tmp/aura/mesh.sock"


def request(cmd: dict) -> dict:
    """Send command to mesh, return response.

    Args:
        cmd: Command dict to send

    Returns:
        Response dict from mesh, or error dict if failed
    """
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(MESH_SOCKET)
        sock.send(json.dumps(cmd).encode())
        response = sock.recv(8192).decode()
        sock.close()
        return json.loads(response)
    except FileNotFoundError:
        return {"error": "mesh not running", "hint": "start mesh daemon first"}
    except Exception as e:
        return {"error": str(e)}


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
