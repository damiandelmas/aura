#!/usr/bin/env python3
"""Generate the Discord *society-category* tree from Aura's society config + live roster.

Tree (society-config + live-roster driven, auto-curated):
  - One CATEGORY per society (flex, flexchat, aura) plus "other" (society-less
    fleets) and "archive" (the existing pre-restructure channels).
  - One CHANNEL per member fleet THAT HAS A live ``:manager`` seat (no manager ->
    no channel). Channel name = fleet minus its society prefix
    (``flexchat-factory`` -> ``#factory``); society-less fleets keep their name.
  - Each channel BOUND to ``<fleet>:manager`` (default target) with the fleet's
    other live seats as ``@seat`` aliases (via ``aura discord bind-channel``).
  - LEGACY: existing channels are RE-PARENTED into "archive" — never deleted,
    bindings left as-is.

Mechanics: channel/category CREATE + the archive MOVE go through the Discord bot
API (Manage-Channels). Aura only BINDS.

DRY-RUN BY DEFAULT — prints the plan, touches nothing. ``--apply`` performs the
creation / re-parent / bind (gated; run only after operator approval).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

DISCORD_API = "https://discord.com/api/v10"
USER_AGENT = "AuraSocietyTree (https://aura.local, 1.0)"
CT_CATEGORY, CT_TEXT = 4, 0
OTHER_CATEGORY = "other"
ARCHIVE_CATEGORY = "archive"
SELF_CATEGORY = "self"
# Personal (non-fleet) channels — kept OUT of the archive sweep, the same
# protection #general (the bot home) has. A re-run must never yank them back.
SELF_CHANNELS = frozenset({"assistant", "life", "spiritual"})
# Manually-managed channels that live in a society category but are NOT fleet
# targets the generator creates (e.g. an operator's direct-to-human lane). Bound
# by hand; protected from the archive sweep so a re-run never reclaims them.
# 'tenants' is here because flexchat-tenants is temporarily 0-seat (dormant): a
# channel is more durable than a transiently-dead fleet, so we keep it under
# flexchat with its binding intact rather than archiving it.
PROTECTED_CHANNELS = frozenset({"sales-ops", "tenants"})
REPO = Path(__file__).resolve().parents[1]
AURA_CLI = REPO / "cli" / "aura"


# ---- Aura data sources (society config + live roster) ---------------------- #

def aura(*args) -> dict:
    out = subprocess.run([sys.executable, str(AURA_CLI), *args],
                         capture_output=True, text=True, timeout=60).stdout
    # tolerate a leading non-JSON warning line
    start = out.find("{")
    return json.loads(out[start:]) if start >= 0 else {}


def live_roster() -> dict[str, list[str]]:
    rows = aura("list").get("rows", [])
    fleets: dict[str, list[str]] = {}
    for r in rows:
        if r.get("terminal") == "alive" and not r.get("hidden"):
            fleets.setdefault(r["fleet"], []).append(r["seat"])
    return {f: sorted(set(s)) for f, s in fleets.items()}


def society_members() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for soc in aura("society", "list").get("societies", []):
        name = soc["name"]
        got = aura("society", "get", name)
        out[name] = [m["name"] for m in got.get("members", [])]
    return out


def channel_name(fleet: str, society: str | None) -> str:
    prefix = f"{society}-"
    if society and fleet.startswith(prefix):
        return fleet[len(prefix):]
    return fleet


def compute_target(roster: dict[str, list[str]], members: dict[str, list[str]]) -> list[dict]:
    """One channel per manager-bearing fleet, assigned to its society or 'other'."""
    manager_fleets = {f for f, seats in roster.items() if "manager" in seats}
    assigned: set[str] = set()
    plan: list[dict] = []
    for society, fleets in sorted(members.items()):
        for fleet in sorted(set(fleets) & manager_fleets):
            assigned.add(fleet)
            plan.append(_channel(fleet, society, roster))
    for fleet in sorted(manager_fleets - assigned):     # society-less -> 'other'
        plan.append(_channel(fleet, None, roster))
    return plan


def _channel(fleet: str, society: str | None, roster: dict[str, list[str]]) -> dict:
    others = [s for s in roster.get(fleet, []) if s != "manager"]
    return {
        "category": society or OTHER_CATEGORY,
        "channel": channel_name(fleet, society),
        "fleet": fleet,
        "default_target": f"{fleet}:manager",
        "aliases": {s: f"{fleet}:{s}" for s in others},
    }


# ---- Discord (read-only here; writes only under --apply) ------------------- #

def discord_env() -> dict[str, str]:
    return dict(l.strip().split("=", 1) for l in
                open(os.path.expanduser("~/.aura/discord/env")) if "=" in l)


def discord_api(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{DISCORD_API}{path}", data=data, method=method,
        headers={"Authorization": f"Bot {token}", "User-Agent": USER_AGENT,
                 "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")


def guild_id(env: dict[str, str]) -> str:
    ch = discord_api("GET", f"/channels/{env['DISCORD_CHANNEL_ID']}", env["DISCORD_TOKEN"])
    return ch["guild_id"]


BINDINGS_PATH = Path(os.path.expanduser("~/.aura/discord/channel-bindings.json"))


def fetch_state(env: dict[str, str], gid: str) -> dict:
    """Current live guild: categories (by name/id), text channels, and an index
    of existing text channels keyed by (category-name, channel-name)."""
    chans = discord_api("GET", f"/guilds/{gid}/channels", env["DISCORD_TOKEN"])
    cats_by_name = {c["name"]: c["id"] for c in chans if c["type"] == CT_CATEGORY}
    cats_by_id = {v: k for k, v in cats_by_name.items()}
    text = [c for c in chans if c["type"] == CT_TEXT]
    by_key = {(cats_by_id.get(c.get("parent_id")), c["name"]): c for c in text}
    return {"cats_by_name": cats_by_name, "cats_by_id": cats_by_id, "text": text, "by_key": by_key}


def load_bindings() -> dict:
    try:
        return json.loads(BINDINGS_PATH.read_text()).get("channels", {})
    except Exception:
        return {}


def _binding_matches(current: dict | None, c: dict) -> bool:
    # The binding is up to date when the default target matches and every DESIRED
    # alias is present with the right target. EXTRA stored aliases are tolerated:
    # `aura discord bind-channel` is additive (can't remove an alias), and per the
    # channel-durability principle a transiently-dead seat's alias is kept dormant
    # rather than churned. So rebind only when a desired alias is MISSING or wrong
    # (a new/renamed live seat) — never just because a dead seat's alias lingers.
    # Exact equality here caused a perpetual rebind once a seat died (desired drops
    # it, stored keeps it) — breaking the re-run no-op.
    if not current or current.get("default_target") != c["default_target"]:
        return False
    cur_aliases = dict(current.get("aliases") or {})
    return all(cur_aliases.get(name) == target for name, target in c["aliases"].items())


def build_plan(target: list[dict], state: dict, env: dict[str, str], bindings: dict) -> dict:
    """Diff the desired tree against live state. Every item carries an action so
    a re-run against an already-applied state produces an empty delta (no-op)."""
    home = env.get("DISCORD_CHANNEL_ID")
    target_keys = {(c["category"], c["channel"]) for c in target}

    needed_cats = sorted({c["category"] for c in target}) + [ARCHIVE_CATEGORY]
    categories = [{"name": cat, "id": state["cats_by_name"].get(cat),
                   "action": "exists" if cat in state["cats_by_name"] else "create"}
                  for cat in needed_cats]

    channels = []
    for c in target:
        existing = state["by_key"].get((c["category"], c["channel"]))   # match by (category, name)
        cid = existing["id"] if existing else None
        bind_ok = _binding_matches(bindings.get(str(cid)) if cid else None, c)
        channels.append({**c, "id": cid,
                         "action": "exists" if existing else "create",
                         "bind_action": "current" if bind_ok else "bind"})

    # ARCHIVE = TRUE LEGACY ONLY: not protected (#general / #self), NOT a target
    # society channel the generator creates, and not already in #archive.
    archive = []
    for ch in state["text"]:
        name, cat = ch["name"], state["cats_by_id"].get(ch.get("parent_id"))
        if ch["id"] == home or name in SELF_CHANNELS or name in PROTECTED_CHANNELS:  # protected
            continue
        if (cat, name) in target_keys:                     # our own society channel — leave it
            continue
        if cat == ARCHIVE_CATEGORY:                        # already archived — no-op
            continue
        archive.append({"id": ch["id"], "name": name, "from": cat or "(uncategorized)"})

    return {"categories": categories, "channels": channels, "archive": archive}


def deltas(plan: dict) -> dict:
    return {
        "categories": [c for c in plan["categories"] if c["action"] == "create"],
        "channels": [c for c in plan["channels"] if c["action"] == "create"],
        "binds": [c for c in plan["channels"] if c["bind_action"] == "bind"],
        "archive": plan["archive"],
    }


# ---- Plan rendering -------------------------------------------------------- #

def render(plan: dict) -> str:
    by_cat: dict[str, list[dict]] = {}
    for c in plan["channels"]:
        by_cat.setdefault(c["category"], []).append(c)
    d = deltas(plan)
    lines = ["DISCORD SOCIETY TREE — DRY RUN (nothing mutated)\n"]
    for cat in list(by_cat) + [ARCHIVE_CATEGORY]:
        cstate = next((x for x in plan["categories"] if x["name"] == cat), None)
        tag = "[create]" if cstate and cstate["action"] == "create" else "[exists]"
        lines.append(f"▸ #{cat}/   {tag}")
        if cat == ARCHIVE_CATEGORY:
            for a in plan["archive"]:
                lines.append(f"    ↳ archive  #{a['name']:<24} ({a['id']})  from #{a['from']}")
            if not plan["archive"]:
                lines.append("    (nothing to archive)")
            continue
        for c in by_cat.get(cat, []):
            mark = "NEW" if c["action"] == "create" else "exists"
            bind = "bind" if c["bind_action"] == "bind" else "ok"
            lines.append(f"    ├─ #{c['channel']:<14} ⇐ {c['fleet']}   [{mark}; binding:{bind}]")
            lines.append(f"    │     default → {c['default_target']}")
            if c["aliases"]:
                lines.append("    │     aliases → " + ", ".join(f"@{k}→{v}" for k, v in c["aliases"].items()))
    lines.append(f"\nDELTA: +{len(d['categories'])} categories, +{len(d['channels'])} channels, "
                 f"{len(d['archive'])} to archive, {len(d['binds'])} (re)binds.")
    if not any(d.values()):
        lines.append("RE-RUN NO-OP ✓ — live state already matches the desired tree.")
    return "\n".join(lines)


# ---- Apply (gated; idempotent — only the delta) ---------------------------- #

def apply(plan: dict, env: dict[str, str], gid: str) -> dict:
    tok = env["DISCORD_TOKEN"]
    cats = {c["name"]: c["id"] for c in plan["categories"] if c["id"]}
    counts = {"categories": 0, "channels": 0, "archived": 0, "binds": 0}
    for c in plan["categories"]:                            # skip-existing
        if c["action"] == "create":
            made = discord_api("POST", f"/guilds/{gid}/channels", tok, {"name": c["name"], "type": CT_CATEGORY})
            cats[c["name"]] = made["id"]; counts["categories"] += 1
            print(f"created category #{c['name']} ({made['id']})"); time.sleep(0.5)
    for a in plan["archive"]:                               # true-legacy only
        discord_api("PATCH", f"/channels/{a['id']}", tok, {"parent_id": cats[ARCHIVE_CATEGORY]})
        counts["archived"] += 1; print(f"archived #{a['name']} ({a['id']})"); time.sleep(0.5)
    for c in plan["channels"]:                              # skip-existing + idempotent bind
        cid = c["id"]
        if c["action"] == "create":
            made = discord_api("POST", f"/guilds/{gid}/channels", tok,
                               {"name": c["channel"], "type": CT_TEXT, "parent_id": cats[c["category"]]})
            cid = made["id"]; counts["channels"] += 1
            print(f"created #{c['category']}/#{c['channel']} ({cid})"); time.sleep(0.5)
        if c["bind_action"] == "bind":
            bind = [str(AURA_CLI), "discord", "bind-channel", cid,
                    "--fleet", c["fleet"], "--default-target", c["default_target"]]
            for name, tgt in c["aliases"].items():
                bind += ["--alias", f"{name}={tgt}"]
            subprocess.run([sys.executable, *bind], check=True, capture_output=True)
            counts["binds"] += 1; print(f"bound #{c['channel']} → {c['default_target']}"); time.sleep(0.3)
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Idempotent Discord society-category tree generator (dry-run default; safe to re-run).")
    ap.add_argument("--apply", action="store_true", help="Apply the delta (gated). A re-run against applied state is a no-op.")
    ap.add_argument("--json", action="store_true", help="Emit the plan + delta as JSON.")
    args = ap.parse_args(argv)

    roster, members = live_roster(), society_members()
    target = compute_target(roster, members)
    env = discord_env()
    gid = guild_id(env)
    state = fetch_state(env, gid)
    plan = build_plan(target, state, env, load_bindings())
    d = deltas(plan)

    if args.json:
        print(json.dumps({"guild_id": gid, "plan": plan, "delta": d}, indent=2, default=str))
    else:
        print(render(plan))

    if args.apply:
        if not any(d.values()):
            print("\n--apply: NO-OP — live state already matches the desired tree (0 changes).")
            return 0
        print("\n--apply: MUTATING DISCORD…\n")
        print(f"\napply complete: {apply(plan, env, gid)}")
    else:
        print("\n(dry-run — re-run with --apply only after operator approval; safe to re-run.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
