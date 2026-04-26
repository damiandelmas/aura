"""Local LLM transport helpers.

Aura keeps provider calls behind this small module so terminal perception can
use local models without coupling command code to Ollama's Python package.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"


def ollama_chat(
    messages: list[dict[str, str]],
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 8.0,
    temperature: float = 0.0,
    num_predict: int = 700,
) -> str:
    """Send a non-streaming Ollama chat request and return message content."""
    base = host.rstrip("/")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ollama request failed: {exc}") from exc

    try:
        body: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ollama returned invalid JSON") from exc

    message = body.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("ollama response missing message")
    content = message.get("content")
    if not isinstance(content, str):
        raise RuntimeError("ollama response missing message.content")
    return content
