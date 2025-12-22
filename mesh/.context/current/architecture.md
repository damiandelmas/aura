# Mesh Architecture

## Overview

Mesh is a communication coordinator that enables multiple Claude Code instances to discover each other and exchange messages in real-time. It solves the fundamental problem of agent isolation: without mesh, each Claude session is a silo with no awareness of sibling agents working on related tasks. The system uses a central daemon model where all agents connect to a single Unix socket, which acts as a message broker and registry. This design was chosen over peer-to-peer because it simplifies discovery and guarantees message ordering. Mesh is intentionally stateless across restarts—it's a runtime coordination layer, not a persistence system. The polling model (agents pull messages) rather than push was chosen because Claude Code's hook system naturally supports pre-prompt injection but not async interrupts.

## Shape

The topology is hub-and-spoke with the mesh daemon as the central coordinator. All agents connect to the same Unix socket and the daemon maintains in-memory registries for agents, messages, and conversations. This centralization makes discovery trivial and routing simple at the cost of a single point of failure.

```
                         UNIX SOCKET
                              │
                    ┌─────────▼─────────┐
                    │       MESH        │
                    │      DAEMON       │
                    │                   │
                    │  agents: {}       │  ← name → Agent
                    │  messages: {}     │  ← id → Message
                    │  queues: {}       │  ← name → [msg_ids]
                    │  conversations: {}│  ← id → Conversation
                    └─────────┬─────────┘
                              │
         ┌──────────┬─────────┼─────────┬──────────┐
         │          │         │         │          │
      ┌──▼──┐   ┌───▼──┐  ┌───▼──┐  ┌───▼──┐   ┌───▼──┐
      │aura │   │aura  │  │aura  │  │ CLI  │   │ ...  │
      │main │   │oracle│  │worker│  │      │   │      │
      └─────┘   └──────┘  └──────┘  └──────┘   └──────┘
```

## Data Model

Three core entities track the mesh state. Agents are the participants, Messages are the payload, and Conversations provide optional structure for bounded exchanges. The separation allows simple fire-and-forget messaging while also supporting coordinated multi-turn dialogues.

```
Agent {
  name: str           # unique identifier, e.g. "oracle"
  session_id: str     # claude session uuid
  socket_path: str    # agent's control socket
  status: idle|busy|waiting
  last_seen: timestamp
}

Message {
  id: str             # "msg-{n}-{HHMMSS}"
  from_agent: str
  to_agent: str       # or "all" for broadcast
  content: str
  conversation_id: str?
  delivered: bool
}

Conversation {
  id: str             # "conv-{n}-{HHMMSS}"
  participants: [str]
  topic: str
  max_turns: int
  current_turn: int
  messages: [msg_id]
  status: active|complete|timeout
}
```

## Message Flow

Messages flow through a queue-based delivery system. The sender's message is stored and the recipient's queue gets the message ID appended. Recipients poll to retrieve messages, at which point the queue clears. This pull model integrates cleanly with aura's pre-prompt hook which injects messages as system reminders.

1. Sender calls `mesh.send(to="B", content="...")`
2. Mesh creates Message, appends id to `queues[B]`
3. Recipient's aura polls `mesh.receive(name="B")`
4. Messages returned, queue cleared
5. Aura injects as `<system-reminder>` on next user input
6. Claude sees: "Message from @A: ..."

## Protocol

The protocol is a simple JSON-over-socket RPC. Each action maps to a method on the Mesh class. All responses include an `ok` field on success or `error` field on failure.

| Action | Params | Returns |
|--------|--------|---------|
| `register` | name, session_id, socket_path | `{ok, name}` |
| `unregister` | name | `{ok}` |
| `heartbeat` | name, status? | `{ok}` |
| `discover` | - | `{agents: [...]}` |
| `send` | from, to, content, conversation_id? | `{message_id}` |
| `receive` | name | `{messages: [...]}` |
| `start_conversation` | initiator, target, topic, max_turns? | `{conversation_id}` |
| `get_conversation` | conversation_id | `{conversation, messages}` |

## Files

The implementation is minimal: one daemon file and one CLI tool. The daemon handles all coordination logic while the CLI provides human/script access to the same protocol.

```
mesh/
├── mesh.py      # daemon - Mesh class, socket server, request handler
├── mesh-ctl     # CLI - discover, send, broadcast, converse, status
└── README.md    # usage examples
```

## Integration Point

Aura (the Claude Code wrapper) is the primary integration target. When aura starts, it registers with mesh if available. The pre-prompt hook polls for messages and injects them. This means message delivery is tied to user interaction cadence—messages arrive when the user presses Enter.

- On startup: `register(name, session_id, socket_path)`
- Periodic: `heartbeat(name, status)`
- Before prompt: `receive(name)` → inject messages
- On exit: `unregister(name)`

## Invariants

These rules are enforced by the implementation and should be assumed true when reasoning about mesh behavior.

- Agent names unique across mesh
- Messages queue until polled (no push)
- Conversations auto-complete at max_turns
- Broadcast excludes sender
- Queue clears on receive (no re-delivery)

## Boundaries

Understanding what mesh doesn't do is critical for knowing when to look elsewhere. Mesh is purely runtime coordination—no durability, no security, no agent management.

**Mesh handles:** routing, queuing, presence, conversation tracking

**Mesh does NOT handle:** message persistence, authentication, retry logic, agent lifecycle management
