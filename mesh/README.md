# Mesh - Agent Communication Network

Real-time communication mesh for Claude Code instances.

## Quick Start

```bash
# Terminal 1: Start mesh daemon
./mesh.py

# Terminal 2: Start agent "main"
cd ../wrapper && ./aura.py --name main

# Terminal 3: Start agent "oracle"
cd ../wrapper && ./aura.py --name oracle

# Terminal 4: Send messages
./mesh-ctl discover              # See both agents
./mesh-ctl send oracle "what's your status?"
./mesh-ctl broadcast "sync point reached"
```

## Architecture

```
                    ┌─────────────┐
                    │    Mesh     │  ← coordinator
                    │   daemon    │
                    └──────┬──────┘
                           │
         ┌────────┬────────┼────────┬────────┐
         │        │        │        │        │
      ┌──▼──┐  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐
      │main │  │oracl│  │work │  │write│  │...  │
      │aura │  │aura │  │aura │  │aura │  │aura │
      └─────┘  └─────┘  └─────┘  └─────┘  └─────┘
```

## Protocol

| Action | Description |
|--------|-------------|
| `register` | Agent joins mesh |
| `unregister` | Agent leaves mesh |
| `heartbeat` | Update status (idle/busy) |
| `discover` | List all agents |
| `send` | Message one agent |
| `broadcast` | Message all agents |
| `start_conversation` | Begin tracked exchange |

## Message Flow

1. Agent A calls `mesh.send(to="B", content="hello")`
2. Mesh queues message for B
3. B's aura polls mesh, receives message
4. Message injected as `<system-reminder>` with next user input
5. B (Claude) sees: "Message from @A: hello"

## Conversations

Tracked, bounded exchanges:

```bash
# Start conversation with max 5 turns
mesh-ctl converse oracle "discuss auth refactor" 5

# Mesh tracks:
# - participants
# - turn count
# - all messages
# - completion status
```

## CLI Reference

```bash
mesh-ctl discover                    # List agents
mesh-ctl status                      # Mesh status
mesh-ctl send <agent> "<message>"    # Direct message
mesh-ctl broadcast "<message>"       # All agents
mesh-ctl converse <agent> "<topic>" [max_turns]
```

## Integration with Aura

Aura auto-connects to mesh if running:

```bash
# Aura startup shows:
[aura] Name: oracle
[aura] Control: /tmp/aura/abc123.sock
[aura] Mesh: connected

# Messages injected on next Enter press
```
