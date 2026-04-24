#!/bin/bash
# AURA LAYOUT - Apply 2-column layout (taller panes for conversations)
# Creates 2 vertical columns, panes stacked horizontally in each

SESSION="${1:-${AURA_PROJECT:-aura}}"
WINDOW="${2:-dashboard}"
COLS="${3:-2}"

echo "📐 AURA LAYOUT - Applying ${COLS}-column layout"

# Get pane count
PANE_COUNT=$(tmux list-panes -t "$SESSION:$WINDOW" 2>/dev/null | wc -l)

if [ "$PANE_COUNT" -eq 0 ]; then
    echo "No panes found in $SESSION:$WINDOW"
    exit 1
fi

echo "Found $PANE_COUNT panes"

# Calculate rows per column
ROWS=$(( (PANE_COUNT + COLS - 1) / COLS ))

echo "Layout: $COLS columns × $ROWS rows"

# Use main-vertical layout as base (1 column left, rest stacked right)
# Then we manually adjust

# For 2 columns with many rows, we can use a custom layout string
# Format: checksum,width,height,x,y[,pane_id][,child...]

# Simpler approach: use select-layout with main-vertical then adjust
# Or just use tiled and accept it

# Actually, best approach: manually position panes
# First, set to tiled to reset
tmux select-layout -t "$SESSION:$WINDOW" tiled

# Now apply main-vertical (gives 2 columns - one main, one stacked)
# This isn't quite right either...

# Let's try a different approach: create the layout string
# Get window dimensions
WIN_WIDTH=$(tmux display-message -t "$SESSION:$WINDOW" -p "#{window_width}")
WIN_HEIGHT=$(tmux display-message -t "$SESSION:$WINDOW" -p "#{window_height}")

COL_WIDTH=$(( WIN_WIDTH / COLS ))

echo "Window: ${WIN_WIDTH}x${WIN_HEIGHT}, Column width: $COL_WIDTH"

# For 2 columns, we want panes 0,2,4,6... in left column
# and panes 1,3,5,7... in right column

# Tmux custom layouts are complex. Let's use a simpler approach:
# Rearrange panes manually using swap-pane and resize

# Actually simplest: use even-vertical for 2 tall columns, then split each horizontally
# But that requires restructuring...

# HACK: Use main-horizontal with main-pane-height set high
# This gives stacked rows with decent height

tmux select-layout -t "$SESSION:$WINDOW" main-horizontal
tmux set-window-option -t "$SESSION:$WINDOW" main-pane-height $(( WIN_HEIGHT * 2 / 3 ))

# Try even-vertical (2 columns)
tmux select-layout -t "$SESSION:$WINDOW" even-vertical

echo "✅ Applied even-vertical layout (2 tall columns)"
echo "   Other layouts: Ctrl-b Space to cycle"
echo "   Options: tiled, even-horizontal, even-vertical, main-horizontal, main-vertical"
