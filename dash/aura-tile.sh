#!/bin/bash
# AURA TILE - Convert windows to panes (dashboard mode)
# All agent windows become panes in a single "dashboard" window

SESSION="${1:-${AURA_PROJECT:-aura}}"
DASH_WINDOW="dashboard"
MAX_PANES="${2:-20}"

echo "🔮 AURA TILE - Converting windows → panes"

# Get all windows except bash (window 0) and any existing dashboard
WINDOWS=$(tmux list-windows -t "$SESSION" -F "#{window_index}:#{window_name}" 2>/dev/null | grep -v "^0:" | grep -v ":$DASH_WINDOW$" | head -$MAX_PANES)
WINDOW_COUNT=$(echo "$WINDOWS" | grep -c . || echo 0)

if [ "$WINDOW_COUNT" -eq 0 ]; then
    echo "No agent windows to tile!"
    exit 1
fi

echo "Found $WINDOW_COUNT windows to tile"

# Create dashboard window from first agent window
FIRST_WIN=$(echo "$WINDOWS" | head -1 | cut -d: -f1)
tmux rename-window -t "$SESSION:$FIRST_WIN" "$DASH_WINDOW"
DASH_IDX=$FIRST_WIN

echo "Dashboard window: $DASH_IDX"

# Join remaining windows as panes
echo "$WINDOWS" | tail -n +2 | while IFS=: read WIN NAME; do
    if [ -n "$WIN" ] && [ "$WIN" != "$DASH_IDX" ]; then
        echo "  Joining $NAME (window $WIN) → dashboard"
        tmux join-pane -s "$SESSION:$WIN" -t "$SESSION:$DASH_IDX" 2>/dev/null
        tmux select-layout -t "$SESSION:$DASH_IDX" tiled 2>/dev/null
    fi
done

# Final tiled layout
tmux select-layout -t "$SESSION:$DASH_IDX" tiled

echo "✅ Done! All agents tiled in '$DASH_WINDOW' window"
echo "   Use: tmux attach -t $SESSION"
echo "   Untile: aura-untile $SESSION"
