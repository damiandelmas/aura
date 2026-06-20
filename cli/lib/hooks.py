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
from typing import Any


AURA_BIN = "/home/axp/.local/bin/aura"

# Repo-owned claude statusline: writes the pane->session FK map (the producer the
# resolvers read) and renders a compact line. Installed on spawned claude seats so
# the FK is reproducible without a hand-placed global script.
STATUSLINE_SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "aura-claude-statusline.sh"

# Directory holding the claude lifecycle hook scripts referenced from a boxed
# seat's settings.json. Scripts are referenced from the repo (not copied into the
# box) so adapter fixes ship without rebuilding boxes — same discipline as the
# Codex keeper installer.
CLAUDE_HOOK_DIR = Path(__file__).resolve().parent.parent / "hooks"


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


def _claude_hook_command(script_name: str) -> str:
    """Shell command for a boxed claude lifecycle hook script."""
    return f"python3 {CLAUDE_HOOK_DIR / script_name}"


def default_hooks_claude_block() -> dict:
    """The Aura hooks block written into a boxed claude seat's settings.json.

    Event → script mapping (claude-code hook contract; timeouts in SECONDS):
      SessionStart     → bind (confirm allocated session) + ambient (born orientation,
                         source=compact recovery)
      UserPromptSubmit → ambient (pending-flag gate; no-op unless society flagged)
      Stop             → keeper (message-count cadence)
      PreCompact       → keeper (boundary=precompact)
      PostCompact      → ambient (set pending-flag to re-orient next prompt)
    """
    bind = _claude_hook_command("claude_bind_hook.py")
    ambient = _claude_hook_command("claude_ambient_hook.py")
    keeper = _claude_hook_command("claude_keeper_hook.py")

    def entry(command: str, timeout: int) -> dict:
        return {"hooks": [{"type": "command", "command": command, "timeout": timeout}]}

    return {
        "SessionStart":     [entry(bind, 10), entry(ambient, 10)],
        "UserPromptSubmit": [entry(ambient, 5)],
        "Stop":             [entry(keeper, 10)],
        "PreCompact":       [entry(keeper, 10)],
        "PostCompact":      [entry(ambient, 10)],
    }


def _entry_commands(entry: Any) -> set[str]:
    """Commands referenced by one settings.json hook entry."""
    commands: set[str] = set()
    if isinstance(entry, dict):
        for hook in entry.get("hooks") or []:
            if isinstance(hook, dict) and hook.get("command"):
                commands.add(hook["command"])
    return commands


def default_hooks_claude(config_dir: str, *, seat_target: str | None = None) -> None:
    """Write/merge the Aura hooks block into ``<config_dir>/settings.json``.

    THE SEAM (frozen, owned by hooks lane). ``config_dir`` is the box's real
    ``CLAUDE_CONFIG_DIR`` (claude's ``CODEX_HOME`` analog); ``settings.json`` lives
    directly under it. Merges the ``hooks`` key only — never clobbers a profile's
    other keys (statusLine, permissions, model, profile-owned hooks), per seam-v2 §1
    (statusLine ownership belongs to claude_box, not here). Idempotent: a second call
    yields a byte-identical file.

    ``seat_target`` is accepted per the frozen signature; routing is left to the
    hook scripts' own self-resolution (pane→env→session) so a rename never strands a
    hardcoded address (two-laws). It is reserved as a future fallback hint.
    """
    cfg = Path(config_dir)
    cfg.mkdir(parents=True, exist_ok=True)
    settings_path = cfg / "settings.json"

    current: dict = {}
    if settings_path.exists():
        try:
            parsed = json.loads(settings_path.read_text(encoding="utf-8"))
            current = parsed if isinstance(parsed, dict) else {}
        except Exception:
            current = {}

    hooks_section = current.get("hooks")
    if not isinstance(hooks_section, dict):
        hooks_section = {}

    for event, entries in default_hooks_claude_block().items():
        existing = hooks_section.get(event)
        if not isinstance(existing, list):
            existing = []
        present: set[str] = set()
        for item in existing:
            present |= _entry_commands(item)
        for entry in entries:
            cmd = next(iter(_entry_commands(entry)), None)
            if cmd is None or cmd in present:
                continue
            existing.append(entry)
            present.add(cmd)
        hooks_section[event] = existing

    current["hooks"] = hooks_section
    # Only the `hooks` key is touched; every other key (statusLine, permissions,
    # profile hooks, model) is preserved exactly as the profile left it.
    settings_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")


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
                parsed = json.loads(settings_path.read_text())
                current = parsed if isinstance(parsed, dict) else {}
            except Exception:
                current = {}

        hooks_section = current.setdefault("hooks", {})
        if not isinstance(hooks_section, dict):
            hooks_section = {}
            current["hooks"] = hooks_section
        ours = default_hooks()

        injected = []
        for event, entries in ours.items():
            existing = hooks_section.get(event, [])
            if not isinstance(existing, list):
                existing = []
            # dedupe: skip if any existing entry already contains our aura command
            has_ours = any(
                AURA_BIN in json.dumps(e) for e in existing
            )
            if has_ours:
                continue
            hooks_section[event] = existing + entries
            injected.append(event)

        # statusLine: install the FK-writer for claude seats. Only when the project
        # has no statusLine of its own — never clobber an explicit one. This is what
        # makes the pane->session FK reproducible on fresh seats.
        statusline_installed = False
        if "statusLine" not in current and STATUSLINE_SCRIPT.exists():
            current["statusLine"] = {"type": "command", "command": f"bash {STATUSLINE_SCRIPT}"}
            statusline_installed = True

        if injected or statusline_installed:
            settings_path.write_text(json.dumps(current, indent=2))

        return {"hooks": "injected" if injected else "already-present",
                "events": injected, "statusline": statusline_installed,
                "path": str(settings_path)}
    except Exception as e:
        return {"hooks": "error", "reason": str(e)}


def inject_compact_recovery(workdir: str, document: str) -> dict[str, Any]:
    """Merge Claude Code compact recovery into <workdir>/.claude/settings.json."""
    try:
        from lib import compact_recovery

        wd = Path(workdir)
        if not wd.is_dir():
            return {"hooks": "skipped", "reason": f"workdir not a dir: {workdir}"}
        doc = Path(document).expanduser()
        result = compact_recovery.write_claude_compact_recovery_settings(wd, doc)
        return {
            "hooks": "injected" if result.get("changed") else "already-present",
            "event": "SessionStart",
            "matcher": "compact",
            **result,
        }
    except Exception as e:
        return {"hooks": "error", "reason": str(e)}
