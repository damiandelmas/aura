#!/bin/bash
# PIPELINE MATRIX - Minority Report mode for prospect pipeline
# Pre-spawns all orchestrators, tiles them, kicks off the pipeline
# Watch the entire flow unfold in front of your eyes

set -e

MODE="${1:-test}"
MAX="${2:-1}"
SKIP_STAGE0="${3:-}"  # Pass "skip" to skip discovery

# Session name from knowledge - agents spawn into tmux session named after project
KNOWLEDGE="find-prospects"
SESSION="$KNOWLEDGE"
WORKDIR="/home/axp/projects/axpmarket/main/prospects/worktrees/refactor-1/main"

# Export for aura CLI
export AURA_PROJECT="$KNOWLEDGE"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║            🔮 PIPELINE MATRIX - MINORITY REPORT MODE             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Mode: $MODE | Max: $MAX | Skip Stage 0: ${SKIP_STAGE0:-no}"
echo ""

# Ensure mesh daemon is running
if ! pgrep -f "mesh.py" > /dev/null; then
    echo "🌐 Starting mesh daemon..."
    python3 /home/axp/projects/aura/main/mesh/mesh.py &
    sleep 2
else
    echo "🌐 Mesh daemon already running"
fi

# Kill any existing orchestrators
echo "🧹 Clearing existing orchestrators..."
for agent in pipeline-orchestrator s0-orchestrator s1-orchestrator s2-orchestrator s3-orchestrator s4-orchestrator; do
    aura cut "$agent" 2>/dev/null || true
done
sleep 1

# Pre-spawn all orchestrators
echo ""
echo "🚀 Pre-spawning orchestrators..."

cd "$WORKDIR"

echo "  → pipeline-orchestrator (master)"
aura spawn pipeline-orchestrator --knowledge find-prospects &

echo "  → s0-orchestrator (discovery)"
aura spawn s0-orchestrator --knowledge find-prospects &

echo "  → s1-orchestrator (extraction)"
aura spawn s1-orchestrator --knowledge find-prospects &

echo "  → s2-orchestrator (validation)"
aura spawn s2-orchestrator --knowledge find-prospects &

echo "  → s3-orchestrator (merge)"
aura spawn s3-orchestrator --knowledge find-prospects &

echo "  → s4-orchestrator (outreach)"
aura spawn s4-orchestrator --knowledge find-prospects &

# Wait for all to register
echo ""
echo "⏳ Waiting for mesh registration..."
sleep 5

# Check status
echo ""
echo "📡 Agent status:"
aura list 2>/dev/null | python3 -c "
import json, sys
agents = json.load(sys.stdin)
for a in sorted(agents, key=lambda x: x['name']):
    status = '✅' if a.get('status') else '⏳'
    print(f\"  {status} {a['name']}\")
print(f'  Total: {len(agents)} agents')
" || echo "  (mesh check failed, continuing...)"

# Tile into dashboard
echo ""
echo "🖼️  Tiling into dashboard..."
/home/axp/projects/tmux-axp/main/scripts/aura-tile.sh "$SESSION" 2>/dev/null || true

# Lock focus on dashboard - prevent auto-switching
tmux select-window -t "$SESSION:dashboard" 2>/dev/null || true
# Disable activity monitoring that causes focus jumps
tmux set-option -t "$SESSION" -g monitor-activity off 2>/dev/null || true
tmux set-option -t "$SESSION" -g visual-activity off 2>/dev/null || true

# Build the prompt
PROMPT="--mode $MODE --max $MAX"
if [ "$SKIP_STAGE0" = "skip" ]; then
    PROMPT="$PROMPT --skip-stage0"
fi

# Kick it off
echo ""
echo "🎬 SHOWTIME! Sending prompt to pipeline-orchestrator..."
echo "   Prompt: $PROMPT"
echo ""

# Send kick-off with retry
SEND_RESULT=$(aura send pipeline-orchestrator "$PROMPT" 2>&1)
if echo "$SEND_RESULT" | grep -q "error"; then
    echo "⚠️  First send failed, retrying..."
    sleep 2
    aura send pipeline-orchestrator "$PROMPT"
fi

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    🎥 MATRIX INITIALIZED                         ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  tmux attach -t $SESSION                                         ║"
echo "║                                                                  ║"
echo "║  Controls:                                                       ║"
echo "║    Ctrl-b + arrow  - Navigate panes                              ║"
echo "║    Ctrl-b + z      - Zoom/unzoom pane                            ║"
echo "║    Ctrl-b + Space  - Cycle layouts                               ║"
echo "║    aura-untile     - Break back to windows                       ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "Attaching to tmux..."
sleep 1

tmux attach -t "$SESSION" 2>/dev/null || echo "Run: tmux attach -t $SESSION"
