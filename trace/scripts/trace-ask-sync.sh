#!/bin/bash
# trace-ask-sync - Query past conversation via synchronous brother agent (blocking)
# Usage: trace-ask-sync SESSION_ID "question"
#
# Session ID format: Full UUID (36 characters)
#   Example: 12c9e48b-d968-4c69-9bdf-2032b241002b

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: trace-ask-sync SESSION_ID \"question\""
  echo ""
  echo "Example:"
  echo "  trace-ask-sync 12c9e48b-d968-4c69-9bdf-2032b241002b \"what did we decide about X?\""
  echo ""
  echo "Session ID: Full UUID required (36 characters)"
  echo "Get session IDs with: trace --list"
  exit 1
fi

SESSION_ID="$1"
QUESTION="$2"

# Validate full UUID format (36 characters with dashes)
if [ ${#SESSION_ID} -ne 36 ]; then
  echo "❌ Error: Full session UUID required (36 characters)"
  echo "   Provided: $SESSION_ID (${#SESSION_ID} characters)"
  echo "   Expected: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  echo ""
  echo "💡 Get full session IDs with: trace --list"
  exit 1
fi

# Validate UUID pattern
if ! [[ "$SESSION_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
  echo "❌ Error: Invalid UUID format"
  echo "   Provided: $SESSION_ID"
  echo "   Expected: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (lowercase hex)"
  exit 1
fi

# Path to trace CLI (use venv version)
TRACE_BIN="/home/axp/projects/fleet/hangar/code/aura/main/venv/bin/trace"

# Verify trace is available
if [ ! -f "$TRACE_BIN" ]; then
  echo "❌ Error: trace CLI not found at $TRACE_BIN"
  echo "   Run: cd /home/axp/projects/fleet/hangar/code/aura/main && ./install.sh"
  exit 1
fi

# Extract conversation using Python trace
echo "📖 Extracting conversation from session $SESSION_ID..."
CONVERSATION=$("$TRACE_BIN" --session "$SESSION_ID" --conversation 2>&1)

# Check if extraction succeeded
if [ $? -ne 0 ]; then
  echo "❌ Error: Failed to extract conversation"
  echo "$CONVERSATION"
  exit 1
fi

# Check if conversation is empty
if [ -z "$CONVERSATION" ]; then
  echo "❌ Error: No conversation found for session $SESSION_ID"
  exit 1
fi

echo "✅ Conversation extracted successfully"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤔 Querying synchronous brother agent..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create prompt and pipe to claude -p (BLOCKING - no &)
cat <<EOF | claude -p --dangerously-skip-permissions
You are analyzing a past Claude Code conversation.

CONVERSATION CONTEXT (Session $SESSION_ID):

$CONVERSATION

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUESTION: $QUESTION

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Answer based only on the conversation above. Be concise but accurate.
If the answer is not in the conversation, say so clearly.
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Query complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
