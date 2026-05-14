"""Aura-managed Codex runtime boxes.

Plain Codex remains unboxed by default.  This adapter is used only when an
explicit Aura runtime-profile/boxed request asks for isolated Codex HOME and
CODEX_HOME values.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from lib import runtime_boxes


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
            "codex_box_auth_seeded": self.auth_seeded,
            "codex_box_config_seeded": self.config_seeded,
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
    source = _source_codex_home()
    auth_seeded = False
    config_seeded = False
    for name in ("auth.json", "credentials.json"):
        auth_seeded = _copy_if_present(source / name, codex_home / name, replace=True) or auth_seeded
    config_seeded = _copy_if_present(source / "config.toml", codex_home / "config.toml", replace=False)
    return auth_seeded, config_seeded


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
    auth_seeded, config_seeded = _seed_codex_home(codex_home)

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
    )
