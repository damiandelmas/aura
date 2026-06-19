#!/usr/bin/env bash
# Canonical self-healing sweep — the repo source of truth.
#
# Install: copy to the no_agent scripts dir and register as a recurring event:
#   cp cli/hooks/heal-sweep.sh "${AURA_EVENT_SCRIPTS_DIR:-$HOME/.aura/event-scripts}/heal-sweep.sh"
#   chmod +x  "${AURA_EVENT_SCRIPTS_DIR:-$HOME/.aura/event-scripts}/heal-sweep.sh"
#   aura event start --name heal-sweep --target aura:self-heal \
#       --no-agent --script heal-sweep.sh --report-state working --every 60
#
# The FULL self-heal loop = reconcile THEN heal:
#
#   reconcile-orphans  rebuilds registry rows for live Aura-born panes whose row
#                      was dropped (a crash, a restart). heal is BLIND to these
#                      panes — no row means nothing to heal — so reconcile MUST
#                      run first or orphan panes stay unmanaged forever. A sweep
#                      that only heals (the old bug) silently leaves every
#                      post-crash pane orphaned until a manual reconcile.
#   heal               rebinds any alive+unbound row (claude via the
#                      pane->session statusline FK, codex via the jsonl nonce).
#
# Both are idempotent: at steady state reconcile=0 and heal=0, so this emits
# nothing AND exits 0 (aura no_agent: empty stdout + exit 0 = silent success ->
# no bus noise). It speaks only on a tick that actually changed something.
#
# CRITICAL: the quiet path MUST exit 0. A non-zero exit is counted as a failure
# (consecutive_errors + backoff, which stalls the cadence). A trailing
# `[ -n "$msg" ] && printf ...` returns 1 when msg is empty — do not do that;
# use an explicit `if` and `exit 0`.
set -uo pipefail

AURA="${AURA_BIN:-aura}"
command -v "$AURA" >/dev/null 2>&1 || AURA="/home/axp/.local/bin/aura"

rec=$("$AURA" sessions reconcile-orphans --all 2>/dev/null)
reconciled=$(printf '%s' "$rec" | jq -r '.reconciled // 0' 2>/dev/null)

out=$("$AURA" sessions heal --all 2>/dev/null)
healed=$(printf '%s' "$out" | jq -r '.healed // 0' 2>/dev/null)

msg=""
if [ "${reconciled:-0}" -gt 0 ] 2>/dev/null; then
    rseats=$(printf '%s' "$rec" | jq -r '[.results[] | select(.status=="would-reconcile" or .status=="reconciled") | .target] | join(", ")' 2>/dev/null)
    msg="reconciled ${reconciled} orphan pane(s): ${rseats}"
fi
if [ "${healed:-0}" -gt 0 ] 2>/dev/null; then
    hseats=$(printf '%s' "$out" | jq -r '[.results[] | select(.status=="healed") | (.seat + " (" + (.method // "?") + ")")] | join(", ")' 2>/dev/null)
    [ -n "$msg" ] && msg="${msg}; "
    msg="${msg}rebound ${healed} seat(s): ${hseats}"
fi

if [ -n "$msg" ]; then printf 'self-heal: %s' "$msg"; fi
exit 0
