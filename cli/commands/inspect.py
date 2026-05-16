"""Inspect one Aura seat through mechanical, raw, or semantic terminal views."""

from __future__ import annotations

import argparse

from commands import check, sense
from lib import seat_schema


def run(args):
    """Return one-seat inspection from existing check/capture/sense primitives."""
    lines = getattr(args, "lines", 40)
    if getattr(args, "sense", False):
        sense_args = argparse.Namespace(
            name=args.name,
            lines=lines,
            question=getattr(args, "question", None),
            features=getattr(args, "features", None),
            contract=getattr(args, "contract", None),
            sense_mode=getattr(args, "sense_mode", None),
            model=getattr(args, "model", None),
            ollama_host=getattr(args, "ollama_host", None),
            llm_timeout=getattr(args, "llm_timeout", None),
        )
        result = sense.run(sense_args)
        result["inspect"] = True
        result["inspect_mode"] = "sense"
        return seat_schema.enrich(result)

    check_args = argparse.Namespace(
        name=args.name,
        output=bool(getattr(args, "raw", False)),
        lines=lines,
        format=getattr(args, "format", "text"),
    )
    result = check.run(check_args)
    if result.get("ok"):
        output = result.get("output")
        if isinstance(output, list) and len(output) > lines:
            result["output"] = output[-lines:]
        result["inspect"] = True
        result["inspect_mode"] = "raw" if getattr(args, "raw", False) else "status"
        result["seat"] = result.get("name")
    return seat_schema.enrich(result)
