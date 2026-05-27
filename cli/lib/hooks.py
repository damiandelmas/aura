"""Claude Code lifecycle hook injection at spawn time.

Picasso-steal from octogent's hookProcessor.ts — merge lifecycle hooks into the
spawned agent's working directory `.claude/settings.json` so every agent
auto-instruments itself without manual config.

Current hooks injected:
  - SessionStart: announce liveness to parent via aura
  - Stop:         announce termination to parent via aura

All hook shell commands run in the agent's env, where AURA_AGENT_NAME and
AURA_PARENT are set by the aura wrapper at spawn. Fleet-based fallback remains
for legacy sessions.
"""

import json
import os
from pathlib import Path


AURA_BIN = "/home/axp/.local/bin/aura"


def _hook_cmd(event: str) -> str:
    """Shell command emitted by a lifecycle hook."""
    return (
        'case "${AURA_AGENT_NAME:-}" in '
        '  ledger-*|keeper-*) exit 0 ;; '
        'esac; '
        'PARENT="${AURA_PARENT:-}"; '
        'if [ -z "$PARENT" ]; then '
        '  FLEET=$(tmux display-message -p "#S" 2>/dev/null); '
        '  case "$FLEET" in '
        '    *-workers) BASE="${FLEET%-workers}"; '
        '      case "$BASE" in '
        '        pm-*) PARENT="$BASE" ;; '
        '        *-*) PRODUCT="${BASE%%-*}"; LANE="${BASE#*-}"; PARENT="${PRODUCT}-leader-${LANE}" ;; '
        '        *) PARENT="${BASE}-manager-project" ;; '
        '      esac ;; '
        '  esac; '
        'fi; '
        f'[ -n "$PARENT" ] && [ -n "$AURA_AGENT_NAME" ] && '
        f'{AURA_BIN} send "$PARENT" '
        f'"{event}: $AURA_AGENT_NAME" '
        f'--as "$AURA_AGENT_NAME" '
        '>/dev/null 2>&1; true'
    )



def default_hooks() -> dict:
    """Canonical aura hook set. Override via env or future flag."""
    return {
        "SessionStart": [{"hooks": [{"type": "command", "command": _hook_cmd("AGENT_STARTED")}]}],
        "Stop":         [{"hooks": [{"type": "command", "command": _hook_cmd("AGENT_STOPPED")}]}],
    }


def inject(workdir: str, emit_lifecycle: bool = True) -> dict:
    """Merge aura lifecycle hooks into <workdir>/.claude/settings.json.

    Idempotent: preserves any existing hook entries, appends ours if absent.
    Returns a diagnostic dict for the spawn result.

    `emit_lifecycle=False` skips the lifecycle-event hooks. Use it only for
    deliberate background launches that must not ping their parent PM.
    """
    if not emit_lifecycle:
        return {"hooks": "skipped", "reason": "emit_lifecycle=False (silent keeper)"}
    try:
        wd = Path(workdir)
        if not wd.is_dir():
            return {"hooks": "skipped", "reason": f"workdir not a dir: {workdir}"}
        settings_dir = wd / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "settings.json"

        current = {}
        if settings_path.exists():
            try:
                current = json.loads(settings_path.read_text())
            except Exception:
                current = {}

        hooks_section = current.setdefault("hooks", {})
        ours = default_hooks()

        injected = []
        for event, entries in ours.items():
            existing = hooks_section.get(event, [])
            # dedupe: skip if any existing entry already contains our aura command
            has_ours = any(
                AURA_BIN in json.dumps(e) for e in existing
            )
            if has_ours:
                continue
            hooks_section[event] = existing + entries
            injected.append(event)

        if injected:
            settings_path.write_text(json.dumps(current, indent=2))

        return {"hooks": "injected" if injected else "already-present",
                "events": injected, "path": str(settings_path)}
    except Exception as e:
        return {"hooks": "error", "reason": str(e)}
