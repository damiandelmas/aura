# Onboard Packet Template

Use this for a managed Aura worker's `onboard.md`.

An onboard packet is the worker's durable read package. It should contain absolute paths and short framing only. Put current task instructions in `work.md`, not here. The onboard packet should let a restarted or replacement worker recover context without inheriting hidden assumptions from the lead.

```markdown
# Onboard

## Purpose

Read every file listed here before doing the assigned work. The goal is to recover enough domain, code, and workflow context to execute the paired `work.md` without inheriting hidden assumptions from the lead.

## Role Boundary

You are responsible for the lane described in the paired `work.md`. Do not assume ownership of adjacent lanes just because their files are listed here.

## Current

- /absolute/path/to/context/current/architecture.md
- /absolute/path/to/context/current/modules/example.md

## Plans

- /absolute/path/to/context/plans/example/plan.md
- /absolute/path/to/context/plans/example/specs/contract.md

## Recent Changes

- /absolute/path/to/context/changes/code/...
- /absolute/path/to/context/changes/workflow/...

## Workstream

- /absolute/path/to/current/workstream/overview.md
- /absolute/path/to/current/workstream/state.md
- /absolute/path/to/current/workstream/phase-board.md
- /absolute/path/to/current/workstream/continue.md

## References

- /absolute/path/to/specific/proof-or-slipbox.md

## Receipts To Trust

- /absolute/path/to/receipt.md

## Receipts To Produce

See the paired `work.md`.
```

## Rules

- Use absolute paths.
- Prefer stable `context`, `workstream`, and receipt files.
- Include identity files only when the worker truly needs role-specific doctrine.
- Do not paste large source text into onboard if a file path is available.
- Do not put task steps here; put them in `work.md`.
- Keep the list bounded. If a worker needs ten folders of context, create a narrower packet first.
- Separate trusted source-of-truth files from optional background references.
