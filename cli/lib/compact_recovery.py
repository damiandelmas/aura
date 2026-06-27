"""Runtime compact-recovery helpers for Aura-managed agents."""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any


MARKER = "AURA_COMPACT_RECOVERY"
DEFAULT_DOC_NAME = "AURA_COMPACT_RECOVERY.md"


def first_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def recovery_document_path(*, runtime_home: Path | None = None) -> Path | None:
    explicit = first_string(os.environ.get("AURA_COMPACT_RECOVERY_DOC"))
    if explicit:
        return Path(explicit).expanduser()
    if runtime_home:
        return runtime_home / DEFAULT_DOC_NAME
    codex_home = first_string(os.environ.get("CODEX_HOME"))
    if codex_home:
        return Path(codex_home).expanduser() / DEFAULT_DOC_NAME
    return None


def read_recovery_document(path: Path | None) -> tuple[Path | None, str]:
    if not path:
        return None, ""
    try:
        return path, path.read_text(encoding="utf-8")
    except OSError:
        return path, ""


def render_recovery_context(
    *,
    document_path: Path | None,
    document_text: str,
    runtime: str,
    compact_summary: str | None = None,
) -> str:
    path_text = str(document_path) if document_path else "<none>"
    parts = [
        f"{MARKER}",
        "",
        f"Runtime: {runtime}",
        f"Required recovery document: {path_text}",
        "",
        "A compaction just completed. Treat this as required recovery context before continuing work.",
    ]
    if compact_summary:
        parts.extend(["", "Compact summary:", compact_summary.strip()])
    if document_text.strip():
        parts.extend(["", "Recovery document:", document_text.strip()])
    else:
        parts.extend(["", "Recovery document was not readable from the configured path."])
    return "\n".join(parts).strip() + "\n"


def claude_compact_recovery_command(document_path: Path, *, aura_root: Path | None = None) -> str:
    root = aura_root or Path(__file__).resolve().parents[1]
    hook = root / "hooks" / "aura_compact_recovery_hook.py"
    return (
        f"AURA_COMPACT_RECOVERY_DOC={shlex.quote(str(document_path))} "
        f"{shlex.quote(os.environ.get('PYTHON', 'python3'))} {shlex.quote(str(hook))} ClaudeCompact"
    )


def merge_claude_compact_recovery_settings(
    current: dict[str, Any],
    *,
    document_path: Path,
    command: str | None = None,
) -> tuple[dict[str, Any], bool]:
    next_settings = dict(current) if isinstance(current, dict) else {}
    hooks = next_settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        next_settings["hooks"] = hooks
    entries = hooks.setdefault("SessionStart", [])
    if not isinstance(entries, list):
        entries = []
        hooks["SessionStart"] = entries

    hook_command = command or claude_compact_recovery_command(document_path)
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("matcher") != "compact":
            continue
        handlers = entry.get("hooks") if isinstance(entry.get("hooks"), list) else []
        if any(isinstance(hook, dict) and hook.get("command") == hook_command for hook in handlers):
            return next_settings, False

    entries.append({
        "matcher": "compact",
        "hooks": [{
            "type": "command",
            "command": hook_command,
            "timeout": 30,
        }],
    })
    return next_settings, True


def write_claude_compact_recovery_settings(workdir: Path, document_path: Path) -> dict[str, object]:
    settings_dir = workdir / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"
    current: dict[str, Any] = {}
    if settings_path.exists():
        try:
            parsed = json.loads(settings_path.read_text(encoding="utf-8"))
            current = parsed if isinstance(parsed, dict) else {}
        except Exception:
            current = {}
    merged, changed = merge_claude_compact_recovery_settings(current, document_path=document_path)
    if changed or not settings_path.exists():
        settings_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "path": str(settings_path),
        "document": str(document_path),
        "changed": changed,
    }
