"""Manage Aura placement groups."""

from __future__ import annotations

from lib import placements


def run(args):
    action = getattr(args, "placement_action", None)
    if action == "list":
        rows = placements.list_placements()
        return {"ok": True, "schema": "aura.placements.v1", "placements": rows, "counts": {"placements": len(rows)}}
    if action == "show":
        record = placements.get_placement(args.placement)
        if not record:
            return {"ok": False, "error": f"placement not found: {args.placement}"}
        return {"ok": True, "schema": "aura.placement.v1", "placement": record}
    if action == "add":
        try:
            record = placements.add_member(
                args.placement,
                args.seat_ref,
                role=getattr(args, "role", None),
                kind=getattr(args, "kind", None) or "group",
                label=getattr(args, "label", None),
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "schema": "aura.placement.v1", "placement": record, "movement": "none"}
    if action == "remove":
        return placements.remove_member(args.placement, args.seat_ref)
    return {"ok": False, "error": f"unknown placement action: {action}"}
