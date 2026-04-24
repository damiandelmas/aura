"""Stop a seat/agent."""

from commands import cut


def run(args):
    """Contract-name wrapper over cut."""
    result = cut.run(args)
    if result.get("ok"):
        result["stop"] = True
        result["seat"] = result.get("name")
    return result
