"""Send message to agent."""


def run(args):
    """Send message to agent."""
    from lib import mesh

    result = mesh.send_message(args.target, args.message, args.sender, args.mode)

    if result.get("ok"):
        return {
            "ok": True,
            "delivered": True,
            "message_id": result.get("message_id", "")
        }
    return result
