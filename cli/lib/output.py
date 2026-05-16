"""JSON formatting for CLI output."""

import json


def _compact_for_cli(data):
    if not isinstance(data, dict):
        return data
    omit = data.get("_aura_cli_omit") or []
    if not omit:
        return data
    omitted = set(omit) | {"_aura_cli_omit"}
    return {key: value for key, value in data.items() if key not in omitted}


def output(data, force_json=False):
    """Output data as stable JSON.

    Args:
        data: Data to output (list, dict, or other JSON-serializable)
        force_json: Legacy compatibility flag; ignored because JSON is default.
    """
    print(json.dumps(_compact_for_cli(data)))
