# Agent Maintenance

Agent maintenance checks whether the surfaces for one durable Aura agent still
join cleanly.

## Inputs

Start from one of these references:

```text
i_<id>
agent alias
legacy agent address if present in a legacy index
fleet:seat
Runway organization row
```

Resolve the reference to the package id when possible.

## Package Check

Check:

```text
package root exists
manifest.json exists
manifest.json parses
manifest runtime/cwd/profile/fleet/seat are expected
runtime-native roots exist when expected
```

Useful commands:

```bash
aura agent inspect <agent-ref>
python3 -m json.tool /home/axp/.aura/agents/i_<id>/manifest.json
find /home/axp/.aura/agents/i_<id> -maxdepth 2 -type d -print
```

## History Check

Check:

```text
aura.json exists when materialized
aura.json parses
aura.json schema is aura.agent_history.v1
current rows match live registry when live
history rows are generated from registry/session-ledger
```

Useful commands:

```bash
aura agent history <agent-ref>
aura agent history <agent-ref> --write
python3 -m json.tool /home/axp/.aura/agents/i_<id>/aura.json
```

## Organization Check

Check:

```text
Runway organization row exists when expected
row points to the package id
row does not contain fleet, seat, cwd, runtime, or session state
legacy r_* rows are visible as migration candidates
```

Useful command:

```bash
python3 -m json.tool /home/axp/.runway/<product>/organization.json
```

## Live Check

Check:

```text
fleet exists when package is live
seat exists when package is live
seat identity matches package id when bound
session id matches aura.json current row when bound
runtime is alive or stale/dead is reported clearly
```

Useful commands:

```bash
aura view fleet <fleet>
aura inspect <fleet>:<seat> --raw --lines 40
```

## Drift Classes

Report these as maintenance findings:

```text
missing-package-root
missing-manifest
invalid-manifest-json
missing-runtime-root
missing-aura-json
stale-aura-json
runway-points-to-missing-package
registry-points-to-missing-package
live-seat-unbound
live-seat-bound-to-wrong-package
dead-seat-still-in-current-view
legacy-desks-identity
duplicate-live-seat-for-package
```

## Output

Return:

```text
agent id
package root
manifest summary
aura history summary
organization assignment
live binding
drift findings
next maintenance action
```
