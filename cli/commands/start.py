"""Human-friendly fresh seat start command.

`aura start FLEET SEAT` is intentionally thin sugar over `aura spawn`.
It is for fresh, non-identity-bound Codex seats. Desks identity placement
continues to use the explicit Desks launch path.
"""

from __future__ import annotations

import argparse
import os

from commands import spawn


def _spawn_args(args) -> argparse.Namespace:
    return argparse.Namespace(
        name=args.seat,
        fleet=args.fleet,
        fleet_id=None,
        knowledge=None,
        memory=None,
        resume_session=None,
        identity_provider=None,
        identity_id=None,
        identity_label=None,
        at=None,
        prompt=None,
        work=None,
        cwd=args.cwd or os.getcwd(),
        context=None,
        wait=False,
        timeout=30,
        model=args.model,
        as_pane=True,
        silent=False,
        runtime="codex",
        profile=None,
        launch_command=None,
    )


def run(args):
    """Start a fresh Codex seat inside an Aura fleet."""
    return spawn.run(_spawn_args(args))
