"""Additive seat-schema aliases for Aura command outputs."""

from __future__ import annotations


# Allowlist for `aura seat tag` writes. Plan 011 phase 1 contract.
#
# Aura identity binding is provider-generic. `identity_provider` + `identity_id`
# is the load-bearing handle for whatever identity harness launched or adopted a
# live seat incarnation. `desks_identity_id` remains as a legacy compatibility
# alias while older rows and tools migrate.
#
# Flex project pointers stay in the allowlist because they are unrelated to the
# identity arc and remain useful as opaque project metadata exported into the
# runtime environment.
TAG_ALLOWLIST = frozenset({
    "desks_identity_id",
    "identity_provider",
    "identity_id",
    "identity_label",
    "identity_bound_at",
    "identity_bind_source",
    "identity_bind_confidence",
    "flex_project_manifest",
    "flex_project_root",
})


def identity_id_for(record: dict | None) -> str | None:
    """Return the generic identity id, falling back to the legacy Desks alias."""
    if not isinstance(record, dict):
        return None
    return record.get("identity_id") or record.get("desks_identity_id")


def identity_provider_for(record: dict | None) -> str | None:
    """Return the identity provider, inferring `desks` for legacy rows."""
    if not isinstance(record, dict):
        return None
    provider = record.get("identity_provider")
    if provider:
        return provider
    if record.get("desks_identity_id"):
        return "desks"
    return None


def infer_backend_ref(terminal_ref: str | None, *, fleet: str | None = None, name: str | None = None) -> str | None:
    """Return backend-local ref without the backend scheme.

    Existing Aura fields keep `terminal_ref` for compatibility. New seat fields use
    `backend` + `backend_ref` so future backends do not have to overload terminal
    language.
    """
    if terminal_ref:
        if terminal_ref.startswith("tmux:"):
            return terminal_ref[len("tmux:"):]
        return terminal_ref
    if fleet and name:
        return f"{fleet}:{name}"
    return None


def enrich(record: dict) -> dict:
    """Return record with additive seat/backend/provider aliases.

    This intentionally does not remove or rename legacy fields such as `name` and
    `terminal_ref`.
    """
    if not isinstance(record, dict):
        return record

    name = record.get("seat") or record.get("name")
    fleet = record.get("fleet")
    terminal_ref = record.get("terminal_ref")
    backend = record.get("backend")
    if not backend and terminal_ref:
        backend = "tmux" if str(terminal_ref).startswith("tmux:") else "terminal"
    if not backend and record.get("terminal") in {"alive", "missing", "killed"}:
        backend = "tmux"

    backend_ref = record.get("backend_ref") or infer_backend_ref(terminal_ref, fleet=fleet, name=name)

    if name is not None:
        record.setdefault("seat", name)
    if fleet and name:
        record.setdefault("seat_ref", f"{fleet}:{name}")
    if backend:
        record.setdefault("backend", backend)
    if backend_ref:
        record.setdefault("backend_ref", backend_ref)
    record.setdefault("provider", None)
    if record.get("runtime") is not None:
        record.setdefault("runtime_ref", record.get("runtime"))
    return record
