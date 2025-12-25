"""JSON/table formatting for CLI output."""

import sys
import json


def output(data, force_json=False):
    """Output data as JSON or pretty table based on context.

    Args:
        data: Data to output (list, dict, or other JSON-serializable)
        force_json: If True, always output as JSON regardless of TTY
    """
    if force_json or not sys.stdout.isatty():
        print(json.dumps(data))
    else:
        if isinstance(data, list):
            print_table(data)
        elif isinstance(data, dict):
            print_dict(data)
        else:
            print(json.dumps(data))


def print_table(rows):
    """Format list of dicts as aligned table.

    Args:
        rows: List of dicts with consistent keys
    """
    if not rows:
        return

    # Handle list of non-dicts
    if not isinstance(rows[0], dict):
        for row in rows:
            print(row)
        return

    # Get column headers from first row
    headers = list(rows[0].keys())

    # Calculate column widths (max of header and all values)
    widths = {}
    for h in headers:
        widths[h] = len(str(h))
        for row in rows:
            val_len = len(str(row.get(h, '')))
            if val_len > widths[h]:
                widths[h] = val_len

    # Print header
    header_line = '  '.join(str(h).upper().ljust(widths[h]) for h in headers)
    print(header_line)
    print('-' * len(header_line))

    # Print rows
    for row in rows:
        row_line = '  '.join(str(row.get(h, '')).ljust(widths[h]) for h in headers)
        print(row_line)


def print_dict(data):
    """Pretty print a single dict.

    Args:
        data: Dict to print in key: value format
    """
    if not data:
        return

    # Calculate max key width for alignment
    max_key_len = max(len(str(k)) for k in data.keys())

    for key, value in data.items():
        # Format nested structures as JSON
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        print(f"{str(key).ljust(max_key_len)}: {value}")
