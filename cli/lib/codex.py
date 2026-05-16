"""Aura-managed Codex runtime boxes.

Plain Codex remains unboxed by default.  This adapter is used only when an
explicit Aura runtime-profile/boxed request asks for isolated Codex HOME and
CODEX_HOME values.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lib import runtime_bases, runtime_boxes


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

    def launch_env(self, source_cwd: str) -> dict[str, str]:
        env = {
            "HOME": str(self.home),
            "CODEX_HOME": str(self.codex_home),
            "AURA_CODEX_BOX": str(self.root),
            "AURA_CODEX_SOURCE_CWD": source_cwd,
        }
        if self.profile:
            env["AURA_CODEX_PROFILE"] = self.profile
        return env

    def metadata(self) -> dict[str, object]:
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
    if destination.exists() and not replace:
        return True
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    try:
        os.chmod(destination, source.stat().st_mode & 0o777)
    except OSError:
        pass
    return True


def _seed_codex_home(codex_home: Path) -> tuple[bool, bool]:
    """Seed auth only from the user's native Codex home.

    Boxed runtime behavior must come from Aura-owned bases/profile templates,
    not from ~/.codex/config.toml. Returning config_seeded=False preserves the
    existing metadata field while making the auth-only boundary explicit.
    """

    source = _source_codex_home()
    auth_seeded = False
    for name in ("auth.json", "credentials.json"):
        auth_seeded = _copy_if_present(source / name, codex_home / name, replace=True) or auth_seeded
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

def _apply_profile_template(
    profile: str | None,
    *,
    home: Path,
    codex_home: Path,
    runtime: Path,
) -> tuple[Path | None, bool, tuple[str, ...]]:
    if not profile:
        return None, False, ()
    root = profile_root(profile)
    if not root.is_dir():
        raise FileNotFoundError(f"codex runtime profile not found: {root}")
    profile_applied, templates_applied = runtime_boxes.apply_templates(
        root,
        {
            "home-template": home,
            "codex-home-template": codex_home,
            "runtime-template": runtime,
        },
    )
    return root, profile_applied, templates_applied


def prepare_box(*, fleet: str, seat: str, source_cwd: str, profile: str | None = None) -> CodexBox:
    """Create a per-seat Codex box without mutating the project cwd."""

    root = box_root(fleet, seat)
    home = root / "home"
    codex_home = root / "codex-home"
    runtime = root / "runtime"
    for path in (home, codex_home, runtime):
        path.mkdir(parents=True, exist_ok=True)

    profile_path, profile_applied, profile_templates_applied = _apply_profile_template(
        profile,
        home=home,
        codex_home=codex_home,
        runtime=runtime,
    )
    base_path, base_applied, base_templates_applied = runtime_bases.apply_default_runtime_base(
        "codex",
        runtime_bases.template_mappings(
            "codex",
            home=home,
            codex_home=codex_home,
            runtime_root=runtime,
        ),
    )
    auth_seeded, config_seeded = _seed_codex_home(codex_home)
    source_cwd_trusted = _trust_source_cwd(codex_home, source_cwd)

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
    )
