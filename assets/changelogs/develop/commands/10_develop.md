# Generate Development Changelog

Auto-generates changelog from this conversation using ORCA workflow.

## Usage

```bash
/log:develop                                    # Basic usage
/log:develop Focus only on code changes         # With custom instructions
```

## How It Works

1. Extract session ID from context (injected by SessionStart hook)
2. Extract complete chronicle using `trace --chronicle` (messages + patches chronologically)
3. Spawn ChangelogAgent brother via `async.sh`
4. Brother runs in background (2-5 minutes)
5. Changelog created at `.context/develop/.changes/{timestamp}_description-in-kebab-case.md`
6. Session ID stored in frontmatter for bidirectional linking

## Implementation

Extract the session ID from conversation context:

Priority extraction (look for these in order):
1. `[CURRENT_SESSION_ID: uuid]` - Most accurate (verified from transcript)
2. `[START_SESSION_ID: uuid]` - Fallback (from session start)

Then spawn async agent:

```bash
# Extract session ID from context
SESSION_ID="[extracted_session_id]"
TIMESTAMP=$(date +%Y%m%d-%H%M)

# Temporary: Use session ID in filename (will be renamed by agent with description)
TEMP_FILENAME="${TIMESTAMP}_temp-${SESSION_ID:0:8}.md"

# Path to binaries
TRACE_BIN="/home/axp/projects/fleet/hangar/code/aura/main/venv/bin/trace"
ASYNC_BIN="/home/axp/projects/fleet/hangar/code/orca/primitives/spawn/async.sh"

# Extract complete chronicle to temp file (avoids prompt length limits)
CHRONICLE_FILE="/tmp/chronicle_${SESSION_ID}.md"
echo "📖 Extracting chronicle from session $SESSION_ID to ${CHRONICLE_FILE}..."
"$TRACE_BIN" --session "$SESSION_ID" --chronicle > "$CHRONICLE_FILE"

# Build custom instructions if provided
CUSTOM_INSTRUCTIONS=""
if [ -n "$ARGUMENTS" ]; then
  CUSTOM_INSTRUCTIONS="

Additional focus: $ARGUMENTS"
fi

# Spawn ChangelogAgent via async.sh
echo "🚀 Spawning ChangelogAgent..."

cat <<EOF | "$ASYNC_BIN" &
You are ChangelogAgent.

TASK: Create a changelog for this session.

**Chronicle:** ${CHRONICLE_FILE}
**Template:** ~/.claude/.aura/templates/00_TEMPLATE.md
**Output:** .context/develop/.changes/${TEMP_FILENAME}
**Session ID:** ${SESSION_ID}
$CUSTOM_INSTRUCTIONS

Instructions:
1. Read the complete chronicle from: ${CHRONICLE_FILE}
   (Contains messages and code patches in chronological order)
2. Read the template at ~/.claude/.aura/templates/00_TEMPLATE.md
3. Analyze the chronicle to understand the work done
4. Follow template structure (progressive disclosure, 44-171 line range)
5. Extract a human-readable description from the work (2-4 words in kebab-case)
6. Create changelog with frontmatter including session_id: "${SESSION_ID}"
7. Save to temporary path: .context/develop/.changes/${TEMP_FILENAME}
8. After writing, rename to: ${TIMESTAMP}_<description-in-kebab-case>.md
9. Use natural field variations (2-6 fields per item)
10. Clean up: rm ${CHRONICLE_FILE}

Example filename transformations:
- ${TIMESTAMP}_temp-${SESSION_ID:0:8}.md → ${TIMESTAMP}_trace-chronicle-refactor.md
- Work on IMEM filters → ${TIMESTAMP}_imem-filter-support.md
- Authentication feature → ${TIMESTAMP}_authentication-implementation.md
EOF

echo "📝 Changelog generation started for session $SESSION_ID"
```

You can continue working while the agent runs in background.
