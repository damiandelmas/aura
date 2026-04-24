#!/bin/bash
# AURA UNTILE - Convert panes back to windows (work mode)
# All panes in dashboard become separate windows again

SESSION="${1:-${AURA_PROJECT:-aura}}"
DASH_WINDOW="${2:-dashboard}"

echo "📂 AURA UNTILE - Converting panes → windows"

# Find the dashboard window
DASH_IDX=$(tmux list-windows -t "$SESSION" -F "#{window_index}:#{window_name}" | grep ":$DASH_WINDOW$" | cut -d: -f1)

if [ -z "$DASH_IDX" ]; then
    echo "No '$DASH_WINDOW' window found in $SESSION"
    echo "Looking for window with multiple panes..."

    # Find any window with multiple panes
    DASH_IDX=$(tmux list-windows -t "$SESSION" -F "#{window_index}:#{window_panes}" | awk -F: '$2 > 1 {print $1; exit}')

    if [ -z "$DASH_IDX" ]; then
        echo "No tiled windows found!"
        exit 1
    fi
fi

# Count panes
PANE_COUNT=$(tmux list-panes -t "$SESSION:$DASH_IDX" | wc -l)
echo "Found $PANE_COUNT panes in window $DASH_IDX"

if [ "$PANE_COUNT" -le 1 ]; then
    echo "Only 1 pane, nothing to untile"
    exit 0
fi

# Break each pane (except first) into its own window
# We go backwards to avoid index shifting issues
for ((i = PANE_COUNT - 1; i >= 1; i--)); do
    # Get the pane's command to use as window name
    PANE_CMD=$(tmux display-message -t "$SESSION:$DASH_IDX.$i" -p "#{pane_current_command}" 2>/dev/null)
    PANE_TITLE=$(tmux display-message -t "$SESSION:$DASH_IDX.$i" -p "#{pane_title}" 2>/dev/null)

    # Use pane title or fall back to generic name
    WIN_NAME="${PANE_TITLE:-agent-$i}"

    echo "  Breaking pane $i → window '$WIN_NAME'"
    tmux break-pane -s "$SESSION:$DASH_IDX.$i" -n "$WIN_NAME" 2>/dev/null
done

# Rename the remaining pane's window
FIRST_TITLE=$(tmux display-message -t "$SESSION:$DASH_IDX.0" -p "#{pane_title}" 2>/dev/null)
if [ -n "$FIRST_TITLE" ] && [ "$FIRST_TITLE" != "$DASH_WINDOW" ]; then
    tmux rename-window -t "$SESSION:$DASH_IDX" "$FIRST_TITLE"
fi

echo "✅ Done! Panes converted to windows"
echo "   Use: tmux attach -t $SESSION"
echo "   Tile again: aura-tile $SESSION"
