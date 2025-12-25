"""Set agent properties."""


def run(args):
    """Set agent properties (mode, etc)."""
    from lib import mesh

    if args.mode:
        result = mesh.set_mode(args.name, args.mode)
        if result.get("ok"):
            return {"ok": True, "name": args.name, "mode": args.mode}
        return result

    return {"ok": False, "error": "no property specified (use --mode)"}
