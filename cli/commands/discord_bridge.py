"""Discord bridge for Aura human/seat routing."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import requests


DEFAULT_ENV_PATH = Path.home() / ".aura" / "discord" / "env"
DEFAULT_ROUTE_STATE_PATH = Path.home() / ".aura" / "discord" / "routes.json"
DEFAULT_CHANNEL_BINDINGS_PATH = Path.home() / ".aura" / "discord" / "channel-bindings.json"
DEFAULT_HERMES_INGRESS_URL = "http://127.0.0.1:7135/v1/messages"
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


def _route_state_path() -> Path:
    return Path(os.environ.get("AURA_DISCORD_ROUTE_STATE") or DEFAULT_ROUTE_STATE_PATH).expanduser()


def _channel_bindings_path() -> Path:
    return Path(
        os.environ.get("AURA_DISCORD_CHANNEL_BINDINGS") or DEFAULT_CHANNEL_BINDINGS_PATH
    ).expanduser()


def _load_route_state(path: Path | None = None) -> dict[str, Any]:
    state_path = path or _route_state_path()
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"schema": "aura.discord.routes.v1", "routes": {}}
    if not isinstance(data, dict):
        return {"schema": "aura.discord.routes.v1", "routes": {}}
    routes = data.get("routes")
    if not isinstance(routes, dict):
        data["routes"] = {}
    data.setdefault("schema", "aura.discord.routes.v1")
    return data


def _load_channel_bindings(path: Path | None = None) -> dict[str, Any]:
    bindings_path = path or _channel_bindings_path()
    try:
        data = json.loads(bindings_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"schema": "aura.discord.channel_bindings.v1", "channels": {}}
    if not isinstance(data, dict):
        return {"schema": "aura.discord.channel_bindings.v1", "channels": {}}
    channels = data.get("channels")
    if not isinstance(channels, dict):
        data["channels"] = {}
    data.setdefault("schema", "aura.discord.channel_bindings.v1")
    return data


def _write_channel_bindings(state: dict[str, Any], path: Path | None = None) -> None:
    bindings_path = path or _channel_bindings_path()
    bindings_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = bindings_path.with_name(f"{bindings_path.name}.tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(bindings_path)


def _channel_binding(channel_id: int | str, *, path: Path | None = None) -> dict[str, Any] | None:
    channels = _load_channel_bindings(path).get("channels", {})
    binding = channels.get(str(channel_id))
    return binding if isinstance(binding, dict) else None


def _resolve_bound_target(target: str, binding: dict[str, Any] | None) -> str:
    if not binding or ":" in target or target.startswith("tmux:"):
        return target
    aliases = binding.get("aliases")
    alias = aliases.get(target) if isinstance(aliases, dict) else None
    if isinstance(alias, str) and alias:
        return alias if ":" in alias else f"{binding.get('fleet')}:{alias}" if binding.get("fleet") else alias
    fleet = binding.get("fleet")
    return f"{fleet}:{target}" if isinstance(fleet, str) and fleet else target


def _default_target_for_channel(channel_id: int | str, *, path: Path | None = None) -> str | None:
    binding = _channel_binding(channel_id, path=path)
    if not binding:
        return None
    target = binding.get("default_target")
    if isinstance(target, str) and target:
        return target
    fleet = binding.get("fleet")
    default_seat = binding.get("default_seat")
    if isinstance(fleet, str) and fleet and isinstance(default_seat, str) and default_seat:
        return f"{fleet}:{default_seat}"
    return None


def _listened_channel_ids(default_channel_id: int | str, *, path: Path | None = None) -> set[str]:
    channels = _load_channel_bindings(path).get("channels", {})
    ids = {str(default_channel_id)}
    for channel_id, binding in channels.items():
        if isinstance(binding, dict) and _binding_routes_to_hermes(binding):
            continue
        ids.add(str(channel_id))
    return ids


def _is_hermes_target(target: Any) -> bool:
    return isinstance(target, str) and target.startswith("hermes:")


def _binding_routes_to_hermes(binding: dict[str, Any]) -> bool:
    if _is_hermes_target(binding.get("default_target")):
        return True
    aliases = binding.get("aliases")
    if isinstance(aliases, dict):
        return any(_is_hermes_target(target) for target in aliases.values())
    return False


def _write_route_state(state: dict[str, Any], path: Path | None = None) -> None:
    state_path = path or _route_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_name(f"{state_path.name}.tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(state_path)


def _route_key(channel_id: int | str, author_id: int | str) -> str:
    return f"{channel_id}:{author_id}"


def _remember_last_target(
    channel_id: int | str,
    author_id: int | str,
    target: str,
    sender: str,
    *,
    path: Path | None = None,
) -> None:
    state = _load_route_state(path)
    state["routes"][_route_key(channel_id, author_id)] = {
        "target": target,
        "sender": sender,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_route_state(state, path)


def _last_target(channel_id: int | str, author_id: int | str, *, path: Path | None = None) -> str | None:
    state = _load_route_state(path)
    route = state.get("routes", {}).get(_route_key(channel_id, author_id))
    if not isinstance(route, dict):
        return None
    target = route.get("target")
    return target if isinstance(target, str) and target else None


def _route_for_message(
    content: str,
    channel_id: int | str,
    author_id: int | str,
    *,
    path: Path | None = None,
    bindings_path: Path | None = None,
) -> tuple[str, str, bool] | None:
    explicit = _parse_route(content)
    if explicit:
        target, body = explicit
        return _resolve_bound_target(target, _channel_binding(channel_id, path=bindings_path)), body, True
    body = (content or "").strip()
    if not body:
        return None
    default_target = _default_target_for_channel(channel_id, path=bindings_path)
    if default_target:
        return default_target, body, False
    target = _last_target(channel_id, author_id, path=path)
    if not target:
        return None
    return target, body, False


def _bind_channel(args) -> dict[str, Any]:
    channel_id = str(args.channel)
    state = _load_channel_bindings()
    channels = state.setdefault("channels", {})
    binding = channels.get(channel_id)
    if not isinstance(binding, dict):
        binding = {}
    if getattr(args, "fleet", None):
        binding["fleet"] = args.fleet
    if getattr(args, "default_target", None):
        binding["default_target"] = args.default_target
    if getattr(args, "default_seat", None):
        binding["default_seat"] = args.default_seat
    aliases = binding.get("aliases")
    if not isinstance(aliases, dict):
        aliases = {}
    for raw in getattr(args, "alias", None) or []:
        if "=" not in raw:
            return {"ok": False, "error": f"alias must be NAME=TARGET, got `{raw}`"}
        name, target = raw.split("=", 1)
        name = name.strip()
        target = target.strip()
        if not name or not target:
            return {"ok": False, "error": f"alias must be NAME=TARGET, got `{raw}`"}
        aliases[name] = target
    if aliases:
        binding["aliases"] = aliases
    channels[channel_id] = binding
    _write_channel_bindings(state)
    return {
        "ok": True,
        "path": str(_channel_bindings_path()),
        "channel_id": channel_id,
        "binding": binding,
    }


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
            "target": f"{fleet}:{name}",
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
        "target": f"{agent.get('fleet')}:{agent.get('name')}",
        "display": f"{agent.get('fleet')}:{agent.get('name')}",
    }


def _service_sender_for(sender: str) -> str:
    service = re.sub(r"[^A-Za-z0-9_.-]+", "-", sender.strip()).strip("-._")
    return service[:128] or "discord"


def _send_to_hermes(target: str, message: str, sender: str) -> dict[str, Any]:
    ingress_url = os.environ.get("HERMES_INGRESS_URL") or DEFAULT_HERMES_INGRESS_URL
    payload = {
        "target": target,
        "from": f"service:{_service_sender_for(sender)}",
        "subject": "Discord channel message",
        "body": message,
        "delivery": "live",
        "reply_mode": "native",
        "metadata": {
            "bridge": "aura-discord",
            "sender": sender,
        },
    }
    try:
        response = requests.post(
            ingress_url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
    except requests.RequestException as exc:
        failure = {"ok": False, "error": f"hermes ingress unavailable: {exc}"}
        _record_inbound_route(target=target, sender=sender, message=message, result=failure)
        return failure
    try:
        parsed = response.json()
    except ValueError:
        parsed = {"ok": False, "error": response.text[-1000:] or "non-json hermes ingress response"}
    if response.status_code >= 400:
        parsed.setdefault("ok", False)
        parsed.setdefault("status_code", response.status_code)
    else:
        parsed.setdefault("ok", True)
        parsed.setdefault("message_id", parsed.get("id") or parsed.get("status") or "accepted")
    parsed.setdefault("display_target", target)
    _record_inbound_route(target=target, sender=sender, message=message, result=parsed)
    return parsed


def _send_to_target(target: str, message: str, sender: str) -> dict[str, Any]:
    if target.startswith("hermes:"):
        return _send_to_hermes(target, message, sender)
    return _send_to_aura(target, message, sender)


def _send_to_aura(target: str, message: str, sender: str) -> dict[str, Any]:
    resolved = _resolve_route_target(target)
    if not resolved.get("ok"):
        return resolved
    cmd = [
        _aura_bin(),
        "send",
        resolved["target"],
        message,
        "--as-service",
        _service_sender_for(sender),
        "--transport",
        "tmux",
        "--force",
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
        response = result.get("response")
        if isinstance(response, str) and response.strip():
            return response.strip()
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


async def _add_message_reaction(message: Any, emoji: str) -> bool:
    if not hasattr(message, "add_reaction"):
        return False
    try:
        await message.add_reaction(emoji)
        return True
    except Exception:
        return False


async def _remove_message_reaction(message: Any, emoji: str, user: Any) -> bool:
    if not hasattr(message, "remove_reaction") or user is None:
        return False
    try:
        await message.remove_reaction(emoji, user)
        return True
    except Exception:
        return False


async def _mark_processing_start(message: Any) -> None:
    await _add_message_reaction(message, "👀")


async def _mark_processing_complete(message: Any, user: Any, ok: bool) -> None:
    await _remove_message_reaction(message, "👀", user)
    await _add_message_reaction(message, "✅" if ok else "❌")


async def _typing_indicator_loop(channel: Any) -> None:
    if not hasattr(channel, "trigger_typing"):
        return
    while True:
        try:
            await channel.trigger_typing()
        except Exception:
            return
        await asyncio.sleep(8)


def _start_typing_indicator(channel: Any) -> asyncio.Task | None:
    if not hasattr(channel, "trigger_typing"):
        return None
    return asyncio.create_task(_typing_indicator_loop(channel))


async def _stop_typing_indicator(task: asyncio.Task | None) -> None:
    if not task:
        return
    task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await task


async def _listen(args) -> dict[str, Any]:
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("discord.py is required for `aura discord listen`") from exc

    token, channel_id = _config(args)
    channel_ids = _listened_channel_ids(channel_id)
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
        print(json.dumps({
            "ok": True,
            "event": "ready",
            "bot_user": str(client.user),
            "channel_id": channel_id,
            "channel_ids": sorted(channel_ids),
        }), flush=True)
        if ready_once:
            await client.close()

    @client.event
    async def on_message(message):
        if message.author.bot or str(message.channel.id) not in channel_ids:
            return
        route = _route_for_message(
            message.content or "",
            message.channel.id,
            message.author.id,
        )
        if not route:
            return
        target, body, explicit = route
        sender = f"{sender_prefix}:{message.author.display_name}"
        await _mark_processing_start(message)
        typing_task = _start_typing_indicator(message.channel)
        try:
            if dry_run:
                result = {"ok": True, "message_id": "dry-run", "submitted_verified": None}
            else:
                result = await asyncio.to_thread(_send_to_target, target, body, sender)
        except Exception as exc:
            result = {"ok": False, "error": f"bridge dispatch failed: {exc}"}
        finally:
            await _stop_typing_indicator(typing_task)
        if explicit and result.get("ok") and not result.get("blocked"):
            display_target = result.get("display_target") or target
            _remember_last_target(message.channel.id, message.author.id, display_target, sender)
        state["routes"] += 1
        await message.channel.send(_ack_for_result(target, result)[:2000])
        await _mark_processing_complete(
            message,
            client.user,
            bool(result.get("ok")) and not bool(result.get("blocked")),
        )

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
    if action == "bind-channel":
        return _bind_channel(args)
    return {"error": f"unknown discord action: {action}"}
