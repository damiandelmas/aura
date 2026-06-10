Perfect. Now I have enough context. Let me create the comprehensive diff-level implementation spec for M4.

---

# M4 Born-Pane Self-Heal + Reliable Reverse Resolution — Diff-Level Implementation Spec

## Executive Summary

M4 completes the "live %N is identity" doctrine by:
1. **Reliable reverse pane→row resolution** (`pane_ref` lookup without alias fallback; reads AURA_FLEET/AURA_SEAT from pane env)
2. **Born-pane self-heal**: reconstruct thin rows from live %N + nonce + birth env when row is missing and pane is live + Aura-born
3. **Automatic orphan reconciliation**: surface and reconcile orphaned Aura-born panes without registry rows
4. **Fix `inspect tmux:...:%N` registered:false bug** by making reverse lookup authoritative

### Key Principle
**Live pane is sovereign identity; a live Aura-born pane with env AURA_FLEET/AURA_SEAT/AURA_LAUNCH_ID/AURA_SEAT_INSTANCE_ID can self-heal its row even if the row has been deleted or never existed.** This breaks the current hard dependency on pre-existing rows (M1's `resolve_live` requirement).

---

## 1. Core Function Signatures & Edits

### 1.1 `cli/lib/pane_resolver.py`

#### New: `_read_birth_env(pane_pid: int | None) -> dict[str, str]`
**Purpose**: Extract AURA birth env from pane and descendants.

**Current state**: `_pane_env()` reads all env vars; no filtering for birth identifiers.

**New code**:
```python
# After _pane_env() function, around line 57
def _read_birth_env(pane_pid: int | None) -> dict[str, str]:
    """Extract Aura-owned birth environment from pane + descendants.
    
    These env vars must be stable for the pane lifetime:
      - AURA_FLEET: owner fleet
      - AURA_SEAT: canonical seat name
      - AURA_LAUNCH_ID: nonce for birth-time discovery
      - AURA_SEAT_INSTANCE_ID: unique occupant identity
    
    Reads pane env and ancestor envs; parent env wins (first-write).
    """
    birth_keys = ("AURA_FLEET", "AURA_SEAT", "AURA_LAUNCH_ID", "AURA_SEAT_INSTANCE_ID")
    env = _pane_env(pane_pid)
    return {key: value for key, value in env.items() if key in birth_keys}
```

---

#### Change: `_resolve_from_record()` signature (line 178)
**Current**:
```python
def _resolve_from_record(pane_rec: dict[str, Any], matched: dict | None) -> dict[str, Any]:
```

**New**:
```python
def _resolve_from_record(
    pane_rec: dict[str, Any],
    matched: dict | None,
    *,
    repair: bool = False,
) -> dict[str, Any]:
```

**Reason**: `repair=True` is passed from `_bind_pane()` (line 1200-1202) to unblock self-heal of exact-mismatch born panes.

---

#### Change: `_match_registry_row()` (line 131–146) — NO alias fallback in reverse lookup
**Current**:
```python
def _match_registry_row(pane: dict[str, Any]) -> dict | None:
    pane_id = str(pane.get("pane_id") or "")
    session = str(pane.get("tmux_session") or pane.get("physical_fleet") or "")
    if not pane_id:
        return None
    exact = f"tmux:{session}:{pane_id}"
    fallback = None
    for record in registry.read_registry().values():
        ref = str(record.get("pane_ref") or "")
        if not ref:
            continue
        if ref == exact:
            return record
        if ref.endswith(f":{pane_id}"):
            fallback = fallback or record
    return fallback
```

**Issue**: Line 144–145 accepts a fallback ref that ends with `:{pane_id}` but has a *different* session. This is the "inspect tmux:...:%N registered:false bug": a row bound to `tmux:fleet-a:%26` will match a query for pane `tmux:fleet-b:%26`, silently returning the wrong row.

**Fixed code**:
```python
def _match_registry_row(pane: dict[str, Any]) -> dict | None:
    """Match pane to registry row by exact pane_ref only.
    
    Live resolution does NOT follow aliases. This is the authoritative
    reverse pane→row lookup. If no exact pane_ref match exists, return None;
    the caller (resolve_pane or self-heal) must then decide whether to
    reconstruct from birth env or error.
    """
    pane_id = str(pane.get("pane_id") or "")
    session = str(pane.get("tmux_session") or pane.get("physical_fleet") or "")
    if not pane_id:
        return None
    exact = f"tmux:{session}:{pane_id}"
    for record in registry.read_registry().values():
        ref = str(record.get("pane_ref") or "")
        if ref == exact:
            return record
    return None
```

---

#### New: `_resolve_from_birth_env(pane_rec: dict[str, Any], birth_env: dict[str, str]) -> dict[str, Any] | None`
**Purpose**: Reconstruct thin row identity from %N + birth env when row is missing.

**Signature & code** (insert after `_match_registry_row`, around line 147):
```python
def _resolve_from_birth_env(pane_rec: dict[str, Any], birth_env: dict[str, str]) -> dict[str, Any] | None:
    """Reconstruct a thin row from pane + birth env for an orphaned Aura-born pane.
    
    A live Aura-born pane carries:
      - AURA_FLEET: fleet owner (stable)
      - AURA_SEAT: seat name at birth (stable even if renamed later)
      - AURA_LAUNCH_ID: nonce for codex-jsonl session discovery
      - AURA_SEAT_INSTANCE_ID: occupant id (matches si on any rebound row)
    
    Return a thin row (name-only, no pane_ref yet) that can be used to reconcile
    orphaned panes, OR None if birth env is incomplete.
    
    This is NOT a live-status resolver; it only constructs the identity skeleton.
    The caller is responsible for calling _resolve_from_record() and bind_gates()
    to verify and bind.
    """
    if not birth_env:
        return None
    fleet = birth_env.get("AURA_FLEET")
    seat = birth_env.get("AURA_SEAT")
    launch_id = birth_env.get("AURA_LAUNCH_ID")
    si = birth_env.get("AURA_SEAT_INSTANCE_ID")
    if not (fleet and seat and (launch_id or si)):
        return None
    pane_ref = pane_rec.get("pane_ref")
    return {
        "name": seat,
        "seat": seat,
        "fleet": fleet,
        "aura_launch_id": launch_id,
        "seat_instance_id": si,
        "pane_ref": pane_ref,
        "registered": False,
        "status": "born-unhealed",
        # Mark as thin/reconstructed for diagnostics
        "_from_birth_env": True,
    }
```

---

#### Change: `resolve_pane()` (line 249–301)
**Current**: Returns `managed_state: "unmanaged"` if no matched row found.

**Issue**: Does NOT attempt to reconstruct from birth env; born panes without rows appear as "unmanaged".

**New intent**: If `matched` is None but birth env exists + pane is live + caller requests repair, reconstruct from birth env. Requires careful bind_gates flow (keep gates strict; self-heal is responsibility of bind paths).

**Scope of change**: `resolve_pane()` itself stays conservative (returns unmanaged). **Self-heal happens in `_resolve_from_record()` and `bind_gates()` + the bind-pane/heal/bind-hook paths** (see §1.2 below). This keeps resolve_pane read-only and non-invasive.

---

#### Change: `_resolve_from_record()` (line 178–246)
**New signature** (already noted above): add `repair: bool = False` parameter.

**Current code**: lines 189–226 try env, then registry binding, then discover_from_pane_pid.

**New edge case**: If matched is None but birth env has AURA_SEAT_INSTANCE_ID, add a step:
```python
    # 4. Born-pane self-heal: reconstruct from AURA birth env if pane is Aura-born
    if not session_id and repair:
        birth_env = _read_birth_env(pane_pid)
        if birth_env:
            si = birth_env.get("AURA_SEAT_INSTANCE_ID")
            if si:
                # A born pane with a seat_instance_id is eligible for self-heal.
                # Don't resolve session_id here; let bind_gates and the bind path
                # handle the reconstruction. Just mark that we have birth env.
                # The session_id will come from the pane env (step 1) or discovery (step 3)
                # on the next bind attempt after the thin row is created.
                evidence["birth_env"] = {k: v for k, v in birth_env.items() if v}
```

**Rationale**: Don't force session discovery here. If the pane has AURA env but no session_id yet, the bind path will attempt nonce (launch_id) or pane-env on the next heal/bind call. This keeps resolve_pane() read-only.

---

#### Change: `bind_gates()` signature (line 304–386)
**Current**:
```python
def bind_gates(
    res: dict[str, Any],
    *,
    previous: dict | None,
    repair: bool = False,
) -> dict[str, Any]:
```

**New**: SAME SIGNATURE (no change needed here; `repair` already exists).

**New intent**: When `repair=True` and `previous` is None but `res` includes birth_env evidence, skip the "no-target" error and allow reconstruction. This is handled in the bind-pane path (§1.2).

---

### 1.2 `cli/commands/sessions.py`

#### Change: `_bind_pane()` (line 1174–1257)
**Current flow** (lines 1184–1195):
```python
    target = getattr(args, "target", None)
    fleet, seat = _target_fleet_seat(target) if target else (None, None)
    matched = res.get("matched_row") or {}
    fleet = fleet or matched.get("fleet")
    seat = seat or matched.get("seat")
    if not fleet or not seat:
        return {
            "ok": False,
            "error": "no-target",
            "detail": "pane is unmanaged; pass --target fleet:seat to bind",
            "resolved": res,
        }
```

**Issue**: Orphaned born panes have no matched row, so this fails. We need to attempt reconstruction from birth env.

**New logic** (replace lines 1184–1195):
```python
    target = getattr(args, "target", None)
    fleet, seat = _target_fleet_seat(target) if target else (None, None)
    matched = res.get("matched_row") or {}
    fleet = fleet or matched.get("fleet")
    seat = seat or matched.get("seat")
    
    # NEW: Attempt to infer fleet/seat from pane birth env if no matched row and no target
    if not fleet or not seat:
        from lib import pane_resolver as pane_resolver_mod
        pane_pid = res.get("pane_pid")
        birth_env = pane_resolver_mod._read_birth_env(pane_pid)
        if birth_env:
            fleet = fleet or birth_env.get("AURA_FLEET")
            seat = seat or birth_env.get("AURA_SEAT")
    
    if not fleet or not seat:
        return {
            "ok": False,
            "error": "no-target",
            "detail": "pane is unmanaged and not Aura-born (no AURA_FLEET/AURA_SEAT env); pass --target fleet:seat to bind",
            "resolved": res,
        }
```

**Rationale**: If the pane has Aura birth env, use it to infer fleet/seat and continue to bind. The usual bind gates (seat-instance-mismatch, package-env-mismatch, body-gate veto) still apply.

---

#### New section in `_bind_pane()`: Reconstruct born-pane row from birth env before bind_gates
**Insert after target resolution, before `_canonical_bind_target()` call** (around line 1197):

```python
    # NEW: Reconstruct thin row from birth env if pane is Aura-born and row doesn't exist
    from lib import pane_resolver as pane_resolver_mod
    if not matched or not matched.get("seat_ref"):
        pane_pid = res.get("pane_pid")
        birth_env = pane_resolver_mod._read_birth_env(pane_pid)
        if birth_env and not matched:
            # Attempt to reconstruct from birth env
            thin_row = pane_resolver_mod._resolve_from_birth_env(res.get("pane_rec", {}), birth_env)
            if thin_row:
                # Log the birth env for diagnostics
                thin_row["_birth_env_keys"] = list(birth_env.keys())
                # Use thin_row as the "previous" input to bind_gates and _bind_registry_session
                # so occupant-keyed gates (seat_instance_id matching) can verify it.
                matched = thin_row
                # Inject the resolved pane_rec for reference (used in _resolve_from_birth_env)
                matched["_resolved_from_pane"] = res.get("pane_ref")
```

Wait—this is getting tangled. Let me reconsider the flow:

**Clearer approach**: The `previous` argument to bind_gates and _bind_registry_session can be a thin row (name-only). When it is, the gates must be aware. Let me refactor this:

---

#### Revised `_bind_pane()` logic (lines 1174–1257)

Replace the no-target error block and add reconstruction:

```python
def _bind_pane(args) -> dict:
    from lib import pane_resolver, registry

    res = pane_resolver.resolve_pane(
        pane=getattr(args, "pane", None),
        current=bool(getattr(args, "current", False)),
    )
    if not res.get("ok"):
        return res

    target = getattr(args, "target", None)
    fleet, seat = _target_fleet_seat(target) if target else (None, None)
    matched = res.get("matched_row") or {}
    fleet = fleet or matched.get("fleet")
    seat = seat or matched.get("seat")
    
    # NEW: Attempt birth-env reconstruction if no matched row
    birth_env = None
    if not fleet or not seat:
        birth_env = pane_resolver._read_birth_env(res.get("pane_pid"))
        if birth_env:
            fleet = fleet or birth_env.get("AURA_FLEET")
            seat = seat or birth_env.get("AURA_SEAT")
    
    if not fleet or not seat:
        return {
            "ok": False,
            "error": "no-target",
            "detail": "pane is unmanaged and not Aura-born (no AURA_FLEET/AURA_SEAT env); pass --target fleet:seat to bind",
            "resolved": res,
        }

    fleet, seat, previous, alias_chain = _canonical_bind_target(registry, fleet=fleet, seat=seat)
    
    # NEW: If no previous row exists but pane is Aura-born, reconstruct thin row
    if not previous and birth_env:
        previous = {
            "name": seat,
            "seat": seat,
            "fleet": fleet,
            "aura_launch_id": birth_env.get("AURA_LAUNCH_ID"),
            "seat_instance_id": birth_env.get("AURA_SEAT_INSTANCE_ID"),
            "pane_ref": res.get("pane_ref"),
            "registered": False,
            "runtime": res.get("runtime_hint") or "codex",
            "status": "unknown",
            "_thin_from_birth_env": True,
        }

    gate = pane_resolver.bind_gates(
        res,
        previous=previous,
        repair=bool(getattr(args, "repair", False)),
    )
    if not gate.get("ok"):
        return {
            "ok": False,
            "error": gate.get("reason"),
            "detail": gate.get("detail"),
            **{key: value for key, value in gate.items() if key not in {"ok", "reason", "detail"}},
            "resolved": res,
        }

    # Rest of function unchanged (session bind call)
    previous = previous or {
        "name": seat,
        "fleet": fleet,
        "runtime": res.get("runtime_hint") or "codex",
        "registered": True,
        "status": "unknown",
    }
    # ... (rest of _bind_registry_session call at line 1237+)
```

---

#### New function: `_reconcile_orphaned_born_panes()`
**Purpose**: Auto-reconcile orphaned Aura-born panes (those in the live mirror but not in the registry).

**Location**: Insert before `_heal()`, around line 427.

```python
def _reconcile_orphaned_born_panes(
    *,
    fleet_filter: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Find orphaned Aura-born panes in the live mirror and reconcile them.
    
    An orphaned Aura-born pane is one that:
      - Exists in the live tmux mirror (is a live %N)
      - Has AURA_FLEET/AURA_SEAT/AURA_SEAT_INSTANCE_ID birth env
      - Has no matching row in the registry (no pane_ref match, no alias)
    
    Reconciliation: construct a thin row from the pane env, verify with bind_gates,
    and (if --dry-run is False) commit it to the registry.
    
    Returns: { ok, dry_run, results, reconciled_count, skipped_count }
      - results: list of { pane_id, fleet, seat, status, reason, ... }
    """
    from lib import pane_resolver, registry, tmux_mirror
    
    # Fetch the live mirror
    mirror = tmux_mirror.list_physical_panes()
    if not mirror.get("ok"):
        return {
            "ok": False,
            "error": "tmux-mirror-unavailable",
            "detail": mirror.get("error"),
        }
    
    live_panes = mirror.get("panes") or []
    live_registry = registry.read_registry()
    live_refs = {str(row.get("pane_ref")): ref for ref, row in live_registry.items() if row.get("pane_ref")}
    
    results = []
    reconciled_count = 0
    skipped_count = 0
    
    for pane in live_panes:
        pane_ref = pane.get("pane_ref")
        if not pane_ref or str(pane_ref) in live_refs:
            # Pane already has a registry row
            continue
        
        # Check if this is an Aura-born pane
        pane_pid = pane_resolver._pane_pid(pane)
        birth_env = pane_resolver._read_birth_env(pane_pid)
        if not birth_env or not birth_env.get("AURA_SEAT_INSTANCE_ID"):
            # Not Aura-born, skip
            skipped_count += 1
            continue
        
        fleet = birth_env.get("AURA_FLEET")
        seat = birth_env.get("AURA_SEAT")
        if fleet_filter and fleet != fleet_filter:
            skipped_count += 1
            continue
        
        if not (fleet and seat):
            # Incomplete birth env
            results.append({
                "pane_id": pane.get("pane_id"),
                "pane_ref": pane_ref,
                "status": "skipped",
                "reason": "incomplete-birth-env",
                "birth_env_keys": list(birth_env.keys()),
            })
            skipped_count += 1
            continue
        
        # Construct thin row and verify
        thin_row = pane_resolver._resolve_from_birth_env(pane, birth_env)
        if not thin_row:
            results.append({
                "pane_id": pane.get("pane_id"),
                "pane_ref": pane_ref,
                "status": "skipped",
                "reason": "reconstruction-failed",
            })
            skipped_count += 1
            continue
        
        if dry_run:
            results.append({
                "pane_id": pane.get("pane_id"),
                "pane_ref": pane_ref,
                "fleet": fleet,
                "seat": seat,
                "seat_instance_id": thin_row.get("seat_instance_id"),
                "status": "would-reconcile",
                "thin_row": {k: v for k, v in thin_row.items() if not k.startswith("_")},
            })
            reconciled_count += 1
            continue
        
        # Commit thin row to registry
        try:
            updated = registry.upsert_agent(thin_row)
            results.append({
                "pane_id": pane.get("pane_id"),
                "pane_ref": pane_ref,
                "fleet": fleet,
                "seat": seat,
                "seat_instance_id": updated.get("seat_instance_id"),
                "status": "reconciled",
                "seat_ref": updated.get("seat_ref"),
            })
            reconciled_count += 1
        except Exception as exc:
            results.append({
                "pane_id": pane.get("pane_id"),
                "pane_ref": pane_ref,
                "fleet": fleet,
                "seat": seat,
                "status": "failed",
                "reason": "registry-upsert-error",
                "error": str(exc),
            })
            skipped_count += 1
    
    return {
        "ok": True,
        "dry_run": dry_run,
        "fleet_filter": fleet_filter,
        "results": results,
        "reconciled": reconciled_count,
        "skipped": skipped_count,
    }
```

---

#### New function: `_reconcile_orphans(args)`
**Purpose**: Public entry point for the `aura sessions reconcile-orphans` verb.

```python
def _reconcile_orphans(args) -> dict:
    """Reconcile orphaned Aura-born panes.
    
    Selector (exactly one required):
      --fleet NAME  → only this fleet
      --all         → all fleets
    
    Each orphaned live pane is reconciled if it has complete AURA birth env
    and passes initial validation.
    
    `--dry-run` performs zero registry writes.
    """
    fleet_filter = getattr(args, "fleet", None)
    all_fleets = bool(getattr(args, "all", False))
    dry_run = bool(getattr(args, "dry_run", False))
    
    if not (fleet_filter or all_fleets):
        return {
            "ok": False,
            "error": "reconcile-orphans requires --fleet NAME or --all",
        }
    
    return _reconcile_orphaned_born_panes(
        fleet_filter=fleet_filter,
        dry_run=dry_run,
    )
```

And add to the main dispatcher in `run()` (line 15–54):
```python
    if getattr(args, "sessions_action", None) == "reconcile-orphans":
        return _reconcile_orphans(args)
```

---

#### Change: `_heal()` — leverage birth env
**Current flow** (lines 428–675): Attempts nonce first, then pane-resolve fallback.

**Enhancement**: Before both attempts, check if the seat is alive and has birth env. If it does and si matches, skip to pane-resolve (which will now self-heal the row if missing).

Insert after line 522 (after `not-alive` skip):
```python
        # NEW: Check if pane is Aura-born and may be missing its row
        from lib import pane_resolver as pane_resolver_mod
        if status_row.get("terminal") == "alive":
            # Get the pane so we can check for birth env
            pane_pid = status_row.get("pane_pid")
            if pane_pid:
                birth_env = pane_resolver_mod._read_birth_env(pane_pid)
                if birth_env:
                    birth_si = birth_env.get("AURA_SEAT_INSTANCE_ID")
                    registry_si = record.get("seat_instance_id")
                    if birth_si and registry_si and birth_si != registry_si:
                        # Occupant mismatch; likely a replaced pane. Skip this seat.
                        results.append({
                            "seat": seat_target,
                            "status": "skipped",
                            "reason": "occupant-mismatch-born-pane",
                            "birth_si": birth_si,
                            "registry_si": registry_si,
                        })
                        skipped_count += 1
                        continue
```

This prevents healing of a seat whose registry si doesn't match the live pane's birth si (means a different pane has since bound to this name).

---

### 1.3 `cli/lib/seat_status.py`

#### Change: `_terminal_status()` — surface orphaned Aura-born panes
**Current** (lines 82–146): Only inspects registry rows and their pane_refs.

**New intent**: Add a separate result type `"born-unhealed"` for live Aura-born panes that have no registry row.

Actually, seat_status already only renders registry rows. To surface orphaned born panes, add a new function:

#### New function: `list_orphaned_born_panes()`
```python
def list_orphaned_born_panes(
    *,
    fleet_filter: str | None = None,
) -> list[dict[str, Any]]:
    """List live Aura-born panes that have no registry row.
    
    Each entry is { pane_id, pane_ref, fleet, seat, seat_instance_id, aura_launch_id, ... }.
    """
    from lib import pane_resolver, tmux_mirror
    
    mirror = tmux_mirror.list_physical_panes()
    if not mirror.get("ok"):
        return []
    
    live_panes = mirror.get("panes") or []
    registry = read_registry()
    live_refs = {str(row.get("pane_ref")): 1 for row in registry.values() if row.get("pane_ref")}
    
    orphaned = []
    for pane in live_panes:
        pane_ref = pane.get("pane_ref")
        if pane_ref and str(pane_ref) in live_refs:
            continue
        
        pane_pid = pane_resolver._pane_pid(pane)
        birth_env = pane_resolver._read_birth_env(pane_pid)
        if not birth_env or not birth_env.get("AURA_SEAT_INSTANCE_ID"):
            continue
        
        fleet = birth_env.get("AURA_FLEET")
        seat = birth_env.get("AURA_SEAT")
        if fleet_filter and fleet != fleet_filter:
            continue
        
        orphaned.append({
            "pane_id": pane.get("pane_id"),
            "pane_ref": pane_ref,
            "fleet": fleet,
            "seat": seat,
            "seat_instance_id": birth_env.get("AURA_SEAT_INSTANCE_ID"),
            "aura_launch_id": birth_env.get("AURA_LAUNCH_ID"),
            "pane_current_command": pane.get("pane_current_command"),
            "pane_current_path": pane.get("pane_current_path"),
            "tmux_session": pane.get("tmux_session"),
            "window_name": pane.get("window_name"),
        })
    
    return orphaned
```

---

## 2. Edge Cases & Interactions

### 2.1 Thin rows (name-only, no pane_ref)
**Scenario**: A born pane's thin row has `seat_instance_id` but no `pane_ref` initially (at reconcile time).

**Handling**: When the thin row is created by `_resolve_from_birth_env()`, it includes the pane_ref from the live pane. This ensures the row is "thick" enough for reverse lookup.

**bind_gates behavior**: Thin rows pass all occupant-id gates (seat_instance_id match is the primary check). Package-env gates are skipped if the thin row has no agent_package_id (status: "not-package").

---

### 2.2 Mirror unavailable
**Scenario**: `tmux list-panes` fails or is slow.

**Handling**: 
- `resolve_pane()` returns early with error (line 261–262, unchanged).
- `_reconcile_orphaned_born_panes()` returns error if mirror unavailable (new code above).
- `seat_status.list_orphaned_born_panes()` returns empty list if mirror unavailable.

---

### 2.3 Fork children & services
**Scenario**: A spawned codex seat runs `codex fork`; the child Codex process is a new %N but has AURA_SEAT_INSTANCE_ID = parent's si.

**Current behavior**: The child pane's si matches the parent registry row's si → `_same_live_incarnation()` returns True (si match). This is WRONG; they are distinct panes.

**M4 fix**: `_same_live_incarnation()` must require **BOTH** si **AND** exact pane_ref match to return True. But wait—that's part of M3, not M4. For M4, we just ensure born-pane self-heal does NOT accidentally bind a child pane to the parent's row.

**safeguard**: In `bind_gates()`, if `repair=False` and `previous.get("pane_ref")` exists but differs from `res.get("pane_ref")`, refuse (line 374–384, already present). For a born pane with no previous, this check is skipped—correct, because previous is None.

**But for a child pane**: The child has `AURA_SEAT_INSTANCE_ID = parent's si` but its own live pane %N. When bind-pane is called on the child, it will try to reconstruct a thin row with si=parent's si. Then bind_gates will compare si and find a match with the parent row. This **needs M3's fix to rename_preflight to refuse duplicate-same-si repairs**. For M4, document this as a known issue requiring M3.

---

### 2.4 Dead pane reference in registry
**Scenario**: Registry has `pane_ref: "tmux:fleet:%26"` but %26 is dead (no longer in the live mirror).

**M4 behavior**: 
- `resolve_pane(%26)` will not find it in the mirror → returns error "pane-not-found".
- `_match_registry_row()` will not match it (mirror pane doesn't exist, so no query).
- `_reconcile_orphaned_born_panes()` skips it (it's not in the live mirror).
- The dead row stays in the registry (it is a "stale" row, cleaned by `aura seat sweep`, part of observability not M4).

---

### 2.5 Same-occupant continuity (stale refs)
**Scenario**: A seat is renamed from `old-seat` to `new-seat`. The live pane has:
  - pane_ref: `tmux:fleet:%26`
  - AURA_SEAT_INSTANCE_ID: `si_abc` (stable across rename)
  - AURA_SEAT: `new-seat` (updated at birth in new row)

An old queued message or subscription targeting `fleet:old-seat` arrives.

**M4 scope**: Does NOT fix sender canonicalization (that's M2). M4 only ensures the reverse pane→row lookup is reliable (exact pane_ref match, no alias fallback).

**M2 will add**: A separate `resolve_occupant()` function that looks up rows by si/launch_id when the name lookup fails, then follows the lineage to find the current name.

---

### 2.6 Rename collision with born pane
**Scenario**: A spawned seat `"scout"` is renamed to `"scout-2"`. Then a new spawn creates another seat named `"scout"` with a different si. The new pane has AURA_SEAT=`"scout"` and is Aura-born.

When bind-pane is called on the new pane:
1. `resolve_pane()` finds it in the mirror, no matched row (born pane).
2. `_bind_pane()` infers fleet/seat from birth env → `fleet:scout`.
3. `_canonical_bind_target()` looks up `fleet:scout` in the registry → finds the old row (if not yet renamed to scout-2) OR finds nothing (if already renamed).
4. If old row exists and old-si ≠ new-si: `bind_gates()` refuses (seat-instance-mismatch).
5. If old row doesn't exist: thin row is created, bind proceeds.

**M4 guarantee**: The occupant-id gates (si match) prevent accidental rebinding of a stale occupant. M3's duplicate-repair refusal also blocks merging distinct si rows.

---

## 3. Interactions with M1/M2/M3/M5

### M1: split `get_agent()` into `resolve_live()` vs `resolve_historical()`
**M4 dependency**: M4 assumes `_match_registry_row()` returns the exact row **only**, with no alias fallback. This is aligned with M1's resolve_live semantics. M4 **requires** M1's completion (or at minimum, the alias-demoting principle).

**M4 delivery**: Fixes the `_match_registry_row()` function to drop the fallback, making it a true resolve_live operation.

---

### M2: Occupant-keyed continuity
**M4 support**: Thin rows include `seat_instance_id`, making them eligible for occupant-keyed lookup (M2's resolve_occupant function will look them up by si).

**M4 does NOT**: Implement the reverse occupant lookup in reports.py or queued_messages.py (that's M2).

---

### M3: Rename on exact live %N
**M4 preparation**: 
- M4 ensures `_same_live_incarnation()` input (the matched row) is reliable (exact pane_ref match).
- M4 does NOT change `_same_live_incarnation()` itself (M3's responsibility).
- When M3 strengthens `_same_live_incarnation()` to require si AND pane_ref match, M4's born-pane rows will pass (they have both).

---

### M5: Operator surface
**M4 deliverables for M5**:
- New verb `aura sessions reconcile-orphans --fleet NAME / --all` (code provided above).
- New surface in `seat_status.list_orphaned_born_panes()` for `aura seat view --orphans` or equivalent (M5 will wire the CLI).
- Docs: born-pane self-heal contract, AURA_* env requirements, reconcile workflow.

---

## 4. Test Coverage

### Tests to add (in `tests/test_pane_resolver.py` and new `tests/test_born_pane_self_heal.py`)

#### `test_read_birth_env_extracts_aura_keys()`
Verify `_read_birth_env()` filters only AURA_* keys and returns a dict.

#### `test_match_registry_row_exact_only()`
Verify `_match_registry_row()` does NOT accept fallback refs with wrong session.

```python
def test_match_registry_row_exact_only(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, pane_resolver
    
    # Register a row with pane_ref for fleet-a:%26
    registry.upsert_agent({
        "name": "scout",
        "fleet": "fleet-a",
        "runtime": "codex",
        "pane_ref": "tmux:fleet-a:%26",
        "seat_instance_id": "si_a",
    })
    
    # Query with fleet-b:%26 (same pane_id, different session)
    pane = {
        "pane_id": "%26",
        "tmux_session": "fleet-b",
        "physical_fleet": "fleet-b",
    }
    pane["pane_ref"] = f"tmux:fleet-b:%26"
    
    matched = pane_resolver._match_registry_row(pane)
    
    # Must return None (no exact match for fleet-b:%26)
    assert matched is None
```

#### `test_resolve_from_birth_env_reconstructs_thin_row()`
Verify thin row reconstruction from birth env.

```python
def test_resolve_from_birth_env_reconstructs_thin_row(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import pane_resolver
    
    pane = {
        "pane_id": "%9",
        "pane_ref": "tmux:orphan-fleet:%9",
    }
    birth_env = {
        "AURA_FLEET": "orphan-fleet",
        "AURA_SEAT": "orphan-scout",
        "AURA_LAUNCH_ID": "nonce-123",
        "AURA_SEAT_INSTANCE_ID": "si_orphan",
    }
    
    thin = pane_resolver._resolve_from_birth_env(pane, birth_env)
    
    assert thin["fleet"] == "orphan-fleet"
    assert thin["seat"] == "orphan-scout"
    assert thin["seat_instance_id"] == "si_orphan"
    assert thin["aura_launch_id"] == "nonce-123"
    assert thin["pane_ref"] == "tmux:orphan-fleet:%9"
    assert thin["registered"] is False
```

#### `test_resolve_from_birth_env_rejects_incomplete_env()`
Verify thin row fails if AURA_SEAT_INSTANCE_ID is missing.

#### `test_bind_pane_self_heals_born_pane()`
Verify that bind-pane reconstructs and binds a born pane.

```python
def test_bind_pane_self_heals_born_pane(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, runtime_session
    from commands import sessions
    
    # No pre-existing row
    assert registry.get_agent("scout", fleet="orphan") is None
    
    # Pane exists with Aura birth env
    pane = {
        "pane_id": "%99",
        "pane_ref": "tmux:orphan:%99",
        "tmux_session": "orphan",
        "window_name": "work",
        "pane_current_command": "codex",
    }
    birth_env = {
        "AURA_FLEET": "orphan",
        "AURA_SEAT": "scout",
        "AURA_LAUNCH_ID": "nonce-xyz",
        "AURA_SEAT_INSTANCE_ID": "si_new",
        "AURA_RUNTIME_SESSION_ID": "sid-born",
    }
    
    # Mock mirror and pane env
    def mock_mirror(**kw):
        return {"ok": True, "panes": [pane]}
    
    def mock_pane_env(pid):
        return dict(birth_env)
    
    monkeypatch.setattr("lib.tmux_mirror.list_physical_panes", mock_mirror)
    monkeypatch.setattr("lib.pane_resolver._pane_env", mock_pane_env)
    
    # Bind the pane
    result = sessions._bind_pane(
        type("Args", (), {
            "pane": "%99",
            "current": False,
            "target": None,
            "repair": False,
        })()
    )
    
    assert result["ok"] is True
    assert result["runtime_session_id"] == "sid-born"
    
    # Verify row was created
    row = registry.get_agent("scout", fleet="orphan")
    assert row is not None
    assert row["seat_instance_id"] == "si_new"
    assert row["pane_ref"] == "tmux:orphan:%99"
```

#### `test_bind_gates_accepts_thin_row_with_matching_si()`
Verify bind_gates allows thin rows with matching seat_instance_id.

#### `test_reconcile_orphaned_born_panes_finds_and_reconciles()`
Verify the orphan reconciliation function finds and updates the registry.

#### `test_bind_hook_preserves_thin_row_fields()`
Verify bind-hook doesn't lose birth env data when binding a reconstructed thin row.

---

## 5. Migration & Rollout

### Registry/Alias Data
**No migration needed**. Thin rows created by M4 are regular rows with `registered: false` initially. Once bound via `_bind_registry_session()`, they become normal rows.

**Alias data**: Unchanged. M4 does NOT modify alias handling (M1's responsibility).

**Existing rows**: No change. The fix to `_match_registry_row()` (drop fallback) improves reliability but does not invalidate existing rows.

---

## 6. Testing & Verification Checklist

- [ ] `_match_registry_row()` does NOT match panes to wrong-session fallback refs (fixes inspect bug)
- [ ] `_read_birth_env()` correctly extracts only AURA_* vars
- [ ] `_resolve_from_birth_env()` reconstructs thin rows with all required fields
- [ ] `_bind_pane()` self-heals a born pane by inferring fleet/seat from birth env
- [ ] `bind_gates()` accepts thin rows with matching seat_instance_id
- [ ] `_reconcile_orphaned_born_panes()` finds orphaned panes and reconciles them (with --dry-run)
- [ ] Born panes with mismatched si are rejected (occupant conflict)
- [ ] Dead panes in the mirror are skipped (not reconciled)
- [ ] Package-env gates still apply to thin rows (if agent_package_id is present)
- [ ] Rename collision: new seat with same name but different si is rejected until old si is orphaned
- [ ] `seat_status.list_orphaned_born_panes()` surfaces orphaned panes for observability
- [ ] `aura sessions reconcile-orphans --all` verb is wired and works

---

## 7. Summary of Changes by File

| File | Change Type | What |
|------|------------|------|
| `cli/lib/pane_resolver.py` | New function | `_read_birth_env()` |
| `cli/lib/pane_resolver.py` | New function | `_resolve_from_birth_env()` |
| `cli/lib/pane_resolver.py` | Modified function | `_match_registry_row()` — drop fallback |
| `cli/lib/pane_resolver.py` | Modified function | `_resolve_from_record()` — add repair param |
| `cli/commands/sessions.py` | Modified function | `_bind_pane()` — reconstruct from birth env |
| `cli/commands/sessions.py` | New function | `_reconcile_orphaned_born_panes()` |
| `cli/commands/sessions.py` | New function | `_reconcile_orphans()` |
| `cli/commands/sessions.py` | Modified function | `run()` — add reconcile-orphans dispatch |
| `cli/lib/seat_status.py` | New function | `list_orphaned_born_panes()` |
| Tests | New suite | `test_born_pane_self_heal.py` (6+ tests) |

---

## 8. Concrete Signature Reference

```python
# pane_resolver.py

def _read_birth_env(pane_pid: int | None) -> dict[str, str]:
    """Extract AURA_FLEET, AURA_SEAT, AURA_LAUNCH_ID, AURA_SEAT_INSTANCE_ID."""

def _match_registry_row(pane: dict[str, Any]) -> dict | None:
    """Match by exact pane_ref only; NO alias fallback."""

def _resolve_from_birth_env(
    pane_rec: dict[str, Any],
    birth_env: dict[str, str],
) -> dict[str, Any] | None:
    """Reconstruct thin row from %N + birth env."""

def _resolve_from_record(
    pane_rec: dict[str, Any],
    matched: dict | None,
    *,
    repair: bool = False,
) -> dict[str, Any]:
    """(unchanged interface; repair param added)"""
```

```python
# sessions.py

def _bind_pane(args) -> dict:
    """(modified to handle born-pane self-heal)"""

def _reconcile_orphaned_born_panes(
    *,
    fleet_filter: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Find orphaned Aura-born panes and reconcile them."""

def _reconcile_orphans(args) -> dict:
    """Public verb for aura sessions reconcile-orphans."""
```

```python
# seat_status.py

def list_orphaned_born_panes(
    *,
    fleet_filter: str | None = None,
) -> list[dict[str, Any]]:
    """List live Aura-born panes without registry rows."""
```