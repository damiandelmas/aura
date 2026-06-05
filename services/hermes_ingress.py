#!/usr/bin/env python3
"""Local HTTP ingress for messaging live Hermes profiles and Aura seats.

This is intentionally small: it is an address router, not an orchestration
brain.  It accepts POST /v1/messages, validates a local request, then either:

- writes a Hermes gateway local-injection envelope for `hermes:<profile>`; or
- calls Aura semantic delivery for `aura:<fleet:seat>`.

Responses mean "accepted by the ingress backend".  They do not prove the target
agent read or completed the work.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError
from uuid import uuid4

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7135
DEFAULT_HERMES_ROOT = Path("/home/axp/.hermes/profiles")
DEFAULT_HERMES_NODES_PATH = Path("/home/axp/.hermes/nodes.json")
DEFAULT_HERMES_NODE_HOST_URL = "http://127.0.0.1:7136/v1/messages"
DEFAULT_AURA_CLI = Path("/home/axp/projects/aura/main/cli/aura")
DEFAULT_AURA_STATE_DIR = Path("/home/axp/.aura")
SERVICE_NAME = "hermes-http-ingress"
MAX_BODY_BYTES = 256 * 1024

ADDRESS_RE = re.compile(r"^(?P<scheme>[a-z][a-z0-9_-]*):(?P<name>.+)$")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class IngressError(Exception):
    def __init__(self, status: int, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.detail = detail


def parse_target(raw: Any) -> tuple[str, str]:
    target = str(raw or "").strip()
    if not target:
        raise IngressError(HTTPStatus.BAD_REQUEST, "missing target")
    match = ADDRESS_RE.match(target)
    if not match:
        raise IngressError(
            HTTPStatus.BAD_REQUEST,
            "target must include an address scheme, e.g. hermes:flexgraph-sales-operator or aura:fleet:seat",
        )
    scheme = match.group("scheme")
    name = match.group("name").strip()
    if not name:
        raise IngressError(HTTPStatus.BAD_REQUEST, "target address is empty")
    if scheme not in {"hermes", "aura"}:
        raise IngressError(HTTPStatus.BAD_REQUEST, f"unsupported target scheme: {scheme}")
    return scheme, name


def normalize_aura_target(target: str) -> str:
    """Return the Aura CLI target for an ingress-level Aura address.

    The HTTP boundary uses explicit target schemes like
    `aura:aura-route:router`.  Aura CLI commands still want the plain
    `fleet:seat` address.  Be defensive and strip one or more accidental
    `aura:` prefixes before calling Aura.
    """
    normalized = target.strip()
    while normalized.startswith("aura:"):
        normalized = normalized[len("aura:") :].strip()
    return normalized


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise IngressError(HTTPStatus.BAD_REQUEST, "JSON payload must be an object")
    _scheme, _name = parse_target(payload.get("target"))
    body = str(payload.get("body") or "").strip()
    if not body:
        raise IngressError(HTTPStatus.BAD_REQUEST, "missing body")
    delivery = str(payload.get("delivery") or "live").strip().lower()
    if delivery != "live":
        raise IngressError(HTTPStatus.BAD_REQUEST, "only delivery='live' is supported")
    reply_mode = str(payload.get("reply_mode") or "native").strip().lower()
    if reply_mode != "native":
        raise IngressError(HTTPStatus.BAD_REQUEST, "only reply_mode='native' is supported")
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise IngressError(HTTPStatus.BAD_REQUEST, "metadata must be an object when provided")
    return payload


def load_hermes_nodes(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        raise IngressError(HTTPStatus.INTERNAL_SERVER_ERROR, f"failed to read Hermes nodes registry: {path}", detail=str(exc))
    nodes = data.get("nodes") if isinstance(data, dict) else None
    if not isinstance(nodes, dict):
        return {}
    return {str(name): cfg for name, cfg in nodes.items() if isinstance(cfg, dict)}


def node_config(profile: str, nodes_path: Path) -> dict[str, Any] | None:
    cfg = load_hermes_nodes(nodes_path).get(profile)
    return cfg if isinstance(cfg, dict) else None


def latest_hermes_source(profile_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    sessions_path = profile_root / "sessions" / "sessions.json"
    if not sessions_path.exists():
        raise IngressError(HTTPStatus.NOT_FOUND, f"Hermes sessions file not found for profile: {profile_root.name}")
    try:
        data = json.loads(sessions_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise IngressError(HTTPStatus.INTERNAL_SERVER_ERROR, f"failed to read Hermes sessions for {profile_root.name}", detail=str(exc))

    preferred = payload.get("session") or {}
    if preferred is not None and not isinstance(preferred, dict):
        raise IngressError(HTTPStatus.BAD_REQUEST, "session must be an object when provided")
    preferred_platform = str(preferred.get("platform") or "").strip() if preferred else ""
    preferred_chat_id = str(preferred.get("chat_id") or "").strip() if preferred else ""

    candidates: list[tuple[str, dict[str, Any]]] = []
    for entry in data.values() if isinstance(data, dict) else []:
        if not isinstance(entry, dict):
            continue
        origin = entry.get("origin") or {}
        if not isinstance(origin, dict):
            continue
        if not origin.get("platform") or not origin.get("chat_id"):
            continue
        if preferred_platform and str(origin.get("platform")) != preferred_platform:
            continue
        if preferred_chat_id and str(origin.get("chat_id")) != preferred_chat_id:
            continue
        candidates.append((str(entry.get("updated_at") or ""), origin))

    if not candidates:
        hint = ""
        if preferred_platform or preferred_chat_id:
            hint = f" matching platform={preferred_platform or '*'} chat_id={preferred_chat_id or '*'}"
        raise IngressError(HTTPStatus.NOT_FOUND, f"no live Hermes session source found for profile {profile_root.name}{hint}")
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def format_ingress_text(payload: dict[str, Any], ingress_id: str) -> str:
    sender = str(payload.get("from") or "unknown").strip()
    subject = str(payload.get("subject") or "Ingress message").strip()
    body = str(payload.get("body") or "").strip()
    metadata = payload.get("metadata") or {}
    request_id = str(metadata.get("request_id") or "").strip() if isinstance(metadata, dict) else ""
    request_part = f" Request id: {request_id}." if request_id else ""
    return (
        f"[HTTP ingress message {ingress_id} from {sender}: {subject}.{request_part} "
        f"Interpret this as a live operator message and respond in the current session.\n\n{body}]"
    )


def dispatch_hermes_node_host(profile: str, payload: dict[str, Any], node_host_url: str) -> dict[str, Any]:
    forwarded = dict(payload)
    forwarded["target"] = f"hermes:{profile}"
    data = json.dumps(forwarded).encode("utf-8")
    req = urlrequest.Request(
        node_host_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body}
            if not (200 <= resp.status < 300):
                raise IngressError(HTTPStatus.BAD_GATEWAY, "Hermes node host rejected message", detail=parsed)
            if isinstance(parsed, dict):
                parsed.setdefault("backend", "hermes-node-host")
                parsed.setdefault("target", f"hermes:{profile}")
                return parsed
            return {"ok": True, "target": f"hermes:{profile}", "backend": "hermes-node-host", "status": "accepted", "response": parsed}
    except URLError as exc:
        raise IngressError(HTTPStatus.BAD_GATEWAY, "Hermes node host unavailable", detail=str(exc))


def dispatch_hermes(profile: str, payload: dict[str, Any], hermes_root: Path, nodes_path: Path, node_host_url: str) -> dict[str, Any]:
    cfg = node_config(profile, nodes_path)
    mode = str((cfg or {}).get("mode") or "").strip()
    if mode in {"warm_node", "headless_warm"}:
        return dispatch_hermes_node_host(profile, payload, node_host_url)

    profile_root = hermes_root / profile
    if not profile_root.exists() or not profile_root.is_dir():
        raise IngressError(HTTPStatus.NOT_FOUND, f"Hermes profile not found: {profile}")
    source = latest_hermes_source(profile_root, payload)
    ingress_id = f"http-ingress-{utc_stamp()}-{uuid4().hex[:8]}"
    envelope = {
        "id": ingress_id,
        "text": format_ingress_text(payload, ingress_id),
        "source": source,
        "message_type": "text",
        "internal": True,
        "created_at": utc_stamp(),
        "reason": "http_ingress",
        "metadata": payload.get("metadata") or {},
        "sender": str(payload.get("from") or "unknown").strip(),
        "subject": str(payload.get("subject") or "Ingress message").strip(),
    }
    inbox = profile_root / "gateway" / "inject" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    target = inbox / f"{ingress_id}.json"
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(target)
    return {
        "ok": True,
        "id": ingress_id,
        "target": f"hermes:{profile}",
        "backend": "hermes",
        "status": "accepted",
        "reply_mode": "native",
        "envelope": str(target),
        "source": {
            "platform": source.get("platform"),
            "chat_id": source.get("chat_id"),
            "chat_type": source.get("chat_type"),
        },
    }


def dispatch_aura(target: str, payload: dict[str, Any], aura_cli: Path, aura_state_dir: Path) -> dict[str, Any]:
    target = normalize_aura_target(target)
    if ":" not in target:
        raise IngressError(HTTPStatus.BAD_REQUEST, "aura target must be fleet:seat")
    if not aura_cli.exists():
        raise IngressError(HTTPStatus.NOT_FOUND, f"Aura CLI not found: {aura_cli}")
    ingress_id = f"http-ingress-{utc_stamp()}-{uuid4().hex[:8]}"
    message = format_ingress_text(payload, ingress_id)
    cmd = [sys.executable, str(aura_cli), "send", target, message, "--as-service", SERVICE_NAME]
    env = os.environ.copy()
    env["AURA_STATE_DIR"] = str(aura_state_dir)
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=60, env=env)
    if proc.returncode != 0:
        raise IngressError(
            HTTPStatus.BAD_GATEWAY,
            "aura send failed",
            detail={"returncode": proc.returncode, "stderr": proc.stderr[-4000:], "stdout": proc.stdout[-4000:]},
        )
    return {
        "ok": True,
        "id": ingress_id,
        "target": f"aura:{target}",
        "aura_target": target,
        "backend": "aura",
        "status": "accepted",
        "reply_mode": "native",
        "aura_state_dir": str(aura_state_dir),
        "stdout": proc.stdout.strip(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HermesIngress/0.1"

    def _check_auth(self) -> None:
        token = self.server.token  # type: ignore[attr-defined]
        if not token:
            return
        expected = f"Bearer {token}"
        if self.headers.get("Authorization") != expected:
            raise IngressError(HTTPStatus.UNAUTHORIZED, "missing or invalid bearer token")

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in {"", "/healthz"}:
            json_response(self, HTTPStatus.OK, {"ok": True, "service": SERVICE_NAME, "time": now_iso()})
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        started = time.time()
        try:
            if self.path.rstrip("/") not in {"/v1/messages", "/message"}:
                raise IngressError(HTTPStatus.NOT_FOUND, "not found")
            self._check_auth()
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                raise IngressError(HTTPStatus.BAD_REQUEST, "empty request body")
            if length > MAX_BODY_BYTES:
                raise IngressError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body too large")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                raise IngressError(HTTPStatus.BAD_REQUEST, "invalid JSON", detail=str(exc))
            payload = validate_payload(payload)
            scheme, name = parse_target(payload.get("target"))
            if scheme == "hermes":
                result = dispatch_hermes(
                    name,
                    payload,
                    self.server.hermes_root,  # type: ignore[attr-defined]
                    self.server.hermes_nodes_path,  # type: ignore[attr-defined]
                    self.server.hermes_node_host_url,  # type: ignore[attr-defined]
                )
            else:
                result = dispatch_aura(name, payload, self.server.aura_cli, self.server.aura_state_dir)  # type: ignore[attr-defined]
            result["elapsed_ms"] = int((time.time() - started) * 1000)
            json_response(self, HTTPStatus.ACCEPTED, result)
        except IngressError as exc:
            payload = {"ok": False, "error": exc.message}
            if exc.detail is not None:
                payload["detail"] = exc.detail
            json_response(self, exc.status, payload)
        except Exception as exc:  # keep ingress failures JSON-shaped
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal error", "detail": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write(f"{now_iso()} {self.address_string()} {format % args}\n")


class IngressServer(ThreadingHTTPServer):
    def __init__(
        self,
        addr: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        token: str,
        hermes_root: Path,
        hermes_nodes_path: Path,
        hermes_node_host_url: str,
        aura_cli: Path,
        aura_state_dir: Path,
    ) -> None:
        super().__init__(addr, handler)
        self.token = token
        self.hermes_root = hermes_root
        self.hermes_nodes_path = hermes_nodes_path
        self.hermes_node_host_url = hermes_node_host_url
        self.aura_cli = aura_cli
        self.aura_state_dir = aura_state_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local HTTP ingress for Hermes profiles and Aura seats.")
    parser.add_argument("--host", default=os.getenv("HERMES_INGRESS_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("HERMES_INGRESS_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--token", default=os.getenv("HERMES_INGRESS_TOKEN", ""), help="Bearer token. Defaults to HERMES_INGRESS_TOKEN; empty disables auth.")
    parser.add_argument("--hermes-root", type=Path, default=Path(os.getenv("HERMES_INGRESS_HERMES_ROOT", str(DEFAULT_HERMES_ROOT))))
    parser.add_argument("--hermes-nodes", type=Path, default=Path(os.getenv("HERMES_INGRESS_HERMES_NODES", str(DEFAULT_HERMES_NODES_PATH))))
    parser.add_argument("--hermes-node-host-url", default=os.getenv("HERMES_NODE_HOST_URL", DEFAULT_HERMES_NODE_HOST_URL))
    parser.add_argument("--aura-cli", type=Path, default=Path(os.getenv("HERMES_INGRESS_AURA_CLI", str(DEFAULT_AURA_CLI))))
    parser.add_argument("--aura-state-dir", type=Path, default=Path(os.getenv("HERMES_INGRESS_AURA_STATE_DIR", str(DEFAULT_AURA_STATE_DIR))))
    args = parser.parse_args(argv)

    server = IngressServer(
        (args.host, args.port),
        Handler,
        token=args.token,
        hermes_root=args.hermes_root,
        hermes_nodes_path=args.hermes_nodes,
        hermes_node_host_url=args.hermes_node_host_url,
        aura_cli=args.aura_cli,
        aura_state_dir=args.aura_state_dir,
    )
    auth_state = "enabled" if args.token else "disabled-local"
    print(f"{SERVICE_NAME} listening on http://{args.host}:{args.port} auth={auth_state}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
