#!/bin/bash
# Tail a specific aura agent's output
# Usage: aura-tail <agent-name> [lines] [refresh]

AGENT="${1:?Usage: aura-tail <agent-name> [lines] [refresh]}"
LINES="${2:-50}"
REFRESH="${3:-2}"

watch -n"$REFRESH" "echo '=== $AGENT ==='; aura check $AGENT --output --lines $LINES 2>/dev/null | tail -$LINES"
