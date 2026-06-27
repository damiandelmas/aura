---
name: aura-operator
description: "Operator surface for Aura's control plane: lifecycle, repair, packages, sessions, hygiene. One op per job; the system fails closed."
---

# Aura Operator

Aura is the control plane for live agent runtimes: agents run as named seats
(`fleet:seat`) in tmux, with a registry of what's live and durable package
bodies that outlast any process. You are operating that control plane itself —
not asking a worker to do a task. Most operator jobs are **one command**: the
system validates and fails closed, so run the op and read the refusal if one
comes back. The refusal reason tells you what's actually wrong; don't build
pre-flight rituals around commands that already guard themselves.

## The Model

```text
runtime   = one live mind in a terminal (codex, claude-code, hermes, gajae-code, shell)
seat      = that mind at a name on the roster: fleet:seat
fleet     = a live group of seats; maps to a tmux session, carries a durable fleet_id
package   = the durable body at ~/.aura/agents/i_<id>/ — manifest.json (the spawn/
            resume recipe) + the runtime's own state (.codex/) + memories/.
            a clean pre-spawn body is manifest.json ONLY.
session   = the runtime's native conversation (a session UUID). THE continuity
            anchor: survives rename, restart, fleet moves. only `bound` is resumable.
registry  = ~/.aura/registry/ — seats, fleets, placements, aliases, ledgers.
            control-plane truth, never runtime memory.
society   = a named, resolvable container above fleets (members + config +
            resolves_to), stored at ~/.aura/societies/registry.json — separate
            from ~/.aura/registry/. society container verbs → aura-society.
```

Two laws govern everything:

```text
READ   live = a real tmux pane joined to a registry row. liveness is COMPUTED from
       tmux on every read — a row alone is HISTORICAL inventory, never a live seat.
       there is no "stale" state: LIVE | HISTORICAL.
WRITE  operations key off the exact pane id %N (or exact name + fleet assertion).
       fail closed on staleness; never a fuzzy-name fallback. a dead %N means the
       seat is already historical — no-op, not a name-guess.
```

And the identity rules that follow:

```text
aliases are HISTORICAL lineage only — live resolution never reads them; a reused
  name can never hijack a live occupant. continuity is keyed to the occupant
  (seat_instance_id / pane), not the name.
every session bind flows through one gated writer with a body-integrity veto —
  a session never binds onto a contaminated or wrong body.
clone ≠ create: clone copies the source's memories + identity + bindings.
  a new role is `agent create`.
NEVER delete .codex/sessions/**/*.jsonl — native resume needs the transcript body.
attempted ≠ accepted — a delivered message proves mechanics, not work.
```

## The Ops

```bash
# lifecycle
aura seat restart FLEET:SEAT                      # new process, keep session
aura seat rollover FLEET:SEAT --reason "..."      # new process, fresh session (explicit, not repair)
aura seat cut FLEET:SEAT                          # retire a live seat
aura seat rename FLEET:OLD NEW                    # relabel, same fleet, exact pane
aura fleets rename OLD NEW --confirm              # relabel a whole fleet, keeps fleet_id
aura seat adopt --pane tmux:F:%N --as F:S --runtime codex   # promote an unmanaged pane

# packages (durable bodies)
aura agent create ADDRESS --runtime codex ...     # new clean body (NOT clone)
aura agent spawn REF --resume-session latest --as-pane --wait   # make a body live again
aura agent inspect REF                            # one body's manifest + state
aura agent census                                 # audit all bodies before acting
aura agent archive REF                            # retire a body, lineage preserved

# sessions (continuity repair, in escalation order)
aura sessions self / bind-current                 # from inside the seat itself
aura sessions resolve-pane --pane tmux:F:%N       # read-only: pane -> session evidence
aura sessions bind-pane --pane tmux:F:%N          # bind from exact pane evidence
aura sessions heal --target FLEET:SEAT            # re-bind from exact evidence; never guesses
aura sessions reconcile-orphans --fleet FLEET     # reconstruct rows for Aura-born panes
aura sessions restore-plan --live                 # advisory command set after an interruption

# hygiene
aura seat gc --ttl 7 --confirm                    # archive cruft rows (keeps resumable lineage)
aura seat sync-windows [--fleet F]                # re-assert window labels from seat names
aura seat alias ls / rm SOURCE --confirm          # the historical alias ledger

# diagnostics + capability
aura capture FLEET:SEAT --lines 120               # raw terminal text, verbatim
aura profile list / inspect REF                   # launch capability templates

# raw terminal (last resort: a stuck TUI, a trust prompt)
aura write FLEET:SEAT "" --keys C-c

# work pool (thin claim-queue; Aura holds NO work-truth — this just flows work to free seats)
aura work submit QUEUE "task body"                # enqueue one task
aura work dispatch-start QUEUE --placement POOL    # drain to idle members (or --fleet POOL)
aura idle-watch start --placement POOL --every 6   # sense which members are free
#   idle = released, NOT done: a freed seat is available again, never proof of success

# edge (external in) — a service, not an aura verb
python3 services/aura_ingress.py    # HTTP in-jack: external POST -> send/broadcast/work submit.
                                    # run under systemd; secrets in ~/.aura/ingress/. See aura-event in-jack.
```

Cross-fleet move is not a rename: spawn the role in the target fleet, verify,
then cut the old seat. The session UUID carries the continuity.

## When It Refuses

That's the system working. Read the reason, fix the named cause, rerun the op:

```text
body-gate-refused        the session doesn't belong to that body — wrong/contaminated
                         target; find the right body (agent census) or pane evidence
target-registry-exists   a rename would collide with a DIFFERENT live pane — both are
                         real; pick another name or cut one deliberately
no-exact-evidence        heal/bind has nothing exact to bind from — needs the nonce or
                         pane evidence; operator assertion (bind-current) is the override
native-subagent-refused  aura spawn from inside a runtime's native child — use the
                         runtime's own delegation, or spawn from a real seat
dead %N / missing pane   the seat is already HISTORICAL — restore or re-up, don't repair
```

## Recovery

The only genuinely multi-step cases. Classify first:

```text
missing_pane     tmux target gone            -> restore/re-up (spawn --resume-session)
dead_process     pane alive, process gone    -> seat restart
input_blocked    tmux flow-control/copy-mode -> unfreeze the CLIENT (stty -ixon on its
                                                tty; refresh-client), not the seat
runtime_wedged   pane+process alive, TUI     -> capture evidence, non-destructive
                 stuck                          interrupt (C-c), resume the bound
                                                session id, verify binding
daemon_dead      an aura event daemon (heal-sweep, dispatcher, watcher) died ->
                 it has no self-supervisor. systemd --user restarts it
                 (aura-event-supervisor.timer -> `aura event ensure-daemons`).
                 `event status` computes daemon liveness from the pid, so a
                 corpse reads dead, not "running".
```

The self-heal sweep (`heal-sweep`, a `no_agent` event) runs **reconcile-then-heal**
every tick: `reconcile-orphans --all` rebuilds rows for live Aura-born panes whose
row was dropped (a crash) — `heal` alone is blind to a pane with no row — then
`heal --all` rebinds them. An orphan self-recovers within a tick; supervise the
daemon itself (above) or the self-healer can die and stay dead.

`aura sessions heal --all` now also recovers PHANTOM-bound seats (a row marked
`bound` with no session id — now impossible to persist by the registry invariant,
the gated writer downgrades it to unbound on read) and adopts a live pane's newer
`seat_instance_id` onto the row when birth-env `fleet:seat` matches (a foreign
pane is still refused — safety, not a bug). Diagnostic order for a drifted
binding: it's probably already healing (the 60s reconcile-then-heal sweep) →
manual `sessions heal --all` → a pane with no birth env needs a one-time
`seat adopt` (the sweep is blind to it).

After a host/tmux interruption: `sessions restore-plan --live` emits the
resume commands — package-backed rows resume via `agent spawn`, plain rows via
`spawn --resume-session`. Reconnect seats to their sessions; never fresh-spawn
over a live session. Never delete runtime homes, package roots, or session
JSONL as first aid — a frozen client is not a dead server, and a quiet pane is
not lost work.

## Boundary

Routine work belongs to routine verbs: a new worker → `aura-spawn`, a message
→ `aura-send`, topology → `aura-view`. You are here only when managing the
floor itself.
