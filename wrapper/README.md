# Aura - Claude Code Control Envelope

Thin PTY wrapper that adds external control handles to Claude Code.

## What It Does

```
External Process                    Aura                         Claude
(AUI, scripts, agents)    →    (control envelope)    →    (actual work)
       │                              │
       │ socket commands              │ PTY passthrough
       └──────────────────────────────┘
```

Aura provides **traction** - hooks for external systems to:
- Trigger refresh (update JSONL, restart)
- Fork sessions (spawn brothers)
- Get status/telemetry
- Lifecycle control (stop, restart)

## Quick Start

```bash
# Terminal 1: Start wrapped Claude
./aura.py
# Shows: [aura] Control: /tmp/aura/new-12345.sock

# Terminal 2: Send commands
./aura-ctl status
./aura-ctl refresh
./aura-ctl fork --name oracle --at 150
./aura-ctl stop
```

## Control Interface

Unix socket at `/tmp/aura/<session>.sock`

| Command | Action |
|---------|--------|
| `{"action": "status"}` | Return session info |
| `{"action": "refresh"}` | Stop → refresh JSONL → restart |
| `{"action": "restart"}` | Stop → restart |
| `{"action": "fork", "name": "x", "at": 150}` | Spawn brother |
| `{"action": "stop"}` | Stop Claude |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ AUI (Interface)                                         │
└─────────────────────┬───────────────────────────────────┘
                      │ calls
┌─────────────────────▼───────────────────────────────────┐
│ Memory (Operations)                                     │
│   recall(), edit(), inherit()                           │
└─────────────────────┬───────────────────────────────────┘
                      │ used by
┌─────────────────────▼───────────────────────────────────┐
│ Orca (Runtime)                                          │
│   ┌───────────────────────────────────────────────────┐ │
│   │ Aura (Envelope)  ← control socket                 │ │
│   │   └── Claude (PTY)                                │ │
│   └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Aura is thin.** It delegates:
- Refresh logic → `memory.edit.conversation.refresh`
- Fork/spawn → `orca.spawn` + `memory.inherit`

## Files

```
aura/wrapper/
├── aura.py      # PTY wrapper with control socket
├── aura-ctl     # CLI to send commands
└── README.md
```

## With tmux (brothers)

```bash
# Spawn brother through aura
tmux send-keys -t orca:worker "aura.py -r $SESSION" Enter

# Control from outside
aura-ctl --socket /tmp/aura/$SESSION.sock refresh
```

## Telemetry

Events emitted to stderr (TODO: configurable sink):
- `started`, `stopped`, `restarted`
- `refresh_start`, `refresh_done`
- `fork_start`, `fork_done`
- `socket_ready`
