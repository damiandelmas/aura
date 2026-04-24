#!/bin/bash
#
# UserPromptSubmit Hook - Ensure CLAUDE_SESSION_ID is set (handles resume)
#
# Triggered when user submits a prompt.
# If CLAUDE_SESSION_ID not in env (resumed session), export it.
#
# Input (stdin): JSON with session_id, transcript_path
# Output: None (env export only)
#

set -euo pipefail

# Already set? Do nothing.
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    exit 0
fi

# Parse input JSON
INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path' 2>/dev/null || echo "")

if [[ -z "$TRANSCRIPT_PATH" ]] || [[ "$TRANSCRIPT_PATH" == "null" ]]; then
    exit 0
fi

# Skip if brother spawn
if [[ -n "${CLAUDE_IS_BROTHER:-}" ]]; then
    exit 0
fi

# Extract session ID from transcript path
SESSION_ID=$(basename "$TRANSCRIPT_PATH" .jsonl)

# Export to environment
if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
    echo "export CLAUDE_SESSION_ID=\"$SESSION_ID\"" >> "$CLAUDE_ENV_FILE"
fi

exit 0
