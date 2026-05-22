"""Manage package-local Aura skills."""

from __future__ import annotations

from lib import skill_libraries


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except skill_libraries.SkillLibraryError as exc:
        return exc.to_dict()
    except Exception as exc:
        return {"ok": False, "error": "skills-command-failed", "detail": str(exc)}


def run(args):
    action = getattr(args, "skills_action", None)
    if action == "apply":
        return _handle(
            skill_libraries.apply,
            args.agent,
            args.skill or [],
            mode=args.mode,
            replace=bool(getattr(args, "replace", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
    if action == "list":
        return _handle(skill_libraries.list_skills, args.agent)
    if action == "doctor":
        return _handle(skill_libraries.doctor, args.agent)
    if action == "remove":
        return _handle(skill_libraries.remove, args.agent, args.skill_name, dry_run=bool(getattr(args, "dry_run", False)))
    if action == "sync":
        return _handle(
            skill_libraries.sync,
            args.agent,
            dry_run=bool(getattr(args, "dry_run", False)),
            prune=bool(getattr(args, "prune", False)),
        )
    if action == "inventory":
        return _handle(
            skill_libraries.inventory,
            roots=getattr(args, "root", None),
            include_packages=not bool(getattr(args, "no_packages", False)),
        )
    if action == "duplicates":
        return _handle(
            skill_libraries.duplicates,
            roots=getattr(args, "root", None),
            include_packages=not bool(getattr(args, "no_packages", False)),
            include_identical=bool(getattr(args, "include_identical", False)),
        )
    if action == "diff":
        return _handle(
            skill_libraries.diff_name,
            args.name,
            roots=getattr(args, "root", None),
            include_packages=not bool(getattr(args, "no_packages", False)),
        )
    if action == "adopt":
        return _handle(
            skill_libraries.adopt_existing,
            args.agent,
            dry_run=not bool(getattr(args, "write", False)),
            replace_lock=bool(getattr(args, "replace_lock", False)),
        )
    return {"ok": False, "error": f"unknown skills action: {action}"}
