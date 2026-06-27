---
name: aura-bridge
description: "Aura's external surfaces — Discord, Clawhip, Hermes ingress: route, reply, and correlate channel evidence with live seats."
---

# Aura Bridge

Aura is the control plane for live agents at `fleet:seat` addresses — and the
outside world reaches them through external surfaces: Discord channels,
Clawhip delivery, Hermes HTTP ingress. Each surface owns its own delivery
evidence; Aura owns the seat identity it lands on. This skill is the edge
work: which surface owns a channel, how to reply into it, and how to correlate
external evidence with live Aura state.

## Ontology

**Sink id** — an external id (a Discord message/channel id, a Clawhip event
id). Channel evidence, never a seat identity.

**Channel binding** — the row in `~/.aura/discord/channel-bindings.json`
mapping a Discord channel to its target: a `default_target` plus optional
`@alias` targets. For Aura-owned channels these rows are machine-authored by
the projection generator (additive — adds, never removes) and re-read live by
the listener.

**Ingress** — the local HTTP router (`127.0.0.1:7135`) for `hermes:<node>` and
`aura:<fleet:seat>` targets.

## Core Rule

Correlate, never substitute: a sink id is matched to a `fleet:seat`, not used
as one. And the bindings file is the live switch — generated and re-read live,
not hand-edited — so always read it, never a remembered snapshot.

## Discord — which path owns a channel

```bash
python3 -m json.tool /home/axp/.aura/discord/channel-bindings.json
```

A binding whose default or any alias routes to `hermes:*` is owned by the
Hermes Discord router (messages go to warm Hermes nodes); everything else is
owned by the Aura Discord listener (messages go to `fleet:seat` via
`aura send`).

## The channel tree is a live projection

The Discord server mirrors the mesh: society → category, fleet → channel (a
channel exists iff the fleet has a live `:manager` seat). A fleet's channel is
bound `default_target = <fleet>:manager` with its other live seats as `@seat`
aliases — post in the channel and the manager answers into it; `@seat` reaches
one seat. A fleet that loses all seats keeps its channel DORMANT in place (💤
name prefix, same id/category/binding), not archived; only true-legacy
channels are archived (never deleted). The tree is generated idempotently from
the society config on a cadence (a steady-state re-run is a no-op) — it is a
consumer of the society primitive. Bindings are machine-authored + additive
(`aura discord bind-channel` adds, never removes, so dormant aliases are
tolerated), and the Aura listener re-reads its watched-channel set live (by
mtime) — a newly-bound channel is watched with no restart.

## Discord — replying into a channel

The common case is now the projection's default: a channel's posts reach the
fleet's `:manager`, and you reply back into the **same channel** the message
came from. `@seat` reaches a specific seat. Operator-curated direct lanes
(e.g. `#sales-ops` → `flexchat-sales:operator`) are the protected special
case, not the norm. Either way `--channel` is still required; omitting it
lands the reply in the default home channel instead:

```bash
aura discord send --channel CHANNEL_ID --from FLEET:SEAT $'MESSAGE'
```

Replies are operator-facing: lead with the answer or current action, concise
and conversational, no internal command dumps. For live interaction, send a
short start acknowledgement before longer work and a closing message when
done. Don't post self-messages expecting a bot to wake — adapters ignore
their own identity.

## Hermes ingress

```bash
curl -sS http://127.0.0.1:7135/healthz

curl -sS -X POST http://127.0.0.1:7135/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"target": "hermes:NODE", "from": "aura:FLEET:SEAT",
       "subject": "...", "body": "Concise; point at durable artifacts.",
       "delivery": "live", "reply_mode": "native"}'
```

`hermes:<node>` routes via `~/.hermes/nodes.json` — a warm node answers
through the node host; a live gateway through its own surface. HTTP acceptance
proves mechanical delivery only; acceptance is still a native reply, report,
or receipt. If ingress is down, route to `aura-operator` rather than assuming
a fallback exists.

## Correlating evidence

```text
identify the fleet:seat
  -> inspect Aura state (delivery records, reports)
  -> query the surface (discord status, clawhip status / verify-bindings)
  -> compare; name the link or the discrepancy
```

Name what each piece of evidence proves — liveness, launch, mechanical
delivery, or acceptance — and don't let a sink receipt mask a missing managed
row.

## References

```text
/home/axp/.runway/runway/places/aura/.context/current/2026-06-04-2022/gateways/discord.md
/home/axp/.runway/runway/places/aura/.context/current/2026-06-04-2022/gateways/channel-bindings.md
/home/axp/.runway/runway/places/aura/.context/current/2026-06-04-2022/runtimes/hermes/mesh-ingress-mailbox.md
```

## Boundary

Bridge work is edges and correlation. Messaging a seat inside the mesh →
`aura-send`. Repairing the listener/router services or a profile →
`aura-operator`. The Hermes ingress here (`:7135`) is a Hermes-specific door;
the general **inbound** HTTP in-jack — external automation / webhooks (Linear,
GitHub) `POST`ing into the mesh — is a trigger, so it lives in `aura-event`
(`references/in-jack.md`), not here.
