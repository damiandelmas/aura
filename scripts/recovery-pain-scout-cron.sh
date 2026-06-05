#!/usr/bin/env bash
# Durable recovery-pain scout runner.
#
# This is intentionally a thin systemd-friendly wrapper around Aura:
# - ensure the scout seat exists
# - skip if the seat is already busy
# - otherwise send exactly one bounded scout tick

set -euo pipefail

AURA_BIN="${AURA_BIN:-/home/axp/projects/aura/main/cli/aura}"
TARGET="flex-community:recovery-pain-scout"
FLEET="flex-community"
SEAT="recovery-pain-scout"
WORKFLOW_ROOT="/home/axp/projects/flex/outreach/sandbox/recovery-pain-scout"
CWD="$WORKFLOW_ROOT"
WORKFLOW="$WORKFLOW_ROOT/README.md"
LOG_ROOT="${AURA_RECOVERY_SCOUT_CRON_LOG_ROOT:-/home/axp/.aura/cron/recovery-pain-scout}"
RUN_LABEL="${1:-scheduled}"

mkdir -p "$LOG_ROOT"

json_escape() {
    python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

log_event() {
    local kind="$1"
    local detail="${2:-}"
    local detail_json
    detail_json=$(printf '%s' "$detail" | json_escape)
    printf '{"at":"%s","kind":"%s","label":"%s","detail":%s}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$kind" "$RUN_LABEL" "$detail_json" \
        >> "$LOG_ROOT/runs.jsonl"
}

inspect_json() {
    "$AURA_BIN" inspect "$TARGET" --raw --lines 20 2>/dev/null || true
}

target_alive() {
    inspect_json | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
if data.get("ok") and data.get("terminal") == "alive":
    raise SystemExit(0)
raise SystemExit(1)
'
}

target_busy() {
    "$AURA_BIN" check "$TARGET" --output --lines 40 2>/dev/null | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
if data.get("terminal") != "alive":
    raise SystemExit(1)
lines = "\n".join(str(x) for x in data.get("output") or [])
busy_markers = (
    "Working (",
    "Thinking",
    "Running",
    "esc to interrupt",
    "tokens used",
)
raise SystemExit(0 if any(marker in lines for marker in busy_markers) else 1)
'
}

BOOTSTRAP_PROMPT=$(cat <<'PROMPT'
You are flex:marketing:distribution:community:scout focused on the Recovery Pain Scout workflow. Read /home/axp/.desks/organizations/flex/units/marketing/distribution/community/TEAM.md and /home/axp/projects/flex/outreach/sandbox/recovery-pain-scout/README.md.

Operating scope: read-only external/community research. Do not post, DM, contact prospects, or mutate product code. You may write concise workflow logs only under /home/axp/projects/flex/outreach/sandbox/recovery-pain-scout/logs/.

Strict target: Claude Code-specific recovery pain only. Look for people who cannot find files, sessions, JSON/session history, lost Claude Code-created work, missing session trail, forgotten commits/lost changes, or need to reconstruct exactly what Claude Code changed. Exclude Claude Desktop/web outage posts, generic ClaudeAI complaints, and generic unsafe-agent/hallucination posts unless they explicitly involve recovering Claude Code files/session/tool edits.

Run one bounded scout wave now, prefer posts from the last 1-2 weeks with a soft max of 3 weeks, log minimal objective notes, and report 3 best opportunities with platform, account, URL, age/date, pain summary, why it is Claude Code-specific, proposed reply angle, risk, and ready_for_damian_reply. End with PASS_TO_DAMIAN summary.
PROMPT
)

WAKEUP_PROMPT=$(cat <<PROMPT
Recovery Pain Scout ${RUN_LABEL} tick: run one bounded read-only scout wave from ${WORKFLOW}.

Strict target: Claude Code-specific recovery pain only: missing files, missing sessions, JSON/session history, lost Claude Code-created work, missing session trail, forgotten commits/lost changes, or reconstructing exactly what Claude Code changed.

Exclude Claude Desktop/web outage posts, generic ClaudeAI complaints, and generic unsafe-agent posts unless they explicitly involve recovering Claude Code files/session/tool edits.

Prefer posts from the last 1-2 weeks, soft max 3 weeks. Do not post, DM, or contact anyone. Write only minimal workflow logs under the recovery-pain-scout logs folder. Report the 3 best opportunities and end with PASS_TO_DAMIAN summary.
PROMPT
)

if ! target_alive; then
    log_event "respawn-start" "$TARGET missing; spawning scout"
    "$AURA_BIN" spawn "$SEAT" \
        --fleet "$FLEET" \
        --runtime codex \
        --cwd "$CWD" \
        --as-pane \
        --wait \
        --timeout 45 \
        --prompt "$BOOTSTRAP_PROMPT" >/tmp/flex-recovery-pain-scout-spawn.json
    log_event "respawned" "$(cat /tmp/flex-recovery-pain-scout-spawn.json)"
    exit 0
fi

if target_busy; then
    log_event "skip-busy" "$TARGET already working"
    exit 0
fi

"$AURA_BIN" send "$TARGET" "$WAKEUP_PROMPT" \
    --as-service flex-recovery-pain-scout \
    --transport tmux \
    --force >/tmp/flex-recovery-pain-scout-send.json
log_event "sent" "$(cat /tmp/flex-recovery-pain-scout-send.json)"
