#!/bin/bash
#
# SessionStart Hook - Export CLAUDE_SESSION_ID + write aura ledger
#
# Triggered when new Claude Code session starts.
# Exports session ID to env so all bash commands can access it.
# If this is an aura-spawned agent, appends a ledger entry.
#
# Input (stdin): JSON with session_id, transcript_path
# Output: None (env export only)
#

set -euo pipefail

# Parse input JSON
INPUT=$(cat)
HOOK_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id' 2>/dev/null || echo "")
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path' 2>/dev/null || echo "")

if [[ -z "$HOOK_SESSION_ID" ]]; then
    exit 0
fi

# Extract session ID from transcript_path (more reliable for resume)
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ "$TRANSCRIPT_PATH" != "null" ]]; then
    SESSION_ID=$(basename "$TRANSCRIPT_PATH" .jsonl)
else
    SESSION_ID="$HOOK_SESSION_ID"
fi

# Skip if brother spawn
if [[ -n "${CLAUDE_IS_BROTHER:-}" ]]; then
    exit 0
fi

# Export SESSION_ID to environment for all subsequent bash commands
if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
    echo "export CLAUDE_SESSION_ID=\"$SESSION_ID\"" >> "$CLAUDE_ENV_FILE"
fi

# --- Aura Ledger ---
# If spawned by aura, write a ledger entry with full session ID
if [[ -n "${AURA_AGENT_NAME:-}" ]]; then
    LEDGER_DIR="$HOME/.aura"
    mkdir -p "$LEDGER_DIR"
    jq -nc \
        --arg ts "$(date -Is)" \
        --arg name "${AURA_AGENT_NAME}" \
        --arg fleet "${AURA_FLEET:-aura}" \
        --arg sid "$SESSION_ID" \
        --arg parent "${AURA_PARENT_SESSION:-}" \
        --arg memory "${AURA_SESSION_ID:-}" \
        --arg workdir "$(pwd)" \
        '{ts:$ts, name:$name, fleet:$fleet, session_id:$sid, parent:$parent, memory:$memory, workdir:$workdir}' \
        >> "$LEDGER_DIR/ledger.jsonl"
fi

exit 0
