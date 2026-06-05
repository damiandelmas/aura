#!/usr/bin/env python3
"""Shared Discord frontend for warm Hermes nodes.

This owns one Discord bot connection for Hermes-node channels and dispatches
messages to `hermes:<node>` targets through hermes-node-host.  It deliberately
does not run one full Hermes gateway per node, so warm nodes do not compete for
the same Discord bot token.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests


DEFAULT_ENV_PATH = Path.home() / ".aura" / "discord" / "env"
DEFAULT_BINDINGS_PATH = Path.home() / ".aura" / "discord" / "channel-bindings.json"
DEFAULT_NODE_HOST_URL = "http://127.0.0.1:7136/v1/messages"
DISCORD_API = "https://discord.com/api/v10"


def _load_env(path: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env_path = Path(path).expanduser() if path else DEFAULT_ENV_PATH
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _config(args: Any) -> tuple[str, str]:
    env = _load_env(getattr(args, "env_file", None))
    token = env.get("DISCORD_TOKEN") or env.get("AURA_DISCORD_TOKEN")
    channel_id = (
        getattr(args, "channel", None)
        or env.get("DISCORD_CHANNEL_ID")
        or env.get("AURA_DISCORD_CHANNEL_ID")
    )
    if not token:
        raise ValueError(f"missing DISCORD_TOKEN in environment or {DEFAULT_ENV_PATH}")
    if not channel_id:
        raise ValueError(f"missing DISCORD_CHANNEL_ID in environment or {DEFAULT_ENV_PATH}")
    return token, str(channel_id)


def _bindings_path(path: str | Path | None = None) -> Path:
    return Path(path or os.environ.get("HERMES_DISCORD_ROUTER_BINDINGS") or DEFAULT_BINDINGS_PATH).expanduser()


def _load_bindings(path: str | Path | None = None) -> dict[str, Any]:
    try:
        data = json.loads(_bindings_path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"schema": "aura.discord.channel_bindings.v1", "channels": {}}
    if not isinstance(data, dict):
        return {"schema": "aura.discord.channel_bindings.v1", "channels": {}}
    channels = data.get("channels")
    if not isinstance(channels, dict):
        data["channels"] = {}
    return data


def _is_hermes_target(target: Any) -> bool:
    return isinstance(target, str) and target.startswith("hermes:")


def _binding_has_hermes(binding: dict[str, Any]) -> bool:
    if _is_hermes_target(binding.get("default_target")):
        return True
    aliases = binding.get("aliases")
    if isinstance(aliases, dict):
        return any(_is_hermes_target(target) for target in aliases.values())
    return False


def _hermes_channels(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    channels = _load_bindings(path).get("channels", {})
    return {
        str(channel_id): binding
        for channel_id, binding in channels.items()
        if isinstance(binding, dict) and _binding_has_hermes(binding)
    }


def _parse_route(content: str) -> tuple[str | None, str] | None:
    text = (content or "").strip()
    if not text:
        return None
    braced = re.match(r"^@\{([^}]+)\}\s+([\s\S]+)$", text)
    if braced:
        return braced.group(1), braced.group(2).strip()
    match = re.match(r"^@([A-Za-z0-9_.:-]+)\s+([\s\S]+)$", text)
    if match:
        return match.group(1), match.group(2).strip()
    return None, text


def _resolve_route(content: str, channel_id: int | str, *, bindings_path: str | Path | None = None) -> tuple[str, str] | None:
    binding = _hermes_channels(bindings_path).get(str(channel_id))
    if not binding:
        return None
    parsed = _parse_route(content)
    if not parsed:
        return None
    target_hint, body = parsed
    if not body:
        return None
    if target_hint:
        if _is_hermes_target(target_hint):
            return target_hint, body
        aliases = binding.get("aliases")
        target = aliases.get(target_hint) if isinstance(aliases, dict) else None
        if _is_hermes_target(target):
            return target, body
        return None
    target = binding.get("default_target")
    if _is_hermes_target(target):
        return target, body
    return None


def _service_sender_for(sender: str) -> str:
    service = re.sub(r"[^A-Za-z0-9_.-]+", "-", sender.strip()).strip("-._")
    return service[:128] or "discord"


def _send_to_node(target: str, message: str, sender: str, *, node_host_url: str | None = None) -> dict[str, Any]:
    payload = {
        "target": target,
        "from": f"service:{_service_sender_for(sender)}",
        "subject": "Discord channel message",
        "body": message,
        "delivery": "live",
        "reply_mode": "native",
        "metadata": {
            "bridge": "hermes-discord-router",
            "sender": sender,
        },
    }
    try:
        response = requests.post(
            node_host_url or os.environ.get("HERMES_NODE_HOST_URL") or DEFAULT_NODE_HOST_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": f"hermes node host unavailable: {exc}"}
    try:
        parsed = response.json()
    except ValueError:
        parsed = {"ok": False, "error": response.text[-1000:] or "non-json hermes node host response"}
    if response.status_code >= 400:
        parsed.setdefault("ok", False)
        parsed.setdefault("status_code", response.status_code)
    else:
        parsed.setdefault("ok", True)
    parsed.setdefault("display_target", target)
    return parsed


def _reply_text(target: str, result: dict[str, Any]) -> str:
    if result.get("ok"):
        response = result.get("response")
        if isinstance(response, str) and response.strip():
            return response.strip()
        return f"routed to `{target}`"
    reason = result.get("reason") or result.get("error") or "send failed"
    return f"failed for `{target}`: {reason}"


def _split_discord_message(text: str, limit: int = 2000) -> list[str]:
    body = (text or "").strip()
    if not body:
        return [""]
    chunks: list[str] = []
    while len(body) > limit:
        cut = body.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = body.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(body[:cut].rstrip())
        body = body[cut:].lstrip()
    chunks.append(body)
    return chunks


async def _add_reaction(message: Any, emoji: str) -> bool:
    if not hasattr(message, "add_reaction"):
        return False
    try:
        await message.add_reaction(emoji)
        return True
    except Exception:
        return False


async def _remove_reaction(message: Any, emoji: str, user: Any) -> bool:
    if not hasattr(message, "remove_reaction") or user is None:
        return False
    try:
        await message.remove_reaction(emoji, user)
        return True
    except Exception:
        return False


async def _typing_loop(channel: Any) -> None:
    if not hasattr(channel, "trigger_typing"):
        return
    while True:
        try:
            await channel.trigger_typing()
        except Exception:
            return
        await asyncio.sleep(8)


def _start_typing(channel: Any) -> asyncio.Task | None:
    if not hasattr(channel, "trigger_typing"):
        return None
    return asyncio.create_task(_typing_loop(channel))


async def _stop_typing(task: asyncio.Task | None) -> None:
    if not task:
        return
    task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await task


async def _listen(args: Any) -> dict[str, Any]:
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("discord.py is required for Hermes Discord router") from exc

    token, default_channel = _config(args)
    channel_ids = set(_hermes_channels(getattr(args, "bindings", None)).keys())
    if getattr(args, "channel", None):
        channel_ids.add(str(args.channel))
    ready_once = bool(getattr(args, "ready_once", False))
    dry_run = bool(getattr(args, "dry_run", False))

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    state: dict[str, Any] = {"ok": True, "ready": False, "routes": 0}

    @client.event
    async def on_ready():
        state["ready"] = True
        state["bot_user"] = str(client.user)
        print(json.dumps({
            "ok": True,
            "event": "ready",
            "bot_user": str(client.user),
            "channel_id": default_channel,
            "channel_ids": sorted(channel_ids),
        }), flush=True)
        if ready_once:
            await client.close()

    @client.event
    async def on_message(message):
        if message.author.bot or str(message.channel.id) not in channel_ids:
            return
        route = _resolve_route(
            message.content or "",
            message.channel.id,
            bindings_path=getattr(args, "bindings", None),
        )
        if not route:
            return
        target, body = route
        sender = f"discord:{message.author.display_name}"
        await _add_reaction(message, "👀")
        typing_task = _start_typing(message.channel)
        try:
            result = {"ok": True, "response": "dry-run"} if dry_run else await asyncio.to_thread(_send_to_node, target, body, sender)
        except Exception as exc:
            result = {"ok": False, "error": f"router dispatch failed: {exc}"}
        finally:
            await _stop_typing(typing_task)
        for chunk in _split_discord_message(_reply_text(target, result)):
            await message.channel.send(chunk[:2000])
        await _remove_reaction(message, "👀", client.user)
        await _add_reaction(message, "✅" if result.get("ok") else "❌")
        state["routes"] += 1

    await client.start(token)
    return state


def status(args: Any) -> dict[str, Any]:
    token, default_channel = _config(args)
    response = requests.get(
        f"{DISCORD_API}/channels/{default_channel}",
        headers={"Authorization": f"Bot {token}"},
        timeout=15,
    )
    channels = _hermes_channels(getattr(args, "bindings", None))
    return {
        "ok": response.status_code < 400,
        "channel_id": default_channel,
        "status_code": response.status_code,
        "bindings_path": str(_bindings_path(getattr(args, "bindings", None))),
        "channel_ids": sorted(channels.keys()),
        "routes": {
            channel_id: {
                "default_target": binding.get("default_target"),
                "aliases": {
                    key: value
                    for key, value in (binding.get("aliases") or {}).items()
                    if _is_hermes_target(value)
                },
            }
            for channel_id, binding in channels.items()
        },
    }


def run(args: Any) -> dict[str, Any]:
    action = getattr(args, "router_action", None)
    if action == "listen":
        return asyncio.run(_listen(args))
    if action == "status":
        return status(args)
    return {"ok": False, "error": f"unknown router action: {action}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shared Discord frontend for warm Hermes nodes.")
    sub = parser.add_subparsers(dest="router_action", required=True)
    p_status = sub.add_parser("status")
    p_status.add_argument("--env-file")
    p_status.add_argument("--bindings")
    p_listen = sub.add_parser("listen")
    p_listen.add_argument("--env-file")
    p_listen.add_argument("--bindings")
    p_listen.add_argument("--channel")
    p_listen.add_argument("--dry-run", action="store_true")
    p_listen.add_argument("--ready-once", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run(args), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
