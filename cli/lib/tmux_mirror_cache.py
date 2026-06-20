"""Event-driven cache for the physical tmux mirror — without polling every read.

Today ``tmux_mirror.list_physical_panes()`` forks ``tmux list-panes -a`` on every
read. This module makes the read event-driven and safe:

- tmux **global hooks** (`set-hook -g`, installed once) touch a cheap *dirty*
  sentinel whenever a pane/window/session is created or destroyed.
- A read serves the cached pane set when it is fresh (no hook fired since the
  cache was written) and within a TTL; otherwise it re-polls once, rewrites the
  cache, and clears the dirty flag.

This gives the event-driven property (a real change invalidates immediately) and
a TTL bounds worst-case drift from any lifecycle event a hook does not cover —
*without* attaching a control-mode client, so it cannot resize live panes or
drink the %output firehose. The control-client path (richer, but it must manage
client size on the live server) is a later, supervised step.

Source is selected by ``AURA_MIRROR_SOURCE``:
    poll    (default) — today's behavior, fork on every read
    cache             — serve from the hook-invalidated cache
    shadow            — poll IS authoritative AND the cache is computed and
                        diffed; divergence is logged. The A/B oracle: run this
                        on the live server, confirm zero divergence, then flip
                        to ``cache``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time

from lib import state

_DEFAULT_TTL = 5.0          # seconds; max staleness even with no hook event
_SHADOW_LOG_CAP = 500


def _source() -> str:
    value = (os.environ.get("AURA_MIRROR_SOURCE") or "poll").strip().lower()
    return value if value in {"poll", "cache", "shadow"} else "poll"


def _ttl() -> float:
    raw = os.environ.get("AURA_MIRROR_TTL")
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return _DEFAULT_TTL


def _registry_dir() -> Path:
    return state.state_root() / "registry"


def cache_path() -> Path:
    return _registry_dir() / "tmux-mirror-cache.json"


def dirty_path() -> Path:
    return _registry_dir() / ".tmux-mirror-dirty"


def shadow_log_path() -> Path:
    return _registry_dir() / "tmux-mirror-shadow.log"


def mark_dirty() -> None:
    """Invalidate the cache (called by the tmux hook). Cheap, best-effort."""
    try:
        dirty_path().parent.mkdir(parents=True, exist_ok=True)
        dirty_path().touch()
    except OSError:
        pass


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _cache_is_fresh() -> bool:
    cache_m = _mtime(cache_path())
    if cache_m == 0.0:
        return False
    if _mtime(dirty_path()) > cache_m:      # a lifecycle event fired since the write
        return False
    if (time.time() - cache_m) > _ttl():    # TTL bound on any uncovered event
        return False
    return True


def _read_cache() -> dict | None:
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data.get("ok") else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(result: dict) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmux-mirror-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f)
        os.replace(tmp, path)
        # clearing dirty: stamp it older than the cache we just wrote
        try:
            dirty_path().unlink()
        except FileNotFoundError:
            pass
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _pane_set(result: dict | None) -> set:
    if not result:
        return set()
    return {p.get("pane_ref") for p in result.get("panes", []) if p.get("pane_ref")}


def _log_shadow(poll_result: dict, cache_result: dict | None) -> None:
    poll_set = _pane_set(poll_result)
    cache_set = _pane_set(cache_result)
    missing = poll_set - cache_set      # live panes the cache lacked
    extra = cache_set - poll_set        # stale panes the cache still held
    line = json.dumps({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "diverged": bool(missing or extra),
        "poll_panes": len(poll_set),
        "cache_panes": len(cache_set),
        "cache_hit": cache_result is not None,
        "missing": sorted(missing)[:20],
        "extra": sorted(extra)[:20],
    })
    try:
        path = shadow_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        existing.append(line)
        if len(existing) > _SHADOW_LOG_CAP:
            existing = existing[-_SHADOW_LOG_CAP:]
        path.write_text("\n".join(existing) + "\n", encoding="utf-8")
    except OSError:
        pass


def serve(poll_fn) -> dict:
    """Return the physical-pane result for the configured source.

    ``poll_fn`` is the original ``tmux list-panes -a`` reader; it is the single
    source of truth in ``poll`` and ``shadow`` modes, and the refill path in
    ``cache`` mode.
    """
    source = _source()

    if source == "cache":
        if _cache_is_fresh():
            cached = _read_cache()
            if cached is not None:
                return cached
        result = poll_fn()
        if result.get("ok"):
            _write_cache(result)
        return result

    # poll-authoritative path (poll + shadow)
    result = poll_fn()
    if source == "shadow":
        cache_result = _read_cache() if _cache_is_fresh() else None
        if cache_result is None and result.get("ok"):
            _write_cache(result)          # warm the cache for the next read
            cache_result = result
        _log_shadow(result, cache_result)
    return result


# tmux global hooks that invalidate the cache. Lifecycle only — no %output.
_HOOK_EVENTS = (
    "after-new-window",
    "after-split-window",
    "after-kill-pane",
    "pane-exited",
    "window-linked",
    "window-unlinked",
    "session-created",
    "session-closed",
    "after-rename-window",
    "after-move-window",
)


def install_hooks_commands(mark_cmd: str) -> list[list[str]]:
    """tmux command argv lists that register the dirty-mark hooks globally.

    ``mark_cmd`` is the shell run by ``run-shell -b`` on each event — a plain
    ``touch`` of the dirty file is cheapest (no aura subprocess in the hook).
    """
    cmds = []
    for event in _HOOK_EVENTS:
        cmds.append(["set-hook", "-g", event, f"run-shell -b {mark_cmd!r}"])
    return cmds
