# Mesh Runbook

## Overview

This runbook provides operational procedures for working with the mesh agent communication system. Use it when you need to start/stop the mesh, send messages between agents, troubleshoot connectivity issues, or implement programmatic mesh access. The mesh daemon must be running before any agents can register or communicate. All operations go through either the `mesh-ctl` CLI tool or direct socket communication using the JSON protocol. The mesh is ephemeral—restarting it clears all registered agents and pending messages, which is intentional for simplicity but means agents must re-register after mesh restart. When debugging multi-agent workflows, always check `mesh-ctl discover` first to verify which agents are actually connected.

## Quick Reference

These are the paths and commands you'll use most frequently. The socket path is hardcoded in both the daemon and CLI, so they must match.

```bash
# Paths
MESH_DIR=/home/axp/projects/fleet/hangar/code/aura/mesh
MESH_SOCKET=/tmp/aura/mesh.sock
MESH_CTL=$MESH_DIR/mesh-ctl

# Check status
$MESH_CTL status

# Start daemon (if offline)
$MESH_DIR/mesh.py &

# Stop daemon
pkill -f "mesh.py"
```

## Operations

### Start Mesh

The daemon runs in the foreground by default, so background it with `&`. It creates the socket file on startup and removes it on clean shutdown. If a stale socket exists from a crash, the daemon will overwrite it.

```bash
/home/axp/projects/fleet/hangar/code/aura/mesh/mesh.py &
# Verify: mesh-ctl status → "Mesh: online"
```

### List Agents

Discover shows all currently registered agents with their truncated session ID and status. Use this to verify agents are connected before attempting to message them.

```bash
mesh-ctl discover
# Output: Name, Session (8 chars), Status, Last Seen
```

### Send Direct Message

Direct messages go to a single named agent. The message queues until that agent polls. If the target doesn't exist, you get an error immediately.

```bash
mesh-ctl send <target> "<message>"
mesh-ctl send oracle "check the auth module"
```

### Broadcast All Agents

Broadcast sends to every registered agent except the sender. Useful for sync points or announcements. Each recipient gets the same message in their queue.

```bash
mesh-ctl broadcast "<message>"
mesh-ctl broadcast "sync point reached"
```

### Start Conversation

Conversations are bounded exchanges with turn tracking. The mesh auto-marks them complete when max_turns is reached. This provides structure for back-and-forth discussions without runaway loops.

```bash
mesh-ctl converse <target> "<topic>" [max_turns]
mesh-ctl converse worker "discuss caching strategy" 5
# Returns conversation_id, sends opening message
```

## Programmatic Access

When building tools or integrations that need mesh access, use direct socket communication. This is the same protocol the CLI uses. The pattern is: connect, send JSON, receive JSON, close.

```python
import socket, json

def mesh_cmd(cmd: dict) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("/tmp/aura/mesh.sock")
    sock.send(json.dumps(cmd).encode())
    resp = json.loads(sock.recv(8192).decode())
    sock.close()
    return resp

# Register
mesh_cmd({"action": "register", "name": "myagent", "session_id": "abc", "socket_path": "/tmp/aura/myagent.sock"})

# Send
mesh_cmd({"action": "send", "from": "myagent", "to": "oracle", "content": "hello"})

# Receive
mesh_cmd({"action": "receive", "name": "myagent"})

# Heartbeat
mesh_cmd({"action": "heartbeat", "name": "myagent", "status": "busy"})
```

## Troubleshooting

Common issues and their resolutions. Most problems stem from either the daemon not running or agents not being registered.

| Symptom | Cause | Fix |
|---------|-------|-----|
| "mesh not running" | Daemon not started | `mesh.py &` |
| "agent not found" | Target not registered | Check `mesh-ctl discover` |
| Empty receive | No pending messages | Normal - queue was empty |
| Stale agents in discover | Agent crashed without unregister | Restart mesh clears state |

## State Reset

Since mesh is purely in-memory, resetting state just means restarting the daemon. This is useful when agents get into a bad state or you want a clean slate. All agents will need to re-register.

```bash
pkill -f "mesh.py"
rm -f /tmp/aura/mesh.sock
# Restart: mesh.py &
```

## Patterns

These are proven patterns for multi-agent coordination using mesh.

### Oracle/Worker Split

One agent plans and delegates, others execute. The oracle sends specific tasks to named workers and can collect results via return messages.

```bash
# Oracle agent handles planning
# Worker agents handle execution
mesh-ctl send worker1 "implement auth module"
mesh-ctl send worker2 "write tests for auth"
```

### Sync Point

All agents pause at named checkpoints. Broadcast a named sync message and agents check for it before proceeding. Useful for phased workflows.

```bash
# All agents pause at named points
mesh-ctl broadcast "SYNC:phase1-complete"
```

### Bounded Discussion

When two agents need to discuss something without spiraling, use conversations with a turn limit. The mesh enforces the bound automatically.

```bash
# 5-turn max conversation
mesh-ctl converse oracle "review my approach" 5
```

## Integration Notes

Understanding how messages appear to receiving agents is critical for crafting useful message content.

- Messages arrive as `<system-reminder>` blocks
- Format: "Message from @{sender}: {content}"
- Injection happens on next user input (aura polls before prompt)
- No push notifications - polling only
