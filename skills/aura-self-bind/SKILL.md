---
name: aura-self-bind
description: "Bind the current runtime process to its Aura fleet and seat when launch metadata is present."
---

# Aura Self Bind

Aura runs agents as live seats (`fleet:seat`); binding ties a seat to its
runtime's native session — the thread that makes it resumable. Binding is
automatic: the SessionStart hook ties the session to the seat the moment it
launches, so `aura view self` shows a real `runtime_session_id`. You rarely
need this skill. Reach for it only when `aura view self` shows this seat
**unbound**: a process that started OUTSIDE any Aura launch path (no birth
env at all) — which the self-heal sweep cannot recover because it has no
birth env to reconcile from — or one whose hook did not fire. (Restart and
rollover now born-bind, and the 60s reconcile-then-heal sweep auto-recovers
drift, so those cases close at the source.)

## Invariants

```text
seat ≠ visible pane ≠ registry row ≠ runtime session
binding ties this seat's row to its own native runtime session id
only a bound session is resumable; the session is the continuity anchor
bind from exact self-evidence (codex: CODEX_THREAD_ID; claude-code: the
  statusline-written pane→session map), never from a guessed address
`bound` is never a phantom — a row claiming bound with no session id is
  downgraded to unbound on every read/write — so `aura view self` showing
  `bound` means a real, resolvable session
```

## Bind this seat

```bash
rt="${AURA_RUNTIME:-claude-code}"            # claude-code (default) | codex
aura sessions self --runtime "$rt"           # what session id does this process see?
target="${AURA_FLEET}:${AURA_SEAT:-$AURA_AGENT_NAME}"
aura sessions bind-current --runtime "$rt" --target "$target"
aura sessions latest                         # confirm a real runtime_session_id replaced pending
```

`sessions self` reads exact self-evidence — `CODEX_THREAD_ID` for codex, the statusline-written pane→session map for claude-code (env-less, branch- and adopt-safe). `bind-current` writes that id onto the current seat and is safe to rerun. `sessions latest` verifies it landed.

## When this isn't enough

- Bind **this** seat only. Binding another seat is operator work → `aura-operator`.
- Self-evidence absent (codex: `CODEX_THREAD_ID` empty; claude-code: no statusline map for this pane) or launch metadata missing → `aura-operator` (`sessions bind-nonce`, `bind-pane`, `heal`); do not invent an address.
- The model behind this — the single bind writer, the body veto, and the repair ladder — lives in Aura's current context docs (`flows/continuity.md`).
