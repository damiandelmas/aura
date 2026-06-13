"""Tests for discord_bridge reaction helpers.

These tests load the helper functions directly via importlib so they work
without the discord.py library installed (the module imports discord lazily /
only when actually running the bot loop).  We exercise _mark_processing_start
and _mark_delivery_outcome with a FakeMessage that records add_reaction /
remove_reaction calls.
"""
import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_bridge(unique_name: str = "discord_bridge"):
    path = ROOT / "cli" / "commands" / "discord_bridge.py"
    spec = importlib.util.spec_from_file_location(unique_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Stub the discord import so the module loads without the discord library.
    import types
    fake_discord = types.ModuleType("discord")
    fake_discord.Client = object
    sys.modules.setdefault("discord", fake_discord)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


class FakeMessage:
    """Minimal async-compatible message stub."""

    def __init__(self):
        self.added: list[str] = []
        self.removed: list[tuple[str, object]] = []

    async def add_reaction(self, emoji: str) -> None:
        self.added.append(emoji)

    async def remove_reaction(self, emoji: str, user: object) -> None:
        self.removed.append((emoji, user))


FAKE_USER = object()


@pytest.mark.asyncio
async def test_start_adds_eyes():
    bridge = _load_bridge("bridge_start")
    msg = FakeMessage()
    await bridge._mark_processing_start(msg)
    assert "👀" in msg.added, "start must add 👀"
    assert msg.removed == [], "start must not remove anything"


@pytest.mark.asyncio
async def test_delivery_success_adds_mailbox_not_checkmark():
    bridge = _load_bridge("bridge_ok")
    msg = FakeMessage()
    await bridge._mark_delivery_outcome(msg, FAKE_USER, ok=True)
    assert "📬" in msg.added, "delivery success must add 📬"
    assert "✅" not in msg.added, "✅ must NEVER be added — bridge cannot observe completion"
    assert "❌" not in msg.added, "no ❌ on success"
    # 👀 must have been removed
    removed_emojis = [e for e, _ in msg.removed]
    assert "👀" in removed_emojis, "delivery success must remove 👀"


@pytest.mark.asyncio
async def test_delivery_failure_adds_cross():
    bridge = _load_bridge("bridge_fail")
    msg = FakeMessage()
    await bridge._mark_delivery_outcome(msg, FAKE_USER, ok=False)
    assert "❌" in msg.added, "delivery failure must add ❌"
    assert "✅" not in msg.added, "✅ must never be added"
    assert "📬" not in msg.added, "📬 must not be added on failure"
    removed_emojis = [e for e, _ in msg.removed]
    assert "👀" in removed_emojis, "delivery failure must remove 👀"
