"""Aura-owned runtime base templates for boxed runtimes.

Runtime bases are clean, reusable behavior/config seeds owned by Aura. They are
not user-global runtime homes. Live runtime boxes may copy auth from the user's
native home, but config/hooks/skills/status behavior should come from these
Aura-owned bases or explicit Aura-owned profile templates.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from lib import runtime_boxes, runtime_profiles, state

SUPPORTED_BASE_RUNTIMES = {"codex", "claude-code"}

# Per-runtime reusable-template layout. Codex boxes three dirs (HOME / CODEX_HOME
# / runtime root); a claude box is a single CLAUDE_CONFIG_DIR, so its profile is
# one template dir copied into the seat's .claude.
_TEMPLATE_NAMES = {
    "codex": ("home-template", "codex-home-template", "runtime-template"),
    "claude-code": ("claude-home-template",),
}
# Where a profile's skill preset lands inside the template, and which skill home
# it is sourced from, per runtime.
_SKILL_TEMPLATE_DIR = {
    "codex": "codex-home-template",
    "claude-code": "claude-home-template",
}

AURA_OPERATOR_SKILL_ALLOWLIST = (
    "aura",
    "aura-bridge",
    "aura-broadcast",
    "aura-crew",
    "aura-event",
    "aura-flex",
    "aura-inspect",
    "aura-operations",
    "aura-operator",
    "aura-queue",
    "aura-report",
    "aura-self-bind",
    "aura-send",
    "aura-view",
    "desks",
    "desks-memory",
    "desks-open-manifest",
    "desks-operator",
    "desks-state",
)

SUPPORTED_PROFILE_PRESETS = {"aura-operator": AURA_OPERATOR_SKILL_ALLOWLIST}

CODEX_DEFAULT_CONFIG = """# Aura-owned boxed Codex runtime base.
# This file intentionally avoids copying ~/.codex/config.toml so boxed Codex
# seats do not inherit global/user behavior accidentally.
[tui]
status_line = ["model-with-reasoning", "git-branch", "current-dir", "session-id"]
"""

# Aura-owned boxed Claude Code runtime base. A minimal settings.json seed; the
# spawn-time box-prep merges the statusline FK-writer + lifecycle hooks and the
# onboarding flags on top, so this only carries reusable behavior, never auth or
# session state.
CLAUDE_DEFAULT_SETTINGS = (
    '{\n'
    '  "permissions": {\n'
    '    "defaultMode": "bypassPermissions"\n'
    '  }\n'
    '}\n'
)


def _validate_supported_runtime(runtime: str) -> str:
    runtime = runtime_boxes.validate_logical_segment(runtime, label="runtime base runtime")
    if runtime not in SUPPORTED_BASE_RUNTIMES:
        raise ValueError(f"runtime base unsupported for {runtime}")
    return runtime


def runtime_base_root(runtime: str, base: str = "default") -> Path:
    runtime = _validate_supported_runtime(runtime)
    base = runtime_boxes.validate_logical_segment(base, label="runtime base name")
    return state.state_root() / "runtime-bases" / runtime / base


def template_names(runtime: str) -> tuple[str, ...]:
    runtime = _validate_supported_runtime(runtime)
    return _TEMPLATE_NAMES[runtime]


def template_mappings(runtime: str, *, home: Path, codex_home: Path, runtime_root: Path | None = None) -> dict[str, Path]:
    runtime = _validate_supported_runtime(runtime)
    if runtime_root is None:
        raise ValueError("codex runtime base requires runtime_root")
    return {
        "home-template": home,
        "codex-home-template": codex_home,
        "runtime-template": runtime_root,
    }


def _write_default_files(root: Path, runtime: str) -> None:
    for dirname in template_names(runtime):
        (root / dirname).mkdir(parents=True, exist_ok=True)
    if runtime == "codex":
        config_path = root / "codex-home-template" / "config.toml"
        if not config_path.exists():
            config_path.write_text(CODEX_DEFAULT_CONFIG, encoding="utf-8")
    elif runtime == "claude-code":
        settings_path = root / "claude-home-template" / "settings.json"
        if not settings_path.exists():
            settings_path.write_text(CLAUDE_DEFAULT_SETTINGS, encoding="utf-8")


def validate_runtime_base(root: Path, runtime: str) -> list[runtime_profiles.TemplateSafetyFinding]:
    findings: list[runtime_profiles.TemplateSafetyFinding] = []
    for dirname in template_names(runtime):
        findings.extend(runtime_profiles.scan_template_safety(root / dirname))
    if findings:
        raise runtime_profiles.TemplateSafetyError(findings)
    return findings


def validate_profile_source(root: Path, runtime: str) -> list[runtime_profiles.TemplateSafetyFinding]:
    """Validate an Aura-owned profile source before cloning any material."""

    _validate_supported_runtime(runtime)
    findings = runtime_profiles.scan_template_safety(root)
    if findings:
        raise runtime_profiles.TemplateSafetyError(findings)
    return findings


def _cleanup_staging(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _staging_root(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex}"


def _publish_staging(staging: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"runtime profile already exists: {destination}")
    staging.replace(destination)


def _copy_tree_no_replace_or_raise(source: Path, destination: Path) -> bool:
    """Copy a safe template tree, rejecting destination collisions."""

    if not source.is_dir():
        return False
    runtime_profiles.validate_template_safety(source)
    copied_any = False
    destination.mkdir(parents=True, exist_ok=True)
    for current_root, dirs, files in os.walk(source, followlinks=False):
        current = Path(current_root)
        relative = current.relative_to(source)
        target_dir = destination / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for dirname in dirs:
            target = target_dir / dirname
            if target.exists() and not target.is_dir():
                raise FileExistsError(f"runtime profile template destination exists: {target}")
            target.mkdir(exist_ok=True)
        for filename in files:
            src = current / filename
            dst = target_dir / filename
            if dst.exists():
                raise FileExistsError(f"runtime profile template destination exists: {dst}")
            shutil.copy2(src, dst)
            copied_any = True
    return copied_any


def _skill_source_root(runtime: str = "codex") -> Path:
    import os

    override = os.environ.get("AURA_PROFILE_SKILLS_SOURCE")
    if override:
        return Path(override).expanduser()
    home_dir = ".claude" if runtime == "claude-code" else ".codex"
    return (Path.home() / home_dir / "skills").expanduser()


def seed_profile_preset(runtime: str, profile_root: Path, preset: str | None) -> dict[str, object]:
    """Seed a deterministic skill preset into a staged profile root."""

    if not preset:
        return {"preset": None, "skills_applied": [], "skills_missing": []}
    if preset not in SUPPORTED_PROFILE_PRESETS:
        raise ValueError(f"unknown runtime profile preset: {preset}")
    runtime = _validate_supported_runtime(runtime)
    source_root = _skill_source_root(runtime)
    destination_root = profile_root / _SKILL_TEMPLATE_DIR[runtime] / "skills"
    destination_root.mkdir(parents=True, exist_ok=True)

    applied: list[str] = []
    missing: list[str] = []
    for skill_name in SUPPORTED_PROFILE_PRESETS[preset]:
        source = source_root / skill_name
        if not (source / "SKILL.md").is_file():
            missing.append(skill_name)
            continue
        destination = destination_root / skill_name
        if destination.exists():
            raise FileExistsError(f"runtime profile skill destination exists: {destination}")
        _copy_tree_no_replace_or_raise(source, destination)
        applied.append(skill_name)

    validate_runtime_base(profile_root, runtime)
    return {
        "preset": preset,
        "skills_source": str(source_root),
        "skills_applied": applied,
        "skills_missing": missing,
    }


def ensure_default_runtime_base(runtime: str) -> Path:
    runtime = _validate_supported_runtime(runtime)
    root = runtime_base_root(runtime)
    _write_default_files(root, runtime)
    validate_runtime_base(root, runtime)
    return root


def apply_default_runtime_base(runtime: str, mappings: dict[str, Path]) -> tuple[Path, bool, tuple[str, ...]]:
    root = ensure_default_runtime_base(runtime)
    applied, names = runtime_boxes.apply_templates(root, mappings)
    return root, applied, names


def create_profile_from_base(
    runtime: str,
    profile_root: Path,
    *,
    description: str | None = None,
    preset: str | None = None,
) -> tuple[bool, tuple[str, ...], dict[str, object]]:
    """Create an Aura-owned reusable profile template from the default base.

    Existing profiles are never overwritten by this helper.
    """

    runtime = _validate_supported_runtime(runtime)
    if profile_root.exists():
        raise FileExistsError(f"runtime profile already exists: {profile_root}")
    base_root = ensure_default_runtime_base(runtime)
    staging = _staging_root(profile_root)
    try:
        staging.mkdir(parents=True, exist_ok=False)
        mappings = {dirname: staging / dirname for dirname in template_names(runtime)}
        applied, names = runtime_boxes.apply_templates(base_root, mappings)
        # Ensure empty template directories exist even when no files were copied.
        for dirname in template_names(runtime):
            (staging / dirname).mkdir(parents=True, exist_ok=True)
        if description:
            (staging / "README.md").write_text(
                f"# {runtime} profile\n\n{description.strip()}\n",
                encoding="utf-8",
            )
        preset_result = seed_profile_preset(runtime, staging, preset)
        validate_runtime_base(staging, runtime)
        _publish_staging(staging, profile_root)
        return applied, names, preset_result
    except Exception:
        _cleanup_staging(staging)
        raise


def create_profile_from_profile(
    runtime: str,
    source_root: Path,
    profile_root: Path,
    *,
    description: str | None = None,
    preset: str | None = None,
) -> tuple[bool, tuple[str, ...], dict[str, object]]:
    """Create a reusable profile by cloning another Aura-owned profile."""

    runtime = _validate_supported_runtime(runtime)
    if profile_root.exists():
        raise FileExistsError(f"runtime profile already exists: {profile_root}")
    if not source_root.is_dir():
        raise FileNotFoundError(f"runtime profile source does not exist: {source_root}")
    validate_profile_source(source_root, runtime)
    staging = _staging_root(profile_root)
    try:
        staging.mkdir(parents=True, exist_ok=False)
        applied: list[str] = []
        for dirname in template_names(runtime):
            if _copy_tree_no_replace_or_raise(source_root / dirname, staging / dirname):
                applied.append(dirname)
            (staging / dirname).mkdir(parents=True, exist_ok=True)
        readme = source_root / "README.md"
        if readme.is_file():
            shutil.copy2(readme, staging / "README.md")
        if description:
            (staging / "README.md").write_text(
                f"# {runtime} profile\n\n{description.strip()}\n",
                encoding="utf-8",
            )
        preset_result = seed_profile_preset(runtime, staging, preset)
        validate_runtime_base(staging, runtime)
        _publish_staging(staging, profile_root)
        return bool(applied), tuple(applied), preset_result
    except Exception:
        _cleanup_staging(staging)
        raise
