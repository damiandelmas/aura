"""Aura-managed Codex runtime boxes.

Plain Codex remains unboxed by default.  This adapter is used only when an
explicit Aura runtime-profile/boxed request asks for isolated Codex HOME and
CODEX_HOME values.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from hashlib import sha256

from lib import runtime_bases, runtime_boxes

HOOK_EVENT_STATE_LABELS: dict[str, str] = {
    "SessionStart": "session_start",
    "PreToolUse": "pre_tool_use",
    "PermissionRequest": "permission_request",
    "PostToolUse": "post_tool_use",
    "PreCompact": "pre_compact",
    "PostCompact": "post_compact",
    "UserPromptSubmit": "user_prompt_submit",
    "SubagentStart": "subagent_start",
    "SubagentStop": "subagent_stop",
    "Stop": "stop",
}

KEEPER_HOOK_EVENTS = ("Stop", "PreCompact")
KEEPER_HOOK_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class CodexBox:
    root: Path
    home: Path
    codex_home: Path
    runtime: Path
    auth_seeded: bool
    config_seeded: bool
    profile: str | None = None
    profile_root: Path | None = None
    profile_applied: bool = False
    profile_templates_applied: tuple[str, ...] = ()
    base_root: Path | None = None
    base_applied: bool = False
    base_templates_applied: tuple[str, ...] = ()
    source_cwd_trusted: bool = False
    aura_hook_installed: bool = False
    aura_hook_command: str | None = None
    aura_keeper_hook_installed: bool = False
    aura_keeper_hook_command: str | None = None
    package_layout: bool = False

    def launch_env(self, source_cwd: str) -> dict[str, str]:
        env = {
            "CODEX_HOME": str(self.codex_home),
            "AURA_CODEX_BOX": str(self.root),
            "AURA_CODEX_SOURCE_CWD": source_cwd,
        }
        if not self.package_layout:
            env["HOME"] = str(self.home)
        if self.profile:
            env["AURA_CODEX_PROFILE"] = self.profile
        return env

    def metadata(self) -> dict[str, object]:
        if self.package_layout:
            return {
                "codex_isolation": "aura-agent-package",
                "codex_package_root": str(self.root),
                "codex_package_codex_home": str(self.codex_home),
                "codex_runtime_base_source": "aura-runtime-base",
                **({"codex_runtime_base_root": str(self.base_root)} if self.base_root else {}),
                "codex_runtime_base_applied": self.base_applied,
                "codex_runtime_base_templates_applied": list(self.base_templates_applied),
                "codex_auth_source": "user-global-auth-only",
                "codex_auth_seeded": self.auth_seeded,
                "codex_config_seeded": self.config_seeded,
                "codex_source_cwd_trusted": self.source_cwd_trusted,
                "codex_aura_hook_installed": self.aura_hook_installed,
                **({"codex_aura_hook_command": self.aura_hook_command} if self.aura_hook_command else {}),
                "codex_aura_keeper_hook_installed": self.aura_keeper_hook_installed,
                **({"codex_aura_keeper_hook_command": self.aura_keeper_hook_command} if self.aura_keeper_hook_command else {}),
                **({"codex_profile": self.profile} if self.profile else {}),
                **({"codex_profile_root": str(self.profile_root)} if self.profile_root else {}),
                "codex_profile_applied": self.profile_applied,
                "codex_profile_templates_applied": list(self.profile_templates_applied),
            }
        return {
            "codex_isolation": "aura-seat-box",
            "codex_box_root": str(self.root),
            "codex_box_home": str(self.home),
            "codex_box_codex_home": str(self.codex_home),
            "codex_box_runtime": str(self.runtime),
            "codex_box_behavior_source": "aura-runtime-base",
            **({"codex_box_base_root": str(self.base_root)} if self.base_root else {}),
            "codex_box_base_applied": self.base_applied,
            "codex_box_base_templates_applied": list(self.base_templates_applied),
            "codex_box_auth_source": "user-global-auth-only",
            "codex_box_auth_seeded": self.auth_seeded,
            "codex_box_config_seeded": self.config_seeded,
            "codex_box_source_cwd_trusted": self.source_cwd_trusted,
            "codex_box_aura_hook_installed": self.aura_hook_installed,
            **({"codex_box_aura_hook_command": self.aura_hook_command} if self.aura_hook_command else {}),
            "codex_box_aura_keeper_hook_installed": self.aura_keeper_hook_installed,
            **({"codex_box_aura_keeper_hook_command": self.aura_keeper_hook_command} if self.aura_keeper_hook_command else {}),
            **({"codex_profile": self.profile} if self.profile else {}),
            **({"codex_profile_root": str(self.profile_root)} if self.profile_root else {}),
            "codex_profile_applied": self.profile_applied,
            "codex_profile_templates_applied": list(self.profile_templates_applied),
        }


def box_root(fleet: str, seat: str) -> Path:
    return runtime_boxes.runtime_home_root("codex", fleet, seat)


def profile_root(profile: str) -> Path:
    return runtime_boxes.runtime_profile_root("codex", profile)


def _source_codex_home() -> Path:
    raw = os.environ.get("AURA_CODEX_SOURCE_CODEX_HOME") or os.environ.get("CODEX_HOME")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def _copy_if_present(source: Path, destination: Path, *, replace: bool = False) -> bool:
    if not source.is_file():
        return False
    if source.resolve() == destination.resolve():
        return True
    if destination.exists() and not replace:
        return True
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    try:
        os.chmod(destination, source.stat().st_mode & 0o777)
    except OSError:
        pass
    return True


def _backup_existing_auth(dest: Path) -> Path:
    """Move a stale regular auth file to .auth-backups/ before replacing it."""
    backup_dir = dest.parent / ".auth-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    target = backup_dir / f"{dest.name}.{stamp}"
    counter = 1
    while target.exists():
        target = backup_dir / f"{dest.name}.{stamp}.{counter}"
        counter += 1
    shutil.move(str(dest), str(target))
    return target


def _link_auth_file(src: Path, dest: Path) -> bool:
    """Symlink dest → src.  Archive a pre-existing regular file first.

    Returns True if dest points at src after the call (whether newly created
    or already correct), False if src does not exist.
    """
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        current = os.readlink(dest)
        if Path(current) == src:
            return True
        dest.unlink()
    elif dest.exists():
        try:
            if dest.samefile(src):
                return True
        except OSError:
            pass
        _backup_existing_auth(dest)
    dest.symlink_to(src)
    return True


def _seed_codex_home(codex_home: Path) -> tuple[bool, bool]:
    """Seed auth only from the user's native Codex home.

    Auth files (auth.json, credentials.json) are SYMLINKED so they stay fresh
    when the user's token refreshes.  Boxed runtime behavior must come from
    Aura-owned bases/profile templates, not from ~/.codex/config.toml.
    Returning config_seeded=False preserves the existing metadata field while
    making the auth-only boundary explicit.
    """

    source = _source_codex_home()
    auth_seeded = False
    for name in ("auth.json", "credentials.json"):
        auth_seeded = _link_auth_file(source / name, codex_home / name) or auth_seeded
    return auth_seeded, False




def _toml_quoted_key(value: str) -> str:
    return json.dumps(value)


def _git_toplevel(path: Path) -> Path | None:
    git = shutil.which("git")
    if not git:
        return None
    try:
        result = subprocess.run(
            [git, "-C", str(path), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return Path(value).expanduser().resolve() if value else None


def _codex_project_config_roots(path: Path) -> list[Path]:
    roots: list[Path] = []
    for candidate in (path, *path.parents):
        if (candidate / ".codex").is_dir():
            roots.append(candidate)
    return roots


def _trust_project_path(existing: str, path: Path) -> tuple[str, bool]:
    header = f"[projects.{_toml_quoted_key(str(path))}]"
    if header in existing:
        start = existing.index(header)
        next_table = existing.find("\n[", start + 1)
        block_end = next_table if next_table != -1 else len(existing)
        if 'trust_level = "trusted"' in existing[start:block_end]:
            return existing, False
    separator = "" if not existing or existing.endswith("\n") else "\n"
    return existing + f'{separator}\n{header}\ntrust_level = "trusted"\n', True


def _trust_source_cwd(codex_home: Path, source_cwd: str) -> bool:
    config_path = codex_home / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    cwd = Path(source_cwd).expanduser().resolve()
    trust_paths = [cwd]
    git_root = _git_toplevel(cwd)
    if git_root and git_root not in trust_paths:
        trust_paths.append(git_root)
    for config_root in _codex_project_config_roots(cwd):
        if config_root not in trust_paths:
            trust_paths.append(config_root)
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    changed = False
    for path in trust_paths:
        existing, path_changed = _trust_project_path(existing, path)
        changed = changed or path_changed
    if changed or not config_path.exists():
        config_path.write_text(existing, encoding="utf-8")
    return bool(trust_paths)


def _canonical_json(value: Any) -> Any:
    if isinstance(value, list):
        return [_canonical_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical_json(value[key]) for key in sorted(value)}
    return value


def _trusted_hash(value: dict[str, Any]) -> str:
    return "sha256:" + sha256(
        json.dumps(_canonical_json(value), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _append_trust_toml(config_path: Path, key: str, trusted_hash: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    header = f'[hooks.state.{json.dumps(key)}]'
    block = f'{header}\ntrusted_hash = "{trusted_hash}"\n'
    if header in existing:
        start = existing.index(header)
        next_table = existing.find("\n[", start + 1)
        end = next_table if next_table != -1 else len(existing)
        current = existing[start:end].strip()
        if f'trusted_hash = "{trusted_hash}"' in current:
            return
        suffix = existing[end:]
        if suffix.startswith("\n"):
            suffix = suffix[1:]
        separator = "\n" if end < len(existing) else ""
        config_path.write_text(f"{existing[:start]}{block}{separator}{suffix}", encoding="utf-8")
        return
    separator = "" if not existing or existing.endswith("\n") else "\n"
    config_path.write_text(f"{existing}{separator}\n{block}", encoding="utf-8")


def _command_hook_identity(event_name: str, entry: dict[str, Any], hook: dict[str, Any]) -> dict[str, Any] | None:
    command = hook.get("command")
    if hook.get("type") != "command" or not isinstance(command, str) or not command.strip():
        return None
    try:
        timeout = max(1, int(hook.get("timeout", 600)))
    except (TypeError, ValueError):
        timeout = 600
    hook_identity: dict[str, Any] = {
        "type": "command",
        "command": command,
        "timeout": timeout,
        "async": bool(hook.get("async", False)),
    }
    if "statusMessage" in hook:
        hook_identity["statusMessage"] = hook["statusMessage"]
    identity: dict[str, Any] = {
        "event_name": HOOK_EVENT_STATE_LABELS[event_name],
        "hooks": [hook_identity],
    }
    matcher = entry.get("matcher")
    if matcher:
        identity["matcher"] = matcher
    return identity


def _trust_state_key(hooks_path: Path, event_name: str, group_index: int, handler_index: int) -> str:
    return f"{hooks_path}:{HOOK_EVENT_STATE_LABELS[event_name]}:{group_index}:{handler_index}"


def _trust_boxed_command_hooks(codex_home: Path) -> dict[str, str]:
    """Trust command hooks already materialized in an Aura-owned Codex box.

    Boxed profiles are copied from Aura-owned templates after safety checks.
    Without pre-seeded trust, Codex pauses at the hook-review TUI before the
    first prompt, which makes automated Aura profile tests and workers stall.
    """

    hooks_path = codex_home / "hooks.json"
    if not hooks_path.is_file():
        return {}
    try:
        parsed = json.loads(hooks_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    hooks = parsed.get("hooks")
    if not isinstance(hooks, dict):
        return {}

    trusted: dict[str, str] = {}
    for event_name, entries in hooks.items():
        if event_name not in HOOK_EVENT_STATE_LABELS or not isinstance(entries, list):
            continue
        for group_index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            handlers = entry.get("hooks")
            if not isinstance(handlers, list):
                continue
            for handler_index, hook in enumerate(handlers):
                if not isinstance(hook, dict):
                    continue
                identity = _command_hook_identity(event_name, entry, hook)
                if identity is None:
                    continue
                key = _trust_state_key(hooks_path, event_name, group_index, handler_index)
                trusted[key] = _trusted_hash(identity)

    if not trusted:
        return {}
    state = parsed.setdefault("state", {})
    if not isinstance(state, dict):
        state = {}
        parsed["state"] = state
    for key, trusted_hash in trusted.items():
        previous = state.get(key) if isinstance(state.get(key), dict) else {}
        state[key] = {**previous, "trusted_hash": trusted_hash}
    _atomic_write_json(hooks_path, parsed)
    for key, trusted_hash in trusted.items():
        _append_trust_toml(codex_home / "config.toml", key, trusted_hash)
    return trusted


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _install_aura_session_hook(codex_home: Path) -> tuple[bool, str]:
    """Install the quiet Aura SessionStart binder into a boxed Codex home."""

    hook_script = Path(__file__).resolve().parents[1] / "hooks" / "codex_bind_hook.py"
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(hook_script))}"
    hooks_path = codex_home / "hooks.json"
    try:
        config = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    except Exception:
        config = {}
    if not isinstance(config, dict):
        config = {}
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        config["hooks"] = hooks
    entries = hooks.setdefault("SessionStart", [])
    if not isinstance(entries, list):
        entries = []
        hooks["SessionStart"] = entries

    hook_entry = {
        "matcher": "startup|resume|clear",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": 30,
            }
        ],
    }
    installed = any(
        isinstance(entry, dict)
        and any(
            isinstance(hook, dict)
            and hook.get("type") == "command"
            and str(hook.get("command") or "") == command
            for hook in (entry.get("hooks") if isinstance(entry.get("hooks"), list) else [])
        )
        for entry in entries
    )
    if not installed:
        entries.append(hook_entry)
        group_index = len(entries) - 1
    else:
        group_index = next(
            index
            for index, entry in enumerate(entries)
            if isinstance(entry, dict)
            and any(
                isinstance(hook, dict)
                and hook.get("type") == "command"
                and str(hook.get("command") or "") == command
                for hook in (entry.get("hooks") if isinstance(entry.get("hooks"), list) else [])
            )
        )
        hook_entry = entries[group_index]

    identity = {
        "event_name": "session_start",
        **({"matcher": hook_entry.get("matcher")} if isinstance(hook_entry, dict) and hook_entry.get("matcher") else {}),
        "hooks": [{
            "type": "command",
            "command": command,
            "timeout": 30,
            "async": False,
        }],
    }
    trust_key = f"{hooks_path}:session_start:{group_index}:0"
    trust_value = {"trusted_hash": _trusted_hash(identity)}
    state = config.setdefault("state", {})
    if not isinstance(state, dict):
        state = {}
        config["state"] = state
    state[trust_key] = trust_value
    _atomic_write_json(hooks_path, config)
    _append_trust_toml(codex_home / "config.toml", trust_key, trust_value["trusted_hash"])
    return True, command


def _find_command_entry(entries: list[Any], command: str) -> int | None:
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        handlers = entry.get("hooks")
        if not isinstance(handlers, list):
            continue
        if any(
            isinstance(hook, dict)
            and hook.get("type") == "command"
            and str(hook.get("command") or "") == command
            for hook in handlers
        ):
            return index
    return None


def _install_aura_keeper_hooks(codex_home: Path) -> tuple[bool, str]:
    """Install memory cadence hooks for package-backed Codex agents."""

    hook_script = Path(__file__).resolve().parents[1] / "hooks" / "aura_keeper_hook.py"
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(hook_script))}"
    hooks_path = codex_home / "hooks.json"
    try:
        config = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    except Exception:
        config = {}
    if not isinstance(config, dict):
        config = {}
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        config["hooks"] = hooks

    changed = False
    for event_name in KEEPER_HOOK_EVENTS:
        event_command = f"{command} {event_name}"
        entries = hooks.setdefault(event_name, [])
        if not isinstance(entries, list):
            entries = []
            hooks[event_name] = entries
            changed = True
        existing_index = _find_command_entry(entries, event_command)
        if existing_index is None:
            entries.append({
                "hooks": [
                    {
                        "type": "command",
                        "command": event_command,
                        "timeout": KEEPER_HOOK_TIMEOUT_SECONDS,
                    }
                ],
            })
            changed = True
        else:
            entry = entries[existing_index]
            handlers = entry.get("hooks") if isinstance(entry, dict) else None
            if isinstance(handlers, list):
                for hook in handlers:
                    if (
                        isinstance(hook, dict)
                        and hook.get("type") == "command"
                        and str(hook.get("command") or "") == event_command
                        and hook.get("timeout") != KEEPER_HOOK_TIMEOUT_SECONDS
                    ):
                        hook["timeout"] = KEEPER_HOOK_TIMEOUT_SECONDS
                        changed = True

    if changed or not hooks_path.exists():
        _atomic_write_json(hooks_path, config)
    return True, command


def install_aura_package_hooks(codex_home: Path) -> dict[str, object]:
    """Install Aura session and keeper hooks into a durable Codex home."""

    session_installed, session_command = _install_aura_session_hook(codex_home)
    keeper_installed, keeper_command = _install_aura_keeper_hooks(codex_home)
    trusted = _trust_boxed_command_hooks(codex_home)
    return {
        "ok": True,
        "codex_home": str(codex_home),
        "session_hook_installed": session_installed,
        "session_hook_command": session_command,
        "keeper_hook_installed": keeper_installed,
        "keeper_hook_command": keeper_command,
        "trusted_hooks": len(trusted),
    }


def _apply_profile_template(
    profile: str | None,
    *,
    home: Path,
    codex_home: Path,
    runtime: Path,
    package_layout: bool = False,
) -> tuple[Path | None, bool, tuple[str, ...]]:
    if not profile:
        return None, False, ()
    root = profile_root(profile)
    if not root.is_dir():
        raise FileNotFoundError(f"codex runtime profile not found: {root}")
    mappings = {"codex-home-template": codex_home}
    if not package_layout:
        mappings.update({"home-template": home, "runtime-template": runtime})
    profile_applied, templates_applied = runtime_boxes.apply_templates(root, mappings)
    return root, profile_applied, templates_applied


def prepare_box(
    *,
    fleet: str,
    seat: str,
    source_cwd: str,
    profile: str | None = None,
    root_override: Path | str | None = None,
    package_layout: bool = False,
) -> CodexBox:
    """Create a per-seat Codex box without mutating the project cwd."""

    root = Path(root_override).expanduser().resolve() if root_override else box_root(fleet, seat)
    home = root / "home"
    codex_home = root / ".codex" if package_layout else root / "codex-home"
    runtime = root / "runtime"
    paths = (codex_home,) if package_layout else (home, codex_home, runtime)
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)

    profile_path, profile_applied, profile_templates_applied = _apply_profile_template(
        profile,
        home=home,
        codex_home=codex_home,
        runtime=runtime,
        package_layout=package_layout,
    )
    base_mappings = {"codex-home-template": codex_home} if package_layout else runtime_bases.template_mappings(
        "codex",
        home=home,
        codex_home=codex_home,
        runtime_root=runtime,
    )
    base_path, base_applied, base_templates_applied = runtime_bases.apply_default_runtime_base(
        "codex",
        base_mappings,
    )
    auth_seeded, config_seeded = _seed_codex_home(codex_home)
    source_cwd_trusted = _trust_source_cwd(codex_home, source_cwd)
    if package_layout:
        hook_result = install_aura_package_hooks(codex_home)
        aura_hook_installed = bool(hook_result["session_hook_installed"])
        aura_hook_command = str(hook_result["session_hook_command"])
        aura_keeper_hook_installed = bool(hook_result["keeper_hook_installed"])
        aura_keeper_hook_command = (
            str(hook_result["keeper_hook_command"])
            if hook_result.get("keeper_hook_command")
            else None
        )
    else:
        aura_hook_installed, aura_hook_command = _install_aura_session_hook(codex_home)
        aura_keeper_hook_installed = False
        aura_keeper_hook_command = None
        _trust_boxed_command_hooks(codex_home)

    return CodexBox(
        root=root,
        home=home,
        codex_home=codex_home,
        runtime=runtime,
        auth_seeded=auth_seeded,
        config_seeded=config_seeded,
        profile=profile,
        profile_root=profile_path,
        profile_applied=profile_applied,
        profile_templates_applied=profile_templates_applied,
        base_root=base_path,
        base_applied=base_applied,
        base_templates_applied=base_templates_applied,
        source_cwd_trusted=source_cwd_trusted,
        aura_hook_installed=aura_hook_installed,
        aura_hook_command=aura_hook_command,
        aura_keeper_hook_installed=aura_keeper_hook_installed,
        aura_keeper_hook_command=aura_keeper_hook_command,
        package_layout=package_layout,
    )
