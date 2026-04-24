#!/bin/bash
# Persistent agents boot script.
#
# Spawns one agent per onboarding package into the `dev` tmux fleet.
# Idempotent: if an agent is already live on mesh, skip. If its tmux window
# exists but mesh dropped it, kill+respawn.
#
# Usage:
#   persistent-agents.sh              # spawn all missing
#   persistent-agents.sh --restart    # kill all + respawn
#   persistent-agents.sh --status     # print live/missing table
#
# Agents list (name → onboard package path):
#   retrieve         → flexsearch/context/onboard/retrieve/onboard.md
#   transpiler       → flexsearch/context/onboard/coding-agent-transpiler/onboard.md
#   module-builder   → flexsearch/context/onboard/module-building/onboard.md
#   boundary         → flexsearch/context/onboard/public-private/onboard.md
#   outreach         → flexsearch/context/onboard/outreach-ops/onboard.md

set -u

DESKS=/home/axp/projects/desks
ONBOARD_ROOT=/home/axp/projects/flexsearch/context/onboard

declare -A AGENTS=(
    [retrieve]="$ONBOARD_ROOT/retrieve/onboard.md"
    [transpiler]="$ONBOARD_ROOT/coding-agent-transpiler/onboard.md"
    [module-builder]="$ONBOARD_ROOT/module-building/onboard.md"
    [boundary]="$ONBOARD_ROOT/public-private/onboard.md"
    [outreach]="$ONBOARD_ROOT/outreach-ops/onboard.md"
)

live_agents() {
    aura list --json 2>/dev/null | python3 -c "
import sys, json
try:
    agents = json.load(sys.stdin)
    print('\n'.join(a['name'] for a in agents))
except Exception:
    pass
" 2>/dev/null
}

is_live() {
    local name="$1"
    live_agents | grep -qxF "$name"
}

ensure_desk() {
    local name="$1"
    local desk="$DESKS/$name"
    [[ -d "$desk" ]] || mkdir -p "$desk"
    echo "$desk"
}

spawn_one() {
    local name="$1"
    local onboard="$2"
    local desk
    desk=$(ensure_desk "$name")

    if is_live "$name"; then
        echo "[skip] $name already live"
        return 0
    fi

    # Kill stale tmux window if present
    tmux kill-window -t "dev:$name" 2>/dev/null

    # Spawn with --as-pane so it doesn't steal focus from an attached tmux
    (cd "$desk" && aura spawn "$name" --fleet dev --model 'claude-opus-4-6[1m]' --as-pane --wait --timeout 30 2>&1 | tail -1)

    # Inject onboarding package as first message
    if [[ -f "$onboard" ]]; then
        local msg
        msg=$(printf 'ONBOARD — read and internalize the following. This is your persistent scope.\n\n%s' "$(cat "$onboard")")
        aura send "$name" "$msg" 2>&1 | tail -1
    else
        echo "[warn] $name: onboard package missing at $onboard"
    fi
}

cmd_spawn() {
    for name in "${!AGENTS[@]}"; do
        spawn_one "$name" "${AGENTS[$name]}"
    done
}

cmd_restart() {
    for name in "${!AGENTS[@]}"; do
        aura cut "$name" 2>/dev/null
        tmux kill-window -t "dev:$name" 2>/dev/null
    done
    cmd_spawn
}

cmd_status() {
    printf '%-16s %-8s %s\n' "NAME" "STATUS" "ONBOARD"
    for name in "${!AGENTS[@]}"; do
        local status="missing"
        if is_live "$name"; then status="live"; fi
        printf '%-16s %-8s %s\n' "$name" "$status" "${AGENTS[$name]}"
    done
}

case "${1:-spawn}" in
    spawn)   cmd_spawn ;;
    --restart|restart) cmd_restart ;;
    --status|status)   cmd_status ;;
    *) echo "usage: $0 [spawn|--restart|--status]" >&2; exit 2 ;;
esac
