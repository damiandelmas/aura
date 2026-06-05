import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_router(name: str = "hermes_discord_router"):
    path = ROOT / "services" / "hermes_discord_router.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_bindings(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "aura.discord.channel_bindings.v1",
                "channels": {
                    "aura-channel": {
                        "default_target": "aura-route:router",
                        "aliases": {"eyes": "aura-route:eyes"},
                    },
                    "context-channel": {
                        "default_target": "hermes:context-owner",
                        "aliases": {
                            "owner": "hermes:context-owner",
                            "router": "aura-route:router",
                        },
                    },
                    "flex-channel": {
                        "default_target": "hermes:flex-context-owner",
                        "aliases": {"engine": "hermes:flex-context-owner"},
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_router_lists_only_hermes_channels(tmp_path):
    router = _load_router("hermes_router_channels")
    bindings = tmp_path / "bindings.json"
    _write_bindings(bindings)

    assert sorted(router._hermes_channels(bindings)) == ["context-channel", "flex-channel"]


def test_router_resolves_default_and_hermes_aliases(tmp_path):
    router = _load_router("hermes_router_routes")
    bindings = tmp_path / "bindings.json"
    _write_bindings(bindings)

    assert router._resolve_route("hello", "context-channel", bindings_path=bindings) == (
        "hermes:context-owner",
        "hello",
    )
    assert router._resolve_route("@owner status", "context-channel", bindings_path=bindings) == (
        "hermes:context-owner",
        "status",
    )
    assert router._resolve_route("@router status", "context-channel", bindings_path=bindings) is None
    assert router._resolve_route("hello", "aura-channel", bindings_path=bindings) is None


def test_router_posts_to_node_host(monkeypatch):
    router = _load_router("hermes_router_send")
    observed = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        observed["url"] = url
        observed["payload"] = json
        observed["timeout"] = timeout

        class Response:
            status_code = 202
            text = ""

            def json(self):
                return {"ok": True, "response": "ready"}

        return Response()

    monkeypatch.setattr(router.requests, "post", fake_post)

    result = router._send_to_node(
        "hermes:context-owner",
        "hello",
        "discord:damian",
        node_host_url="http://node-host.local/v1/messages",
    )

    assert result["ok"] is True
    assert result["response"] == "ready"
    assert observed["url"] == "http://node-host.local/v1/messages"
    assert observed["timeout"] == 180
    assert observed["payload"]["target"] == "hermes:context-owner"
    assert observed["payload"]["from"] == "service:discord-damian"
    assert observed["payload"]["metadata"]["bridge"] == "hermes-discord-router"


def test_router_splits_long_discord_replies():
    router = _load_router("hermes_router_split")
    chunks = router._split_discord_message("a" * 2001, limit=2000)

    assert len(chunks) == 2
    assert len(chunks[0]) == 2000
    assert len(chunks[1]) == 1


@pytest.mark.asyncio
async def test_router_typing_errors_do_not_escape():
    router = _load_router("hermes_router_typing")

    class Channel:
        async def trigger_typing(self):
            raise RuntimeError("typing denied")

    task = router._start_typing(Channel())
    await asyncio.sleep(0)
    await router._stop_typing(task)
