#!/usr/bin/env bash
# Aura claude-code status line + pane->session FK writer.
#
# Claude exposes a seat's LIVE session id only on statusline/hook stdin (the env
# var goes stale after /branch and on adopted panes). This script is the producer
# for Aura's pane->session map: it persists {session_id,cwd,ts} keyed by the exact
# tmux pane into <state>/runtime/claude-pane-session/<pane>, where Aura's resolvers
# (runtime_session.claude_pane_session_id / pane_resolver) read it back exactly —
# branch- and adopt-safe. Shipped + installed by aura (hooks.inject) so fresh seats
# get the FK without a hand-placed global script. Failure-isolated; also renders a
# compact line so it can stand in as the seat's statusLine without losing display.
set -u

input=$(cat)
session_id=$(printf '%s' "$input" | jq -r '.session_id // ""' 2>/dev/null)
cwd=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // ""' 2>/dev/null)
used_pct=$(printf '%s' "$input" | jq -r '.context_window.used_percentage // empty' 2>/dev/null)

# --- the FK write (the whole point): pane -> session, AURA_STATE_DIR-aware ---
if [ -n "$session_id" ] && [ -n "${TMUX_PANE:-}" ]; then
    state="${AURA_STATE_DIR:-$HOME/.aura}"
    map="$state/runtime/claude-pane-session"
    if mkdir -p "$map" 2>/dev/null; then
        printf '{"session_id":"%s","cwd":"%s","ts":"%s"}' \
            "$session_id" "$cwd" "$(date -u +%FT%TZ)" > "$map/${TMUX_PANE}.tmp" 2>/dev/null \
            && mv -f "$map/${TMUX_PANE}.tmp" "$map/${TMUX_PANE}" 2>/dev/null || true
    fi
fi

# --- compact display: dir [short-sid · ctx%] ---
dir=$(basename "${cwd:-$PWD}")
printf '\033[1;36m%s\033[0m' "$dir"
if [ -n "$session_id" ] || [ -n "$used_pct" ]; then
    printf '\033[2m ['
    [ -n "$session_id" ] && printf '%s' "${session_id:0:8}"
    [ -n "$session_id" ] && [ -n "$used_pct" ] && printf ' \xc2\xb7 '
    [ -n "$used_pct" ] && printf '%.0f%%' "$used_pct"
    printf ']\033[0m'
fi
