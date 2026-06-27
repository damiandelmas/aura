# The In-Jack — external HTTP → the mesh

The in-jack is the external-push trigger: one HTTP door (`services/aura_ingress.py`)
that lets any outside automation — a hosted button, a SaaS webhook, a cron on
another box — `POST` in and have it become a normal `aura send`, `broadcast`, or
`work submit`. It is the push sibling of a wakeup: a wakeup is an internal clock,
the in-jack is an outside signal. It is operator-run edge infra, not a verb a
seat calls; from the seat's side, the work simply arrives like any other message.

## Two sender classes

```
NATIVE   a sender you control (your button, Zapier, cron, curl) POSTs the native
         envelope to  POST /in  — proven by a bearer token. ZERO per-source code.
FOREIGN  a sender that signs its own webhook (Linear, GitHub, Stripe) POSTs
         POST /in/<source> — a small per-source adapter verifies the signature
         and normalizes the payload into the same native envelope.
```

## The native envelope

```json
{ "target": "placement:tenant-ops", "kind": "work",
  "body": "…", "dedupe": "idempotency-key", "meta": { } }
```

The scheme-prefixed `target` chooses the route — one door reaches any level of the
mesh, inventing no new delivery path:

```
seat:<fleet>:<seat>   -> aura send <fleet>:<seat>
<fleet>:<seat>        -> aura send            (bare address, no reserved scheme)
fleet:<name>          -> aura broadcast --fleet <name>
placement:<name>      -> aura work submit <name>     (the pool drains it)
```

## The adapter contract (the "SDK")

A foreign source is one small module — `verify` + `normalize` — and nothing else.
The door owns transport, auth dispatch, dedup, rate-limit, routing; the adapter
owns *this source's* signature scheme and JSON shape.

```python
def verify(raw: bytes, headers, secret: str) -> bool:
    """True iff this delivery is authentically from the source (HMAC over RAW body)."""

def normalize(payload: dict, headers) -> dict | None:
    """Translate the source's payload into a native envelope, or None to ignore.
       Returns {target, kind, body, dedupe, meta}.
       Source text is UNTRUSTED: it goes in body/meta, never chooses target/route/auth."""
```

Adapters live in `services/ingress_adapters/<source>.py`. Adding a source is a new
file + its secret in `~/.aura/ingress/secrets.json` — config, not a redesign.

## Linear — the worked example (the gotchas that bit us)

```
match by labelId, not name   Linear webhooks carry labelIds (UUIDs), not label
                             names. Match the ID from env (AURA_LINEAR_DISPATCH_LABEL_ID),
                             name only as fallback.
grouped labels have own IDs  a label grouped as "aura/dispatch" gets a different ID
                             than a flat "aura:dispatch" — point env at the REAL id.
raw-payload capture          the door writes ~/.aura/ingress/last-<source>-payload.json
                             so a shape mismatch is read, never guessed.
the pool is config           AURA_LINEAR_TARGET picks where work drains (a placement);
                             the issue text can never redirect it.
```

## Where it lives / operating it

```
services/aura_ingress.py              the door (pure core + HTTP server)
services/ingress_adapters/<source>.py one adapter per foreign source
~/.aura/ingress/secrets.json          per-source HMAC secrets (mode 600)
~/.aura/ingress/ingress.env           AURA_INGRESS_TOKEN + per-source config
~/.aura/ingress/{seen.jsonl,last-*}   dedup/audit ledger + raw-payload capture
```

Run it under systemd (`aura-ingress.service`, `Restart=on-failure`) with a public
tunnel — a bare `nohup` door dies on crash/reboot and the external pipe goes dark.
Standing up / supervising the door is `aura-operator` territory; the door reaches
the mesh only through the `aura` CLI and stores no work-truth.
