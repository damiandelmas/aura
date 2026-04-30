"""JSON formatting for CLI output."""

import json


def output(data, force_json=False):
    """Output data as stable JSON.

    Args:
        data: Data to output (list, dict, or other JSON-serializable)
        force_json: Legacy compatibility flag; ignored because JSON is default.
    """
    print(json.dumps(data))
