#!/usr/bin/env python3
"""Warm local node host for Hermes profiles.

This service keeps Hermes profile agents in one local process and exposes a
small loopback HTTP surface for the Aura/Hermes ingress.  It is deliberately
not a Discord gateway: no messaging-platform adapter is started here, so many
profile-backed nodes can run without competing for one Discord bot token.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError
from uuid import uuid4

try:
    import yaml
except Exception:  # pragma: no cover - service startup will report this clearly
    yaml = None

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7136
DEFAULT_HERMES_ROOT = Path("/home/axp/.hermes/profiles")
DEFAULT_NODES_PATH = Path("/home/axp/.hermes/nodes.json")
DEFAULT_INGRESS_URL = "http://127.0.0.1:7135/v1/messages"
DEFAULT_HERMES_AGENT_ROOT = Path("/home/axp/.hermes/hermes-agent")
SERVICE_NAME = "hermes-node-host"
MAX_BODY_BYTES = 256 * 1024


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class NodeHostError(Exception):
    def __init__(self, status: int, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.detail = detail


def load_nodes(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        raise NodeHostError(HTTPStatus.INTERNAL_SERVER_ERROR, f"failed to read nodes registry: {path}", detail=str(exc))
    nodes = data.get("nodes") if isinstance(data, dict) else None
    if not isinstance(nodes, dict):
        return {}
    return {str(name): cfg for name, cfg in nodes.items() if isinstance(cfg, dict)}


def profile_config(profile_root: Path) -> dict[str, Any]:
    config_path = profile_root / "config.yaml"
    if not config_path.exists():
        return {}
    if yaml is None:
        raise NodeHostError(HTTPStatus.INTERNAL_SERVER_ERROR, "PyYAML is required to read Hermes profile config")
    try:
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise NodeHostError(HTTPStatus.INTERNAL_SERVER_ERROR, f"failed to read profile config: {config_path}", detail=str(exc))


def resolve_model(cfg: dict[str, Any]) -> str:
    model_cfg = cfg.get("model") or {}
    if isinstance(model_cfg, str):
        return model_cfg
    if isinstance(model_cfg, dict):
        return str(model_cfg.get("default") or model_cfg.get("model") or "")
    return ""


def resolve_provider(cfg: dict[str, Any]) -> str | None:
    model_cfg = cfg.get("model") or {}
    if isinstance(model_cfg, dict):
        provider = str(model_cfg.get("provider") or "").strip()
        return provider or None
    return None


def node_prompt(payload: dict[str, Any], node_name: str, node_config: dict[str, Any] | None = None) -> str:
    sender = str(payload.get("from") or "unknown").strip()
    subject = str(payload.get("subject") or "Node message").strip()
    body = str(payload.get("body") or "").strip()
    cfg = node_config or {}
    request_id = ""
    metadata = payload.get("metadata") or {}
    if isinstance(metadata, dict):
        request_id = str(metadata.get("request_id") or "").strip()
    request_part = f" Request id: {request_id}." if request_id else ""
    territory = cfg.get("territory") if isinstance(cfg.get("territory"), dict) else {}
    territory_lines = []
    for key in ("context_name", "visible_name", "context_root", "project_root", "flex_cell"):
        value = territory.get(key)
        if isinstance(value, str) and value.strip():
            territory_lines.append(f"- {key}: {value.strip()}")
    source_order = territory.get("source_order")
    if isinstance(source_order, list) and source_order:
        territory_lines.append("- source_order: " + ", ".join(str(item) for item in source_order))
    territory_part = ""
    if territory_lines:
        territory_part = "\n\nNode territory:\n" + "\n".join(territory_lines)
    return (
        f"[Hermes warm node message for {node_name} from {sender}: {subject}."
        f"{request_part}{territory_part}\n\n{body}]"
    )


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


@dataclass
class WarmNode:
    name: str
    config: dict[str, Any]
    hermes_root: Path
    ingress_url: str
    hermes_agent_root: Path
    lock: threading.Lock = field(default_factory=threading.Lock)
    agent: Any = None
    history: list[dict[str, Any]] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: f"node_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}")
    turns: int = 0
    created_at: str = field(default_factory=now_iso)
    last_active_at: str | None = None

    @property
    def profile(self) -> str:
        return str(self.config.get("profile") or self.name)

    @property
    def profile_root(self) -> Path:
        return self.hermes_root / self.profile

    def prewarm(self) -> None:
        with self.lock:
            self._ensure_agent()

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.time()
        with self.lock:
            agent = self._ensure_agent()
            prompt = node_prompt(payload, self.name, self.config)
            result = self._run_profile_conversation(agent, prompt)
            self.history = result.get("messages") or self.history
            self.turns += 1
            self.last_active_at = now_iso()

        response = str(result.get("final_response") or "").strip()
        payload_reply_to = str(payload.get("reply_to") or "").strip()
        reply_to = payload_reply_to or str(self.config.get("reply_to") or "").strip()
        post_result: dict[str, Any] | None = None
        if reply_to and response:
            post_result = self._post_reply(reply_to, payload, response)

        record = {
            "time": now_iso(),
            "node": self.name,
            "profile": self.profile,
            "from": payload.get("from"),
            "subject": payload.get("subject"),
            "reply_to": reply_to or None,
            "elapsed_ms": int((time.time() - started) * 1000),
            "completed": result.get("completed"),
            "api_calls": result.get("api_calls"),
        }
        append_jsonl(self.profile_root / "nodes" / "turns.jsonl", record)
        return {
            "ok": True,
            "node": self.name,
            "profile": self.profile,
            "mode": "warm_node",
            "session_id": self.session_id,
            "turns": self.turns,
            "response": response,
            "reply_to": reply_to or None,
            "reply_post": post_result,
            "elapsed_ms": record["elapsed_ms"],
            "model": result.get("model"),
            "provider": result.get("provider"),
            "completed": result.get("completed"),
            "api_calls": result.get("api_calls"),
        }

    def _run_profile_conversation(self, agent: Any, prompt: str) -> dict[str, Any]:
        from hermes_constants import reset_hermes_home_override, set_hermes_home_override

        token = set_hermes_home_override(self.profile_root)
        try:
            return agent.run_conversation(prompt, conversation_history=self.history)
        finally:
            reset_hermes_home_override(token)

    def status(self) -> dict[str, Any]:
        return {
            "node": self.name,
            "profile": self.profile,
            "mode": "warm_node",
            "session_id": self.session_id,
            "warm": self.agent is not None,
            "turns": self.turns,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "profile_root": str(self.profile_root),
        }

    def _ensure_agent(self) -> Any:
        if self.agent is not None:
            return self.agent
        if not self.profile_root.exists():
            raise NodeHostError(HTTPStatus.NOT_FOUND, f"Hermes profile not found: {self.profile}")
        self._prepare_imports()

        from dotenv import load_dotenv
        from hermes_constants import reset_hermes_home_override, set_hermes_home_override
        from hermes_cli.config import load_config
        from hermes_cli.models import detect_provider_for_model
        from hermes_cli.oneshot import _normalize_toolsets
        from hermes_cli.runtime_provider import resolve_runtime_provider
        from hermes_cli.tools_config import _get_platform_tools
        from run_agent import AIAgent

        load_dotenv(self.profile_root / ".env", override=False)
        token = set_hermes_home_override(self.profile_root)
        try:
            cfg = load_config()
            model = str(self.config.get("model") or "").strip() or resolve_model(cfg)
            provider = str(self.config.get("provider") or "").strip() or resolve_provider(cfg)
            if not provider and model:
                detected = detect_provider_for_model(model, "auto")
                if detected:
                    provider, model = detected
            runtime = resolve_runtime_provider(requested=provider or None, target_model=model or None)
            toolsets = _normalize_toolsets(self.config.get("toolsets"))
            if toolsets is None:
                toolsets = sorted(_get_platform_tools(cfg, "cli"))
            agent_cfg = cfg.get("agent") if isinstance(cfg.get("agent"), dict) else {}
            max_turns = int(self.config.get("max_turns") or agent_cfg.get("max_turns") or 60)
            disabled_toolsets = agent_cfg.get("disabled_toolsets") or None
            fallback = cfg.get("fallback_providers") or cfg.get("fallback_model") or None
            self.agent = AIAgent(
                api_key=runtime.get("api_key"),
                base_url=runtime.get("base_url"),
                provider=runtime.get("provider"),
                api_mode=runtime.get("api_mode"),
                command=runtime.get("command"),
                args=list(runtime.get("args") or []),
                credential_pool=runtime.get("credential_pool"),
                model=model,
                max_iterations=max_turns,
                enabled_toolsets=toolsets,
                disabled_toolsets=disabled_toolsets,
                quiet_mode=True,
                platform="local",
                user_id="hermes-node-host",
                user_name=SERVICE_NAME,
                chat_id=self.name,
                chat_name=f"hermes:{self.name}",
                chat_type="node",
                gateway_session_key=f"node:{self.name}",
                session_id=self.session_id,
                fallback_model=fallback,
            )
            self.agent.suppress_status_output = True
            self.agent.stream_delta_callback = None
            self.agent.tool_gen_callback = None
            return self.agent
        finally:
            reset_hermes_home_override(token)

    def _prepare_imports(self) -> None:
        root = str(self.hermes_agent_root)
        if root not in sys.path:
            sys.path.insert(0, root)

    def _post_reply(self, target: str, payload: dict[str, Any], response: str) -> dict[str, Any]:
        request_payload = {
            "target": target,
            "from": f"hermes:{self.name}",
            "subject": f"{self.name} reply",
            "body": response,
            "delivery": "live",
            "reply_mode": "native",
            "metadata": {
                "node": self.name,
                "profile": self.profile,
                "source_request_id": (payload.get("metadata") or {}).get("request_id") if isinstance(payload.get("metadata"), dict) else None,
            },
        }
        data = json.dumps(request_payload).encode("utf-8")
        req = urlrequest.Request(self.ingress_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": body[-2000:]}
        except URLError as exc:
            return {"ok": False, "error": str(exc)}


class NodeHost:
    def __init__(self, *, nodes_path: Path, hermes_root: Path, ingress_url: str, hermes_agent_root: Path) -> None:
        self.nodes_path = nodes_path
        self.hermes_root = hermes_root
        self.ingress_url = ingress_url
        self.hermes_agent_root = hermes_agent_root
        self._nodes: dict[str, WarmNode] = {}
        self._nodes_mtime: float | None = None
        self._lock = threading.Lock()

    def nodes(self) -> dict[str, WarmNode]:
        self._reload_if_needed()
        return self._nodes

    def get(self, name: str) -> WarmNode:
        nodes = self.nodes()
        node = nodes.get(name)
        if node is None:
            raise NodeHostError(HTTPStatus.NOT_FOUND, f"Hermes node not found: {name}")
        return node

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": SERVICE_NAME,
            "time": now_iso(),
            "nodes_path": str(self.nodes_path),
            "nodes": {name: node.status() for name, node in self.nodes().items()},
        }

    def prewarm(self) -> None:
        for node in self.nodes().values():
            if bool(node.config.get("prewarm")):
                node.prewarm()

    def _reload_if_needed(self) -> None:
        try:
            mtime = self.nodes_path.stat().st_mtime
        except FileNotFoundError:
            mtime = None
        with self._lock:
            if self._nodes and self._nodes_mtime == mtime:
                return
            raw_nodes = load_nodes(self.nodes_path)
            kept: dict[str, WarmNode] = {}
            for name, cfg in raw_nodes.items():
                mode = str(cfg.get("mode") or "").strip()
                if mode not in {"warm_node", "headless_warm"}:
                    continue
                old = self._nodes.get(name)
                if old and old.config == cfg:
                    kept[name] = old
                    continue
                kept[name] = WarmNode(
                    name=name,
                    config=cfg,
                    hermes_root=self.hermes_root,
                    ingress_url=self.ingress_url,
                    hermes_agent_root=self.hermes_agent_root,
                )
            self._nodes = kept
            self._nodes_mtime = mtime


class Handler(BaseHTTPRequestHandler):
    server_version = "HermesNodeHost/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in {"", "/healthz", "/v1/nodes"}:
            json_response(self, HTTPStatus.OK, self.server.host_state.status())  # type: ignore[attr-defined]
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        started = time.time()
        try:
            if self.path.rstrip("/") not in {"/v1/messages", "/message"}:
                raise NodeHostError(HTTPStatus.NOT_FOUND, "not found")
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                raise NodeHostError(HTTPStatus.BAD_REQUEST, "empty request body")
            if length > MAX_BODY_BYTES:
                raise NodeHostError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body too large")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                raise NodeHostError(HTTPStatus.BAD_REQUEST, "invalid JSON", detail=str(exc))
            if not isinstance(payload, dict):
                raise NodeHostError(HTTPStatus.BAD_REQUEST, "JSON payload must be an object")
            target = str(payload.get("target") or "").strip()
            if target.startswith("hermes:"):
                node_name = target[len("hermes:") :].strip()
            else:
                node_name = str(payload.get("node") or "").strip()
            if not node_name:
                raise NodeHostError(HTTPStatus.BAD_REQUEST, "missing Hermes node target")
            body = str(payload.get("body") or "").strip()
            if not body:
                raise NodeHostError(HTTPStatus.BAD_REQUEST, "missing body")
            result = self.server.host_state.get(node_name).handle(payload)  # type: ignore[attr-defined]
            result["host_elapsed_ms"] = int((time.time() - started) * 1000)
            json_response(self, HTTPStatus.ACCEPTED, result)
        except NodeHostError as exc:
            payload = {"ok": False, "error": exc.message}
            if exc.detail is not None:
                payload["detail"] = exc.detail
            json_response(self, exc.status, payload)
        except Exception as exc:
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal error", "detail": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write(f"{now_iso()} {self.address_string()} {format % args}\n")


class Server(ThreadingHTTPServer):
    def __init__(self, addr: tuple[str, int], handler: type[BaseHTTPRequestHandler], *, host_state: NodeHost) -> None:
        super().__init__(addr, handler)
        self.host_state = host_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Warm local node host for Hermes profiles.")
    parser.add_argument("--host", default=os.getenv("HERMES_NODE_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("HERMES_NODE_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--nodes", type=Path, default=Path(os.getenv("HERMES_NODES_PATH", str(DEFAULT_NODES_PATH))))
    parser.add_argument("--hermes-root", type=Path, default=Path(os.getenv("HERMES_NODE_HERMES_ROOT", str(DEFAULT_HERMES_ROOT))))
    parser.add_argument("--ingress-url", default=os.getenv("HERMES_NODE_INGRESS_URL", DEFAULT_INGRESS_URL))
    parser.add_argument("--hermes-agent-root", type=Path, default=Path(os.getenv("HERMES_AGENT_ROOT", str(DEFAULT_HERMES_AGENT_ROOT))))
    parser.add_argument("--prewarm", action="store_true", default=os.getenv("HERMES_NODE_PREWARM", "").lower() in {"1", "true", "yes"})
    args = parser.parse_args(argv)

    host_state = NodeHost(
        nodes_path=args.nodes,
        hermes_root=args.hermes_root,
        ingress_url=args.ingress_url,
        hermes_agent_root=args.hermes_agent_root,
    )
    if args.prewarm:
        host_state.prewarm()
    server = Server((args.host, args.port), Handler, host_state=host_state)
    print(f"{SERVICE_NAME} listening on http://{args.host}:{args.port} nodes={args.nodes}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
