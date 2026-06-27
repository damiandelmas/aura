# Workflow: Lite Crew

The lightest managed-crew shape — one lead, a few seats, one bounded outcome, managed within one active session.

Use this skill when one lead is managing several live Aura seats for one bounded outcome. Keep the machinery light: create clear assignments, launch or message seats, inspect progress, collect receipts, verify results, and close the run.

Aura crew work is live control-plane coordination. The source of truth for the actual product remains the project files, tests, receipts, and changelogs created by the workers.

## Operating Shape

```text
state goal
  -> name seats and ownership
  -> spawn or message seats
  -> inspect reports and captures
  -> integrate receipts
  -> verify the claim
  -> park or cut seats when done
```

## Use When

Use for:

- parallel read-only audits
- implementation plus independent verification
- multi-seat evidence gathering
- short sprint coordination across clear file scopes
- reducing several worker receipts into one final answer

Do not use when a single direct action is enough.

## Lead Contract

Before creating seats, define:

```text
objective
acceptance evidence
seat list and ownership
allowed write scope per seat
report expectation
stop gate
```

Keep assignments short. Prefer absolute paths and specific commands over broad history dumps.

## Seat Assignment Template

```text
Objective: ...
Scope: ...
Do not touch: ...
Evidence required: ...
Report format: status, changed files, verification, blockers
Stop when: ...
```

## Common Commands

Spawn a worker:

```bash
aura spawn NAME --fleet FLEET --runtime codex --cwd /path/to/project --prompt "Objective..." --as-pane --wait
```

Send an immediate instruction:

```bash
aura send FLEET:NAME "Message"
```

Queue a non-interruptive instruction:

```bash
aura queue FLEET:NAME "After your next report, do ..."
```

Inspect a seat:

```bash
aura inspect FLEET:NAME --lines 80
```

View the fleet:

```bash
aura view fleet FLEET
```

Collect recent reports:

```bash
aura report list --fleet FLEET --limit 30
```

## Lead Loop

1. Keep a compact run note in the project or context area if the run spans more than one turn.
2. Prefer queued messages when a worker is already busy.
3. Use immediate sends only for launch, unblock, correction, or intentional interruption.
4. Verify receipts before integrating them.
5. Park idle seats or cut finished disposable seats.
6. Final output names evidence, known gaps, and seat disposition.

## Completion Gate

A crew run is complete only when:

- every active assignment has a receipt, blocker, or deliberate cut decision
- the lead verified the integrated claim
- changed files or evidence paths are named
- unfinished seats have an explicit next action or are parked/cut
- the closeout names attach commands for newly spawned/restored fleets when useful
- state-only handoffs are labeled as state-only and do not assign new work unless the operator requested it
