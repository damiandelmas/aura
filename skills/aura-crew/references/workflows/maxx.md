# Workflow: Maxx Crew

The serious managed-crew shape — board, worker packets, reports, optional events, verification, closeout. For crews that run long, span turns, or carry real integration risk.

The maxx workflow is the lead/conductor pattern for running several persistent Aura agents toward one assignment or workstream. It does not replace Aura's lower-level verbs; it explains how to combine spawn, queue/send, reports, optional events, verification, and closeout into one managed loop. The core discipline is file-backed work: create a board, give each worker an `onboard.md` and `work.md`, monitor reports, verify receipts, and only then integrate. During orchestration, prefer non-interruptive queued messages unless the target is idle, blocked, or explicitly waiting; use immediate send only when interruption is intended.

Keep three planes separate:

- decision plane: priorities, gates, acceptance, and escalation
- floor plane: roster health, reports, events, queues, receipts, and board state
- work plane: live agents producing receipts

Small crews may collapse these planes into one lead. Long-running or noisy crews should not.

Complementary skills:

- `aura-queue`: deliver non-interruptive instructions at the worker's next report boundary.
- `aura-send`: deliver immediate launch packets, unblockers, or intentional interrupts.
- `aura-event`: create report subscriptions or wakeup cadences.
- `aura-report`: write worker check-ins.
- `aura-view`: see current topology.
- `aura-inspect`: inspect one known seat.
- `aura-spawn`: create ordinary live persistent agents.
- `aura-operator`: package/resume/fork, seat lifecycle, repair, session binding, runtime-profile, and closeout guidance.

## Use When

Use this skill when one lead is managing multiple live agents, especially for parallel audits, provider proof batches, implementation plus independent verification, or integration/reduction after agent outputs. Do not use it for a single handoff, a broad broadcast, or seat repair. If the request is about registry cleanup, terminal recovery, rehoming, adoption, or stuck runtime surgery, route to `aura-operator` and stop treating it as routine crew work.

Good crew work has clear seams: each agent has a mission, an input boundary, a write scope, receipts, and a report contract. Avoid spawning workers with only a general context dump. Avoid counting wakeups, subscriptions, or heartbeat jobs as workers; they are control machinery.

## Two Crew Paths

Use the lightest path that preserves the work.

### Manual Managed Crew

Use this path by default for short or high-context crews.

```text
lead writes board and packets
  -> lead sends or queues assignments
  -> workers report
  -> lead manually reads reports
  -> lead verifies receipts
  -> lead sends next packet
  -> lead records closeout
```

Strengths:

- fewer moving parts
- quieter panes
- simpler failure surface
- good for crews that can be managed within one active session

Weakness:

- can stall when the lead goes away
- requires manual polling or user return
- weaker liveness guarantees

### Event-Backed Managed Crew

Use this path when the crew must survive across turns, run for hours, or continue while the lead is not actively watching.

```text
manual managed crew foundation
  + report subscriptions when push delivery is useful
  + wakeups when file-backed continuation is required
  + continue contract naming safe next actions and stop gates
  + floor coordinator when event noise would overload the decision lead
```

Strengths:

- better liveness
- resumable from files
- can continue without user nudges
- catches blocked or complete reports sooner

Weakness:

- more moving parts
- subscriptions can duplicate or self-echo if configured poorly
- wakeups can become noise when the work is parked
- the lead can become an event clerk without a floor role

Events and subscriptions are an overlay on the manual crew loop, not a replacement for board, packets, reports, receipts, and lead reduction.

## Coordinator Posture

A crew coordinator should orient just enough to route work, then delegate bounded lanes instead of personally executing every analysis. Read the minimum context needed to identify lanes, dependencies, blockers, and the right worker packets; do not spend the first turn grinding through all project data unless the manager itself is the assigned analyst. The coordinator owns decomposition, sequencing, receipt review, blocker routing, and integration decisions. In a longer run, delegate floor work separately: report reduction, tick/subscription health, stale-seat checks, board upkeep, and receipt inventory can consume the whole lead if left implicit.

```text
coordinator does:
  identify lanes
  create/refresh work packets
  queue/send assignments
  monitor reports
  verify receipts
  integrate accepted results
  keep decision gates specific

coordinator avoids:
  doing every lane's research personally
  mutating production state directly
  contacting workers before packets exist
  reading huge data surfaces without a routing purpose
  replacing specialist judgment with manager guesses
  treating event delivery as proof of task completion
```

## Crew Contract

Before spawning, create or identify a crew packet that names the goal, lead identity, fleet, workers, write scopes, required reads, expected receipts, optional subscriptions/wakeups, and close/resume policy. This packet is the control surface for the run; Aura reports are the event stream, not the plan. If a worker can mutate files, make its write scope explicit and disjoint from other mutating workers.

```text
goal
lead identity
fleet
workers
write scopes
required read lists
expected receipts
report subscription names, if used
wakeup/event names, if used
close/resume policy
human approval gates
```

## Crew Operations

Shape the crew with concrete control decisions. Create separate workers only when scopes, dependencies, or verification duties differ; block dependent workers until the required receipt exists; queue non-urgent instructions instead of interrupting active turns. Inspect reports and receipts before intervening, verify worker output before integrating it, and close or park workers intentionally at the end of the run. If a role is only needed for one bounded slice, spawn it as a temporary worker instead of growing the standing fleet.

## Standard Loop

The standard loop is manual unless the crew explicitly needs event backing. Define board, write worker packets, check topology, spawn/resume workers, verify task start, reduce reports, verify receipts, integrate, record the ledger, and cut or park workers. Add subscriptions or wakeups only when the crew needs push delivery, liveness checks, or file-backed continuation. Worker completion is evidence, not acceptance. The lead owns final verification and must not promote state only because a worker reported success.

```text
lead defines board
  -> lead writes worker packets
  -> lead checks topology
  -> lead optionally creates report subscriptions or wakeups
  -> lead spawns or resumes workers
  -> lead waits briefly and verifies task start
  -> lead sends immediate launch nudges only if needed
  -> workers report working/blocked/complete
  -> lead queues non-urgent follow-ups for report boundaries
  -> lead reduces reports and verifies receipts
  -> lead sends immediate unblockers only when needed
  -> lead integrates accepted changes
  -> lead records session/report ledger, plus event ledger if events were used
  -> lead cuts, parks, or marks workers resumable
```

## Pre-Launch Gate

Do not spawn workers until the crew contract, board, and worker packets exist. At minimum, the lead should have `situation.md`, phase files or a crew contract, `crew/<worker>/onboard.md`, and `crew/<worker>/work.md`; if these are missing, create them first. This is the Aura equivalent of state-first team launch: the filesystem describes the assignment before live seats start acting.

## Control And Evidence Planes

Aura's control plane is seats, spawn/resume, queue/send, report subscriptions, and lifecycle operations. The evidence plane is worker reports, queued-message receipts, project/factory receipt files, diffs, tests, and explicit inspections. Keep those separate: a delivered message or a live pane proves mechanics, while a receipt plus lead verification proves work.

## Board Shape

A workshop should hold active operating material, not duplicate bootstrap or compaction doctrine. Use `situation.md` for the current push, `board/` for phases and gates, `crew/` for worker packets, and `workflow/` for SOPs specific to this run. Keep identity recovery files at the identity root.

```text
workshop/{timestamp}/
  situation.md
  board/
    00-crew-contract.md
    01-worker-a.md
    02-worker-b.md
    03-integrator.md
  crew/
    worker-a/onboard.md
    worker-a/work.md
    worker-b/onboard.md
    worker-b/work.md
    README.md
  workflow/
    managed-worker-sop.md
```

## Worker Packet

Each worker should get two files: `onboard.md` for durable required reading and `work.md` for the current bounded mission. The onboard file should mostly list absolute paths to current docs, plans, changelogs, workstream docs, and proof receipts; avoid copying large prose when a stable file path exists. The work file should include role, mission, write scope, forbidden actions, commands/tests, receipts, report format, and blocker rules.

```text
onboard.md  durable read package for the worker's role/scope
work.md     current bounded mission
```

Use current project, workstream, runbook, and receipt files as the doctrine source when creating onboard/workshop material. Prefer explicit absolute paths supplied by the current task over standing historical organization paths.

`work.md` should include:

```text
role
mission
required reads
allowed write paths
forbidden paths/actions
commands/tests to run
receipts to produce
report format
blocker rules
```

If a worker can edit code, give it a disjoint write scope.

See `references/onboard-packet.md` and `references/worker-packet.md`.

## Report Subscriptions

Create report subscriptions before or immediately after spawning only when the crew needs push-based check-ins. Manual managed crews can skip subscriptions and rely on explicit report reads plus targeted `aura view` or `aura inspect`. Use `aura-event` for exact command details because the CLI surface can evolve.

Prefer a single broad subscription first. Add a blocker-focused subscription only if delivery semantics dedupe by `report_id` or the team explicitly accepts duplicate delivery risk. If the lead is inside the same fleet, avoid self-echo: reports written by the lead should be inspected through the report ledger, not delivered back into the lead's active pane. When in doubt, make the floor coordinator the subscription target instead of the decision lead.

```bash
aura event subscribe reports \
  --name <crew>-checkins \
  --fleet <fleet> \
  --to <fleet>:<lead-seat> \
  --as <fleet>:<lead-seat>
```

For blockers:

```bash
aura event subscribe reports \
  --name <crew>-blockers \
  --fleet <fleet> \
  --state blocked \
  --state needs_decision \
  --state failed \
  --to <fleet>:<lead-seat> \
  --as <fleet>:<lead-seat>
```

Subscription setup is not proof that work is happening. It only proves delivery mechanics. Worker reports still need receipts and lead verification.

## Wakeups And Autoloops

Wakeups are control machinery, not staff. Use them to resume a file-backed manager or floor loop, not to invent state from chat memory. Manual managed crews do not need wakeups. Event-backed crews should add wakeups only when liveness or continuation matters.

Every recurring wakeup should name the files to read, the exact safe action shape, and the stop conditions.

Good recurring wakeups:

- read the board or continue contract
- inspect reports or receipt paths
- advance at most one safe coordination step
- report state
- stop at explicit approval gates, unsafe ambiguity, or completion

Avoid overlapping wakeups with the same purpose. If both a heartbeat and an autoloop exist, define which one owns progress and which one only checks liveness. Pause or remove wakeups when the crew is parked at a human decision gate.

## Launch Message

For ordinary live agents, use `aura-spawn` with the work packet or concise prompt, then wait briefly before assuming the agent is idle. Use `aura-operator` only for package agents, resume/fork, adoption, repair, or lifecycle surgery. After 5-15 seconds, inspect the target or wait for the first report; if the worker is processing, do nothing. If it is idle at the composer with no submitted task, send an immediate semantic launch nudge that points to the onboard/work files and repeats the reporting boundary.

```text
spawn worker
  -> wait 5-15 seconds
  -> inspect target or wait for first report
  -> if the worker is actively processing, do nothing
  -> if idle at composer with no submitted task, send a semantic launch nudge
```

Example:

```text
You are worker-a for this crew. Read:

- /path/to/crew/worker-a/onboard.md
- /path/to/crew/worker-a/work.md

Work only in the declared paths. Report `working`, `blocked`, or `complete` through Aura with receipt paths. Do not perform Aura seat repair; report symptoms instead.
```

Use `aura-send` for the initial semantic nudge only when the worker needs to start now. If the installed Aura CLI rejects that form or the runtime is visibly idle after spawn, inspect once and send one concise launch nudge. Raw terminal write is operator repair, not the default crew path.

## Queue By Default

For an already-running worker, use `aura-queue` by default so the message arrives at the worker's next report boundary instead of piling into an active turn. Queue review notes, additional context, non-urgent corrections, next-phase instructions, and "after you finish X" handoffs. Use `aura-send` only for immediate launch, explicit unblock, safety correction, or intentional interruption.

```text
running worker + non-urgent instruction -> aura-queue
idle worker + start task                 -> aura-send
blocked worker + unblock instruction     -> aura-send
dangerous/wrong active work              -> aura-send or operator intervention
```

## Active Monitoring

The lead must not go blind while a crew is active. Use report subscriptions or a floor coordinator as the primary event loop, but periodically check topology or inspect a known target if no report arrives within the expected cadence. Treat silence as a state to investigate, not as evidence that work is proceeding. Keep a short list of active seats, expected next report times, and outstanding receipts.

## Reduction Rules

Worker reports are evidence, not acceptance. The lead must read receipt files, inspect code diffs before committing, rerun focused verification when needed, classify failures, update the board, and only then write promoted truth. Do not accept terminal scrollback, live pane status, or event delivery as semantic truth.

- read receipt files
- inspect code diffs before committing
- rerun focused verification
- classify failures
- update the board
- write promoted truth only after verification

## Operator Boundary

Routine workers should not cut, adopt, rename seats, edit registry rows, perform raw terminal repair, or restart shared services unless explicitly assigned. They should report symptoms and receipts; the lead routes lifecycle and repair issues through `aura-operator`, or uses `aura-operator` only when explicitly acting as an Aura operator. Keep dangerous recipes out of worker packets.

- cut/adopt/rename seats
- kill unknown processes
- edit Aura registry rows
- perform raw terminal repair
- restart shared services unless explicitly assigned

## Failure Modes

Handle common crew failures with observation before intervention. If a seat exists but the task did not start, wait briefly, inspect, then send one semantic nudge; if a worker reports complete but receipts are missing, gate integration and ask for the missing receipt; if messages pile up, reroute future notes through `aura-queue`. If a worker is blocked on lifecycle, registry, service, or terminal repair, route to `aura-operator` or explicitly enter `aura-operator` mode instead of embedding repair steps in the worker mission.

```text
spawned-but-idle              -> wait, inspect, then one launch nudge
complete-without-receipts     -> gate integration until receipts exist
running-worker-extra-context  -> queue, do not interrupt
blocked-on-operator-work      -> route to aura-operator or explicit aura-operator
stale-or-ambiguous-seat       -> inspect, ledger, then cut/park intentionally
lead-overloaded-by-ops        -> assign floor coordinator or shrink crew
self-echoing-subscriptions    -> remove or retarget; use report ledger for lead's own reports
```

## Close Or Resume

At the end of a crew run, record a ledger with seat, runtime, runtime session id when known, work packet, report ids, event/subscription names, final status, close policy, and commits or receipt paths. Cut completed disposable workers or mark them intentionally resumable. Do not leave ambiguous seats behind.

```text
seat
runtime
runtime_session_id if known
work packet
report ids
event/subscription names
final status
cut/resume decision
commits or receipt paths
```

If a fleet was newly spawned or restored, include the useful attach command once in closeout:

```bash
tmux attach -t FLEET
```

For handoff-only messages, label them as state-only and avoid assigning new work unless the operator explicitly requested it.

## References

Load on demand for the specific phase of crew work:

```text
references/coordinator-posture.md     personality + delegation discipline for the lead
references/crew-ledger.md             closeout ledger template
references/onboard-packet.md          durable read package per worker
references/worker-packet.md           per-worker mission/scope/receipt template
```
