"""Shared filesystem helpers for Aura-managed runtime boxes.

Runtime boxes are per-seat runtime homes prepared by Aura so project
directories remain work surfaces, not runtime profile stores.  This module
intentionally owns only boring filesystem mechanics; runtime adapters still
own command semantics, setup, auth seeding, and environment variables.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from lib import state


def safe_segment(value: str) -> str:
    """Return a filesystem-safe path segment for runtime/fleet/seat/profile ids."""

    segment = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "")).strip(".-")
    return segment or "unknown"


def is_safe_logical_segment(value: str) -> bool:
    """Return true when ``value`` is already one safe logical id segment."""

    raw = str(value or "").strip()
    if not raw or raw in {".", ".."}:
        return False
    if raw.startswith(("/", "\\")) or "/" in raw or "\\" in raw:
        return False
    return safe_segment(raw) == raw


def validate_logical_segment(value: str, *, label: str = "segment") -> str:
    """Return a logical id segment or raise before it becomes a filesystem path."""

    raw = str(value or "").strip()
    if not is_safe_logical_segment(raw):
        raise ValueError(f"{label} must be a single safe logical segment")
    return raw


def runtime_home_root(
    runtime: str,
    fleet: str,
    seat: str,
    *,
    legacy_omx: bool = False,
) -> Path:
    """Return the Aura-owned per-seat runtime home root.

    New boxed runtimes use ``runtime-homes/<runtime>/<fleet>/<seat>``.  OMX
    keeps its historical ``omx-homes/<fleet>/<seat>`` path until a separate
    migration explicitly changes that operator contract.
    """

    if legacy_omx and runtime == "omx":
        return state.state_root() / "omx-homes" / safe_segment(fleet) / safe_segment(seat)
    return (
        state.state_root()
        / "runtime-homes"
        / safe_segment(runtime)
        / safe_segment(fleet)
        / safe_segment(seat)
    )


def runtime_profile_root(runtime: str, profile: str, *, legacy_omx: bool = False) -> Path:
    """Return the reusable runtime profile template root."""

    if legacy_omx and runtime == "omx":
        return state.state_root() / "omx-profiles" / safe_segment(profile)
    return state.state_root() / "runtime-profiles" / safe_segment(runtime) / safe_segment(profile)


def validate_no_symlinks(source: Path) -> None:
    """Reject symlinks in a profile template before any copy occurs."""

    from lib import runtime_profiles

    findings = [
        finding
        for finding in runtime_profiles.scan_template_safety(source)
        if finding.reason == "symlink"
    ]
    if findings:
        raise ValueError(f"runtime profile template symlink rejected: {source / findings[0].path}")


def copy_template_tree_no_replace(source: Path, destination: Path) -> bool:
    """Copy template contents without overwriting existing runtime-home files."""

    from lib import runtime_profiles

    if not source.is_dir():
        return False
    runtime_profiles.validate_template_safety(source)
    copied_any = False
    destination.mkdir(parents=True, exist_ok=True)
    for current_root, dirs, files in os.walk(source):
        current = Path(current_root)
        relative = current.relative_to(source)
        target_dir = destination / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for dirname in dirs:
            (target_dir / dirname).mkdir(exist_ok=True)
        for filename in files:
            src = current / filename
            dst = target_dir / filename
            if dst.exists():
                continue
            shutil.copy2(src, dst)
            copied_any = True
    return copied_any


def apply_templates(profile_root: Path, mappings: dict[str, Path]) -> tuple[bool, tuple[str, ...]]:
    """Apply named template directories into destination roots.

    All existing template directories are symlink-validated before any file is
    copied.  This prevents a later unsafe template from being discovered only
    after earlier template files have already been copied.
    """

    from lib import runtime_profiles

    for dirname in mappings:
        source = profile_root / dirname
        if source.exists() or source.is_symlink():
            runtime_profiles.validate_template_safety(source)

    applied: list[str] = []
    for dirname, destination in mappings.items():
        if copy_template_tree_no_replace(profile_root / dirname, destination):
            applied.append(dirname)
    return bool(applied), tuple(applied)
