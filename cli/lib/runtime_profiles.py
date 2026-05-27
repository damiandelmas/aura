"""Shared runtime-profile substrate for Aura runtime adapters.

Runtime profiles are identity/config references.  Runtime boxes are the
materialized per-seat filesystem sandboxes used at launch time.  This module
keeps those concepts separate so adapters can support native profile systems
such as Hermes without copying homes, while boxed runtimes such as Codex/OMX
can still use safe reusable templates.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

from lib import runtime_boxes


class RuntimeProfileKind(str, Enum):
    """How a runtime implements or consumes a profile reference."""

    NATIVE_REF = "native-ref"
    BOXED_TEMPLATE = "boxed-template"
    BOXED_HOME = "boxed-home"
    BOXED_XDG_HOME = "boxed-xdg-home"
    LAUNCH_PRESET = "launch-preset"
    INVENTORY_ONLY = "inventory-only"


@dataclass(frozen=True)
class RuntimeProfileRef:
    """Canonical runtime/profile reference such as ``codex/dev``."""

    runtime: str
    profile: str

    @property
    def canonical(self) -> str:
        return f"{self.runtime}/{self.profile}"


@dataclass(frozen=True)
class RuntimeBoxDescriptor:
    """Adapter-neutral description of a materialized runtime box."""

    runtime: str
    root: Path
    native_state_ref: Path | None = None
    profile_ref: RuntimeProfileRef | None = None
    kind: RuntimeProfileKind | None = None

    def metadata(self) -> dict[str, object]:
        return {
            "runtime_box_runtime": self.runtime,
            "runtime_box_root": str(self.root),
            **({"native_state_ref": str(self.native_state_ref)} if self.native_state_ref else {}),
            **({"runtime_profile_ref": self.profile_ref.canonical} if self.profile_ref else {}),
            **({"runtime_profile_kind": self.kind.value} if self.kind else {}),
        }


@dataclass(frozen=True)
class RuntimeAdapterDescriptor:
    """Read-only adapter metadata used by docs, tests, and inspect surfaces."""

    runtime: str
    kind: RuntimeProfileKind
    supports_box: bool
    supports_native_profile: bool = False
    notes: str = ""

    def metadata(self) -> dict[str, object]:
        return {
            "runtime": self.runtime,
            "runtime_profile_kind": self.kind.value,
            "runtime_profile_supports_box": self.supports_box,
            "runtime_profile_supports_native_profile": self.supports_native_profile,
            **({"runtime_profile_notes": self.notes} if self.notes else {}),
        }


@dataclass(frozen=True)
class TemplateSafetyFinding:
    """One unsafe path discovered in a reusable runtime-profile template."""

    path: str
    reason: str


class TemplateSafetyError(ValueError):
    """Raised when profile template material is unsafe to seed into a box."""

    def __init__(self, findings: list[TemplateSafetyFinding]):
        self.findings = findings
        details = ", ".join(f"{finding.path}: {finding.reason}" for finding in findings)
        prefix = (
            "runtime profile template symlink rejected"
            if any(finding.reason == "symlink" for finding in findings)
            else "unsafe runtime profile template material rejected"
        )
        super().__init__(f"{prefix}: {details}")


_DENIED_EXACT_FILENAMES = {
    ".env",
    ".env.local",
    ".envrc",
    "auth.json",
    "credentials.json",
    "secrets.json",
    "secret.json",
    "token.json",
    "tokens.json",
    "opencode.db",
    "sessions.db",
    "history",
}

_DENIED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
    ".sqlite-wal",
    ".sqlite-shm",
    ".wal",
    ".shm",
    ".jsonl",
    ".log",
    ".history",
}

_DENIED_COMPONENTS = {
    "log",
    "logs",
    "cache",
    "caches",
    "lock",
    "locks",
    "state",
    "states",
    "session",
    "sessions",
    "transcript",
    "transcripts",
    "history",
    "histories",
    "metrics",
    "backup",
    "backups",
    "generated",
    "__pycache__",
}

_DENIED_NAME_TOKENS = (
    "api_key",
    "apikey",
    "auth",
    "credential",
    "credentials",
    "oauth",
    "secret",
    "token",
    "update-check",
)


def normalize_runtime_profile_ref(
    ref: str,
    *,
    expected_runtime: str | None = None,
) -> RuntimeProfileRef:
    """Normalize and validate a runtime-profile ref.

    Refs are logical identifiers, never path fragments.  Bare profile names
    must be expanded by callers that already know the selected runtime.
    """

    raw = str(ref or "").strip()
    if not raw:
        raise ValueError("runtime profile ref is required")
    parts = [part.strip() for part in raw.split("/")]
    if len(parts) != 2:
        raise ValueError("runtime profile ref must use <runtime>/<profile>, e.g. codex/dev")
    runtime, profile = parts
    runtime = runtime_boxes.validate_logical_segment(runtime, label="runtime profile runtime")
    profile = runtime_boxes.validate_logical_segment(profile, label="runtime profile name")
    if expected_runtime and runtime != expected_runtime:
        raise ValueError(
            f"runtime profile {raw!r} is for {runtime}, not selected runtime {expected_runtime}"
        )
    return RuntimeProfileRef(runtime=runtime, profile=profile)


def classify_runtime_profile_adapter(runtime: str) -> RuntimeAdapterDescriptor:
    """Return the atlas-backed profile adapter classification for a runtime."""

    runtime = runtime_boxes.validate_logical_segment(runtime, label="runtime")
    classifications = {
        "hermes": RuntimeAdapterDescriptor(
            runtime="hermes",
            kind=RuntimeProfileKind.NATIVE_REF,
            supports_box=False,
            supports_native_profile=True,
            notes="Hermes profiles are native runtime homes; Aura stores refs.",
        ),
        "codex": RuntimeAdapterDescriptor(
            runtime="codex",
            kind=RuntimeProfileKind.BOXED_TEMPLATE,
            supports_box=True,
            notes="Codex uses Aura-boxed CODEX_HOME templates.",
        ),
        "omx": RuntimeAdapterDescriptor(
            runtime="omx",
            kind=RuntimeProfileKind.BOXED_TEMPLATE,
            supports_box=True,
            notes="OMX uses a dedicated boxed Codex/OMX adapter.",
        ),
        "opencode": RuntimeAdapterDescriptor(
            runtime="opencode",
            kind=RuntimeProfileKind.BOXED_XDG_HOME,
            supports_box=True,
            notes="Future adapter: boxed HOME/XDG plus OPENCODE_CONFIG.",
        ),
        "claude-code": RuntimeAdapterDescriptor(
            runtime="claude-code",
            kind=RuntimeProfileKind.BOXED_HOME,
            supports_box=True,
            notes="Future adapter; mutable profile creation deferred pending dogfood.",
        ),
        "goose": RuntimeAdapterDescriptor(
            runtime="goose",
            kind=RuntimeProfileKind.BOXED_XDG_HOME,
            supports_box=True,
            notes="Future ACP-oriented boxed XDG launch preset.",
        ),
        "aider": RuntimeAdapterDescriptor(
            runtime="aider",
            kind=RuntimeProfileKind.LAUNCH_PRESET,
            supports_box=False,
            notes="Future explicit config/history launch preset.",
        ),
    }
    return classifications.get(
        runtime,
        RuntimeAdapterDescriptor(
            runtime=runtime,
            kind=RuntimeProfileKind.INVENTORY_ONLY,
            supports_box=False,
        ),
    )


def _relative_template_path(root: Path, candidate: Path) -> PurePosixPath | None:
    try:
        return PurePosixPath(candidate.relative_to(root).as_posix())
    except ValueError:
        return None


def _deny_reason_for_relative_path(relative: PurePosixPath) -> str | None:
    parts = [part.lower() for part in relative.parts]
    name = parts[-1] if parts else ""
    if any(part in {"", ".", ".."} for part in parts):
        return "unsafe-path"
    if any(part in _DENIED_COMPONENTS for part in parts):
        return "runtime-generated"
    if any(name.endswith(suffix) for suffix in _DENIED_SUFFIXES):
        return "database" if any(db in name for db in (".db", ".sqlite", ".wal", ".shm")) else "history"
    if name in _DENIED_EXACT_FILENAMES:
        if any(token in name for token in ("auth", "credential", "secret", "token", "env")):
            return "secret"
        return "runtime-state"
    if any(token in name for token in _DENIED_NAME_TOKENS):
        return "secret"
    return None


def scan_template_safety(source: Path) -> list[TemplateSafetyFinding]:
    """Return unsafe paths in a runtime profile template without mutating it."""

    source = Path(source)
    findings: list[TemplateSafetyFinding] = []
    if source.is_symlink():
        return [TemplateSafetyFinding(path=str(source), reason="symlink")]
    if not source.exists():
        return []
    if not source.is_dir():
        return [TemplateSafetyFinding(path=str(source), reason="not-directory")]

    root = source.resolve(strict=False)
    for current_root, dirs, files in os.walk(source, followlinks=False):
        current = Path(current_root)
        candidates = [current / dirname for dirname in dirs] + [current / filename for filename in files]
        for candidate in candidates:
            relative = _relative_template_path(source, candidate)
            path_label = relative.as_posix() if relative else str(candidate)
            if candidate.is_symlink():
                findings.append(TemplateSafetyFinding(path=path_label, reason="symlink"))
                continue
            resolved_parent = candidate.parent.resolve(strict=False)
            if not str(resolved_parent).startswith(str(root)):
                findings.append(TemplateSafetyFinding(path=path_label, reason="unsafe-path"))
                continue
            if relative is None:
                findings.append(TemplateSafetyFinding(path=path_label, reason="unsafe-path"))
                continue
            reason = _deny_reason_for_relative_path(relative)
            if reason:
                findings.append(TemplateSafetyFinding(path=path_label, reason=reason))
    return findings


def validate_template_safety(source: Path) -> None:
    """Raise when a reusable runtime-profile template contains unsafe material."""

    findings = scan_template_safety(source)
    if findings:
        raise TemplateSafetyError(findings)
