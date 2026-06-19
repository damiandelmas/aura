#!/usr/bin/env python3
"""Aura HTTP in-jack: one door for external automation to reach the mesh.

This is the general entry point. Any external automation (a button on a hosted
board, Zapier, cron, curl) POSTs Aura's *native envelope* to ``POST /in`` and it
is routed to a seat, a fleet, the work pool, or the report bus. Foreign signers
(Linear, GitHub, Stripe) — which impose their own signature scheme and JSON
shape — POST to ``POST /in/<source>``, where a small per-source adapter verifies
the signature and translates the payload into the same native envelope.

The door is a router, not a workflow engine: it proves the sender, dedups, rate
limits, then shells the existing ``aura`` CLI (``send`` / ``broadcast`` /
``work submit``). It owns no work-truth and invents no delivery machinery.

A 202/200 response means "accepted by the ingress backend". It does NOT prove
the target seat read or completed the work — acceptance is a reply/report.

Untrusted by construction: a foreign payload's text is task content only. An
adapter must place it in ``body``/``meta`` and never let it choose ``target``,
the route, or auth.
"""
from __future__ import annotations

import argparse
import hmac
import importlib.util
import json
import os
import subprocess
import sys
import time
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7137
DEFAULT_AURA_CLI = Path("/home/axp/projects/aura/main/cli/aura")
DEFAULT_STATE_DIR = Path(os.environ.get("AURA_STATE_DIR", str(Path.home() / ".aura")))
SERVICE_SENDER = "aura-ingress"
MAX_BODY_BYTES = 256 * 1024
RATE_LIMIT_DEFAULT = 30          # requests
RATE_WINDOW_DEFAULT = 60.0       # seconds
ADAPTERS_PACKAGE_DIR = Path(__file__).resolve().parent / "ingress_adapters"


class IngressError(Exception):
    def __init__(self, status: int, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.detail = detail


# --------------------------------------------------------------------------- #
# Pure core (no sockets, no subprocess) — fully unit-testable                  #
# --------------------------------------------------------------------------- #

def verify_signature(secret: str, raw: bytes, signature_hex: str) -> bool:
    """Timing-safe HMAC-SHA256 over the RAW body (ported from ClaudeClaw)."""
    if not secret or not signature_hex:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw, sha256).hexdigest()
    # Accept "sha256=..." prefixed forms (GitHub style) too.
    candidate = signature_hex.split("=", 1)[-1].strip()
    try:
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def parse_target(target: str) -> tuple[str, str]:
    """Map a scheme-prefixed target to a (route, value) pair.

    ``seat:<fleet>:<seat>``  -> ("send", "<fleet>:<seat>")
    ``fleet:<name>``         -> ("broadcast", "<name>")
    ``placement:<name>``     -> ("work", "<name>")
    bare ``<fleet>:<seat>``  -> ("send", "<fleet>:<seat>")   (no known scheme)
    """
    target = str(target or "").strip()
    if not target or ":" not in target:
        raise IngressError(HTTPStatus.BAD_REQUEST, "target must be scheme:value (seat:/fleet:/placement:) or fleet:seat")
    scheme, rest = target.split(":", 1)
    rest = rest.strip()
    if scheme == "seat":
        if ":" not in rest:
            raise IngressError(HTTPStatus.BAD_REQUEST, "seat target must be seat:<fleet>:<seat>")
        return "send", rest
    if scheme == "fleet":
        if not rest:
            raise IngressError(HTTPStatus.BAD_REQUEST, "fleet target must be fleet:<name>")
        return "broadcast", rest
    if scheme == "placement":
        if not rest:
            raise IngressError(HTTPStatus.BAD_REQUEST, "placement target must be placement:<name>")
        return "work", rest
    # Unknown scheme: treat the whole thing as a bare fleet:seat send address.
    return "send", target


def build_argv(envelope: Mapping[str, Any], *, service: str = SERVICE_SENDER) -> list[str]:
    """Translate a native envelope into ``aura`` CLI argv (the target-kind switch)."""
    body = str(envelope.get("body") or "").strip()
    if not body:
        raise IngressError(HTTPStatus.BAD_REQUEST, "missing body")
    route, value = parse_target(envelope.get("target"))
    dedupe = str(envelope.get("dedupe") or "").strip()
    if route == "send":
        argv = ["send", value, body, "--as-service", service]
        if dedupe:
            argv += ["--dedupe-key", dedupe]
        return argv
    if route == "broadcast":
        argv = ["broadcast", body, "--fleet", value, "--as-service", service]
        if dedupe:
            argv += ["--dedupe-key", dedupe]
        return argv
    if route == "work":
        return ["work", "submit", value, body]
    raise IngressError(HTTPStatus.BAD_REQUEST, f"unsupported route: {route}")


class RateLimiter:
    """Per-key fixed-window limiter (ported from ClaudeClaw checkRateLimit)."""

    def __init__(self, limit: int = RATE_LIMIT_DEFAULT, window: float = RATE_WINDOW_DEFAULT,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._buckets: dict[str, tuple[int, float]] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        count, reset_at = self._buckets.get(key, (0, 0.0))
        if now > reset_at:
            self._buckets[key] = (1, now + self.window)
            return True
        if count >= self.limit:
            return False
        self._buckets[key] = (count + 1, reset_at)
        return True


class DedupLedger:
    """Append-only seen-key ledger; folds to an in-memory set. Doubles as audit."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._seen: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                key = row.get("dedup_key")
                if key:
                    self._seen.add(str(key))

    def seen(self, key: str) -> bool:
        return bool(key) and key in self._seen

    def record(self, row: Mapping[str, Any]) -> None:
        key = row.get("dedup_key")
        if key:
            self._seen.add(str(key))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(row), sort_keys=True) + "\n")


def load_adapter(source: str, *, adapters_dir: Path = ADAPTERS_PACKAGE_DIR):
    """Load a per-source adapter module exposing verify() and normalize()."""
    if not source or not source.replace("-", "").replace("_", "").isalnum():
        raise IngressError(HTTPStatus.BAD_REQUEST, "invalid source name")
    path = Path(adapters_dir) / f"{source}.py"
    if not path.exists():
        raise IngressError(HTTPStatus.NOT_FOUND, f"no ingress adapter for source: {source}")
    spec = importlib.util.spec_from_file_location(f"ingress_adapters.{source}", path)
    if spec is None or spec.loader is None:
        raise IngressError(HTTPStatus.INTERNAL_SERVER_ERROR, f"cannot load adapter: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "verify") or not hasattr(module, "normalize"):
        raise IngressError(HTTPStatus.INTERNAL_SERVER_ERROR, f"adapter {source} missing verify/normalize")
    return module


# --------------------------------------------------------------------------- #
# Request processing (pure given injected deps) — no socket dependence         #
# --------------------------------------------------------------------------- #

class IngressDeps:
    def __init__(self, *, token: str, secrets: Mapping[str, str], rate: RateLimiter,
                 dedup: DedupLedger, dispatch: Callable[[list[str]], dict],
                 adapters_dir: Path = ADAPTERS_PACKAGE_DIR) -> None:
        self.token = token
        self.secrets = dict(secrets or {})
        self.rate = rate
        self.dedup = dedup
        self.dispatch = dispatch
        self.adapters_dir = adapters_dir


def _check_bearer(headers: Mapping[str, str], token: str) -> None:
    if not token:
        return  # local/dev: auth disabled
    got = str(headers.get("authorization") or "")
    if not hmac.compare_digest(got, f"Bearer {token}"):
        raise IngressError(HTTPStatus.UNAUTHORIZED, "missing or invalid bearer token")


def _audit_row(*, source: str, envelope: Mapping[str, Any], state: str,
               result: Any = None) -> dict:
    route, value = ("?", "?")
    try:
        route, value = parse_target(envelope.get("target"))
    except Exception:
        pass
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "state": state,
        "route": route,
        "value": value,
        "kind": envelope.get("kind"),
        "dedup_key": str(envelope.get("dedupe") or ""),
        "meta": envelope.get("meta") or {},
        "result": result,
    }


def process(method: str, path: str, headers: Mapping[str, str], raw: bytes,
            deps: IngressDeps) -> tuple[int, dict]:
    """Core request handler. Returns (status, json_body). Never raises IngressError."""
    headers = {str(k).lower(): v for k, v in dict(headers).items()}
    path = (path or "/").split("?", 1)[0].rstrip("/") or "/"
    try:
        if method == "GET" and path in ("/", "/healthz", "/health"):
            return HTTPStatus.OK, {"ok": True, "service": SERVICE_SENDER}
        if method != "POST":
            raise IngressError(HTTPStatus.NOT_FOUND, "not found")
        if len(raw) > MAX_BODY_BYTES:
            raise IngressError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body too large")

        # Route: /in (native) | /in/<source> (foreign adapter)
        if path == "/in":
            source = "native"
            _check_bearer(headers, deps.token)
            envelope = _parse_native(raw)
        elif path.startswith("/in/"):
            source = path[len("/in/"):]
            adapter = load_adapter(source, adapters_dir=deps.adapters_dir)
            secret = deps.secrets.get(source, "")
            sig = (headers.get("linear-signature") or headers.get("x-signature")
                   or headers.get("x-hub-signature-256") or headers.get("stripe-signature") or "")
            if not adapter.verify(raw, headers, secret):
                raise IngressError(HTTPStatus.UNAUTHORIZED, "invalid signature")
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                raise IngressError(HTTPStatus.BAD_REQUEST, "invalid JSON", detail=str(exc))
            # Best-effort raw capture: the real foreign payload shape, never a guess.
            try:
                (deps.dedup.path.parent / f"last-{source}-payload.json").write_text(
                    json.dumps(payload, indent=2)[:30000], encoding="utf-8")
            except Exception:
                pass
            envelope = adapter.normalize(payload, headers)
            if envelope is None:
                deps.dedup.record(_audit_row(source=source, envelope={}, state="ignored"))
                return HTTPStatus.OK, {"ok": True, "status": "ignored"}
        else:
            raise IngressError(HTTPStatus.NOT_FOUND, "not found")

        # Validate + build argv up front (rejects bad envelopes before any side effect).
        argv = build_argv(envelope)

        # Dedup (idempotency) — a repeated delivery is accepted but not re-dispatched.
        dedup_key = str(envelope.get("dedupe") or "").strip()
        if dedup_key and deps.dedup.seen(dedup_key):
            return HTTPStatus.OK, {"ok": True, "status": "duplicate", "dedup_key": dedup_key}

        # Rate limit per source.
        if not deps.rate.allow(source):
            raise IngressError(HTTPStatus.TOO_MANY_REQUESTS, "rate limit exceeded")

        result = deps.dispatch(argv)
        deps.dedup.record(_audit_row(source=source, envelope=envelope, state="dispatched", result=result))
        return HTTPStatus.ACCEPTED, {"ok": True, "status": "accepted", "argv": argv, "result": result}

    except IngressError as exc:
        body = {"ok": False, "error": exc.message}
        if exc.detail is not None:
            body["detail"] = exc.detail
        return exc.status, body
    except Exception as exc:  # keep ingress failures JSON-shaped
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal error", "detail": str(exc)}


def _parse_native(raw: bytes) -> dict:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise IngressError(HTTPStatus.BAD_REQUEST, "invalid JSON", detail=str(exc))
    if not isinstance(payload, dict):
        raise IngressError(HTTPStatus.BAD_REQUEST, "payload must be a JSON object")
    return {
        "target": payload.get("target"),
        "kind": payload.get("kind"),
        "body": payload.get("body"),
        "dedupe": payload.get("dedupe"),
        "meta": payload.get("meta") or {},
    }


# --------------------------------------------------------------------------- #
# Production dispatch (shells the aura CLI) + HTTP server                       #
# --------------------------------------------------------------------------- #

def make_cli_dispatch(aura_cli: Path, state_dir: Path) -> Callable[[list[str]], dict]:
    def dispatch(argv: list[str]) -> dict:
        if not Path(aura_cli).exists():
            raise IngressError(HTTPStatus.NOT_FOUND, f"aura CLI not found: {aura_cli}")
        cmd = [sys.executable, str(aura_cli), *argv]
        env = os.environ.copy()
        env["AURA_STATE_DIR"] = str(state_dir)
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=90, env=env)
        if proc.returncode != 0:
            raise IngressError(HTTPStatus.BAD_GATEWAY, "aura command failed",
                               detail={"returncode": proc.returncode, "stderr": proc.stderr[-2000:]})
        return {"stdout": proc.stdout.strip()[-2000:]}
    return dispatch


def _load_secrets(path: Path) -> dict[str, str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


class Handler(BaseHTTPRequestHandler):
    server_version = "AuraIngress/1.0"

    def _respond(self, status: int, body: dict) -> None:
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        status, body = process("GET", self.path, self.headers, b"", self.server.deps)  # type: ignore[attr-defined]
        self._respond(status, body)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        status, body = process("POST", self.path, self.headers, raw, self.server.deps)  # type: ignore[attr-defined]
        self._respond(status, body)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write(f"{time.strftime('%H:%M:%S')} {self.address_string()} {fmt % args}\n")


class IngressServer(ThreadingHTTPServer):
    def __init__(self, addr: tuple[str, int], handler, *, deps: IngressDeps) -> None:
        super().__init__(addr, handler)
        self.deps = deps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aura HTTP in-jack.")
    parser.add_argument("--host", default=os.getenv("AURA_INGRESS_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("AURA_INGRESS_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--token", default=os.getenv("AURA_INGRESS_TOKEN", ""),
                        help="Bearer token for /in. Empty disables auth (local only).")
    parser.add_argument("--aura-cli", type=Path, default=Path(os.getenv("AURA_INGRESS_AURA_CLI", str(DEFAULT_AURA_CLI))))
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--secrets", type=Path,
                        default=Path(os.getenv("AURA_INGRESS_SECRETS", str(DEFAULT_STATE_DIR / "ingress" / "secrets.json"))))
    parser.add_argument("--rate-limit", type=int, default=int(os.getenv("AURA_INGRESS_RATE_LIMIT", str(RATE_LIMIT_DEFAULT))))
    args = parser.parse_args(argv)

    deps = IngressDeps(
        token=args.token,
        secrets=_load_secrets(args.secrets),
        rate=RateLimiter(limit=args.rate_limit),
        dedup=DedupLedger(args.state_dir / "ingress" / "seen.jsonl"),
        dispatch=make_cli_dispatch(args.aura_cli, args.state_dir),
    )
    server = IngressServer((args.host, args.port), Handler, deps=deps)
    auth = "enabled" if args.token else "disabled-local"
    print(f"{SERVICE_SENDER} listening on http://{args.host}:{args.port} auth={auth}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
