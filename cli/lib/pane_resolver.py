"""Resolve a physical tmux pane to a native runtime session id.

Aura live truth starts from the pane on screen and resolves to the runtime
session id by exact evidence only:

    tmux pane -> pane pid/env/cwd/process -> runtime_session_id

`resolve_pane()` is read-only. `bind_gates()` evaluates the safety invariants a
caller must pass before writing a binding; the actual registry/session-ledger
write stays in `commands/sessions.py` so the established bind path is reused.
"""

from __future__ import annotations

from pathlib import Path
import os
from typing import Any, Callable

from lib import bind_guard, registry, runtime_session, tmux_mirror


# Single source of truth lives in bind_guard; aliased here for existing callers.
_AURA_SESSION_ENV = bind_guard.AURA_OWNED_SESSION_ENVS
_PACKAGE_ENV_KEYS = (
    "AURA_AGENT_PACKAGE_ID",
    "AURA_AGENT_PACKAGE_ROOT",
    "AURA_RUNTIME_CAPSULE_REF",
    "CODEX_HOME",
    "AURA_SEAT_INSTANCE_ID",
)
_COMMAND_RUNTIME_HINTS = {
    "codex": "codex",
    "omx": "omx",
    "claude": "claude-code",
    "node": "claude-code",
    "gjc": "gajae-code",
}


def _pane_pid(pane: dict[str, Any]) -> int | None:
    raw = pane.get("pane_pid")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _pane_env(pane_pid: int | None) -> dict[str, str]:
    """Merge process environ across the pane pid and its descendants (parent wins)."""
    if not pane_pid:
        return {}
    merged: dict[str, str] = {}
    for pid in runtime_session._descendant_pids(int(pane_pid)):
        env = runtime_session._read_process_environ(pid)
        for key, value in env.items():
            merged.setdefault(key, value)
    return merged


def _runtime_from_command(command: str | None) -> str | None:
    if not command:
        return None
    return _COMMAND_RUNTIME_HINTS.get(str(command).strip().lower())


def _pane_codex_home(pane_env: dict[str, str]) -> str | None:
    value = pane_env.get("CODEX_HOME")
    return str(Path(value).expanduser()) if value else None


def _discover_transcript(session_id: str | None, *, codex_home: str | None, record: dict | None) -> str | None:
    """Find `<root>/sessions/**/*{session_id}*.jsonl` under the pane's actual home first."""
    if not session_id:
        return None
    roots: list[Path] = []
    if codex_home:
        roots.append(Path(codex_home).expanduser())
    if record:
        for key in ("native_state_ref", "codex_package_codex_home"):
            value = record.get(key)
            if value:
                roots.append(Path(str(value)).expanduser())
        runtime_home = record.get("runtime_home")
        if runtime_home:
            roots.append(Path(str(runtime_home)).expanduser() / ".codex")
    roots.append(Path.home() / ".codex")

    seen: set[str] = set()
    matches: list[Path] = []
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        sessions = root / "sessions"
        if not sessions.exists():
            continue
        try:
            matches.extend(sessions.glob(f"**/*{session_id}*.jsonl"))
        except OSError:
            continue
    if not matches:
        return None
    matches.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    return str(matches[0])


def _compact_match(record: dict | None) -> dict[str, Any] | None:
    if not record:
        return None
    fleet = record.get("fleet")
    seat = record.get("seat") or record.get("name")
    return {
        key: value
        for key, value in {
            "fleet": fleet,
            "seat": seat,
            "target": f"{fleet}:{seat}" if fleet and seat else None,
            "runtime": record.get("runtime"),
            "pane_ref": record.get("pane_ref"),
            "seat_instance_id": record.get("seat_instance_id"),
            "runtime_session_id": record.get("runtime_session_id") or record.get("session_id"),
            "runtime_session_binding": record.get("runtime_session_binding"),
            "agent_package_id": record.get("agent_package_id"),
            "agent_package_root": record.get("agent_package_root"),
        }.items()
        if value is not None
    }


def _match_registry_row(pane: dict[str, Any]) -> dict | None:
    pane_id = str(pane.get("pane_id") or "")
    session = str(pane.get("tmux_session") or pane.get("physical_fleet") or "")
    if not pane_id:
        return None
    exact = f"tmux:{session}:{pane_id}"
    fallback = None
    for record in registry.read_registry().values():
        ref = str(record.get("pane_ref") or "")
        if not ref:
            continue
        if ref == exact:
            return record
        if ref.endswith(f":{pane_id}"):
            fallback = fallback or record
    return fallback


def _package_env_status(pane_env: dict[str, str], record: dict | None) -> dict[str, Any]:
    """Compare pane env / registry against the intended package root.

    Canonical implementation lives in ``bind_guard.package_env_status`` so every
    bind writer shares one body-integrity definition; kept here as a thin alias
    for existing pane-resolver callers.
    """
    return bind_guard.package_env_status(pane_env, record)


def _resolve_pane_id(
    pane: str | None,
    current: bool,
    *,
    runner: Callable[..., Any] | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (session, pane_id, error)."""
    if current and not pane:
        pane = os.environ.get("TMUX_PANE")
        if not pane:
            return None, None, "no-current-pane: $TMUX_PANE is unset"
    if not pane:
        return None, None, "pane-required: pass --pane %ID or --current"
    session, pane_id = tmux_mirror._pane_ref_parts(pane)
    if not pane_id:
        return None, None, f"invalid-pane-ref: {pane}"
    return session, pane_id, None


def _resolve_from_record(pane_rec: dict[str, Any], matched: dict | None) -> dict[str, Any]:
    """Resolve session evidence + package status for an already-listed pane record.

    Shared by resolve_pane (single pane) and classify_physical (every pane), so the
    exact-evidence ladder is defined once.
    """
    pane_pid = _pane_pid(pane_rec)
    pane_env = _pane_env(pane_pid)
    runtime_hint = (matched or {}).get("runtime") or _runtime_from_command(pane_rec.get("pane_current_command"))
    codex_home = _pane_codex_home(pane_env)

    session_id: str | None = None
    source: str | None = None
    confidence = "none"
    evidence: dict[str, Any] = {}
    candidates: list[dict[str, Any]] = []

    # 1. Aura-owned process env (reliable; CODEX_THREAD_ID is excluded by design).
    for name in _AURA_SESSION_ENV:
        value = pane_env.get(name)
        if value:
            session_id, source, confidence = value, "tmux-pane:env", "exact"
            evidence = {"env": name}
            break

    # 2. Existing bound registry row for the same pane.
    if not session_id and matched and runtime_session.is_bound_session(matched):
        sid = matched.get("runtime_session_id") or matched.get("session_id")
        if sid:
            session_id, source, confidence = sid, "tmux-pane:registry", "exact"
            evidence = {"matched_pane_ref": matched.get("pane_ref")}

    # 3. Codex resume argv (exact) or unbound state-thread candidates.
    if not session_id and runtime_hint in runtime_session.CODEX_BACKED_RUNTIMES and pane_pid:
        disc = runtime_session.discover_from_pane_pid(
            runtime_hint,
            pane_pid,
            seat_name=(matched or {}).get("seat") or (matched or {}).get("name"),
            launch_id=(matched or {}).get("aura_launch_id"),
        )
        disc_sid = disc.get("runtime_session_id")
        disc_src = disc.get("runtime_session_source")
        if disc_sid and disc_src == "argv:codex-resume":
            session_id, source, confidence = disc_sid, "tmux-pane:argv", "exact"
            evidence = {"argv_source": disc_src}
        else:
            for candidate in disc.get("runtime_session_possible_matches") or []:
                candidates.append(candidate)

    transcript_path = _discover_transcript(session_id, codex_home=codex_home, record=matched)
    if session_id and not evidence.get("transcript_path") and transcript_path:
        evidence = {**evidence, "transcript_path": transcript_path}
    if not session_id and candidates:
        confidence = "candidates"

    return {
        "pane_pid": pane_pid,
        "runtime_hint": runtime_hint,
        "pane_codex_home": codex_home,
        "runtime_session_id": session_id,
        "runtime_session_source": source,
        "runtime_session_confidence": confidence,
        "runtime_session_evidence": evidence or None,
        "transcript_path": transcript_path,
        "candidates": candidates,
        "package_env_status": _package_env_status(pane_env, matched),
        "pane_seat_instance_id": pane_env.get("AURA_SEAT_INSTANCE_ID"),
        "pane_agent_package_id": pane_env.get("AURA_AGENT_PACKAGE_ID"),
    }


def resolve_pane(
    pane: str | None = None,
    current: bool = False,
    *,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Read-only resolution of a tmux pane to a runtime session id."""
    session, pane_id, error = _resolve_pane_id(pane, current, runner=runner)
    if error:
        return {"ok": False, "error": error}

    mirror = tmux_mirror.list_physical_panes(runner=runner)
    if not mirror.get("ok"):
        return {"ok": False, "error": "tmux-mirror-unavailable", "detail": mirror.get("error")}

    pane_rec = None
    for row in mirror.get("panes") or []:
        if str(row.get("pane_id")) != pane_id:
            continue
        if session and str(row.get("tmux_session") or row.get("physical_fleet") or "") != session:
            continue
        pane_rec = row
        break
    if pane_rec is None:
        return {"ok": False, "error": "pane-not-found", "pane_id": pane_id, "tmux_session": session}

    matched = _match_registry_row(pane_rec)
    core = _resolve_from_record(pane_rec, matched)
    return {
        "ok": True,
        "schema": "aura.pane_resolver.v1",
        "pane_ref": pane_rec.get("pane_ref"),
        "tmux_session": pane_rec.get("tmux_session") or pane_rec.get("physical_fleet"),
        "window_id": pane_rec.get("window_id"),
        "window_name": pane_rec.get("window_name"),
        "pane_id": pane_rec.get("pane_id"),
        "pane_pid": core["pane_pid"],
        "pane_current_path": pane_rec.get("pane_current_path"),
        "pane_current_command": pane_rec.get("pane_current_command"),
        "runtime_hint": core["runtime_hint"],
        "managed_state": "managed" if matched else "unmanaged",
        "matched_row": _compact_match(matched),
        "runtime_session_id": core["runtime_session_id"],
        "runtime_session_source": core["runtime_session_source"],
        "runtime_session_confidence": core["runtime_session_confidence"],
        "runtime_session_evidence": core["runtime_session_evidence"],
        "transcript_path": core["transcript_path"],
        "evidence_source": core["runtime_session_source"],
        "candidates": core["candidates"],
        "pane_codex_home": core["pane_codex_home"],
        "package_env_status": core["package_env_status"],
        "pane_seat_instance_id": core["pane_seat_instance_id"],
    }


def bind_gates(
    res: dict[str, Any],
    *,
    previous: dict | None,
    repair: bool = False,
) -> dict[str, Any]:
    """Evaluate the bind safety invariants. Return {ok, reason?, detail?}.

    A bind must refuse on ambiguity or contradictory body evidence. A real
    runtime_session_id is not sufficient if package/root evidence disagrees.
    """
    if not res.get("ok"):
        return {"ok": False, "reason": "unresolved-pane", "detail": res.get("error")}

    if res.get("candidates") and not res.get("runtime_session_id"):
        return {
            "ok": False,
            "reason": "multiple-candidates",
            "detail": "low-confidence candidates remain; resolve explicitly before binding",
            "candidates": res.get("candidates"),
        }

    if not res.get("runtime_session_id") or res.get("runtime_session_confidence") != "exact":
        return {
            "ok": False,
            "reason": "no-exact-evidence",
            "detail": "no exact runtime session evidence for this pane (no env/registry/argv match)",
        }

    # seat_instance_id env vs registry must agree when both are present.
    pane_instance = res.get("pane_seat_instance_id")
    registry_instance = (previous or {}).get("seat_instance_id")
    if pane_instance and registry_instance and pane_instance != registry_instance:
        return {
            "ok": False,
            "reason": "seat-instance-mismatch",
            "detail": "pane AURA_SEAT_INSTANCE_ID does not match registry seat row",
            "expected_seat_instance_id": registry_instance,
            "actual_seat_instance_id": pane_instance,
        }

    # package/env/root alignment must not contradict.
    pkg = res.get("package_env_status") or {}
    if pkg.get("status") == "mismatch":
        return {
            "ok": False,
            "reason": "package-env-mismatch",
            "detail": "pane package/runtime env contradicts the registry/intended package body",
            "mismatches": pkg.get("mismatches"),
        }

    # a discovered transcript must live under the pane's actual Codex home.
    transcript = res.get("transcript_path")
    codex_home = res.get("pane_codex_home")
    if transcript and codex_home:
        try:
            transcript_resolved = Path(transcript).expanduser().resolve()
            home_resolved = Path(codex_home).expanduser().resolve()
            if home_resolved not in transcript_resolved.parents:
                return {
                    "ok": False,
                    "reason": "transcript-outside-home",
                    "detail": "discovered transcript is not under the pane's CODEX_HOME",
                    "transcript_path": transcript,
                    "pane_codex_home": codex_home,
                }
        except OSError:
            pass

    # an explicit --target must point at the same pane unless repairing.
    if previous and not repair:
        previous_ref = str(previous.get("pane_ref") or "")
        pane_ref = str(res.get("pane_ref") or "")
        if previous_ref and pane_ref and previous_ref != pane_ref:
            return {
                "ok": False,
                "reason": "target-pane-mismatch",
                "detail": "registry target points at a different pane; pass --repair to rebind",
                "registry_pane_ref": previous_ref,
                "resolved_pane_ref": pane_ref,
            }

    return {"ok": True}


def classify_physical(
    *,
    include_hidden: bool = False,
    resolve: bool = False,
    include_stale: bool = True,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Classify every live tmux pane as the live graph read model.

    States:
      managed-bound    pane + managed seat with an exact/bound runtime session
      managed-unbound  pane + managed seat, no session yet (legitimate, e.g. fresh)
      unmanaged        pane with no managed seat row
      stale            managed seat row whose pane is gone
      mismatch         pane + managed seat whose package/env body contradicts the seat

    `resolve=False` is cheap (registry binding fields only; cannot detect mismatch).
    `resolve=True` runs the per-pane resolver for managed panes only, which adds true
    binding verification and the mismatch (contamination) verdict. spawned-unbound is
    never reported as mismatch — only contradictory body evidence is.
    """
    base = tmux_mirror.list_physical_panes(runner=runner)
    if not base.get("ok"):
        return {"ok": False, "error": "tmux-mirror-unavailable", "detail": base.get("error")}

    records = [
        row for row in registry.read_registry().values()
        if include_hidden or not row.get("hidden")
    ]
    joined = tmux_mirror.join_managed(base.get("panes") or [], records)
    rows_by_ref = {str(row.get("pane_ref")): row for row in records if row.get("pane_ref")}

    panes_out: list[dict[str, Any]] = []
    counts: dict[str, int] = {
        "managed-bound": 0, "managed-unbound": 0, "unmanaged": 0, "mismatch": 0, "stale": 0,
    }
    for pane in joined.get("panes") or []:
        entry = {
            key: pane.get(key)
            for key in (
                "pane_ref", "tmux_session", "window_name", "pane_id", "pane_pid",
                "pane_current_command", "pane_current_path",
            )
        }
        entry["managed"] = pane.get("managed") or []
        if pane.get("managed_state") != "managed":
            state = "unmanaged"
        else:
            row = rows_by_ref.get(str(pane.get("pane_ref")))
            entry["agent_package_id"] = (row or {}).get("agent_package_id")
            if resolve:
                core = _resolve_from_record(pane, row)
                pkg = core.get("package_env_status") or {}
                entry["runtime_session_id"] = core.get("runtime_session_id")
                entry["runtime_session_source"] = core.get("runtime_session_source")
                entry["pane_agent_package_id"] = core.get("pane_agent_package_id")
                entry["package_env_status"] = pkg.get("status")
                if pkg.get("mismatches"):
                    entry["mismatches"] = pkg.get("mismatches")
                if pkg.get("status") == "mismatch":
                    state = "mismatch"
                elif core.get("runtime_session_id") and core.get("runtime_session_confidence") == "exact":
                    state = "managed-bound"
                elif runtime_session.is_bound_session(row):
                    state = "managed-bound"
                else:
                    state = "managed-unbound"
            else:
                state = "managed-bound" if runtime_session.is_bound_session(row) else "managed-unbound"
        entry["physical_state"] = state
        counts[state] = counts.get(state, 0) + 1
        panes_out.append(entry)

    stale_all = []
    for row in joined.get("missing_managed") or []:
        item = dict(row)
        item["physical_state"] = "stale"
        stale_all.append(item)
    counts["stale"] = len(stale_all)
    counts["panes"] = len(panes_out)

    return {
        "ok": True,
        "schema": "aura.view.physical.classified.v1",
        "view_scope": "physical",
        "resolved": bool(resolve),
        "counts": counts,
        "panes": panes_out,
        # Stale rows are registry drift, not live state. They are a cleanup queue
        # (`aura seat sweep`), so the detail list is opt-in; the count always shows.
        "stale": stale_all if include_stale else [],
    }
