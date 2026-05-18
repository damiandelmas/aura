"""Aura-managed OMX seat boxing.

OMX is a Codex wrapper with setup-owned hooks, skills, prompts, and runtime
state. Aura's default OMX runtime must not install those files into the project
cwd, because later non-OMX Codex seats in the same folder would inherit them.

This module prepares a per-seat OMX/Codex home under Aura state and returns the
environment needed to run OMX against the requested project cwd without
mutating that cwd.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lib import omx_adapter, runtime_bases, runtime_boxes


SETUP_MARKER = "aura-omx-box.json"


@dataclass(frozen=True)
class OmxBox:
    root: Path
    home: Path
    codex_home: Path
    omx_root: Path
    omx_state: Path
    omx_team_state_root: Path
    runtime: Path
    setup_ran: bool
    auth_seeded: bool
    config_seeded: bool
    profile: str | None = None
    profile_root: Path | None = None
    profile_applied: bool = False
    profile_templates_applied: tuple[str, ...] = ()
    base_root: Path | None = None
    base_applied: bool = False
    base_templates_applied: tuple[str, ...] = ()
    setup_skipped: bool = False
    setup_error: str | None = None
    star_prompt_preseeded: bool = False
    source_cwd_trusted: bool = False
    adapter: omx_adapter.OmxAdapterResult | None = None

    def launch_env(self, source_cwd: str) -> dict[str, str]:
        env = {
            "HOME": str(self.home),
            "CODEX_HOME": str(self.codex_home),
            # Upstream OMX stores actual state under "$OMX_ROOT/.omx".
            "OMX_ROOT": str(self.omx_root),
            "OMX_TEAM_STATE_ROOT": str(self.omx_team_state_root),
            "OMX_LAUNCH_POLICY": "direct",
            "OMXBOX_ACTIVE": "1",
            # Aura owns update cadence/readiness for managed seats; interactive
            # update prompts make `aura spawn --wait` report a live but unusable
            # pane and also write update-check state into the source cwd.
            "OMX_AUTO_UPDATE": "0",
            # Native Codex hooks still run from hooks.json.  The polling fallback
            # is a best-effort compatibility watcher and currently writes some
            # authority state under the source cwd; keep Aura-managed boxes clean.
            "OMX_NOTIFY_FALLBACK": "0",
            "OMX_SOURCE_CWD": source_cwd,
            "AURA_OMX_BOX": str(self.root),
            "PATH": omx_adapter.adapter_path_prefix(self.runtime),
        }
        if self.profile:
            env["AURA_OMX_PROFILE"] = self.profile
        return env

    def metadata(self) -> dict[str, object]:
        return {
            "omx_isolation": "aura-seat-box",
            "omx_box_root": str(self.root),
            "omx_box_home": str(self.home),
            "omx_box_codex_home": str(self.codex_home),
            "omx_box_omx_root": str(self.omx_root),
            "omx_box_omx_state": str(self.omx_state),
            "omx_box_team_state_root": str(self.omx_team_state_root),
            "omx_box_runtime": str(self.runtime),
            "omx_box_behavior_source": "aura-runtime-base",
            **({"omx_box_base_root": str(self.base_root)} if self.base_root else {}),
            "omx_box_base_applied": self.base_applied,
            "omx_box_base_templates_applied": list(self.base_templates_applied),
            "omx_box_setup_ran": self.setup_ran,
            "omx_box_setup_skipped": self.setup_skipped,
            "omx_box_auth_seeded": self.auth_seeded,
            "omx_box_config_seeded": self.config_seeded,
            "omx_box_star_prompt_preseeded": self.star_prompt_preseeded,
            "omx_box_source_cwd_trusted": self.source_cwd_trusted,
            **(self.adapter.metadata() if self.adapter else {"omx_adapter_enabled": False}),
            **({"omx_profile": self.profile} if self.profile else {}),
            **({"omx_profile_root": str(self.profile_root)} if self.profile_root else {}),
            "omx_profile_applied": self.profile_applied,
            "omx_profile_templates_applied": list(self.profile_templates_applied),
            **({"omx_box_setup_error": self.setup_error} if self.setup_error else {}),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def box_root(fleet: str, seat: str) -> Path:
    return runtime_boxes.runtime_home_root("omx", fleet, seat, legacy_omx=True)


def profile_root(profile: str) -> Path:
    return runtime_boxes.runtime_profile_root("omx", profile, legacy_omx=True)


def _source_codex_home() -> Path:
    raw = os.environ.get("AURA_OMX_SOURCE_CODEX_HOME") or os.environ.get("CODEX_HOME")
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


def _apply_profile_template(profile: str | None, *, home: Path, codex_home: Path, omx_root: Path) -> tuple[Path | None, bool, tuple[str, ...]]:
    """Apply an explicit reusable OMX profile template into a per-seat box.

    Profiles are opt-in templates under ~/.aura/omx-profiles/<profile>/.
    They seed a seat-local box; they are not shared mutable runtime homes.
    """
    if not profile:
        return None, False, ()
    root = profile_root(profile)
    if not root.is_dir():
        raise FileNotFoundError(f"omx profile not found: {root}")
    profile_applied, templates_applied = runtime_boxes.apply_templates(
        root,
        {
            "home-template": home,
            "codex-home-template": codex_home,
            "omx-root-template": omx_root,
        },
    )
    return root, profile_applied, templates_applied


def _seed_codex_home(codex_home: Path) -> tuple[bool, bool]:
    """Seed auth only; boxed OMX behavior comes from Aura bases/templates."""

    source = _source_codex_home()
    auth_seeded = False
    for name in ("auth.json", "credentials.json"):
        auth_seeded = _copy_if_present(source / name, codex_home / name, replace=True) or auth_seeded
    return auth_seeded, False


def _toml_quoted_key(value: str) -> str:
    # TOML quoted keys use the same string escaping needed for JSON strings for
    # ordinary filesystem paths.  json.dumps also keeps spaces and punctuation
    # safe inside [projects."..."] table headers.
    return json.dumps(value)


def _preseed_star_prompt(home: Path) -> bool:
    """Mark OMX's one-time GitHub star prompt as already seen for this box."""

    path = home / ".omx" / "state" / "star-prompt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"prompted_at": _now_iso()}, indent=2) + "\n", encoding="utf-8")
    return True


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
    """Return ancestor project roots that contain project-local Codex config."""

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
    """Pre-trust the operator-selected cwd and effective Codex project root."""

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
    if changed:
        config_path.write_text(existing, encoding="utf-8")
    return True


def _has_setup(codex_home: Path) -> bool:
    return all(
        path.exists()
        for path in (
            codex_home / "AGENTS.md",
            codex_home / "config.toml",
            codex_home / "hooks.json",
            codex_home / "skills",
            codex_home / "agents",
        )
    )


def _setup_disabled() -> bool:
    value = os.environ.get("AURA_OMX_BOX_SETUP", "1").strip().lower()
    return value in {"0", "false", "no", "off", "skip"}


def _run_setup(root: Path, home: Path, codex_home: Path, omx_root: Path, runtime: Path) -> None:
    env = {
        **os.environ,
        "HOME": str(home),
        "CODEX_HOME": str(codex_home),
        "OMX_ROOT": str(omx_root),
        "OMX_LAUNCH_POLICY": "direct",
        "OMXBOX_ACTIVE": "1",
        "OMX_AUTO_UPDATE": "0",
        "OMX_NOTIFY_FALLBACK": "0",
    }
    result = subprocess.run(
        [
            "omx",
            "setup",
            "--scope",
            "user",
            "--force",
            "--install-mode",
            "legacy",
            "--mcp",
            "none",
        ],
        cwd=str(runtime),
        env=env,
        text=True,
        capture_output=True,
        timeout=float(os.environ.get("AURA_OMX_BOX_SETUP_TIMEOUT", "45")),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"omx setup failed with exit code {result.returncode}")
    marker = {
        "schema": "aura.omx_box.v1",
        "created_at": _now_iso(),
        "root": str(root),
        "home": str(home),
        "codex_home": str(codex_home),
        "omx_root": str(omx_root),
        "omx_state": str(omx_root / ".omx"),
        "runtime": str(runtime),
    }
    (root / SETUP_MARKER).write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare_box(
    *,
    fleet: str,
    seat: str,
    source_cwd: str,
    profile: str | None = None,
    root_override: Path | str | None = None,
    package_layout: bool = False,
) -> OmxBox:
    """Create and initialize the per-seat OMX box.

    The project cwd is intentionally *not* used as CODEX_HOME or OMX_ROOT.
    """
    root = Path(root_override).expanduser().resolve() if root_override else box_root(fleet, seat)
    home = root / "home"
    codex_home = root / ".codex" if package_layout else root / "codex-home"
    # When package_layout is enabled, OMX_ROOT is the package root because
    # upstream OMX stores runtime state under "$OMX_ROOT/.omx".
    omx_root = root if package_layout else root / "omx-root"
    omx_state = omx_root / ".omx"
    omx_team_state_root = omx_state / "state"
    runtime = root / "runtime"
    for path in (home, codex_home, omx_root, omx_team_state_root, runtime):
        path.mkdir(parents=True, exist_ok=True)

    profile_path, profile_applied, profile_templates_applied = _apply_profile_template(
        profile,
        home=home,
        codex_home=codex_home,
        omx_root=omx_root,
    )
    base_path, base_applied, base_templates_applied = runtime_bases.apply_default_runtime_base(
        "omx",
        runtime_bases.template_mappings(
            "omx",
            home=home,
            codex_home=codex_home,
            omx_root=omx_root,
        ),
    )
    auth_seeded, config_seeded = _seed_codex_home(codex_home)
    already_ready = _has_setup(codex_home)
    force_setup = os.environ.get("AURA_OMX_BOX_FORCE_SETUP", "").strip().lower() in {"1", "true", "yes", "on"}
    setup_ran = False
    setup_skipped = False
    setup_error = None
    star_prompt_preseeded = _preseed_star_prompt(home)
    setup_disabled = _setup_disabled()
    if setup_disabled:
        setup_skipped = True
    elif force_setup or not already_ready:
        try:
            _run_setup(root, home, codex_home, omx_root, runtime)
            setup_ran = True
            # setup may refresh config.toml; re-apply box-local prompt/trust
            # preseed after it writes managed config.
            star_prompt_preseeded = _preseed_star_prompt(home)
        except Exception as exc:  # pragma: no cover - exercised through caller error path.
            setup_error = str(exc)
            raise

    source_cwd_trusted = _trust_source_cwd(codex_home, source_cwd)
    adapter_result = omx_adapter.apply_adapter(root=root, codex_home=codex_home, runtime=runtime)
    if adapter_result.error and not setup_disabled:
        raise RuntimeError(f"omx adapter failed: {adapter_result.error}")

    return OmxBox(
        root=root,
        home=home,
        codex_home=codex_home,
        omx_root=omx_root,
        omx_state=omx_state,
        omx_team_state_root=omx_team_state_root,
        runtime=runtime,
        setup_ran=setup_ran,
        auth_seeded=auth_seeded,
        config_seeded=config_seeded,
        profile=profile,
        profile_root=profile_path,
        profile_applied=profile_applied,
        profile_templates_applied=profile_templates_applied,
        base_root=base_path,
        base_applied=base_applied,
        base_templates_applied=base_templates_applied,
        setup_skipped=setup_skipped,
        setup_error=setup_error,
        star_prompt_preseeded=star_prompt_preseeded,
        source_cwd_trusted=source_cwd_trusted,
        adapter=adapter_result,
    )
