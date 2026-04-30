"""Discord bridge for Aura human/seat routing."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import requests


DEFAULT_ENV_PATH = Path.home() / ".aura" / "discord" / "env"
DISCORD_API = "https://discord.com/api/v10"


def _aura_bin() -> str:
    return os.environ.get("AURA_BIN") or str((Path(__file__).resolve().parents[1] / "aura"))


def _load_env(path: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env_path = Path(path).expanduser() if path else DEFAULT_ENV_PATH
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                env[key] = value
    return env


def _config(args) -> tuple[str, str]:
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


def _post_message(token: str, channel_id: str, content: str) -> dict[str, Any]:
    response = requests.post(
        f"{DISCORD_API}/channels/{channel_id}/messages",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        },
        json={"content": content[:2000]},
        timeout=15,
    )
    if response.status_code >= 400:
        body = response.text[-1000:]
        return {"ok": False, "status_code": response.status_code, "error": body}
    data = response.json()
    return {
        "ok": True,
        "channel_id": data.get("channel_id"),
        "message_id": data.get("id"),
    }


def _handle_for(sender: str | None) -> str | None:
    if not sender:
        return None
    if sender.startswith("@"):
        return sender
    if ":" in sender:
        return f"@{{{sender}}}"
    current_fleet = os.environ.get("AURA_FLEET") or os.environ.get("AURA_TMUX_SESSION")
    current_seat = os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")
    if current_fleet and (not current_seat or current_seat == sender):
        return f"@{{{current_fleet}:{sender}}}"
    try:
        from lib import registry

        matches = [
            agent
            for agent in registry.list_agents()
            if agent.get("name") == sender and agent.get("fleet")
        ]
    except Exception:
        matches = []
    if len(matches) == 1:
        return f"@{{{matches[0].get('fleet')}:{sender}}}"
    return f"@{sender}"


def _parse_route(content: str) -> tuple[str, str] | None:
    text = content.strip()
    braced = re.match(r"^@\{([^}]+)\}\s+([\s\S]+)$", text)
    if braced:
        return braced.group(1), braced.group(2).strip()
    role_prefix = re.match(r"^<@&\d+>([-A-Za-z0-9_.:]+)\s+([\s\S]+)$", text)
    if role_prefix:
        # Discord may rewrite @flex-leaders-2:engineer as a role mention
        # for the "flex" role. Recover the intended Aura fleet prefix.
        return f"flex{role_prefix.group(1)}", role_prefix.group(2).strip()
    match = re.match(r"^@([A-Za-z0-9_.:-]+)\s+([\s\S]+)$", text)
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def _target_ref(agent: dict[str, Any]) -> str:
    return agent.get("pane_ref") or agent.get("terminal_ref") or f"{agent.get('fleet')}:{agent.get('name')}"


def _is_live(agent: dict[str, Any]) -> bool:
    target = _target_ref(agent)
    try:
        from lib import terminal

        return bool(terminal.target_exists(target))
    except Exception:
        return False


def _resolve_route_target(target: str) -> dict[str, Any]:
    try:
        from lib import registry
    except Exception as exc:
        return {"ok": False, "error": f"registry unavailable: {exc}"}

    if ":" in target and not target.startswith("tmux:"):
        fleet, name = target.split(":", 1)
        agent = registry.get_agent(name, fleet=fleet)
        if not agent:
            return {"ok": False, "error": f"unknown target `{target}`"}
        if registry.is_hidden_agent(agent):
            return {"ok": False, "blocked": True, "reason": "target-hidden", "error": f"target `{target}` is hidden/internal"}
        if not _is_live(agent):
            return {"ok": False, "error": f"target `{target}` is not live"}
        return {
            "ok": True,
            "target": _target_ref(agent),
            "display": f"{fleet}:{name}",
        }

    candidates = [
        agent
        for agent in registry.list_agents()
        if agent.get("name") == target and _is_live(agent)
    ]
    if not candidates:
        return {"ok": False, "error": f"unknown or non-live target `{target}`"}
    if len(candidates) > 1:
        handles = [f"@{{{agent.get('fleet')}:{agent.get('name')}}}" for agent in candidates]
        return {
            "ok": False,
            "ambiguous": True,
            "error": f"ambiguous target `@{target}`; use one of: {', '.join(handles)}",
            "candidates": handles,
        }
    agent = candidates[0]
    return {
        "ok": True,
        "target": _target_ref(agent),
        "display": f"{agent.get('fleet')}:{agent.get('name')}",
    }


def _send_to_aura(target: str, message: str, sender: str) -> dict[str, Any]:
    resolved = _resolve_route_target(target)
    if not resolved.get("ok"):
        return resolved
    cmd = [
        _aura_bin(),
        "send",
        resolved["target"],
        message,
        "--as",
        sender,
        "--transport",
        "tmux",
        "--defer-if-busy",
    ]
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    parsed = None
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        parsed.setdefault("returncode", result.returncode)
        parsed.setdefault("display_target", resolved.get("display"))
        _record_inbound_route(
            target=resolved.get("display") or target,
            sender=sender,
            message=message,
            result=parsed,
        )
        return parsed
    failure = {
        "ok": False,
        "returncode": result.returncode,
        "error": result.stderr[-1000:] or result.stdout[-1000:] or "aura send failed",
    }
    _record_inbound_route(
        target=resolved.get("display") or target,
        sender=sender,
        message=message,
        result=failure,
    )
    return failure


def _record_inbound_route(*, target: str, sender: str, message: str, result: dict[str, Any]) -> None:
    try:
        from lib import delivery

        state = "delivered" if result.get("ok") and not result.get("blocked") else "blocked" if result.get("blocked") else "failed"
        record = delivery.new_delivery_record(
            delivery_type="human_inbound_route",
            sender=sender,
            target=target,
            backend="discord",
            state=state,
            route_result=result,
            payload_hash=delivery.body_hash(message),
        )
        delivery.append_attempt(record, state=state, evidence={
            "message_id": result.get("message_id"),
            "deferred": result.get("deferred"),
            "blocked": result.get("blocked"),
            "reason": result.get("reason") or result.get("error"),
        })
        delivery.append_record(record)
    except Exception:
        pass


def _ack_for_result(target: str, result: dict[str, Any]) -> str:
    if result.get("ok"):
        if result.get("blocked") and result.get("deferred"):
            deferred_record = result.get("deferred_record") or {}
            deferred_id = deferred_record.get("deferred_id")
            suffix = f"; deferred `{deferred_id}`" if deferred_id else ""
            reason = result.get("reason") or "target-busy"
            return f"deferred for `{target}`: {reason}{suffix}"
        message_id = result.get("message_id") or "sent"
        display = result.get("display_target") or target
        verified = result.get("submitted_verified")
        suffix = "" if verified is None else f", submitted_verified={str(verified).lower()}"
        return f"routed to `{display}`: `{message_id}`{suffix}"
    reason = result.get("reason") or result.get("error") or "send failed"
    if result.get("blocked"):
        return f"blocked for `{target}`: {reason}"
    return f"failed for `{target}`: {reason}"


async def _listen(args) -> dict[str, Any]:
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("discord.py is required for `aura discord listen`") from exc

    token, channel_id = _config(args)
    channel_id_int = int(channel_id)
    sender_prefix = getattr(args, "sender_prefix", None) or "discord"
    dry_run = bool(getattr(args, "dry_run", False))
    ready_once = bool(getattr(args, "ready_once", False))

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    state: dict[str, Any] = {"ok": True, "ready": False, "routes": 0}

    @client.event
    async def on_ready():
        state["ready"] = True
        state["bot_user"] = str(client.user)
        print(json.dumps({"ok": True, "event": "ready", "bot_user": str(client.user), "channel_id": channel_id}), flush=True)
        if ready_once:
            await client.close()

    @client.event
    async def on_message(message):
        if message.author.bot or message.channel.id != channel_id_int:
            return
        route = _parse_route(message.content or "")
        if not route:
            return
        target, body = route
        sender = f"{sender_prefix}:{message.author.display_name}"
        if dry_run:
            result = {"ok": True, "message_id": "dry-run", "submitted_verified": None}
        else:
            result = await asyncio.to_thread(_send_to_aura, target, body, sender)
        state["routes"] += 1
        await message.channel.send(_ack_for_result(target, result)[:2000])

    await client.start(token)
    return state


def _status(args) -> dict[str, Any]:
    token, channel_id = _config(args)
    response = requests.get(
        f"{DISCORD_API}/channels/{channel_id}",
        headers={"Authorization": f"Bot {token}"},
        timeout=15,
    )
    if response.status_code >= 400:
        return {"ok": False, "status_code": response.status_code, "error": response.text[-1000:]}
    data = response.json()
    return {
        "ok": True,
        "channel_id": data.get("id"),
        "channel_name": data.get("name"),
        "guild_id": data.get("guild_id"),
        "env_file": str(Path(getattr(args, "env_file", None) or DEFAULT_ENV_PATH).expanduser()),
    }


def run(args):
    action = getattr(args, "discord_action", None)
    if action == "send":
        token, channel_id = _config(args)
        sender = getattr(args, "sender", None)
        content = args.message
        if sender:
            handle = _handle_for(sender)
            if handle:
                content = f"`{handle}` {content}"
            else:
                content = f"**{sender}:** {content}"
        return _post_message(token, channel_id, content)
    if action == "listen":
        return asyncio.run(_listen(args))
    if action == "status":
        return _status(args)
    return {"error": f"unknown discord action: {action}"}
