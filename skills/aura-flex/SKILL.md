---
name: aura:flex
description: "Use Aura live fleet views to scope Flex session searches for current agents."
allowed-tools:
  - mcp__flex__flex_search
user-invocable: true
argument-hint: "fleet:NAME, FLEET:SEAT, or a question about what live agents did"
---

# aura:flex

Aura runs agents as live seats (`fleet:seat`), and each seat's runtime keeps a
native session transcript. Flex indexes those transcripts. This skill joins the
two: use Aura's live views to find the seats and their `session_id`s, then
query Flex for what those agents actually did.

## Default Path

For routine questions like:

```text
what did your fleet do?
read the last N messages for each agent in your fleet
give me a pulse on this fleet
what should this live fleet do next?
```

run exactly this sequence:

```bash
aura view self
aura view fleet
```

Then query Flex directly with the `session_id` values from the fleet rows.

Do not run `aura_flex.py` first for "your fleet", current-fleet tails, last messages, or simple summaries.
Do not run `pulse --all-live` unless the user explicitly asks for all live Aura seats.

For a named fleet, skip self and run:

```bash
aura view fleet FLEET
```

For fleet discovery only:

```bash
aura view fleets
```

Use the returned rows:

```json
{
  "target": "FLEET:SEAT",
  "runtime": "codex",
  "session_id": "019...",
  "identity": "r_...",
  "name": "product:unit:role",
  "report": "latest useful sentence"
}
```

Only query Flex for rows with `session_id`.

## Flex Query

Always orient the Flex cell once before querying:

```text
mcp__flex__flex_search cell="codex" query="@orient"
```

Cell choice comes from runtime:

```text
runtime=codex       -> cell=codex
runtime=claude_code -> cell=claude_code
```

If a fleet has mixed runtimes, run one Flex query per cell and merge results by `target`.

For "last N messages per agent", use this query shape:

```sql
WITH seats(target, session_id) AS (
  VALUES
    ('FLEET:SEAT_A', 'SESSION_A'),
    ('FLEET:SEAT_B', 'SESSION_B')
), ranked AS (
  SELECT seats.target,
         m.session_id,
         m.position,
         m.type,
         m.tool_name,
         substr(replace(replace(m.content, char(10), ' '), char(13), ' '), 1, 900) AS content,
         ROW_NUMBER() OVER (
           PARTITION BY seats.target
           ORDER BY m.position DESC
         ) AS rn
  FROM seats
  JOIN messages m ON m.session_id = seats.session_id
  WHERE m.type IN ('user_prompt', 'assistant', 'tool_call')
    AND m.content NOT LIKE '%aura sessions bind-current%'
    AND m.content NOT LIKE '%runtime session binding%'
    AND m.content NOT LIKE '<environment_context>%'
)
SELECT target, session_id, rn, position, type, tool_name, content
FROM ranked
WHERE rn <= 3
ORDER BY target, rn;
```

Summarize by `target`, not just by `session_id`.

## Helper Status

`aura_flex.py` exists, but do not teach or use helper modes as the normal path right now.
The current reliable path is Aura view output plus direct Flex SQL.

Allowed helper use for now:

```bash
python /home/axp/.flex/utils/skills/aura_flex.py pulse --fleet FLEET --pretty
python /home/axp/.flex/utils/skills/aura_flex.py scope --fleet FLEET --pretty
```

Only use these when the user explicitly asks for the helper payload or a rough helper pulse.

## Response Shape

Keep session ids visible:

```json
{
  "fleet": "FLEET",
  "included": [
    {"target": "FLEET:SEAT", "runtime": "codex", "session_id": "019..."}
  ],
  "missing": [
    {"target": "FLEET:SEAT", "reason": "missing_session_id"}
  ],
  "results": []
}
```
