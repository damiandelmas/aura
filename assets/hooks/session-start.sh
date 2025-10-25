#!/bin/bash
#
# SessionStart Hook - Auto-register Claude Code conversations
#
# Triggered by Claude Code when new conversation starts.
# Generates bookmark, updates registry, injects context markers.
#
# Input (stdin): JSON with session_id
# Output (stdout): Context injection text
#

set -euo pipefail

# Parse input JSON (Claude Code provides session_id)
SESSION_ID=$(jq -r '.session_id' 2>/dev/null || echo "")

if [[ -z "$SESSION_ID" ]]; then
    # No session_id provided (hook test or old Claude Code)
    exit 0
fi

# Skip registration if this is a brother spawn (not a user conversation)
if [[ -n "${CLAUDE_IS_BROTHER:-}" ]]; then
    # This is a brother agent, don't pollute the registry
    exit 0
fi

# Find project root (walk up to .git)
PROJECT_ROOT=$(pwd)
while [[ "$PROJECT_ROOT" != "/" ]]; do
    if [[ -d "$PROJECT_ROOT/.git" ]]; then
        break
    fi
    PROJECT_ROOT=$(dirname "$PROJECT_ROOT")
done

# Update registry (using Python helper)
cd "$PROJECT_ROOT"
if [[ -f "aura-v2/venv/bin/python" ]]; then
    PYTHON="aura-v2/venv/bin/python"
elif [[ -f "aura/venv/bin/python" ]]; then
    PYTHON="aura/venv/bin/python"
else
    PYTHON="python3"
fi

$PYTHON -c "
import sys
from orchestrator.registry import add_session
add_session('$SESSION_ID')
print(f'Registered: ${SESSION_ID:0:12}...', file=sys.stderr)
" 2>&1 || echo "⚠️  Registry update failed" >&2

# Output JSON for Claude Code to inject into conversation context
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "SESSION_ID: ${SESSION_ID}\n\nUse /log:develop to create changelog for this conversation."
  }
}
EOF

exit 0
