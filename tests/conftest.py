"""Global test isolation — nothing in the suite may touch live Aura state.

Root cause of a live-registry truncation incident: tests run *inside an Aura
seat* inherit ambient path-override env (`AURA_REGISTRY_PATH`,
`AURA_SEAT_ALIASES_PATH`, `AURA_FLEETS_PATH`, …) that point at the real
`~/.aura`. `registry_path()` honors `AURA_REGISTRY_PATH` *over* `AURA_STATE_DIR`,
so a test that only set `AURA_STATE_DIR` still wrote the LIVE registry — and a
test that writes a small fixture dict clobbered it (42 rows -> 4).

This autouse fixture runs for EVERY test: it points all Aura state at a per-test
tmp dir and strips every ambient override (path overrides + seat-identity env
that also leaks into resolution). A test can no longer reach live state by
construction. Individual tests may still set their own `AURA_STATE_DIR`/paths on
top of this clean baseline.
"""
import os

import pytest

# Seat-identity env that leaks into resolution code (the source of the
# "fails-in-seat / passes-clean" flakiness, too).
_IDENTITY_VARS = (
    "AURA_FLEET", "AURA_SEAT", "AURA_RUNTIME", "AURA_RUNTIME_SESSION_ID",
    "AURA_SESSION_ID", "AURA_SEAT_INSTANCE_ID", "AURA_LAUNCH_ID",
    "AURA_LAUNCH_NONCE", "CLAUDECODE", "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT", "CODEX_THREAD_ID",
    "TMUX", "TMUX_PANE",
)


@pytest.fixture(autouse=True)
def _isolate_aura_state(tmp_path, monkeypatch):
    # 1. Strip every AURA_*_PATH override (these point at real ~/.aura and win
    #    over AURA_STATE_DIR). Programmatic so no override can slip through.
    for var in list(os.environ):
        if var.startswith("AURA_") and var.endswith("_PATH"):
            monkeypatch.delenv(var, raising=False)
    # 2. Strip ambient seat identity so resolution can't bind to the live seat.
    for var in _IDENTITY_VARS:
        monkeypatch.delenv(var, raising=False)
    # 3. Point all state at a per-test tmp dir (the clean baseline).
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.delenv("AURA_REGISTRY_ALLOW_SHRINK", raising=False)
    yield
