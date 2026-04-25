"""Capture seat terminal output."""

import argparse

from commands import check


def run(args):
    """Return recent terminal residue for a seat/agent."""
    check_args = argparse.Namespace(
        name=args.name,
        output=True,
        lines=getattr(args, "lines", 20),
    )
    result = check.run(check_args)
    from lib import seat_schema
    if result.get("ok"):
        result["capture"] = True
        result["seat"] = result.get("name")
        result = seat_schema.enrich(result)
    return result
