"""Shared binding invariants — the single source of truth for the bind contract.

Every path that writes a runtime-session binding (pane bind, codex hook, nonce,
current-process, footer, spawn observe/nonce/resume) must obey the body-integrity
veto: a real session id must never bind onto a contaminated or wrong body. Before
this module those checks lived only inside ``pane_resolver`` and only ran for
``aura sessions bind-pane``; every other writer bound blind. See
``context/changes/code/260603-1652_pane-runtime-session-resolver.md`` for the
contract this enforces.

This module owns:
  - ``AURA_OWNED_SESSION_ENVS``: the Aura-owned session-id env allowlist.
  - ``package_env_status(env, record)``: canonical body-integrity comparison.
  - ``body_gates(record, *, env, seat_instance_id, repair)``: pane-independent
    veto that every writer can call (no live tmux pane required).

``pane_resolver.bind_gates`` layers the pane-only gates (exact-evidence,
multiple-candidates, transcript-outside-home, target-pane-mismatch) on top of the
body veto defined here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


# Single source of truth for the Aura-owned runtime-session id environment
# variables. CODEX_THREAD_ID is intentionally NOT here: it is inherited across
# tmux-spawned Codex seats and would bind the wrong session.
AURA_OWNED_SESSION_ENVS = ("AURA_RUNTIME_SESSION_ID", "AURA_SESSION_ID")


def _norm(value: Any) -> str | None:
    if not value:
        return None
    return str(Path(str(value)).expanduser()).rstrip("/")


def package_env_status(env: dict[str, str] | None, record: dict | None) -> dict[str, Any]:
    """Compare a body's process env / registry record against its intended package root.

    ``env`` is the body's process environment: the pane ``/proc`` env, or the
    agent's own ``os.environ`` for an in-body hook bind. Pass ``None``/``{}`` when
    no body process env is available (e.g. a spawner binding a child) — only
    record-internal fields are then compared. This function NEVER reads
    ``os.environ`` itself; the caller decides what env (if any) is the body.

    Only fields present on BOTH sides are asserted, so a thin record never
    false-refuses. Returns status: ``not-package`` | ``ok`` | ``mismatch`` |
    ``unknown``.
    """
    env = env or {}
    record = record or {}
    intended = env.get("AURA_AGENT_PACKAGE_ROOT") or record.get("agent_package_root")
    is_package = bool(
        intended
        or env.get("AURA_AGENT_PACKAGE_ID")
        or record.get("agent_package_id")
    )
    if not is_package:
        return {"status": "not-package", "checks": [], "mismatches": []}

    intended_root = _norm(intended)
    checks: list[dict[str, Any]] = []

    def _check(name: str, left: Any, right: Any) -> None:
        if left in (None, "") or right in (None, ""):
            return
        checks.append({"check": name, "left": str(left), "right": str(right), "ok": str(left) == str(right)})

    def _check_under(name: str, value: Any, root: Any) -> None:
        """Assert `value` is the package root or lives under it (runtime-agnostic)."""
        if value in (None, "") or root in (None, ""):
            return
        try:
            child = Path(str(value)).expanduser()
            parent = Path(str(root)).expanduser()
            ok = child == parent or parent in child.parents
        except (OSError, ValueError):
            ok = str(value).startswith(str(root))
        checks.append({"check": name, "left": str(value), "right": f"under {root}", "ok": ok})

    _check("agent_package_id", env.get("AURA_AGENT_PACKAGE_ID"), record.get("agent_package_id"))
    _check(
        "agent_package_root",
        _norm(env.get("AURA_AGENT_PACKAGE_ROOT")),
        _norm(record.get("agent_package_root")),
    )
    if intended_root:
        expected_codex_home = str(Path(intended_root) / ".codex")
        _check("codex_home", _norm(env.get("CODEX_HOME")), expected_codex_home)
        _check("runtime_capsule_ref", _norm(env.get("AURA_RUNTIME_CAPSULE_REF")), intended_root)
        _check("registry_runtime_home", _norm(record.get("runtime_home")), intended_root)
        # native_state_ref is runtime-specific (.codex for codex, .omx for omx,
        # .gjc for gajae); assert only that it lives under the intended package
        # root so the universal gate stays runtime-agnostic while still catching a
        # state dir that points at a DIFFERENT package body.
        _check_under("registry_native_state_ref", _norm(record.get("native_state_ref")), intended_root)

    mismatches = [item for item in checks if not item["ok"]]
    status = "mismatch" if mismatches else ("ok" if checks else "unknown")
    return {
        "status": status,
        "intended_root": intended_root,
        "checks": checks,
        "mismatches": mismatches,
    }


def body_gates(
    record: dict | None,
    *,
    env: dict[str, str] | None = None,
    seat_instance_id: str | None = None,
    repair: bool = False,
) -> dict[str, Any]:
    """Pane-independent body-integrity veto for every bind writer.

    Refuses (``ok=False`` + stable ``reason``) when the body contradicts the seat
    the bind targets:
      - ``package-env-mismatch``: package id/root, ``CODEX_HOME``, capsule ref,
        registry ``runtime_home`` / ``native_state_ref`` disagree.
      - ``seat-instance-mismatch``: process ``AURA_SEAT_INSTANCE_ID`` != registry row.

    ``repair=True`` bypasses the veto (operator-intended rebind). A thin/``None``
    record with no package identity resolves to ``not-package`` → ``ok``. ``env``
    must be ``None`` when no body process env is available; it is NEVER read from
    ``os.environ`` here.
    """
    if repair:
        return {"ok": True, "repair": True}

    record = record or {}
    env = env or {}

    pane_instance = seat_instance_id or env.get("AURA_SEAT_INSTANCE_ID")
    registry_instance = record.get("seat_instance_id")
    if pane_instance and registry_instance and str(pane_instance) != str(registry_instance):
        return {
            "ok": False,
            "reason": "seat-instance-mismatch",
            "detail": "process AURA_SEAT_INSTANCE_ID does not match registry seat row",
            "expected_seat_instance_id": registry_instance,
            "actual_seat_instance_id": pane_instance,
        }

    status = package_env_status(env, record)
    if status.get("status") == "mismatch":
        return {
            "ok": False,
            "reason": "package-env-mismatch",
            "detail": "runtime body env contradicts the registry/intended package body",
            "mismatches": status.get("mismatches"),
        }

    return {"ok": True, "package_env_status": status}
