"""Runtime-home and global runtime storage hygiene checks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


GIB = 1024 ** 3
DEFAULT_CODEX_WAL_WARN_BYTES = GIB
DEFAULT_CODEX_WAL_CRITICAL_BYTES = 10 * GIB

CAPSULE_RESIDUE = (
    "agent.json",
    "aura-launch.json",
    "runtime-session.json",
    "receipts",
    "artifacts",
    "home",
    "runtime",
    "codex-home",
    "omx-root",
)


def _finding(
    code: str,
    *,
    severity: str,
    path: Path | None = None,
    detail: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "severity": severity}
    if path is not None:
        item["path"] = str(path)
    if detail:
        item["detail"] = detail
    for key, value in extra.items():
        if value is not None:
            item[key] = value
    return item


def _read_manifest(root: Path) -> dict[str, Any] | None:
    path = root / "manifest.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def package_runtime_findings(
    root: str | Path,
    manifest: dict[str, Any] | None = None,
    *,
    runtime: str | None = None,
) -> list[dict[str, Any]]:
    """Return structured runtime-home hygiene findings for an agent package."""
    root_path = Path(root).expanduser().resolve()
    findings: list[dict[str, Any]] = []
    if not root_path.exists():
        return [
            _finding(
                "missing-package-root",
                severity="error",
                path=root_path,
                detail="agent package root does not exist",
            )
        ]

    for name in CAPSULE_RESIDUE:
        path = root_path / name
        if path.exists():
            findings.append(
                _finding(
                    "package-runtime-residue",
                    severity="error",
                    path=path,
                    detail=f"package root contains legacy runtime capsule residue: {name}",
                    residue=name,
                )
            )

    manifest = manifest if isinstance(manifest, dict) else _read_manifest(root_path)
    runtime_name = str(runtime or (manifest or {}).get("runtime") or "").strip()
    env = (manifest or {}).get("env")
    if not isinstance(env, dict):
        return findings

    expected_env: dict[str, str] = {}
    if runtime_name == "codex":
        expected_env = {"CODEX_HOME": ".codex"}
    elif runtime_name == "omx":
        expected_env = {
            "CODEX_HOME": ".codex",
            "OMX_ROOT": ".",
            "OMX_TEAM_STATE_ROOT": ".omx/state",
        }
    elif runtime_name == "gajae-code":
        expected_env = {
            "GJC_CONFIG_DIR": ".gjc",
            "GJC_CODING_AGENT_DIR": ".gjc/agent",
        }

    for key, expected in expected_env.items():
        if key not in env:
            continue
        actual = str(env.get(key) or "")
        if actual != expected:
            findings.append(
                _finding(
                    "package-runtime-env-drift",
                    severity="error",
                    detail=f"manifest env {key} points outside package-owned runtime root",
                    env=key,
                    expected=expected,
                    actual=actual,
                )
            )

    return findings


def severe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [finding for finding in findings if finding.get("severity") == "error"]


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(parsed, 0)


def _file_size(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"path": str(path), "exists": False, "bytes": 0}
    return {"path": str(path), "exists": True, "bytes": stat.st_size}


def _lsof_holders(paths: list[Path]) -> tuple[str, list[dict[str, Any]]]:
    lsof = shutil.which("lsof")
    if not lsof:
        return "unavailable", []
    existing = [str(path) for path in paths if path.exists()]
    if not existing:
        return "no-files", []
    try:
        result = subprocess.run(
            [lsof, "-F", "pcn", *existing],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return "failed", []
    if result.returncode not in {0, 1}:
        return "failed", []

    holders: dict[str, dict[str, Any]] = {}
    current_pid: str | None = None
    for line in result.stdout.splitlines():
        if not line:
            continue
        tag, value = line[0], line[1:]
        if tag == "p":
            current_pid = value
            holders.setdefault(current_pid, {"pid": value, "command": None, "paths": []})
        elif tag == "c" and current_pid:
            holders.setdefault(current_pid, {"pid": current_pid, "command": None, "paths": []})["command"] = value
        elif tag == "n" and current_pid:
            holder = holders.setdefault(current_pid, {"pid": current_pid, "command": None, "paths": []})
            if value not in holder["paths"]:
                holder["paths"].append(value)
    return "ok", sorted(holders.values(), key=lambda item: item["pid"])


def codex_global_storage_pressure(home: str | Path | None = None) -> dict[str, Any]:
    """Return read-only global Codex SQLite/WAL pressure telemetry."""
    codex_home = Path(home).expanduser() if home is not None else Path.home() / ".codex"
    db = codex_home / "logs_2.sqlite"
    wal = codex_home / "logs_2.sqlite-wal"
    shm = codex_home / "logs_2.sqlite-shm"
    files = {
        "db": _file_size(db),
        "wal": _file_size(wal),
        "shm": _file_size(shm),
    }
    warn = _int_env("AURA_CODEX_WAL_WARN_BYTES", DEFAULT_CODEX_WAL_WARN_BYTES)
    critical = _int_env("AURA_CODEX_WAL_CRITICAL_BYTES", DEFAULT_CODEX_WAL_CRITICAL_BYTES)
    wal_bytes = int(files["wal"]["bytes"])
    level = "ok"
    if wal_bytes >= critical:
        level = "critical"
    elif wal_bytes >= warn:
        level = "warning"

    holder_check, holders = _lsof_holders([db, wal, shm])
    holder_count = len(holders)
    checkpoint_ready = bool(files["db"]["exists"] and holder_check == "ok" and holder_count == 0)
    return {
        "home": str(codex_home),
        "level": level,
        "thresholds": {"warning_bytes": warn, "critical_bytes": critical},
        "files": files,
        "holder_check": holder_check,
        "holder_count": holder_count,
        "holders": holders,
        "checkpoint_ready": checkpoint_ready,
        "safe_operator_hints": [
            f"lsof {db} {wal} {shm}",
            f"sqlite3 {db} 'PRAGMA wal_checkpoint(TRUNCATE);'",
        ],
    }
