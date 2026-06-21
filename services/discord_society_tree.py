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


def current_tree(env: dict[str, str], gid: str) -> tuple[dict, list[dict]]:
    chans = discord_api("GET", f"/guilds/{gid}/channels", env["DISCORD_TOKEN"])
    cats = {c["name"]: c["id"] for c in chans if c["type"] == CT_CATEGORY}
    home = env.get("DISCORD_CHANNEL_ID")  # the bot's home channel (#general) — NEVER archived
    text = [{"id": c["id"], "name": c["name"], "parent": c.get("parent_id")}
            for c in chans if c["type"] == CT_TEXT and c["id"] != home]
    return cats, text


# ---- Plan rendering -------------------------------------------------------- #

def render(target: list[dict], existing_cats: dict, existing_text: list[dict]) -> str:
    by_cat: dict[str, list[dict]] = {}
    for c in target:
        by_cat.setdefault(c["category"], []).append(c)
    lines = ["DISCORD SOCIETY TREE — DRY RUN (nothing mutated)\n"]
    lines.append("CATEGORIES TO ENSURE: " +
                 ", ".join(sorted(by_cat) + [ARCHIVE_CATEGORY]) +
                 f"   (existing categories: {sorted(existing_cats) or 'none'})\n")
    for cat in list(by_cat) + [ARCHIVE_CATEGORY]:
        lines.append(f"▸ #{cat}/" + ("   [NEW]" if cat not in existing_cats else "   [exists]"))
        if cat == ARCHIVE_CATEGORY:
            for t in existing_text:
                lines.append(f"    ↳ re-parent  #{t['name']:<28} ({t['id']})  [binding untouched]")
            continue
        for c in by_cat.get(cat, []):
            lines.append(f"    ├─ #{c['channel']:<14} ⇐ {c['fleet']}")
            lines.append(f"    │     default → {c['default_target']}")
            if c["aliases"]:
                al = ", ".join(f"@{k}→{v}" for k, v in c["aliases"].items())
                lines.append(f"    │     aliases → {al}")
            else:
                lines.append(f"    │     aliases → (none — manager only)")
    lines.append(f"\nSUMMARY: {len(target)} channels to create + bind across "
                 f"{len(by_cat)} society categories; "
                 f"{len(existing_text)} existing channels → archive (no delete).")
    return "\n".join(lines)


# ---- Apply (gated; only after approval) ------------------------------------ #

def apply(target, env, gid, existing_cats, existing_text) -> None:
    tok = env["DISCORD_TOKEN"]
    cats = dict(existing_cats)
    for cat in sorted({c["category"] for c in target}) + [ARCHIVE_CATEGORY]:
        if cat not in cats:
            made = discord_api("POST", f"/guilds/{gid}/channels", tok,
                               {"name": cat, "type": CT_CATEGORY})
            cats[cat] = made["id"]
            print(f"created category #{cat} ({made['id']})")
            time.sleep(0.5)
    # re-parent existing channels into archive (no delete; #general already excluded)
    for t in existing_text:
        discord_api("PATCH", f"/channels/{t['id']}", tok, {"parent_id": cats[ARCHIVE_CATEGORY]})
        print(f"archived #{t['name']} ({t['id']})")
        time.sleep(0.5)
    # create + bind the society channels
    for c in target:
        made = discord_api("POST", f"/guilds/{gid}/channels", tok,
                           {"name": c["channel"], "type": CT_TEXT, "parent_id": cats[c["category"]]})
        cid = made["id"]
        bind = [str(AURA_CLI), "discord", "bind-channel", cid,
                "--fleet", c["fleet"], "--default-target", c["default_target"]]
        for name, tgt in c["aliases"].items():
            bind += ["--alias", f"{name}={tgt}"]
        subprocess.run([sys.executable, *bind], check=True)
        print(f"created #{c['category']}/#{c['channel']} ({cid}) + bound → {c['default_target']}")
        time.sleep(0.5)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Discord society-category tree generator (dry-run default).")
    ap.add_argument("--apply", action="store_true", help="Perform creation/re-parent/bind (gated — needs approval).")
    ap.add_argument("--json", action="store_true", help="Emit the plan as JSON instead of a tree.")
    args = ap.parse_args(argv)

    roster, members = live_roster(), society_members()
    target = compute_target(roster, members)

    env = discord_env()
    gid = guild_id(env)
    existing_cats, existing_text = current_tree(env, gid)

    if args.json:
        print(json.dumps({"guild_id": gid, "channels": target,
                          "archive": existing_text, "existing_categories": existing_cats}, indent=2))
    else:
        print(render(target, existing_cats, existing_text))

    if args.apply:
        print("\n--apply: MUTATING DISCORD…\n")
        apply(target, env, gid, existing_cats, existing_text)
        print("\napply complete.")
    else:
        print("\n(dry-run — re-run with --apply only after operator approval.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
