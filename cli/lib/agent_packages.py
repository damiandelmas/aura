"""Minimal package-native Aura agents.

Agent packages are durable runtime bodies under ``~/.aura/agents/i_*``.  The
body intentionally contains only Aura's spawn recipe plus native runtime homes.
Pure Codex bodies contain ``manifest.json`` and ``.codex/``. OMX bodies contain
``manifest.json``, ``.codex/``, and ``.omx/``. Lookup names live in the external
agent index; launch/session evidence lives in Aura registry/runtime state.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import runtime_boxes, runtime_profiles, state


AGENT_SCHEMA = "aura.agent_manifest.v1"
INDEX_SCHEMA = "aura.agent_package.index.v1"

SUPPORTED_RUNTIMES = {"codex", "omx"}


def _empty_index() -> dict[str, Any]:
    return {"schema": INDEX_SCHEMA, "agents": {}, "addresses": {}, "aliases": {}}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def agents_root() -> Path:
    return state.state_root() / "agents"


def index_path() -> Path:
    return agents_root() / "index.json"


def new_agent_id() -> str:
    return f"i_{uuid.uuid4().hex[:12]}"


def normalize_address(address: str) -> str:
    raw = str(address or "").strip()
    if not raw:
        raise ValueError("agent address is required")
    parts = [part.strip() for part in raw.split(":")]
    if any(not part for part in parts):
        raise ValueError("agent address cannot contain empty ':' segments")
    if len(parts) < 2:
        raise ValueError("agent address should have at least two ':' segments")
    for part in parts:
        runtime_boxes.validate_logical_segment(part, label="agent address segment")
    return ":".join(parts)


def normalize_runtime(runtime: str) -> str:
    value = runtime_boxes.validate_logical_segment(str(runtime or "").strip(), label="runtime")
    if value not in SUPPORTED_RUNTIMES:
        raise ValueError(f"runtime must be one of: {', '.join(sorted(SUPPORTED_RUNTIMES))}")
    return value


def normalize_profile_ref(profile: str | None, *, runtime: str) -> str | None:
    raw = str(profile or "").strip()
    if not raw:
        return None
    if "/" not in raw:
        raw = f"{runtime}/{raw}"
    return runtime_profiles.normalize_runtime_profile_ref(raw, expected_runtime=runtime).canonical


def default_seat_from_address(address: str) -> str:
    leaf = address.split(":")[-1]
    return runtime_boxes.safe_segment(leaf)


def default_fleet_from_address(address: str) -> str:
    parts = address.split(":")
    if len(parts) >= 2:
        return runtime_boxes.safe_segment("-".join(parts[:2]))
    return "agents"


def package_root(agent_id: str) -> Path:
    if not re.fullmatch(r"i_[A-Za-z0-9_.-]+", str(agent_id or "")):
        raise ValueError("agent id must look like i_<id>")
    return agents_root() / agent_id


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def read_index() -> dict[str, Any]:
    path = index_path()
    if not path.exists():
        return _empty_index()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid agent package index: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid agent package index: {path}: expected object")
    payload.setdefault("schema", INDEX_SCHEMA)
    payload.setdefault("agents", {})
    payload.setdefault("addresses", {})
    payload.setdefault("aliases", {})
    return payload


def write_index(index: dict[str, Any]) -> None:
    index = dict(index)
    index["schema"] = INDEX_SCHEMA
    index["updated_at"] = now_iso()
    _atomic_write_json(index_path(), index)


def manifest_path(root: Path) -> Path:
    return root / "manifest.json"


def legacy_agent_path(root: Path) -> Path:
    return root / "agent.json"


def _read_manifest(root: Path) -> dict[str, Any]:
    path = manifest_path(root)
    if not path.exists():
        path = legacy_agent_path(root)
    if not path.exists():
        raise FileNotFoundError(f"agent package missing manifest.json: {root}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid agent package: {path}")
    return payload


def _index_agent_meta(index: dict[str, Any], agent_id: str) -> dict[str, Any]:
    raw = index.get("agents", {}).get(agent_id)
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        return {"root": raw}
    return {}


def _find_index_key(mapping: dict[str, Any], agent_id: str) -> str | None:
    for key, value in mapping.items():
        if value == agent_id:
            return key
    return None


def _enrich_record(record: dict[str, Any], *, index: dict[str, Any], agent_id: str, root: Path) -> dict[str, Any]:
    meta = _index_agent_meta(index, agent_id)
    enriched = dict(record)
    enriched["agent_id"] = agent_id
    enriched["root"] = str(root)
    address = meta.get("address") or record.get("address") or _find_index_key(index.get("addresses", {}), agent_id)
    alias = meta.get("alias") or record.get("alias") or _find_index_key(index.get("aliases", {}), agent_id)
    if address:
        enriched["address"] = address
    if alias:
        enriched["alias"] = alias
    return enriched


def resolve(ref: str) -> dict[str, Any]:
    raw = str(ref or "").strip()
    if not raw:
        raise ValueError("agent ref is required")
    index = read_index()
    agent_id = None
    if raw.startswith("i_"):
        agent_id = raw
    elif raw in index.get("addresses", {}):
        agent_id = index["addresses"][raw]
    elif raw in index.get("aliases", {}):
        agent_id = index["aliases"][raw]
    if not agent_id:
        raise FileNotFoundError(f"unknown agent package: {raw}")
    root = package_root(agent_id)
    meta = _index_agent_meta(index, agent_id)
    if meta.get("root"):
        root = Path(str(meta["root"])).expanduser().resolve()
    record = _read_manifest(root)
    return _enrich_record(record, index=index, agent_id=agent_id, root=root)


def package_dirs(root: Path, runtime: str | None = None) -> dict[str, str]:
    dirs = {
        "root": str(root),
        "codex_home": str(root / ".codex"),
    }
    if runtime == "omx":
        dirs.update({
            "omx_root": str(root),
            "omx_state": str(root / ".omx"),
            "omx_team_state": str(root / ".omx" / "state"),
        })
    return dirs


def _spawn_env(runtime: str) -> dict[str, str]:
    env = {"CODEX_HOME": ".codex"}
    if runtime == "omx":
        env["OMX_ROOT"] = "."
        env["OMX_TEAM_STATE_ROOT"] = ".omx/state"
    return env


def _spawn_argv(runtime: str) -> list[str]:
    return [runtime]


def create(
    *,
    address: str,
    runtime: str,
    profile: str | None,
    cwd: str,
    fleet: str | None,
    seat: str | None,
    alias: str | None = None,
) -> dict[str, Any]:
    address = normalize_address(address)
    runtime = normalize_runtime(runtime)
    profile_ref = normalize_profile_ref(profile, runtime=runtime)
    cwd_path = Path(cwd).expanduser().resolve()
    fleet = runtime_boxes.validate_logical_segment(
        fleet or default_fleet_from_address(address),
        label="fleet",
    )
    seat = runtime_boxes.validate_logical_segment(
        seat or default_seat_from_address(address),
        label="seat",
    )
    alias_value = (
        runtime_boxes.validate_logical_segment(alias, label="alias")
        if alias
        else None
    )

    index = read_index()
    existing_id = index.get("addresses", {}).get(address)
    if existing_id:
        raise FileExistsError(f"agent address already exists: {address} -> {existing_id}")
    if alias_value and alias_value in index.get("aliases", {}):
        raise FileExistsError(f"agent alias already exists: {alias_value}")

    agent_id = new_agent_id()
    root = package_root(agent_id)
    dirs = package_dirs(root, runtime)
    for key in ("codex_home", "omx_team_state"):
        if key in dirs:
            Path(dirs[key]).mkdir(parents=True, exist_ok=True)

    record = {
        "schema": AGENT_SCHEMA,
        "runtime": runtime,
        "cwd": str(cwd_path),
        "argv": _spawn_argv(runtime),
        "env": _spawn_env(runtime),
        "resume": {"default": "latest"},
        "fleet": fleet,
        "seat": seat,
        **({"profile": profile_ref} if profile_ref else {}),
    }
    _atomic_write_json(manifest_path(root), record)

    index.setdefault("agents", {})[agent_id] = {
        "root": str(root),
        "address": address,
        **({"alias": alias_value} if alias_value else {}),
    }
    index.setdefault("addresses", {})[address] = agent_id
    if alias_value:
        index.setdefault("aliases", {})[alias_value] = agent_id
    write_index(index)
    return {"ok": True, "agent": _enrich_record(record, index=index, agent_id=agent_id, root=root)}


def adopt_root(
    *,
    root: str,
    address: str,
    alias: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Add an existing package body to the package index without copying it."""
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"agent package root does not exist: {root_path}")
    record = _read_manifest(root_path)
    runtime = normalize_runtime(str(record.get("runtime") or ""))
    missing_runtime_roots = _runtime_root_findings(root_path, record)
    if missing_runtime_roots:
        raise FileNotFoundError(
            f"agent package missing runtime roots: {', '.join(missing_runtime_roots)}"
        )
    address = normalize_address(address)
    alias_value = (
        runtime_boxes.validate_logical_segment(alias, label="alias")
        if alias
        else None
    )
    package_id = str(agent_id or root_path.name)
    package_root(package_id)

    index = read_index()
    if package_id in index.get("agents", {}):
        raise FileExistsError(f"agent package already indexed: {package_id}")
    existing_id = index.get("addresses", {}).get(address)
    if existing_id:
        raise FileExistsError(f"agent address already exists: {address} -> {existing_id}")
    if alias_value and alias_value in index.get("aliases", {}):
        raise FileExistsError(f"agent alias already exists: {alias_value}")

    index.setdefault("agents", {})[package_id] = {
        "root": str(root_path),
        "address": address,
        **({"alias": alias_value} if alias_value else {}),
    }
    index.setdefault("addresses", {})[address] = package_id
    if alias_value:
        index.setdefault("aliases", {})[alias_value] = package_id
    write_index(index)
    return {
        "ok": True,
        "adopted": True,
        "runtime": runtime,
        "agent": _enrich_record(record, index=index, agent_id=package_id, root=root_path),
    }


def clone(
    ref: str,
    *,
    address: str,
    alias: str | None = None,
    cwd: str | None = None,
    fleet: str | None = None,
    seat: str | None = None,
) -> dict[str, Any]:
    """Clone an indexed package body to a new package id and address."""
    source = resolve(ref)
    source_root = Path(source["root"])
    if not source_root.exists():
        raise FileNotFoundError(f"source package root does not exist: {source_root}")
    address = normalize_address(address)
    alias_value = (
        runtime_boxes.validate_logical_segment(alias, label="alias")
        if alias
        else None
    )
    index = read_index()
    if address in index.get("addresses", {}):
        raise FileExistsError(f"agent address already exists: {address} -> {index['addresses'][address]}")
    if alias_value and alias_value in index.get("aliases", {}):
        raise FileExistsError(f"agent alias already exists: {alias_value}")

    target_id = new_agent_id()
    target_root = package_root(target_id)
    shutil.copytree(source_root, target_root)
    manifest = _read_manifest(target_root)
    if cwd:
        manifest["cwd"] = str(Path(cwd).expanduser().resolve())
    if fleet:
        manifest["fleet"] = runtime_boxes.validate_logical_segment(fleet, label="fleet")
    if seat:
        manifest["seat"] = runtime_boxes.validate_logical_segment(seat, label="seat")
    _atomic_write_json(manifest_path(target_root), manifest)

    index.setdefault("agents", {})[target_id] = {
        "root": str(target_root),
        "address": address,
        **({"alias": alias_value} if alias_value else {}),
        "cloned_from": source["agent_id"],
    }
    index.setdefault("addresses", {})[address] = target_id
    if alias_value:
        index.setdefault("aliases", {})[alias_value] = target_id
    write_index(index)
    return {
        "ok": True,
        "source_agent_id": source["agent_id"],
        "source_root": str(source_root),
        "agent": _enrich_record(manifest, index=index, agent_id=target_id, root=target_root),
    }


def _copy_required_dir(source: str | None, target: Path, *, label: str) -> None:
    if not source:
        raise FileNotFoundError(f"seat is missing {label}")
    source_path = Path(str(source)).expanduser().resolve()
    if not source_path.is_dir():
        raise FileNotFoundError(f"seat {label} does not exist: {source_path}")
    shutil.copytree(source_path, target)


def promote_seat(
    target: str,
    *,
    address: str,
    alias: str | None = None,
) -> dict[str, Any]:
    """Promote one live registry seat into a durable package body."""
    from lib import registry

    row = registry.get_agent(target)
    if not row:
        raise FileNotFoundError(f"seat not found: {target}")
    if row.get("agent_package_id"):
        raise FileExistsError(f"seat already has package binding: {row.get('agent_package_id')}")
    runtime = normalize_runtime(str(row.get("runtime") or ""))
    address = normalize_address(address)
    alias_value = (
        runtime_boxes.validate_logical_segment(alias, label="alias")
        if alias
        else None
    )
    index = read_index()
    if address in index.get("addresses", {}):
        raise FileExistsError(f"agent address already exists: {address} -> {index['addresses'][address]}")
    if alias_value and alias_value in index.get("aliases", {}):
        raise FileExistsError(f"agent alias already exists: {alias_value}")

    agent_id = new_agent_id()
    root = package_root(agent_id)
    try:
        root.mkdir(parents=True)
        if runtime == "codex":
            _copy_required_dir(
                row.get("codex_package_codex_home") or row.get("codex_box_codex_home") or row.get("native_state_ref"),
                root / ".codex",
                label="codex home",
            )
        elif runtime == "omx":
            _copy_required_dir(
                row.get("omx_package_codex_home") or row.get("omx_box_codex_home"),
                root / ".codex",
                label="codex home",
            )
            _copy_required_dir(
                row.get("omx_package_omx_state") or row.get("omx_box_omx_state") or row.get("native_state_ref"),
                root / ".omx",
                label="omx state",
            )
        manifest = {
            "schema": AGENT_SCHEMA,
            "runtime": runtime,
            "cwd": str(Path(row.get("cwd") or row.get("runtime_process_cwd") or Path.cwd()).expanduser().resolve()),
            "argv": _spawn_argv(runtime),
            "env": _spawn_env(runtime),
            "resume": {"default": "latest"},
            "fleet": row.get("fleet"),
            "seat": row.get("name") or row.get("seat"),
            **({"profile": row.get("runtime_profile")} if row.get("runtime_profile") else {}),
        }
        _atomic_write_json(manifest_path(root), manifest)
        index.setdefault("agents", {})[agent_id] = {
            "root": str(root),
            "address": address,
            **({"alias": alias_value} if alias_value else {}),
            "promoted_from": registry.seat_ref(row.get("fleet"), row.get("name") or row.get("seat")),
        }
        index.setdefault("addresses", {})[address] = agent_id
        if alias_value:
            index.setdefault("aliases", {})[alias_value] = agent_id
        write_index(index)
    except Exception:
        if root.exists():
            shutil.rmtree(root)
        raise

    updated = registry.upsert_agent({
        "name": row.get("name") or row.get("seat"),
        "fleet": row.get("fleet"),
        "agent_package_id": agent_id,
        "agent_package_address": address,
        "agent_package_root": str(root),
        "identity_provider": "aura-agent",
        "identity_id": agent_id,
        "identity_label": address,
    })
    return {
        "ok": True,
        "promoted": True,
        "source": registry.seat_ref(row.get("fleet"), row.get("name") or row.get("seat")),
        "agent": _enrich_record(manifest, index=index, agent_id=agent_id, root=root),
        "registry": {
            "seat_ref": updated.get("seat_ref"),
            "agent_package_id": updated.get("agent_package_id"),
            "agent_package_root": updated.get("agent_package_root"),
            "runtime_process_still_uses_original_home": True,
        },
    }


def append_spawn_history(agent_id: str, event: dict[str, Any]) -> dict[str, Any]:
    # Compatibility no-op: package manifest.json is the spawn recipe only. Spawn
    # and session evidence lives in the registry/session ledger.
    return resolve(agent_id)


def inspect(ref: str) -> dict[str, Any]:
    record = resolve(ref)
    root = Path(record["root"])
    runtime = str(record.get("runtime") or "")
    dirs = package_dirs(root, runtime)
    files = {
        "manifest": str(manifest_path(root)),
        "legacy_agent_json": str(legacy_agent_path(root)),
    }
    sizes = {}
    for label, path in dirs.items():
        p = Path(path)
        if p.exists() and p.is_dir():
            sizes[label] = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return {
        "ok": True,
        "agent": record,
        "dirs": dirs,
        "files": {key: value for key, value in files.items() if Path(value).exists()},
        "missing_files": {key: value for key, value in files.items() if not Path(value).exists()},
        "sizes": sizes,
    }


def _agent_ids_from_index(index: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    agents = index.get("agents", {})
    if isinstance(agents, dict):
        ids.update(str(agent_id) for agent_id in agents)
    for key in ("addresses", "aliases"):
        mapping = index.get(key, {})
        if isinstance(mapping, dict):
            ids.update(str(agent_id) for agent_id in mapping.values() if str(agent_id).startswith("i_"))
    return ids


def _agent_ids_from_dirs() -> set[str]:
    root = agents_root()
    if not root.exists():
        return set()
    return {path.name for path in root.iterdir() if path.is_dir() and path.name.startswith("i_")}


def _agent_ids_from_registry_rows(rows: list[tuple[str, dict[str, Any]]]) -> set[str]:
    ids: set[str] = set()
    for _ref, row in rows:
        agent_id = row.get("agent_package_id") or row.get("identity_id")
        if agent_id and str(agent_id).startswith("i_"):
            ids.add(str(agent_id))
    return ids


def _root_for_census(index: dict[str, Any], agent_id: str) -> Path:
    meta = _index_agent_meta(index, agent_id)
    if meta.get("root"):
        return Path(str(meta["root"])).expanduser().resolve()
    return package_root(agent_id)


def _manifest_status(root: Path) -> tuple[dict[str, Any] | None, list[str], str | None]:
    if not root.exists():
        return None, ["missing-package-root"], None
    path = manifest_path(root)
    legacy_path = legacy_agent_path(root)
    used_path: Path | None = None
    if path.exists():
        used_path = path
    elif legacy_path.exists():
        used_path = legacy_path
    if not used_path:
        return None, ["missing-manifest"], None
    try:
        payload = json.loads(used_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, ["invalid-manifest-json"], str(used_path)
    if not isinstance(payload, dict):
        return None, ["invalid-manifest-json"], str(used_path)
    return payload, [], str(used_path)


def _runtime_root_findings(root: Path, manifest: dict[str, Any] | None) -> list[str]:
    if manifest is None:
        return []
    runtime = str(manifest.get("runtime") or "")
    findings: list[str] = []
    if runtime in {"codex", "omx"} and not (root / ".codex").is_dir():
        findings.append("missing-runtime-root:.codex")
    if runtime == "omx" and not (root / ".omx").is_dir():
        findings.append("missing-runtime-root:.omx")
    return findings


def _registry_rows_for_agent(
    rows: list[tuple[str, dict[str, Any]]],
    *,
    agent_id: str,
    root: Path,
) -> list[dict[str, Any]]:
    root_text = str(root)
    matched: list[dict[str, Any]] = []
    for ref, row in rows:
        row_agent_id = row.get("agent_package_id") or row.get("identity_id")
        row_root = row.get("agent_package_root") or row.get("runtime_capsule_ref")
        if row_agent_id == agent_id or (row_root and str(row_root) == root_text):
            matched.append({
                "ref": ref,
                "fleet": row.get("fleet"),
                "seat": row.get("name") or row.get("seat"),
                "runtime": row.get("runtime"),
                "runtime_session_id": row.get("runtime_session_id") or row.get("session_id"),
                "runtime_session_binding": row.get("runtime_session_binding"),
                "pane_ref": row.get("pane_ref"),
                "status": row.get("status"),
                "liveness": row.get("liveness"),
            })
    return matched


def _classification(*, root: Path, manifest: dict[str, Any] | None, findings: list[str], bindings: list[dict[str, Any]]) -> str:
    if "missing-package-root" in findings:
        return "registry-ghost" if bindings else "indexed-missing-package"
    if manifest is None:
        return "package-broken"
    if len(bindings) > 1:
        return "durable-package-duplicate-bindings"
    if bindings:
        return "durable-package-bound"
    return "durable-package-unbound"


def census() -> dict[str, Any]:
    """Classify durable package bodies against live registry references."""
    from lib import registry

    index = read_index()
    registry_rows = sorted(registry.read_registry().items())
    agent_ids = (
        _agent_ids_from_index(index)
        | _agent_ids_from_dirs()
        | _agent_ids_from_registry_rows(registry_rows)
    )
    packages: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for agent_id in sorted(agent_ids):
        root = _root_for_census(index, agent_id)
        manifest, findings, manifest_file = _manifest_status(root)
        findings.extend(_runtime_root_findings(root, manifest))
        bindings = _registry_rows_for_agent(registry_rows, agent_id=agent_id, root=root)
        if len(bindings) > 1:
            findings.append("duplicate-live-seat-for-package")
        classification = _classification(root=root, manifest=manifest, findings=findings, bindings=bindings)
        counts[classification] = counts.get(classification, 0) + 1
        meta = _index_agent_meta(index, agent_id)
        packages.append({
            "agent_id": agent_id,
            "classification": classification,
            "root": str(root),
            "indexed": agent_id in _agent_ids_from_index(index),
            "address": meta.get("address") or (manifest or {}).get("address") or _find_index_key(index.get("addresses", {}), agent_id),
            "alias": meta.get("alias") or (manifest or {}).get("alias") or _find_index_key(index.get("aliases", {}), agent_id),
            "manifest": manifest_file,
            "runtime": (manifest or {}).get("runtime"),
            "cwd": (manifest or {}).get("cwd"),
            "fleet": (manifest or {}).get("fleet"),
            "seat": (manifest or {}).get("seat"),
            "bindings": bindings,
            "findings": findings,
        })
    return {
        "ok": True,
        "schema": "aura.agent_package.census.v1",
        "agents_root": str(agents_root()),
        "index": str(index_path()),
        "counts": counts,
        "packages": packages,
    }
