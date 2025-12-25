"""List all agents."""


def run(args):
    """List all agents."""
    from lib import mesh

    result = mesh.discover()
    if not result.get("ok"):
        return result

    agents = result.get("agents", [])

    # Apply filters
    if args.status:
        agents = [a for a in agents if a.get("status") == args.status]
    if args.mode:
        agents = [a for a in agents if a.get("delivery_mode") == args.mode]

    # Return simplified list
    return [
        {
            "name": a.get("name"),
            "status": a.get("status", "unknown"),
            "mode": a.get("delivery_mode", "immediate"),
            "last_seen": a.get("last_seen", "")[:19]  # Trim to seconds
        }
        for a in agents
    ]
