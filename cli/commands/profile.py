"""Runtime profile inventory and Aura-owned boxed-template management."""

from __future__ import annotations

from pathlib import Path

from lib import runtime_bases, runtime_boxes, runtime_profiles

SUPPORTED_CREATE_RUNTIMES = {"codex", "omx"}
PROFILE_SCHEMAS = {
    "list": "aura.profile.list.v1",
    "inspect": "aura.profile.inspect.v1",
    "create": "aura.profile.create.v1",
    "error": "aura.profile.error.v1",
}
FUTURE_RUNTIMES = ("opencode", "claude-code", "goose", "aider")
KNOWN_RUNTIMES = ("codex", "omx", "hermes", *FUTURE_RUNTIMES)


def _error(code: str, detail: str, **extra) -> dict[str, object]:
    return {"ok": False, "schema": PROFILE_SCHEMAS["error"], "error": code, "detail": detail, **extra}


def _runtime_profile_root(runtime: str, profile: str) -> Path:
    if runtime == "codex":
        return runtime_boxes.runtime_profile_root("codex", profile)
    if runtime == "omx":
        return runtime_boxes.runtime_profile_root("omx", profile, legacy_omx=True)
    if runtime == "hermes":
        if profile == "default":
            return (Path.home() / ".hermes").resolve()
        return (Path.home() / ".hermes" / "profiles" / profile).resolve()
    raise ValueError(f"runtime profile unsupported for {runtime}")


def _profile_parent(runtime: str) -> Path:
    if runtime == "codex":
        return runtime_boxes.runtime_profile_root("codex", "__placeholder__").parent
    if runtime == "omx":
        return runtime_boxes.runtime_profile_root("omx", "__placeholder__", legacy_omx=True).parent
    if runtime == "hermes":
        return (Path.home() / ".hermes" / "profiles").resolve()
    raise ValueError(f"runtime profile unsupported for {runtime}")


def _profile_ref(raw: str, *, expected_runtime: str | None = None) -> runtime_profiles.RuntimeProfileRef:
    if expected_runtime and "/" not in raw:
        raw = f"{expected_runtime}/{raw}"
    return runtime_profiles.normalize_runtime_profile_ref(raw, expected_runtime=expected_runtime)


def _adapter_row(runtime: str) -> dict[str, object]:
    desc = runtime_profiles.classify_runtime_profile_adapter(runtime)
    return {
        "runtime": runtime,
        "kind": desc.kind.value,
        "supports_box": desc.supports_box,
        "supports_native_profile": desc.supports_native_profile,
        "create_supported": runtime in SUPPORTED_CREATE_RUNTIMES,
        "notes": desc.notes,
    }


def _safe_counts(root: Path) -> dict[str, int]:
    files = 0
    directories = 0
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_dir():
                directories += 1
            elif path.is_file():
                files += 1
    return {"files": files, "directories": directories}


def _safety_rows(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not root.exists():
        return rows
    for finding in runtime_profiles.scan_template_safety(root):
        rows.append({"path": finding.path, "reason": finding.reason})
    return rows


def _template_rows(runtime: str, root: Path) -> list[dict[str, object]]:
    names = runtime_bases.template_names(runtime) if runtime in SUPPORTED_CREATE_RUNTIMES else ()
    rows: list[dict[str, object]] = []
    for name in names:
        template_root = root / name
        rows.append(
            {
                "name": name,
                "path": str(template_root),
                "exists": template_root.is_dir(),
                **_safe_counts(template_root),
                "safety_findings": _safety_rows(template_root),
            }
        )
    return rows


def _profile_row(runtime: str, profile: str, root: Path) -> dict[str, object]:
    desc = runtime_profiles.classify_runtime_profile_adapter(runtime)
    return {
        "runtime": runtime,
        "profile": profile,
        "ref": f"{runtime}/{profile}",
        "kind": desc.kind.value,
        "root": str(root),
        "exists": root.is_dir(),
        "create_supported": runtime in SUPPORTED_CREATE_RUNTIMES,
    }


def _list_profiles(args) -> dict[str, object]:
    runtimes = [args.runtime] if args.runtime else ["codex", "omx", "hermes"]
    profiles: list[dict[str, object]] = []
    for runtime in runtimes:
        runtime = runtime_boxes.validate_logical_segment(runtime, label="runtime")
        if runtime not in KNOWN_RUNTIMES:
            return _error("invalid-runtime", f"unknown runtime: {runtime}")
        if runtime in FUTURE_RUNTIMES:
            continue
        parent = _profile_parent(runtime)
        if runtime == "hermes":
            root = _runtime_profile_root(runtime, "default")
            if root.is_dir():
                profiles.append(_profile_row(runtime, "default", root))
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir(), key=lambda p: p.name):
            if child.is_dir() and runtime_boxes.is_safe_logical_segment(child.name):
                profiles.append(_profile_row(runtime, child.name, child))
    classifications = [_adapter_row(rt) for rt in (KNOWN_RUNTIMES if args.include_future else runtimes)]
    return {"ok": True, "schema": PROFILE_SCHEMAS["list"], "profiles": profiles, "classifications": classifications}


def _inspect_profile(args) -> dict[str, object]:
    try:
        ref = _profile_ref(args.profile_ref, expected_runtime=args.runtime)
    except ValueError as exc:
        return _error("invalid-profile-ref", str(exc))
    if ref.runtime in FUTURE_RUNTIMES:
        return _error("runtime-profile-not-supported", f"{ref.runtime} profile inspect is not implemented yet", classification=_adapter_row(ref.runtime))
    if ref.runtime not in {"codex", "omx", "hermes"}:
        return _error("invalid-runtime", f"unknown runtime: {ref.runtime}")
    root = _runtime_profile_root(ref.runtime, ref.profile)
    if not root.is_dir():
        return _error("profile-not-found", f"runtime profile not found: {root}", expected_root=str(root), ref=ref.canonical)
    row = _profile_row(ref.runtime, ref.profile, root)
    row["classification"] = _adapter_row(ref.runtime)
    if ref.runtime in SUPPORTED_CREATE_RUNTIMES:
        row["templates"] = _template_rows(ref.runtime, root)
        row["safety_findings"] = _safety_rows(root)
    else:
        row["native_profile"] = True
        row["contents_redacted"] = True
    return {"ok": True, "schema": PROFILE_SCHEMAS["inspect"], "profile": row}


def _create_profile(args) -> dict[str, object]:
    try:
        ref = _profile_ref(args.profile_ref, expected_runtime=args.runtime)
    except ValueError as exc:
        return _error("invalid-profile-ref", str(exc))
    if ref.runtime not in KNOWN_RUNTIMES:
        return _error("invalid-runtime", f"unknown runtime: {ref.runtime}")
    if ref.runtime not in SUPPORTED_CREATE_RUNTIMES:
        return _error("profile-create-unsupported", f"Aura-owned profile create is not supported for {ref.runtime}", classification=_adapter_row(ref.runtime))
    root = _runtime_profile_root(ref.runtime, ref.profile)
    source_profile_ref = getattr(args, "source_profile", None)
    preset = getattr(args, "preset", None)
    try:
        source_ref = None
        source_root = None
        if source_profile_ref:
            source_ref = _profile_ref(source_profile_ref, expected_runtime=ref.runtime)
            source_root = _runtime_profile_root(source_ref.runtime, source_ref.profile)
            expected_parent = _profile_parent(ref.runtime).resolve()
            resolved_source_root = source_root.resolve(strict=False)
            if resolved_source_root.parent != expected_parent:
                return _error(
                    "invalid-source-profile",
                    "source profile must resolve under the Aura-owned profile root",
                    source_profile_ref=source_ref.canonical,
                    source_root=str(source_root),
                    expected_parent=str(expected_parent),
                )
            if not source_root.is_dir():
                return _error("source-profile-not-found", f"source runtime profile not found: {source_root}", source_profile_ref=source_ref.canonical)
            applied, templates, preset_result = runtime_bases.create_profile_from_profile(
                ref.runtime,
                source_root,
                root,
                description=args.description,
                preset=preset,
            )
        else:
            applied, templates, preset_result = runtime_bases.create_profile_from_base(
                ref.runtime,
                root,
                description=args.description,
                preset=preset,
            )
    except FileExistsError as exc:
        return _error("profile-exists", str(exc), ref=ref.canonical, root=str(root))
    except runtime_profiles.TemplateSafetyError as exc:
        return _error("unsafe-template", str(exc), findings=[finding.__dict__ for finding in exc.findings])
    except ValueError as exc:
        return _error("invalid-profile-create", str(exc), ref=ref.canonical, root=str(root))
    return {
        "ok": True,
        "schema": PROFILE_SCHEMAS["create"],
        "profile": _profile_row(ref.runtime, ref.profile, root),
        "created": True,
        **({"source_profile_ref": source_ref.canonical, "source_profile_root": str(source_root)} if source_profile_ref and source_ref and source_root else {}),
        "base_ref": f"{ref.runtime}/default",
        "base_root": str(runtime_bases.runtime_base_root(ref.runtime)),
        "templates_applied": list(templates),
        "preset": preset_result.get("preset"),
        "skills_source": preset_result.get("skills_source"),
        "skills_applied": preset_result.get("skills_applied", []),
        "skills_missing": preset_result.get("skills_missing", []),
        "applied": applied,
        "warnings": ["Aura profile templates do not include auth, sessions, logs, histories, or user-global config."],
    }


def run(args):
    action = getattr(args, "profile_action", None)
    try:
        if action == "list":
            return _list_profiles(args)
        if action == "inspect":
            return _inspect_profile(args)
        if action == "create":
            return _create_profile(args)
    except Exception as exc:
        return _error("profile-command-failed", str(exc))
    return _error("profile-command-invalid", f"unknown profile action: {action}")
