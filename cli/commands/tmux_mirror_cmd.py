"""`aura tmux-mirror` — manage the event-driven physical-mirror cache.

Actions:
  install-hooks    register tmux global hooks that invalidate the cache on pane/
                   window/session lifecycle (idempotent; safe — no client attach)
  uninstall-hooks  remove those hooks
  status           show source mode, TTL, cache freshness, ages, pane counts
  mark-dirty       invalidate the cache now (what the hook does)
  shadow-report    summarize the shadow A/B divergence log
"""

from __future__ import annotations

import subprocess
import time

from lib import tmux_mirror_cache as cache


def _run_tmux(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def _install_hooks() -> dict:
    mark_cmd = f"touch {cache.dirty_path()}"
    installed = []
    errors = []
    for argv in cache.install_hooks_commands(mark_cmd):
        result = _run_tmux(argv)
        if result.returncode == 0:
            installed.append(argv[2])  # the event name
        else:
            errors.append({"event": argv[2], "error": result.stderr.strip()})
    return {
        "ok": not errors,
        "schema": "aura.tmux_mirror_hooks.v1",
        "action": "install-hooks",
        "mark_cmd": mark_cmd,
        "installed": installed,
        "errors": errors,
    }


def _uninstall_hooks() -> dict:
    removed = []
    for event in cache._HOOK_EVENTS:
        _run_tmux(["set-hook", "-gu", event])
        removed.append(event)
    return {"ok": True, "action": "uninstall-hooks", "removed": removed}


def _status() -> dict:
    now = time.time()
    cache_m = cache._mtime(cache.cache_path())
    dirty_m = cache._mtime(cache.dirty_path())
    cached = cache._read_cache()
    return {
        "ok": True,
        "schema": "aura.tmux_mirror_status.v1",
        "source": cache._source(),
        "ttl_seconds": cache._ttl(),
        "cache_path": str(cache.cache_path()),
        "cache_present": cache_m > 0,
        "cache_age_seconds": round(now - cache_m, 3) if cache_m else None,
        "cache_fresh": cache._cache_is_fresh(),
        "dirty_pending": dirty_m > cache_m,
        "cached_pane_count": len(cached.get("panes", [])) if cached else 0,
    }


def _shadow_report() -> dict:
    import json
    path = cache.shadow_log_path()
    if not path.exists():
        return {"ok": True, "action": "shadow-report", "samples": 0,
                "note": "no shadow log yet; run reads with AURA_MIRROR_SOURCE=shadow"}
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    diverged = [r for r in rows if r.get("diverged")]
    hits = [r for r in rows if r.get("cache_hit")]
    return {
        "ok": True,
        "action": "shadow-report",
        "samples": len(rows),
        "diverged": len(diverged),
        "divergence_rate": round(len(diverged) / len(rows), 4) if rows else 0.0,
        "cache_hits": len(hits),
        "recent_divergences": diverged[-5:],
    }


def run(args):
    action = getattr(args, "tmux_mirror_action", None)
    if action == "install-hooks":
        return _install_hooks()
    if action == "uninstall-hooks":
        return _uninstall_hooks()
    if action == "status":
        return _status()
    if action == "mark-dirty":
        cache.mark_dirty()
        return {"ok": True, "action": "mark-dirty"}
    if action == "shadow-report":
        return _shadow_report()
    return {"ok": False, "error": f"unknown tmux-mirror action: {action}"}
