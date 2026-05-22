"""Aura package-local skill materialization.

This module owns the boring filesystem part of skill distribution: resolve a
canonical skill directory, project it into one Aura agent package's runtime home,
and record package-local provenance for doctor/sync/remove.  It intentionally
keeps fleet rollout and semantic skill discovery out of this layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import agent_packages


LOCK_SCHEMA = "aura.agent_skills_lock.v1"
PLAN_SCHEMA = "aura.skill_apply_plan.v1"
SUPPORTED_RUNTIMES = {"codex", "omx"}
VALID_MODES = {"symlink", "copy"}
UNSAFE_COMPONENTS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "cache",
    "caches",
    "log",
    "logs",
    "session",
    "sessions",
    "history",
    "histories",
    "backup",
    "backups",
    "state",
    "states",
}
UNSAFE_SUBSTRINGS = ("_archive", "_buffer", ".archive")
UNSAFE_NAME_TOKENS = ("auth", "credential", "credentials", "secret", "token", "api_key", "apikey")
UNSAFE_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".jsonl", ".log", ".history")


class SkillLibraryError(Exception):
    """Structured skill materialization error."""

    def __init__(self, code: str, detail: str, **extra: Any):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.extra = extra

    def to_dict(self) -> dict[str, Any]:
        return {"ok": False, "error": self.code, "detail": self.detail, **self.extra}


@dataclass(frozen=True)
class SkillSource:
    name: str
    description: str
    source_path: str
    resolved_path: str
    skill_file: str


@dataclass(frozen=True)
class LockEntry:
    name: str
    mode: str
    source_path: str
    resolved_path: str
    target_path: str
    owned: bool
    applied_at: str
    library: str | None = None
    provenance: str = "direct"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_name(value: str, *, label: str = "name") -> str:
    raw = str(value or "").strip()
    if not raw:
        raise SkillLibraryError("invalid-name", f"{label} is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}", raw):
        raise SkillLibraryError("invalid-name", f"{label} must be a safe logical segment", value=raw)
    return raw


def _unsafe_reason(path: Path) -> str | None:
    lowered = str(path).lower()
    for marker in UNSAFE_SUBSTRINGS:
        if marker in lowered:
            return f"unsafe substring: {marker}"
    for part in path.parts:
        lp = part.lower()
        if lp in UNSAFE_COMPONENTS:
            return f"unsafe component: {part}"
        if any(token in lp for token in UNSAFE_NAME_TOKENS):
            return f"unsafe name token: {part}"
    if path.suffix.lower() in UNSAFE_SUFFIXES:
        return f"unsafe suffix: {path.suffix}"
    return None


def _resolve_path(path: str | Path, *, label: str, unsafe_check: bool = True) -> Path:
    try:
        resolved = Path(path).expanduser().resolve(strict=False)
    except OSError as exc:
        raise SkillLibraryError("invalid-path", f"cannot resolve {label}: {path}: {exc}") from exc
    if unsafe_check:
        reason = _unsafe_reason(resolved)
        if reason:
            raise SkillLibraryError("unsafe-path", f"unsafe {label}: {resolved} ({reason})", path=str(resolved), reason=reason)
    return resolved


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    data: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in {"name", "description"}:
            data[key] = value
    return data, parts[2]


def _first_paragraph(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if not stripped:
            if lines:
                break
            continue
        lines.append(stripped)
    return " ".join(lines)[:300]


def _validate_skill_tree_safe(root: Path) -> None:
    for child in root.rglob("*"):
        rel = child.relative_to(root)
        reason = _unsafe_reason(rel)
        if reason:
            raise SkillLibraryError(
                "unsafe-path",
                f"unsafe skill content: {child} ({reason})",
                path=str(child),
                reason=reason,
            )
        if child.is_symlink():
            raise SkillLibraryError("unsafe-path", f"skill content symlink rejected: {child}", path=str(child), reason="symlink")


def resolve_skill_source(path: str | Path) -> SkillSource:
    source = Path(path).expanduser()
    resolved = _resolve_path(source, label="skill source", unsafe_check=True)
    if not resolved.is_dir():
        raise SkillLibraryError("skill-not-directory", f"skill source is not a directory: {resolved}", path=str(resolved))
    skill_file = resolved / "SKILL.md"
    if not skill_file.is_file():
        alt = resolved / "SKILLS.md"
        if alt.is_file():
            skill_file = alt
        else:
            raise SkillLibraryError(
                "skill-file-missing",
                f"skill source has no SKILL.md or SKILLS.md: {resolved}",
                path=str(resolved),
            )
    _validate_skill_tree_safe(resolved)
    try:
        text = skill_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SkillLibraryError("skill-file-unreadable", f"skill file is not utf-8: {skill_file}") from exc
    frontmatter, body = _parse_frontmatter(text)
    name = safe_name(frontmatter.get("name") or resolved.name, label="skill name")
    description = (frontmatter.get("description") or _first_paragraph(body)).strip()
    return SkillSource(
        name=name,
        description=description,
        source_path=str(source),
        resolved_path=str(resolved),
        skill_file=str(skill_file),
    )


def resolve_agent(ref: str) -> dict[str, Any]:
    try:
        record = agent_packages.resolve(ref)
    except Exception as exc:
        raise SkillLibraryError("agent-resolve-failed", f"failed to resolve agent package {ref}: {exc}", agent=ref) from exc
    runtime = str(record.get("runtime") or "")
    if runtime not in SUPPORTED_RUNTIMES:
        raise SkillLibraryError(
            "unsupported-runtime",
            f"runtime must be one of {sorted(SUPPORTED_RUNTIMES)}",
            runtime=runtime,
            agent=ref,
        )
    root = Path(str(record.get("root") or "")).expanduser().resolve()
    if not (root / "manifest.json").is_file() and not (root / "agent.json").is_file():
        raise SkillLibraryError("package-manifest-missing", f"agent package missing manifest: {root}", agent=ref, agent_root=str(root))
    codex_home = root / ".codex"
    if not codex_home.is_dir():
        raise SkillLibraryError("codex-home-missing", f"agent package missing .codex directory: {root}", agent=ref, agent_root=str(root))
    return {**record, "root": str(root)}


def lock_path(root: str | Path) -> Path:
    return Path(root) / "skills.lock.json"


def skills_dir(root: str | Path) -> Path:
    return Path(root) / ".codex" / "skills"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def read_lock(root: str | Path, *, agent_id: str | None = None) -> dict[str, Any]:
    path = lock_path(root)
    if not path.exists():
        return {"schema": LOCK_SCHEMA, "agent_id": agent_id, "agent_root": str(root), "entries": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillLibraryError("corrupt-provenance", f"invalid lockfile JSON: {path}: {exc}", lockfile=str(path)) from exc
    if not isinstance(payload, dict) or payload.get("schema") != LOCK_SCHEMA or not isinstance(payload.get("entries"), list):
        raise SkillLibraryError("corrupt-provenance", f"invalid lockfile schema: {path}", lockfile=str(path))
    payload.setdefault("agent_id", agent_id)
    payload.setdefault("agent_root", str(root))
    return payload


def write_lock(root: str | Path, *, agent_id: str | None, entries: list[dict[str, Any]]) -> None:
    _atomic_write_json(lock_path(root), {
        "schema": LOCK_SCHEMA,
        "agent_id": agent_id,
        "agent_root": str(root),
        "updated_at": now_iso(),
        "entries": entries,
    })


def _lock_owned_by_target(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("target_path")): dict(entry)
        for entry in lock.get("entries", [])
        if isinstance(entry, dict) and entry.get("owned") and entry.get("target_path")
    }


def _lock_owned_by_name(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("name")): dict(entry)
        for entry in lock.get("entries", [])
        if isinstance(entry, dict) and entry.get("owned") and entry.get("name")
    }


def plan_apply(agent_ref: str, skill_paths: list[str], *, mode: str = "symlink", replace: bool = False) -> dict[str, Any]:
    if mode not in VALID_MODES:
        raise SkillLibraryError("invalid-mode", "mode must be symlink or copy", mode=mode)
    if not skill_paths:
        raise SkillLibraryError("skill-required", "at least one --skill is required")
    agent = resolve_agent(agent_ref)
    root = Path(agent["root"])
    lock = read_lock(root, agent_id=agent.get("agent_id"))
    owned_targets = _lock_owned_by_target(lock)
    owned_names = _lock_owned_by_name(lock)
    sources = [resolve_skill_source(path) for path in skill_paths]
    seen: set[str] = set()
    actions: list[dict[str, Any]] = []
    for source in sources:
        if source.name in seen:
            raise SkillLibraryError("duplicate-skill", f"duplicate skill name in request: {source.name}", name=source.name)
        seen.add(source.name)
        target = skills_dir(root) / source.name
        exists = target.exists() or target.is_symlink()
        owned = str(target) in owned_targets or source.name in owned_names
        if exists and not owned and not replace:
            raise SkillLibraryError("destination-exists", f"destination exists and is not Aura-owned: {target}", target=str(target))
        actions.append({
            "action": "materialize",
            "mode": mode,
            "replace": replace,
            "owned": owned,
            "skill": asdict(source),
            "target_path": str(target),
        })
    return {
        "ok": True,
        "schema": PLAN_SCHEMA,
        "agent": _agent_summary(agent),
        "agent_root": str(root),
        "dry_run": False,
        "actions": actions,
    }


def _archive_existing(target: Path) -> str | None:
    if not (target.exists() or target.is_symlink()):
        return None
    archive_root = target.parents[2] / "skills-archive" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_root.mkdir(parents=True, exist_ok=True)
    archive_path = archive_root / target.name
    counter = 1
    while archive_path.exists() or archive_path.is_symlink():
        archive_path = archive_root / f"{target.name}.{counter}"
        counter += 1
    shutil.move(str(target), str(archive_path))
    return str(archive_path)


def _remove_target(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)


def _materialize(source: dict[str, Any], target: Path, *, mode: str) -> None:
    if mode == "symlink":
        target.symlink_to(source["resolved_path"], target_is_directory=True)
    elif mode == "copy":
        shutil.copytree(source["resolved_path"], target, symlinks=False)
    else:  # pragma: no cover - guarded by plan
        raise SkillLibraryError("invalid-mode", "mode must be symlink or copy", mode=mode)


def apply(agent_ref: str, skill_paths: list[str], *, mode: str = "symlink", replace: bool = False, dry_run: bool = False) -> dict[str, Any]:
    plan = plan_apply(agent_ref, skill_paths, mode=mode, replace=replace)
    if dry_run:
        return {**plan, "dry_run": True}
    agent = plan["agent"]
    root = Path(plan["agent_root"])
    lock = read_lock(root, agent_id=agent.get("agent_id"))
    by_name = _lock_owned_by_name(lock)
    applied: list[dict[str, Any]] = []
    skills_dir(root).mkdir(parents=True, exist_ok=True)
    for action in plan["actions"]:
        source = action["skill"]
        target = Path(action["target_path"])
        if target.exists() or target.is_symlink():
            if action.get("replace"):
                archive_path = _archive_existing(target)
            else:
                _remove_target(target)
                archive_path = None
        else:
            archive_path = None
        _materialize(source, target, mode=mode)
        entry = asdict(LockEntry(
            name=source["name"],
            mode=mode,
            source_path=source["source_path"],
            resolved_path=source["resolved_path"],
            target_path=str(target),
            owned=True,
            applied_at=now_iso(),
        ))
        if archive_path:
            entry["archive_path"] = archive_path
        by_name[source["name"]] = entry
        applied.append(entry)
    write_lock(root, agent_id=agent.get("agent_id"), entries=sorted(by_name.values(), key=lambda e: e.get("name", "")))
    return {"ok": True, "agent": agent, "agent_root": str(root), "applied": applied, "lockfile": str(lock_path(root))}


def _agent_summary(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        key: agent[key]
        for key in ("agent_id", "address", "alias", "runtime", "root")
        if key in agent and agent[key] is not None
    }


def _actual_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    directory = skills_dir(root)
    if not directory.is_dir():
        return rows
    for child in sorted(directory.iterdir(), key=lambda p: p.name):
        rows.append({
            "name": child.name,
            "path": str(child),
            "is_symlink": child.is_symlink(),
            "target": os.readlink(child) if child.is_symlink() else None,
            "kind": "symlink" if child.is_symlink() else ("directory" if child.is_dir() else "file"),
        })
    return rows


def list_skills(agent_ref: str) -> dict[str, Any]:
    agent = resolve_agent(agent_ref)
    root = Path(agent["root"])
    lock = read_lock(root, agent_id=agent.get("agent_id"))
    owned_targets = _lock_owned_by_target(lock)
    actual = []
    for row in _actual_rows(root):
        locked = owned_targets.get(row["path"])
        actual.append({**row, "owned": bool(locked), "lock_entry": locked})
    return {
        "ok": True,
        "agent": _agent_summary(agent),
        "agent_root": str(root),
        "lockfile": str(lock_path(root)),
        "locked": lock.get("entries", []),
        "actual": actual,
    }


def doctor(agent_ref: str) -> dict[str, Any]:
    agent = resolve_agent(agent_ref)
    root = Path(agent["root"])
    lock = read_lock(root, agent_id=agent.get("agent_id"))
    locked = _lock_owned_by_target(lock)
    actual = {row["path"]: row for row in _actual_rows(root)}
    issues: list[dict[str, Any]] = []
    for target, entry in locked.items():
        path = Path(target)
        if not (path.exists() or path.is_symlink()):
            issues.append({"kind": "lock-with-missing-link", "entry": entry})
        elif path.is_symlink() and not Path(os.readlink(path)).exists():
            issues.append({"kind": "broken-owned-link", "entry": entry})
    for target, row in actual.items():
        if target not in locked:
            issues.append({
                "kind": "owned-link-with-missing-lock" if row.get("is_symlink") else "unmanaged-file",
                "target_path": target,
                "name": row.get("name"),
            })
    return {"ok": True, "agent": _agent_summary(agent), "agent_root": str(root), "issues": issues}


def remove(agent_ref: str, skill_name: str, *, dry_run: bool = False) -> dict[str, Any]:
    name = safe_name(skill_name, label="skill name")
    agent = resolve_agent(agent_ref)
    root = Path(agent["root"])
    lock = read_lock(root, agent_id=agent.get("agent_id"))
    entries = [dict(entry) for entry in lock.get("entries", []) if isinstance(entry, dict)]
    match = next((entry for entry in entries if entry.get("name") == name and entry.get("owned")), None)
    if not match:
        raise SkillLibraryError("skill-not-owned", f"skill is not Aura-owned in this package: {name}", name=name, agent=agent_ref)
    target = Path(str(match.get("target_path") or skills_dir(root) / name))
    plan = {"ok": True, "agent": _agent_summary(agent), "agent_root": str(root), "dry_run": dry_run, "remove": match}
    if dry_run:
        return plan
    if target.exists() or target.is_symlink():
        _remove_target(target)
    remaining = [entry for entry in entries if not (entry.get("name") == name and entry.get("owned"))]
    write_lock(root, agent_id=agent.get("agent_id"), entries=remaining)
    return {**plan, "removed": match, "lockfile": str(lock_path(root))}


def _repair_entry(entry: dict[str, Any]) -> dict[str, Any]:
    source = resolve_skill_source(str(entry.get("resolved_path") or entry.get("source_path") or ""))
    if source.name != entry.get("name"):
        raise SkillLibraryError("skill-name-mismatch", f"source now resolves to {source.name}, expected {entry.get('name')}")
    target = Path(str(entry["target_path"]))
    if target.exists() or target.is_symlink():
        _remove_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _materialize(asdict(source), target, mode=str(entry.get("mode") or "symlink"))
    repaired = dict(entry)
    repaired.update({
        "source_path": source.source_path,
        "resolved_path": source.resolved_path,
        "repaired_at": now_iso(),
    })
    return repaired


def sync(agent_ref: str, *, dry_run: bool = False, prune: bool = False) -> dict[str, Any]:
    agent = resolve_agent(agent_ref)
    root = Path(agent["root"])
    lock = read_lock(root, agent_id=agent.get("agent_id"))
    issues = doctor(agent_ref)["issues"]
    repairs = [issue for issue in issues if issue.get("kind") == "lock-with-missing-link"]
    prunes = [issue for issue in issues if issue.get("kind") == "owned-link-with-missing-lock"] if prune else []
    result: dict[str, Any] = {
        "ok": True,
        "agent": _agent_summary(agent),
        "agent_root": str(root),
        "dry_run": dry_run,
        "issues": issues,
        "repairs": repairs,
        "prunes": prunes,
    }
    if dry_run:
        return result
    if repairs:
        entries = [dict(entry) for entry in lock.get("entries", []) if isinstance(entry, dict)]
        by_target = {entry.get("target_path"): entry for entry in entries}
        repaired_entries = []
        for issue in repairs:
            repaired = _repair_entry(dict(issue["entry"]))
            by_target[repaired["target_path"]] = repaired
            repaired_entries.append(repaired)
        write_lock(root, agent_id=agent.get("agent_id"), entries=list(by_target.values()))
        result["repaired"] = repaired_entries
    if prunes:
        for issue in prunes:
            target = Path(str(issue.get("target_path")))
            if target.exists() or target.is_symlink():
                _remove_target(target)
        result["pruned"] = prunes
    return result


def _read_skill_file(path: Path) -> tuple[dict[str, str], str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SkillLibraryError("skill-file-unreadable", f"skill file is not utf-8: {path}") from exc
    frontmatter, body = _parse_frontmatter(text)
    return frontmatter, body, text


def _skill_file_for_dir(directory: Path) -> Path | None:
    for name in ("SKILL.md", "SKILLS.md"):
        path = directory / name
        if path.is_file():
            return path
    return None


def _metadata_for_skill_dir(directory: Path) -> dict[str, Any] | None:
    skill_file = _skill_file_for_dir(directory)
    if not skill_file:
        return None
    try:
        frontmatter, body, text = _read_skill_file(skill_file)
        error = None
    except SkillLibraryError as exc:
        frontmatter, body, text, error = {}, "", "", exc.detail
    name = (frontmatter.get("name") or directory.name).strip() or directory.name
    description = (frontmatter.get("description") or _first_paragraph(body)).strip()
    return {
        "name": name,
        "directory_name": directory.name,
        "description": description,
        "path": str(directory),
        "real_path": str(directory.resolve(strict=False)),
        "skill_file": str(skill_file),
        "skill_file_name": skill_file.name,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if error is None else None,
        "read_error": error,
    }


def _default_inventory_roots(*, include_packages: bool = True) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    codex = Path.home() / ".codex" / "skills"
    if codex.exists():
        roots.append({"label": "codex-user", "path": codex, "mode": "tree"})
    claude = Path.home() / ".claude" / "skills"
    if claude.exists():
        roots.append({"label": "claude-user", "path": claude, "mode": "tree"})
    context_current = Path.cwd().parent / "context" / "current" / "skills"
    if context_current.exists():
        roots.append({"label": "aura-current", "path": context_current, "mode": "tree"})
    if include_packages:
        packages = agent_packages.agents_root()
        if packages.exists():
            roots.append({"label": "aura-packages", "path": packages, "mode": "packages"})
    return roots


def _category_for(path: Path, *, root_label: str) -> str:
    text = str(path)
    if "/.system/" in text:
        return "system"
    if "/.aura/agents/i_" in text:
        return "aura-agent-package"
    if root_label:
        return root_label
    return "other"


def _record_for_skill_dir(directory: Path, *, root_label: str, package_id: str | None = None) -> dict[str, Any] | None:
    meta = _metadata_for_skill_dir(directory)
    if not meta:
        return None
    is_symlink = directory.is_symlink()
    target = os.readlink(directory) if is_symlink else None
    meta.update({
        "category": _category_for(directory, root_label=root_label),
        "package_id": package_id,
        "kind": "symlink" if is_symlink else ("directory" if directory.is_dir() else "file"),
        "is_symlink": is_symlink,
        "symlink_target": target,
        "broken": bool(is_symlink and not directory.exists()),
    })
    return meta


def _iter_root_skill_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    dirs: list[Path] = []
    for file_name in ("SKILL.md", "SKILLS.md"):
        for skill_file in root.rglob(file_name):
            if "/.tmp/" in str(skill_file):
                continue
            dirs.append(skill_file.parent)
    return sorted(set(dirs), key=lambda p: str(p))


def _iter_package_skill_dirs(packages_root: Path) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    if not packages_root.exists():
        return rows
    for package in sorted(packages_root.glob("i_*"), key=lambda p: p.name):
        skill_root = package / ".codex" / "skills"
        if not skill_root.is_dir():
            continue
        for child in sorted(skill_root.iterdir(), key=lambda p: p.name):
            if _skill_file_for_dir(child):
                rows.append((package.name, child))
    return rows


def inventory(*, roots: list[str] | None = None, include_packages: bool = True) -> dict[str, Any]:
    """Return a read-only skill inventory across known roots."""

    specs: list[dict[str, Any]] = []
    if roots:
        specs.extend({"label": "custom", "path": Path(root).expanduser(), "mode": "tree"} for root in roots)
    else:
        specs = _default_inventory_roots(include_packages=include_packages)
    records: list[dict[str, Any]] = []
    scanned_roots = []
    seen_paths: set[str] = set()
    for spec in specs:
        root = Path(spec["path"]).expanduser()
        mode = spec.get("mode") or "tree"
        scanned_roots.append({"label": spec.get("label"), "path": str(root), "mode": mode, "exists": root.exists()})
        if mode == "packages":
            for package_id, directory in _iter_package_skill_dirs(root):
                key = str(directory)
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                record = _record_for_skill_dir(directory, root_label="aura-agent-package", package_id=package_id)
                if record:
                    records.append(record)
            continue
        for directory in _iter_root_skill_dirs(root):
            key = str(directory)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            record = _record_for_skill_dir(directory, root_label=str(spec.get("label") or "custom"))
            if record:
                records.append(record)
    by_name: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_name.setdefault(str(record.get("name")), []).append(record)
    duplicate_names = {
        name: rows
        for name, rows in sorted(by_name.items())
        if len(rows) > 1
    }
    divergent_names = {
        name: rows
        for name, rows in duplicate_names.items()
        if len({row.get("sha256") for row in rows if row.get("sha256")}) > 1
    }
    by_category: dict[str, int] = {}
    for record in records:
        category = str(record.get("category") or "unknown")
        by_category[category] = by_category.get(category, 0) + 1
    return {
        "ok": True,
        "schema": "aura.skills_inventory.v1",
        "scanned_roots": scanned_roots,
        "summary": {
            "total": len(records),
            "by_category": dict(sorted(by_category.items())),
            "duplicate_name_count": len(duplicate_names),
            "divergent_duplicate_name_count": len(divergent_names),
        },
        "records": records,
    }


def duplicates(*, roots: list[str] | None = None, include_packages: bool = True, include_identical: bool = False) -> dict[str, Any]:
    inv = inventory(roots=roots, include_packages=include_packages)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in inv["records"]:
        grouped.setdefault(str(record.get("name")), []).append(record)
    rows = []
    for name, items in sorted(grouped.items()):
        if len(items) <= 1:
            continue
        hashes = sorted({str(item.get("sha256")) for item in items if item.get("sha256")})
        divergent = len(hashes) > 1
        if not divergent and not include_identical:
            continue
        rows.append({
            "name": name,
            "count": len(items),
            "hashes": hashes,
            "divergent": divergent,
            "items": items,
        })
    return {"ok": True, "schema": "aura.skills_duplicates.v1", "summary": {"groups": len(rows)}, "duplicates": rows}


def diff_name(name: str, *, roots: list[str] | None = None, include_packages: bool = True) -> dict[str, Any]:
    inv = inventory(roots=roots, include_packages=include_packages)
    matches = [record for record in inv["records"] if record.get("name") == name or record.get("directory_name") == name]
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for record in matches:
        by_hash.setdefault(str(record.get("sha256") or "unreadable"), []).append(record)
    return {
        "ok": True,
        "schema": "aura.skills_diff.v1",
        "name": name,
        "match_count": len(matches),
        "hash_count": len(by_hash),
        "by_hash": [
            {"sha256": digest, "count": len(items), "items": items}
            for digest, items in sorted(by_hash.items())
        ],
    }


def _entry_from_existing(agent: dict[str, Any], directory: Path) -> dict[str, Any] | None:
    meta = _metadata_for_skill_dir(directory)
    if not meta:
        return None
    # Ownership operations use the target directory name because frontmatter
    # names may contain runtime display names such as flex:context.
    entry_name = safe_name(directory.name, label="skill directory name")
    mode = "symlink" if directory.is_symlink() else "copy"
    resolved_source = Path(os.readlink(directory)).expanduser().resolve(strict=False) if directory.is_symlink() else directory.resolve(strict=False)
    source_path = os.readlink(directory) if directory.is_symlink() else str(directory)
    return {
        "name": entry_name,
        "skill_name": meta.get("name"),
        "description": meta.get("description"),
        "mode": mode,
        "source_path": source_path,
        "resolved_path": str(resolved_source),
        "target_path": str(directory),
        "owned": True,
        "applied_at": now_iso(),
        "provenance": "adopted-existing",
        "source_sha256": meta.get("sha256"),
    }


def adopt_existing(agent_ref: str, *, dry_run: bool = True, replace_lock: bool = False) -> dict[str, Any]:
    """Adopt existing package-local skills into skills.lock.json without moving files."""

    agent = resolve_agent(agent_ref)
    root = Path(agent["root"])
    current = read_lock(root, agent_id=agent.get("agent_id"))
    existing_by_name = _lock_owned_by_name(current)
    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in _actual_rows(root):
        directory = Path(row["path"])
        if not _skill_file_for_dir(directory):
            skipped.append({"name": row.get("name"), "reason": "skill-file-missing", "path": str(directory)})
            continue
        entry = _entry_from_existing(agent, directory)
        if not entry:
            skipped.append({"name": row.get("name"), "reason": "unreadable", "path": str(directory)})
            continue
        if entry["name"] in existing_by_name and not replace_lock:
            skipped.append({"name": entry["name"], "reason": "already-owned", "path": str(directory)})
            continue
        planned.append(entry)
    result = {
        "ok": True,
        "schema": "aura.skills_adopt.v1",
        "agent": _agent_summary(agent),
        "agent_root": str(root),
        "dry_run": dry_run,
        "replace_lock": replace_lock,
        "planned": planned,
        "skipped": skipped,
        "lockfile": str(lock_path(root)),
    }
    if dry_run:
        return result
    if replace_lock:
        entries = planned
    else:
        by_name = dict(existing_by_name)
        for entry in planned:
            by_name[entry["name"]] = entry
        entries = sorted(by_name.values(), key=lambda item: item.get("name", ""))
    write_lock(root, agent_id=agent.get("agent_id"), entries=entries)
    return {**result, "adopted": planned}
