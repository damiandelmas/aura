"""Aura-owned compatibility adapter for boxed OMX seats.

The adapter lives outside the installed oh-my-codex package.  Its job is not to
reimplement OMX; it keeps Aura-managed seat boxes work-ready even when an OMX
install refreshes its Codex hook command paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HOOKS_FILE = "hooks.json"
CONFIG_FILE = "config.toml"
ADAPTER_MARKER = "aura-omx-adapter.json"
WRAPPER_NAME = "aura-omx-native-hook"
TRUST_BLOCK_START = "# Aura OMX adapter-owned Codex hook trust state"
TRUST_BLOCK_END = "# End Aura OMX adapter-owned Codex hook trust state"
LEGACY_TRUST_BLOCK_START = "# OMX-owned Codex hook trust state"
LEGACY_TRUST_BLOCK_END = "# End OMX-owned Codex hook trust state"

MANAGED_HOOK_EVENTS: dict[str, str] = {
    "SessionStart": "session_start",
    "PreToolUse": "pre_tool_use",
    "PostToolUse": "post_tool_use",
    "UserPromptSubmit": "user_prompt_submit",
    "PreCompact": "pre_compact",
    "PostCompact": "post_compact",
    "Stop": "stop",
}


@dataclass(frozen=True)
class OmxAdapterResult:
    enabled: bool
    wrapper_path: Path | None = None
    native_hook_path: Path | None = None
    hooks_rewritten: bool = False
    trust_state_updated: bool = False
    config_trust_updated: bool = False
    native_probe: str = "skipped"
    hud_probe: str = "skipped"
    error: str | None = None

    def metadata(self) -> dict[str, object]:
        return {
            "omx_adapter_enabled": self.enabled,
            **({"omx_adapter_wrapper": str(self.wrapper_path)} if self.wrapper_path else {}),
            **({"omx_adapter_native_hook": str(self.native_hook_path)} if self.native_hook_path else {}),
            "omx_adapter_hooks_rewritten": self.hooks_rewritten,
            "omx_adapter_trust_state_updated": self.trust_state_updated,
            "omx_adapter_config_trust_updated": self.config_trust_updated,
            "omx_adapter_native_probe": self.native_probe,
            "omx_adapter_hud_probe": self.hud_probe,
            **({"omx_adapter_error": self.error} if self.error else {}),
        }


def adapter_bin_dir(runtime: Path) -> Path:
    return runtime / "bin"


def wrapper_path(runtime: Path) -> Path:
    return adapter_bin_dir(runtime) / WRAPPER_NAME


def adapter_path_prefix(runtime: Path, current_path: str | None = None) -> str:
    current = current_path if current_path is not None else os.environ.get("PATH", "")
    adapter_bin = str(adapter_bin_dir(runtime))
    return adapter_bin if not current else f"{adapter_bin}:{current}"


def _is_omx_native_hook_command(command: str, wrapper: Path | None = None) -> bool:
    if wrapper and command.strip() == shlex.quote(str(wrapper)):
        return True
    return "codex-native-hook.js" in command or WRAPPER_NAME in command


def _extract_native_hook_command(hooks_config: dict[str, Any]) -> tuple[str, Path] | None:
    hooks = hooks_config.get("hooks")
    if not isinstance(hooks, dict):
        return None
    for event_name in MANAGED_HOOK_EVENTS:
        entries = hooks.get(event_name)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks") or []:
                if not isinstance(hook, dict):
                    continue
                command = hook.get("command")
                if not isinstance(command, str) or "codex-native-hook.js" not in command:
                    continue
                parts = shlex.split(command)
                for part in parts:
                    if part.endswith("codex-native-hook.js"):
                        return command, Path(part)
    return None


def _read_marker_native_hook(root: Path) -> Path | None:
    marker_path = root / ADAPTER_MARKER
    if not marker_path.is_file():
        return None
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    native_hook = marker.get("native_hook") if isinstance(marker, dict) else None
    if isinstance(native_hook, str) and native_hook.strip():
        return Path(native_hook)
    return None


def _write_native_hook_wrapper(path: Path, *, node_path: str, native_hook_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bind_hook_path = Path(__file__).resolve().parents[1] / "hooks" / "codex_bind_hook.py"
    script = f"""#!/usr/bin/env bash
set -euo pipefail
export OMX_NOTIFY_FALLBACK="${{OMX_NOTIFY_FALLBACK:-0}}"
payload_file="$(mktemp -t aura-omx-hook.XXXXXX)"
trap 'rm -f "$payload_file"' EXIT
cat > "$payload_file"
{shlex.quote(shutil.which("python3") or "python3")} {shlex.quote(str(bind_hook_path))} < "$payload_file" >/dev/null 2>&1 || true
exec {shlex.quote(node_path)} {shlex.quote(str(native_hook_path))} < "$payload_file"
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _canonical_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical_json(item) for item in value]
    return value


def _trusted_hash(identity: dict[str, Any]) -> str:
    raw = json.dumps(_canonical_json(identity), separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _command_hook_identity(event_name: str, entry: dict[str, Any], hook: dict[str, Any]) -> dict[str, Any]:
    hook_identity: dict[str, Any] = {
        "type": "command",
        "command": hook["command"],
        "timeout": max(1, int(hook.get("timeout", 600))),
        "async": False,
    }
    if "statusMessage" in hook:
        hook_identity["statusMessage"] = hook["statusMessage"]
    identity: dict[str, Any] = {
        "event_name": MANAGED_HOOK_EVENTS[event_name],
        "hooks": [hook_identity],
    }
    if entry.get("matcher"):
        identity["matcher"] = entry["matcher"]
    return identity


def _trust_state_key(hooks_path: Path, event_name: str, group_index: int, handler_index: int) -> str:
    return f"{hooks_path}:{MANAGED_HOOK_EVENTS[event_name]}:{group_index}:{handler_index}"


def _rewrite_hooks_config(
    hooks_path: Path,
    wrapper: Path,
    *,
    fallback_native_hook_path: Path | None = None,
) -> tuple[Path | None, bool, bool, dict[str, str]]:
    if not hooks_path.is_file():
        return None, False, False, {}
    parsed = json.loads(hooks_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"invalid OMX hooks config: {hooks_path}")
    extracted = _extract_native_hook_command(parsed)
    if not extracted and fallback_native_hook_path is None:
        return None, False, False, {}
    if extracted:
        command, native_hook_path = extracted
        parts = shlex.split(command)
        node_path = parts[0] if parts else shutil.which("node") or "node"
    else:
        native_hook_path = fallback_native_hook_path
        node_path = shutil.which("node") or "node"
    _write_native_hook_wrapper(wrapper, node_path=node_path, native_hook_path=native_hook_path)
    wrapper_command = shlex.quote(str(wrapper))

    hooks = parsed.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"invalid hooks object in {hooks_path}")
    rewritten = False
    managed_trust: dict[str, str] = {}
    for event_name in MANAGED_HOOK_EVENTS:
        entries = hooks.get(event_name)
        if not isinstance(entries, list):
            continue
        for group_index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            handlers = entry.get("hooks")
            if not isinstance(handlers, list):
                continue
            for handler_index, hook in enumerate(handlers):
                if not isinstance(hook, dict) or hook.get("type") != "command":
                    continue
                command_value = hook.get("command")
                if not isinstance(command_value, str):
                    continue
                if not _is_omx_native_hook_command(command_value, wrapper):
                    continue
                if command_value != wrapper_command:
                    hook["command"] = wrapper_command
                    rewritten = True
                key = _trust_state_key(hooks_path, event_name, group_index, handler_index)
                managed_trust[key] = _trusted_hash(_command_hook_identity(event_name, entry, hook))

    if not managed_trust:
        return native_hook_path, rewritten, False, {}
    existing_state = parsed.get("state") if isinstance(parsed.get("state"), dict) else {}
    next_state = {
        key: value
        for key, value in existing_state.items()
        if not (isinstance(key, str) and key.startswith(f"{hooks_path}:"))
    }
    for key, trusted_hash in managed_trust.items():
        previous = next_state.get(key) if isinstance(next_state.get(key), dict) else {}
        next_state[key] = {**previous, "trusted_hash": trusted_hash}
    parsed["state"] = next_state
    hooks_path.write_text(json.dumps(parsed, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return native_hook_path, rewritten, True, managed_trust


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_trust_toml(managed_trust: dict[str, str]) -> str:
    lines = [TRUST_BLOCK_START]
    for key in sorted(managed_trust):
        lines.append(f'[hooks.state."{_toml_escape(key)}"]')
        lines.append(f'trusted_hash = "{_toml_escape(managed_trust[key])}"')
        lines.append("")
    lines.append(TRUST_BLOCK_END)
    return "\n".join(lines).rstrip() + "\n"


def _replace_marked_block(content: str, start_marker: str, end_marker: str, replacement: str) -> tuple[str, bool]:
    start = content.find(start_marker)
    if start < 0:
        return content, False
    end = content.find(end_marker, start)
    if end < 0:
        return content, False
    end += len(end_marker)
    if end < len(content) and content[end:end + 1] == "\n":
        end += 1
    prefix = content[:start].rstrip() + "\n\n" if content[:start].strip() else ""
    suffix = "\n" + content[end:].lstrip() if content[end:].strip() else ""
    return prefix + replacement.rstrip() + "\n" + suffix, True


def _update_config_trust_state(config_path: Path, managed_trust: dict[str, str]) -> bool:
    if not managed_trust:
        return False
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    block = _build_trust_toml(managed_trust)
    content, replaced = _replace_marked_block(existing, TRUST_BLOCK_START, TRUST_BLOCK_END, block)
    if not replaced:
        content, replaced = _replace_marked_block(content, LEGACY_TRUST_BLOCK_START, LEGACY_TRUST_BLOCK_END, block)
    if not replaced:
        separator = "" if not content or content.endswith("\n") else "\n"
        content = f"{content}{separator}\n{block}"
    if content != existing:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(content, encoding="utf-8")
        return True
    return False


def _probes_enabled() -> bool:
    value = os.environ.get("AURA_OMX_ADAPTER_PROBE", "1").strip().lower()
    return value not in {"0", "false", "no", "off", "skip"}


def _run_native_probe(wrapper: Path, runtime: Path) -> str:
    if not _probes_enabled():
        return "skipped"
    probe_root = Path(tempfile.mkdtemp(prefix="native-", dir=str(runtime)))
    try:
        source = probe_root / "source"
        home = probe_root / "home"
        codex_home = probe_root / "codex-home"
        omx_root = probe_root / "omx-root"
        for path in (source, home, codex_home, omx_root):
            path.mkdir(parents=True, exist_ok=True)
        git = shutil.which("git")
        if git:
            subprocess.run([git, "init", "-q"], cwd=str(source), check=True, timeout=5)
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "OMX_ROOT": str(omx_root),
            "OMX_TEAM_STATE_ROOT": str(omx_root / ".omx" / "state"),
            "OMX_NOTIFY_FALLBACK": "0",
        }
        payload = {
            "hook_event_name": "SessionStart",
            "cwd": str(source),
            "session_id": "aura-adapter-probe",
            "transcript_path": "",
            "source": "startup",
        }
        result = subprocess.run(
            [str(wrapper)],
            cwd=str(source),
            env=env,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=float(os.environ.get("AURA_OMX_ADAPTER_PROBE_TIMEOUT", "8")),
        )
        if result.returncode != 0:
            return f"failed:{(result.stderr or result.stdout).strip()[:240]}"
        if (source / ".omx").exists():
            return "failed:source-omx-created"
        exclude = source / ".git" / "info" / "exclude"
        if exclude.exists() and ".omx/" in exclude.read_text(encoding="utf-8", errors="ignore"):
            return "failed:source-git-exclude-mutated"
        if not (omx_root / ".omx" / "state" / "session.json").exists():
            return "failed:boxed-session-state-missing"
        return "passed"
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)


def _run_hud_probe(native_hook_path: Path, runtime: Path) -> str:
    if not _probes_enabled():
        return "skipped"
    package_root = native_hook_path.parent.parent.parent
    authority = package_root / "dist" / "hud" / "authority.js"
    if not authority.is_file():
        return "skipped:hud-authority-missing"
    probe_root = Path(tempfile.mkdtemp(prefix="hud-", dir=str(runtime)))
    try:
        source = probe_root / "source"
        omx_root = probe_root / "omx-root"
        source.mkdir(parents=True, exist_ok=True)
        omx_root.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "OMX_ROOT": str(omx_root), "OMX_NOTIFY_FALLBACK": "0"}
        code = "\n".join([
            f"import {{ runHudAuthorityTick }} from {json.dumps(authority.as_uri())};",
            "await runHudAuthorityTick({ cwd: process.argv[1], timeoutMs: 1000 }, { runProcess: async () => {} });",
        ])
        result = subprocess.run(
            [shutil.which("node") or "node", "--input-type=module", "-e", code, str(source)],
            cwd=str(source),
            env=env,
            text=True,
            capture_output=True,
            timeout=float(os.environ.get("AURA_OMX_ADAPTER_PROBE_TIMEOUT", "8")),
        )
        if result.returncode != 0:
            return f"failed:{(result.stderr or result.stdout).strip()[:240]}"
        if (source / ".omx").exists():
            return "failed:source-omx-created"
        if not (omx_root / ".omx" / "state" / "notify-fallback-authority-owner.json").exists():
            return "failed:boxed-hud-authority-missing"
        return "passed"
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)


def apply_adapter(*, root: Path, codex_home: Path, runtime: Path) -> OmxAdapterResult:
    """Install Aura's boxed OMX adapter into a prepared seat box."""

    hooks_path = codex_home / HOOKS_FILE
    config_path = codex_home / CONFIG_FILE
    path = wrapper_path(runtime)
    try:
        native_hook_path, hooks_rewritten, trust_updated, managed_trust = _rewrite_hooks_config(
            hooks_path,
            path,
            fallback_native_hook_path=_read_marker_native_hook(root),
        )
        if not native_hook_path:
            return OmxAdapterResult(enabled=False, error="native OMX hook not found in boxed hooks.json")
        config_updated = _update_config_trust_state(config_path, managed_trust)
        native_probe = _run_native_probe(path, runtime)
        hud_probe = _run_hud_probe(native_hook_path, runtime)
        if native_probe.startswith("failed") or hud_probe.startswith("failed"):
            raise RuntimeError(f"OMX adapter probe failed: native={native_probe}; hud={hud_probe}")
        marker = {
            "schema": "aura.omx_adapter.v1",
            "wrapper": str(path),
            "native_hook": str(native_hook_path),
            "hooks_rewritten": hooks_rewritten,
            "trust_state_updated": trust_updated,
            "config_trust_updated": config_updated,
            "native_probe": native_probe,
            "hud_probe": hud_probe,
        }
        (root / ADAPTER_MARKER).write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return OmxAdapterResult(
            enabled=True,
            wrapper_path=path,
            native_hook_path=native_hook_path,
            hooks_rewritten=hooks_rewritten,
            trust_state_updated=trust_updated,
            config_trust_updated=config_updated,
            native_probe=native_probe,
            hud_probe=hud_probe,
        )
    except Exception as exc:
        return OmxAdapterResult(enabled=False, wrapper_path=path if path.exists() else None, error=str(exc))
