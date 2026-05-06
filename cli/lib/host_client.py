"""Client helpers for the local Aura PTY host protocol."""

from __future__ import annotations

import json
import socket


class HostClientError(RuntimeError):
    """Protocol request failed with enough stage evidence for delivery policy."""

    def __init__(self, message: str, *, stage: str, possible_write: bool = False):
        super().__init__(message)
        self.stage = stage
        self.possible_write = possible_write


def request(socket_path: str, payload: dict, *, timeout: float = 5.0) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(timeout)
        try:
            conn.connect(socket_path)
        except Exception as exc:
            raise HostClientError(str(exc), stage="connect", possible_write=False) from exc
        try:
            conn.sendall(json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n")
        except Exception as exc:
            raise HostClientError(str(exc), stage="send", possible_write=False) from exc
        chunks = []
        while True:
            try:
                chunk = conn.recv(65536)
            except Exception as exc:
                raise HostClientError(str(exc), stage="receive", possible_write=True) from exc
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk:
                break
    raw_lines = b"".join(chunks).splitlines()
    if not raw_lines:
        raise HostClientError("host closed without response", stage="receive", possible_write=True)
    try:
        return json.loads(raw_lines[0].decode("utf-8"))
    except Exception as exc:
        raise HostClientError(str(exc), stage="parse", possible_write=True) from exc
