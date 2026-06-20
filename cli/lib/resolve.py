"""The resolver seam — pure scheme dispatch, zero domain knowledge.

A *pointer* is ``scheme://path``. A bare value (no ``://``) is a *literal*.
Resolution looks the scheme up in a registry and calls its resolver; a literal or
an unknown scheme passes through unchanged — so a new capability (secret deref,
Runway binding) is added later by registering one resolver, never by editing
callers or this file.

This module holds NO domain knowledge. Domain resolvers self-register from their
own module (e.g. the ``fleet-id`` resolver lives in ``lib.fleets`` and registers
itself at import). Adding a node type adds nothing here.
"""

from __future__ import annotations

from typing import Any, Callable

_RESOLVERS: dict[str, Callable[[str, dict], Any]] = {}


def register(scheme: str, fn: Callable[[str, dict], Any]) -> None:
    """Register a resolver for a pointer scheme. Idempotent (last wins)."""
    _RESOLVERS[scheme] = fn


def registered_schemes() -> list[str]:
    return sorted(_RESOLVERS)


def resolve(pointer: Any, ctx: dict | None = None) -> Any:
    """Resolve one pointer.

    ``scheme://path`` -> its resolver(path, ctx); bare value -> literal as-is;
    unknown scheme -> opaque passthrough (returned unchanged, never raises).
    """
    if not isinstance(pointer, str):
        return pointer
    scheme, sep, path = pointer.partition("://")
    if not sep:
        return pointer  # literal
    fn = _RESOLVERS.get(scheme)
    return fn(path, ctx or {}) if fn else pointer  # unknown -> raw passthrough


def resolve_map(d: dict | None, ctx: dict | None = None) -> dict:
    """Resolve every value in a flat dict (config blobs). Lists resolve element-wise."""
    out: dict[str, Any] = {}
    for k, v in (d or {}).items():
        out[k] = [resolve(x, ctx) for x in v] if isinstance(v, list) else resolve(v, ctx)
    return out
