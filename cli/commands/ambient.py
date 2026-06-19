"""Render ambient Aura context for runtime hooks."""

from __future__ import annotations

from lib import ambient


def run(args):
    from lib import terminal

    values = list(getattr(args, "ambient_args", None) or [])
    refresh = False
    if values and values[0] == "refresh":
        refresh = True
        values = values[1:]
    target = values[0] if values else "self"
    return ambient.build_ambient(target, terminal=terminal, refresh=refresh)
