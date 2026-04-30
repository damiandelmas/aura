"""Aura Ether objective coordination commands."""

from __future__ import annotations


def _split_csv(values):
    result = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                result.append(part)
    return result


def run(args):
    from lib import ether, objectives, recommendations

    area = args.ether_area
    if area == "objective":
        action = args.objective_action
        if action == "create":
            record = objectives.create_objective(
                args.objective_id,
                title=getattr(args, "title", None),
                seats=_split_csv(getattr(args, "seat", None)),
            )
            return {"ok": True, "objective": record}
        if action == "list":
            return {"ok": True, "objectives": objectives.list_objectives(include_archived=getattr(args, "include_archived", False))}
        if action == "show":
            return {"ok": True, "objective": objectives.load_objective(args.objective_id)}
        if action == "add-seat":
            record = objectives.add_seats(args.objective_id, _split_csv(getattr(args, "seat", None)))
            return {"ok": True, "objective": record}
        if action == "archive":
            return {"ok": True, "objective": objectives.archive_objective(args.objective_id)}

    if area == "evaluate":
        objective = objectives.load_objective(args.objective_id)
        return ether.evaluate_objective(objective, dry_run=getattr(args, "dry_run", False))

    if area == "recommendations":
        rows = recommendations.list_recommendations(
            objective_id=getattr(args, "objective", None),
            status=getattr(args, "status", None),
            limit=getattr(args, "limit", 50),
        )
        return {"ok": True, "recommendations": rows}

    if area == "recommendation":
        if args.recommendation_action == "mark":
            row = recommendations.mark_recommendation(args.recommendation_id, args.status)
            if not row:
                return {"ok": False, "error": f"recommendation not found: {args.recommendation_id}"}
            return {"ok": True, "recommendation": row}

    return {"ok": False, "error": "unknown ether action"}
