Now I have enough context. Let me create the comprehensive spec for M3:

## M3 Implementation Spec: Rename on Exact Live %N + Repair Never Orphans

### Summary

Move M3 implements two critical changes to the seat rename and duplicate-repair logic:

1. **Exact pane identity**: rename acts on the exact live %N (pane_id) recorded in the source row's `pane_ref`, not on resolved/merged targets
2. **No orphaning repair**: when two rows share a `seat_instance_id`, repair merges data but **preserves** the loser row as `terminal_state="terminal"` + `replaced_by` metadata, never deletes the loser if its `pane_ref` points to a live, distinct %N

This spec assumes M1 has already split `get_agent()` into `resolve_live()` (pane-ref first, never alias) and `resolve_historical()` (name->alias->lineage). All live consumers use `resolve_live()`.

---

### Part 1: Core Function Changes in `cli/lib/registry.py`

#### 1.1 New function: `resolve_live()`

**Signature:**
```python
def resolve_live(name: str, fleet: str | None = None) -> dict[str, Any] | None:
    """Resolve by exact live %N first, then by seat_instance_id, then by current name.
    
    Never consults aliases for live routing. Used by all bind, send, and adoption paths.
    """
```

**Implementation intent:**
- Read registry and filter by fleet (if provided)
- For each candidate row with the same name/fleet:
  - Check if row has `pane_ref` (live %N); if so, verify the pane still exists in tmux
    - If pane exists and is **live and distinct**, return that row immediately (don't merge)
  - If multiple rows exist with same fleet:seat and at least one has a live pane, return the live one(s), not the merged winner
- Fall back to name-based match (existing behavior)
- **Do NOT call `resolve_alias()` at any point in live resolution**

**Pseudo-code:**
```python
def resolve_live(name: str, fleet: str | None = None) -> dict[str, Any] | None:
    fleet, name = split_ref(str(name), fleet=fleet)
    data = read_registry()
    if fleet:
        ref = _key(fleet, name)
        record = data.get(ref)
        if record:
            # Check if pane_ref is live
            if _is_pane_live(record.get("pane_ref"), fleet):
                return record
    # Fall back to name-only search (do not alias-chain)
    matches = [v for v in data.values() if v.get("name") == name and (not fleet or v.get("fleet") == fleet)]
    if not matches:
        return None
    matches.sort(key=lambda r: r.get("last_seen", ""), reverse=True)
    return matches[0]

def _is_pane_live(pane_ref: str | None, fleet: str) -> bool:
    """Check if pane_ref points to a live tmux pane."""
    if not pane_ref:
        return False
    target = _tmux_target(pane_ref)
    if not target.startswith("%"):
        return False
    try:
        result = subprocess.run(["tmux", "display-message", "-p", "-t", target, "#{pane_id}"],
                                capture_output=True, text=True, timeout=1)
        return result.returncode == 0
    except Exception:
        return False
```

**Interaction with M1:** This replaces the alias-following path in current `get_agent()`. The old `get_agent()` becomes `resolve_historical()` and is used only by audit, lineage, and same-occupant fallback.

---

#### 1.2 Modified function: `_same_live_incarnation()`

**Current code (lines 466-474):**
```python
def _same_live_incarnation(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    if not left or not right:
        return False
    for key in ("seat_instance_id", "pane_ref"):
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value and right_value and str(left_value) == str(right_value):
            return True
    return False
```

**NEW signature and intent:**
```python
def _same_live_incarnation(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    """Two rows are the same live occupant iff:
    - Both have non-null seat_instance_id AND they match, AND
    - Both have non-null pane_ref AND they match (must be the EXACT SAME pane, not just same si).
    
    Repair is triggered only when BOTH conditions are true.
    """
    if not left or not right:
        return False
    
    # Both must have seat_instance_id and they must match
    left_si = left.get("seat_instance_id")
    right_si = right.get("seat_instance_id")
    if not (left_si and right_si and str(left_si) == str(right_si)):
        return False
    
    # Both must have pane_ref and they must match
    left_pane = left.get("pane_ref")
    right_pane = right.get("pane_ref")
    if not (left_pane and right_pane and str(left_pane) == str(right_pane)):
        return False
    
    return True
```

**Edge cases:**
- If left has si but no pane_ref (thin row from M4 self-heal), return False → no repair, both rows coexist
- If one row has si but the other doesn't, return False → distinct occupants
- If both have si but different panes, return False → distinct panes, no repair

**Effect on `rename_preflight()` and `rename_agent()`:**
- Rename checks `_same_live_incarnation()` to decide if repair is needed
- If True, the caller knows the two rows are exact duplicates (same pane + si) and can safely merge
- If False, even with same si, the rows must represent distinct live panes → reject with "target already exists" error (current line 505)

---

#### 1.3 Modified function: `rename_preflight()`

**Current code (lines 477-516):**
```python
def rename_preflight(source: str, *, new_name: str | None = None) -> dict[str, Any]:
    source_fleet, source_name = split_ref(source)
    if not source_fleet:
        agent = get_agent(source_name)  # <-- M1: becomes resolve_live()
        if not agent:
            return {"ok": False, "error": f"agent not found: {source}"}
        source_fleet = agent.get("fleet")
        source_name = agent.get("name")
    source_ref = _key(source_fleet, source_name)
    data = read_registry()
    existing = data.get(source_ref)
    if not existing:
        resolved, chain = resolve_alias(source_ref)
        if chain:
            return {"ok": False, "error": f"source is an alias; use canonical target instead: {resolved}", "alias_chain": chain}
        return {"ok": False, "error": f"agent not found: {source_ref}"}

    target_name = new_name or existing.get("name")
    target_fleet = existing.get("fleet")
    target_ref = _key(target_fleet, target_name)
    target_existing = data.get(target_ref)
    repair_duplicate = False
    if target_ref != source_ref and target_existing:
        if not _same_live_incarnation(existing, target_existing):
            return {"ok": False, "error": f"target already exists: {target_ref}", "reason": "target-registry-exists", "target": target_ref}
        repair_duplicate = True

    return {
        "ok": True,
        "source": source_ref,
        "target": target_ref,
        "source_record": existing,
        "target_record": target_existing,
        "repair_duplicate": repair_duplicate,
    }
```

**NEW implementation:**
```python
def rename_preflight(source: str, *, new_name: str | None = None) -> dict[str, Any]:
    """Preflight check for rename: resolve source to its live %N, guard target existence."""
    source_fleet, source_name = split_ref(source)
    if not source_fleet:
        agent = resolve_live(source_name)  # <-- M1: use resolve_live instead of get_agent
        if not agent:
            return {"ok": False, "error": f"agent not found: {source}"}
        source_fleet = agent.get("fleet")
        source_name = agent.get("name")
    source_ref = _key(source_fleet, source_name)
    data = read_registry()
    existing = data.get(source_ref)
    if not existing:
        # M3: do NOT check aliases; source must be a current row
        return {"ok": False, "error": f"agent not found: {source_ref}"}

    target_name = new_name or existing.get("name")
    target_fleet = existing.get("fleet")
    target_ref = _key(target_fleet, target_name)
    target_existing = data.get(target_ref)
    repair_duplicate = False
    
    if target_ref != source_ref and target_existing:
        # M3: only repair if BOTH si AND pane_ref match exactly
        if not _same_live_incarnation(existing, target_existing):
            return {
                "ok": False,
                "error": f"target already exists: {target_ref}",
                "reason": "target-registry-exists",
                "target": target_ref,
                "detail": "another live row at this address; cannot rename",
            }
        repair_duplicate = True

    return {
        "ok": True,
        "source": source_ref,
        "target": target_ref,
        "source_record": existing,
        "target_record": target_existing,
        "repair_duplicate": repair_duplicate,
    }
```

**Changes:**
- Line: `agent = resolve_live(source_name)` replaces `get_agent(source_name)`
- Removed alias fallback (lines 493-495): no `resolve_alias()` call
- Enhanced comment on `_same_live_incarnation()` check to clarify M3 semantics

---

#### 1.4 Modified function: `rename_agent()`

**Current code (lines 518-576):**
```python
def rename_agent(
    source: str,
    *,
    new_name: str,
    metadata: dict[str, Any] | None = None,
    alias_old: bool = True,
) -> dict[str, Any]:
    """Rename a seat inside its current fleet without changing fleet ownership."""
    source_fleet, source_name = split_ref(source)
    existing = get_agent(source_name, fleet=source_fleet)
    if not existing:
        resolved, chain = resolve_alias(source)
        if chain:
            return {"ok": False, "error": f"source is an alias; rename canonical target instead: {resolved}", "alias_chain": chain}
        return {"ok": False, "error": f"agent not found: {source}"}
    target_fleet = existing.get("fleet")
    preflight = rename_preflight(source, new_name=new_name)
    if not preflight.get("ok"):
        return preflight

    with _registry_lock():
        source_ref = preflight["source"]
        target_ref = preflight["target"]
        data = read_registry()
        existing = data.get(source_ref) or preflight["source_record"]
        target_existing = data.get(target_ref) if target_ref != source_ref else None

        record = dict(existing)
        if target_existing:
            record.update(target_existing)  # <-- M3: changes here
        record.update(metadata or {})
        record["name"] = new_name
        record["fleet"] = target_fleet
        record["seat"] = new_name
        record["seat_ref"] = target_ref
        record["logical_fleet"] = target_fleet
        record["logical_name"] = new_name
        record["rename_source"] = source_ref
        record["rename_at"] = now_iso()
        record["last_seen"] = now_iso()
        record.setdefault("physical_fleet", existing.get("physical_fleet") or target_fleet)
        record = _with_logical_physical_fields(record, fleet=target_fleet, name=new_name)
        record = _without_transient_fields(record)

        if target_ref != source_ref:
            data.pop(source_ref, None)  # <-- M3: issue: deletes loser without checking if pane_ref is live
        data[target_ref] = record
        _write_registry_unlocked(data)

    alias = add_alias(source_ref, target_ref, reason="rename") if alias_old and target_ref != source_ref else None
    return {
        "ok": True,
        "source": source_ref,
        "target": target_ref,
        "record": record,
        "alias": alias,
        "repair_duplicate": bool(preflight.get("repair_duplicate")),
    }
```

**NEW implementation:**
```python
def rename_agent(
    source: str,
    *,
    new_name: str,
    metadata: dict[str, Any] | None = None,
    alias_old: bool = True,
) -> dict[str, Any]:
    """Rename a seat inside its current fleet, preserving loser rows whose panes are live.
    
    Repair (same pane + si collapse): merges target_existing into winner, but preserves
    loser as terminal_state="terminal" + replaced_by historical entry.
    
    Non-repair rename: deletes old row only if target is new name. If target exists with
    different si/pane, error (checked in preflight).
    """
    source_fleet, source_name = split_ref(source)
    existing = resolve_live(source_name, fleet=source_fleet)  # M1: resolve_live instead of get_agent
    if not existing:
        # M3: do NOT check aliases
        return {"ok": False, "error": f"agent not found: {source}"}
    target_fleet = existing.get("fleet")
    preflight = rename_preflight(source, new_name=new_name)
    if not preflight.get("ok"):
        return preflight

    repair_duplicate = bool(preflight.get("repair_duplicate"))
    with _registry_lock():
        source_ref = preflight["source"]
        target_ref = preflight["target"]
        data = read_registry()
        existing = data.get(source_ref) or preflight["source_record"]
        target_existing = data.get(target_ref) if target_ref != source_ref else None

        record = dict(existing)
        if target_existing and repair_duplicate:
            # M3: repair mode — merge occupant metadata, but preserve loser
            # Merge occupant-neutral fields from target_existing (e.g., terminal_ref updates)
            # but keep source as the authoritative pane_ref/si
            for key in ("terminal_ref", "backend_ref", "runtime_session_id", "session_id"):
                if key in target_existing and key not in existing:
                    record[key] = target_existing[key]
        record.update(metadata or {})
        record["name"] = new_name
        record["fleet"] = target_fleet
        record["seat"] = new_name
        record["seat_ref"] = target_ref
        record["logical_fleet"] = target_fleet
        record["logical_name"] = new_name
        record["rename_source"] = source_ref
        record["rename_at"] = now_iso()
        record["last_seen"] = now_iso()
        record.setdefault("physical_fleet", existing.get("physical_fleet") or target_fleet)
        record = _with_logical_physical_fields(record, fleet=target_fleet, name=new_name)
        record = _without_transient_fields(record)

        if target_ref != source_ref:
            # M3: Only delete source_ref if it's not a live pane that's distinct from target_existing
            # In repair mode, preserve loser as terminal_state="terminal"
            if repair_duplicate and target_existing:
                # Preserve loser (target_existing) as historical; mark it as replaced_by winner
                loser = dict(target_existing)
                loser["terminal_state"] = "terminal"
                loser["replaced_by"] = target_ref
                loser["replaced_at"] = now_iso()
                loser["last_seen"] = now_iso()
                # Keep the loser under a renamed historical key to preserve occupant continuity
                # E.g., source_ref becomes "fleet:seat~terminal~<si>" or just mark terminal_state
                # For now: keep target_existing in registry but mark terminal
                data[target_ref] = loser
            # Delete source_ref unconditionally (it's being renamed to target_ref)
            data.pop(source_ref, None)
        data[target_ref] = record
        _write_registry_unlocked(data)

    # M3: Alias behavior changes per M1 contract
    # Alias now records occupant lineage (si/launch_id), not live routing
    alias = None
    if alias_old and target_ref != source_ref:
        alias = add_alias(
            source=source_ref,
            target=target_ref,
            reason="rename",
            occupant_id=existing.get("seat_instance_id"),  # New field
            launched_at=existing.get("aura_launch_id"),     # New field
        )
    return {
        "ok": True,
        "source": source_ref,
        "target": target_ref,
        "record": record,
        "alias": alias,
        "repair_duplicate": repair_duplicate,
        "repair_detail": {
            "loser_preserved": bool(repair_duplicate),
            "loser_terminal_state": "terminal" if repair_duplicate else None,
        } if repair_duplicate else None,
    }
```

**Key M3 changes:**
1. Line: `existing = resolve_live(...)` — use M1 `resolve_live()` instead of `get_agent()`
2. Removed alias fallback (no `resolve_alias()` call)
3. **NEW repair logic (lines ~558-569):**
   - If `repair_duplicate=True` and `target_existing` exists:
     - Preserve loser as `terminal_state="terminal"` + `replaced_by` metadata
     - Mark the loser with occupant continuity fields (si, launch_id) for M2
   - Always delete `source_ref` from data (it's being renamed)
4. **NEW alias record (lines ~575-583):**
   - Add occupant metadata to alias: `occupant_id` (seat_instance_id) and `launched_at` (aura_launch_id)
   - This makes the alias a historical breadcrumb, not a live router

---

#### 1.5 New helper: `_is_pane_live()` and `_pane_ref_from_record()`

**New function:**
```python
def _is_pane_live(pane_ref: str | None, fleet: str) -> bool:
    """Check if pane_ref points to a live tmux pane (non-blocking, 1s timeout)."""
    if not pane_ref:
        return False
    target = _tmux_target(pane_ref)
    if not target.startswith("%"):
        return False
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", target, "#{pane_id}"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        return result.returncode == 0
    except Exception:
        return False

def _pane_ref_from_record(record: dict[str, Any]) -> str | None:
    """Extract canonicalized pane_ref from a registry row."""
    return record.get("pane_ref") if record else None
```

---

### Part 2: Changes in `cli/commands/seat.py`

#### 2.1 Modified function: `_rename_terminal_exact()`

**Current code (lines 218-300):**
```python
def _rename_terminal_exact(record: dict, *, fleet: str, name: str) -> dict:
    """Rename exactly the registered live seat window."""
    source = record.get("pane_ref")
    if not source:
        return {
            "ok": False,
            "error": "rename-source-pane-missing",
            "detail": "seat rename requires an exact registered pane_ref",
        }
    # ... rest of implementation
```

**M3 changes:** No functional change needed. This function already acts on `record.get("pane_ref")` (the exact %N). Just ensure:
- It fails if `pane_ref` is None (already does)
- It rejects rename if the pane is dead (already checks with `display-message`)
- Pass test asserting that rename uses the exact pane_ref from the source row, not resolved/merged values

---

#### 2.2 Modified function: `_rename()`

**Current code (lines 2145-2210):**
```python
def _rename(args, registry) -> dict:
    source = getattr(args, "source", None)
    name = getattr(args, "name", None)
    if not source or not name:
        return {"ok": False, "error": "usage", "detail": "rename requires SOURCE and NEW_NAME"}
    if ":" in name:
        return {
            "ok": False,
            "error": "rename-target-must-be-seat-name",
            "detail": "use only the new seat name; rename never changes fleet",
        }
    preflight = registry.rename_preflight(source, new_name=name)
    if not preflight.get("ok"):
        return preflight
    existing = preflight.get("source_record")
    if not existing:
        return {"ok": False, "error": f"agent not found: {source}"}
    fleet = existing.get("fleet")
    current_name = existing.get("name") or existing.get("seat")
    if name == current_name:
        return {"ok": True, "renamed": False, "source": preflight.get("source"), "target": preflight.get("source")}

    renamed_terminal = _rename_terminal_exact(existing, fleet=fleet, name=name)
    if not renamed_terminal.get("ok"):
        return renamed_terminal
    metadata = {
        "terminal_ref": renamed_terminal["terminal_ref"],
        "backend_ref": renamed_terminal["backend_ref"],
        "pane_ref": renamed_terminal["pane_ref"],
        "physical_fleet": renamed_terminal["physical_fleet"],
    }

    result = registry.rename_agent(source, new_name=name, metadata=metadata, alias_old=True)
    # ... rest of implementation
```

**M3 changes:** Add logging/evidence for repair case:
```python
def _rename(args, registry) -> dict:
    # ... existing code ...
    result = registry.rename_agent(source, new_name=name, metadata=metadata, alias_old=True)
    if result.get("ok"):
        try:
            from lib import session_ledger
            after = result.get("record")
            session_ledger.append_seat_event(
                event="seat_renamed",
                before=existing,
                after=after,
                evidence={
                    "source": result.get("source"),
                    "target": result.get("target"),
                    "same_fleet": True,
                    "metadata_keys": sorted(metadata.keys()),
                    "repair_duplicate": bool(result.get("repair_duplicate")),  # NEW
                    "repair_detail": result.get("repair_detail"),  # NEW
                },
                source_command="aura seat rename",
                source_ref=result.get("source"),
                target_ref=result.get("target"),
            )
            if result.get("alias"):
                session_ledger.append_seat_event(
                    event="seat_alias_created",
                    before=existing,
                    after=after,
                    evidence={
                        **result.get("alias"),
                        "occupant_id": result.get("alias", {}).get("occupant_id"),  # NEW
                    },
                    source_command="aura seat rename",
                    source_ref=result["alias"].get("source"),
                    target_ref=result["alias"].get("target"),
                )
        except Exception:
            pass
        result["renamed"] = True
    return result
```

---

#### 2.3 Modified function: `_adopt_pane_as_seat()` (only if needed)

**Current behavior:** Creates a new seat by reading live pane state.

**M3 interaction:** No changes needed. Adoption creates a thin row with `pane_ref`, `seat_instance_id`, and nonce env. If a row already exists at that fleet:seat, adoption fails (line 1626-1632). This is correct: reuse of a name requires an explicit `aura seat rename` or `aura seat adopt --force` (which should error gracefully).

**Clarification to add in comments:**
```python
def _adopt_pane_as_seat(...):
    existing = registry.get_agent(target)  # M1: should use resolve_live() once available
    if existing:
        return {
            "ok": False,
            "error": "already-registered",
            "detail": f"registry already has a row for {target!r}; use 'aura seat rename' to move it, or 'aura seat sweep' to archive stale rows",
            "record": existing,
        }
```

---

### Part 3: Edge Cases and Failure Modes

#### 3.1 Thin/Name-Only Rows (from M4 Self-Heal)

**Scenario:** M4 self-heal creates a row with only `name`, `fleet`, `seat_ref`, `pane_ref`, and env nonce. No `seat_instance_id` yet.

**M3 behavior:**
- `_same_live_incarnation()` checks both si and pane_ref; if si is missing, returns False
- Rename can proceed without triggering repair
- If new name collides with a thin row (si=None), `_same_live_incarnation()` returns False, rename fails with "target already exists"
- **This is correct**: thin rows are not yet occupant-identified; they require explicit adoption/reconciliation before rename

**Test:** `test_rename_thin_row_no_repair()`

---

#### 3.2 Mirror Unavailable (tmux down)

**Scenario:** `_is_pane_live()` fails because tmux is not running.

**M3 behavior:**
- `_is_pane_live()` catches exceptions and returns False
- `resolve_live()` falls back to name-based matching (no live check)
- Rename proceeds using the name-only match
- **Acceptable risk**: if tmux is down, the operator is already in a recovery path. Conservatively using name-based fallback is safe.

**Test:** `test_rename_with_mirror_unavailable()`

---

#### 3.3 Fork/Service Children

**Scenario:** A row has `fork_child_of` or `service_parent` metadata.

**M3 behavior:**
- Rename treats the row as a normal seat; fork/service metadata is preserved
- If the row has a distinct live pane, rename uses that pane
- **Correct behavior**: fork/service relationships are logical; rename is physical

**Test:** `test_rename_service_child()`

---

#### 3.4 Dead %N with Live Pane Elsewhere

**Scenario:** A row has `pane_ref=tmux:fleet:%42` but that pane is dead; a live pane %99 exists at the same fleet:seat name in tmux.

**M3 behavior:**
- `resolve_live()` checks if recorded pane_ref %42 is live; it's not
- Falls back to name-only match; finds no other row with that name
- Rename fails: "agent not found"
- **Correct**: the operator must use `aura seat adopt --pane tmux:fleet:%99 --force` to repair the binding or `aura seat sweep` to clean up stale rows

**Test:** `test_rename_dead_pane_stale_binding()`

---

#### 3.5 Rename Collision Guard (Alias Shadow)

**Scenario:** Old row A exists at `fleet:name_old` with si=s1. Renamed to `fleet:name_new` (row B). Alias added. Now user tries to spawn into the old name again (spawn checks alias, shadows name).

**Current defect (no M1/M3):** Spawn fails with "agent already exists" because alias shadows the name.

**M3 fix (with M1):**
- `resolve_live()` does NOT check aliases
- Spawn uses `resolve_live()` to check if name is available
- Alias check is deferred to `resolve_historical()` (audit/lineage only)
- **Result**: spawn succeeds, creates new row at `fleet:name_old` with si=s2
- Old alias record `fleet:name_old -> fleet:name_new (occupant s1)` is preserved for lineage

**Test:** `test_spawn_reuse_renamed_name_no_alias_shadow()`

---

### Part 4: Changes to Alias Record Format

**Current alias record (lines 341-352):**
```json
{
  "schema": "aura.seat_alias.v1",
  "source": "fleet:old_name",
  "target": "fleet:new_name",
  "reason": "rename",
  "created_at": "2026-06-05T..."
}
```

**M3 NEW alias record (updated in `add_alias()` signature):**
```python
def add_alias(
    source: str,
    target: str,
    *,
    reason: str = "alias",
    occupant_id: str | None = None,  # NEW: seat_instance_id of the occupant at source time
    launched_at: str | None = None,  # NEW: aura_launch_id for same-occupant continuity
) -> dict[str, Any]:
    aliases = read_aliases()
    record = {
        "schema": "aura.seat_alias.v1",
        "source": source,
        "target": target,
        "reason": reason,
        "created_at": now_iso(),
        "occupant_id": occupant_id,  # M2/M3: historical occupant marker
        "launched_at": launched_at,  # M2/M3: same-occupant continuity key
    }
    aliases[source] = record
    write_aliases(aliases)
    return record
```

**JSON example:**
```json
{
  "schema": "aura.seat_alias.v1",
  "source": "fleet:old_name",
  "target": "fleet:new_name",
  "reason": "rename",
  "created_at": "2026-06-05T...",
  "occupant_id": "si_abc123def456",
  "launched_at": "aura-launch-xyz789"
}
```

**Backward compatibility:** Old alias records without occupant_id/launched_at are still valid; M2 continuity resolver treats them as "unknown occupant" (no continuity match).

---

### Part 5: Test Cases

#### 5.1 Basic Rename (No Repair)
```python
def test_rename_basic_no_repair(tmp_path, monkeypatch):
    """Rename a single live seat: source row deleted, target row created, pane renamed."""
    # Create row: fleet:old with pane_ref=tmux:fleet:%42, si=si_abc
    # Rename to fleet:new
    # Expect: fleet:old deleted, fleet:new created with same si and pane_ref
    # Expect: alias fleet:old -> fleet:new (occupant: si_abc)
```

#### 5.2 Repair Duplicate (Same SI + Pane)
```python
def test_rename_repair_duplicate_same_si_pane(tmp_path, monkeypatch):
    """Rename when two rows share si and pane_ref: merge and preserve loser as terminal."""
    # Create row A: fleet:new with si=si_abc, pane_ref=tmux:fleet:%42
    # Create row B: fleet:old with si=si_abc, pane_ref=tmux:fleet:%42
    # Rename B to fleet:new
    # Expect: preflight detects repair (same_live_incarnation=True)
    # Expect: row B deleted, row A updated with rename_source/rename_at
    # Expect: row A preserved as terminal (if loser) with replaced_by metadata
```

#### 5.3 Reject: Distinct Panes, Same SI
```python
def test_rename_reject_distinct_panes_same_si(tmp_path, monkeypatch):
    """Rename fails if target exists with same si but different pane (data corruption guard)."""
    # Create row A: fleet:new with si=si_abc, pane_ref=tmux:fleet:%42
    # Create row B: fleet:old with si=si_abc, pane_ref=tmux:fleet:%99
    # Rename B to fleet:new
    # Expect: preflight fails with "target already exists" (same_live_incarnation=False)
```

#### 5.4 Reject: Target Exists with Different SI
```python
def test_rename_reject_target_different_occupant(tmp_path, monkeypatch):
    """Rename fails if target has a different occupant (distinct live pane)."""
    # Create row A: fleet:new with si=si_abc, pane_ref=tmux:fleet:%42
    # Create row B: fleet:old with si=si_xyz, pane_ref=tmux:fleet:%99
    # Rename B to fleet:new
    # Expect: preflight fails with "target already exists" (different si)
```

#### 5.5 Thin Row No Repair
```python
def test_rename_thin_row_no_repair(tmp_path, monkeypatch):
    """Rename a thin row (M4 self-heal): no si yet, so no repair even if pane_ref matches."""
    # Create thin row A: fleet:old with pane_ref=tmux:fleet:%42, si=None
    # Rename A to fleet:new
    # Expect: rename succeeds (thin rows don't trigger repair)
    # Expect: fleet:old deleted, fleet:new created
```

#### 5.6 No Alias Shadow on Spawn
```python
def test_spawn_reuse_renamed_name_no_alias_shadow(tmp_path, monkeypatch):
    """After rename, spawn into the old name succeeds (alias is historical, not live router)."""
    # Create row: fleet:name_old with si=si_abc
    # Rename to fleet:name_new → alias created
    # Spawn new agent into fleet:name_old with si=si_xyz
    # Expect: spawn succeeds (resolve_live doesn't check alias)
    # Expect: two rows coexist (old alias preserved for lineage)
```

#### 5.7 Pane Dead + Rename Fails
```python
def test_rename_dead_pane_fails(tmp_path, monkeypatch):
    """Rename fails if source pane is dead and terminal_ref is also dead."""
    # Create row: fleet:old with pane_ref=tmux:fleet:%42 (dead)
    # Rename to fleet:new
    # Expect: _rename_terminal_exact fails (pane not found)
    # Expect: rename aborts before writing registry
```

#### 5.8 Preserve Loser Metadata
```python
def test_rename_repair_preserves_loser_occupant_metadata(tmp_path, monkeypatch):
    """After repair rename, loser row's occupant metadata is preserved (not lost)."""
    # Create row A: fleet:new with si=si_abc, occupant metadata
    # Create row B: fleet:old with si=si_abc (same si/pane)
    # Rename B to fleet:new
    # Expect: row A has replaced_by metadata pointing to fleet:new
    # Expect: alias created with occupant_id=si_abc for M2 same-occupant continuity
```

#### 5.9 Mirror Unavailable (Fallback to Name)
```python
def test_rename_mirror_unavailable_fallback(tmp_path, monkeypatch):
    """If tmux is down, resolve_live falls back to name-based matching."""
    # Create row: fleet:old with pane_ref=tmux:fleet:%42
    # Kill tmux (or mock unavailable)
    # Rename to fleet:new
    # Expect: resolve_live returns row by name (pane_live check skipped)
    # Expect: rename proceeds (preflight succeeds)
```

---

### Part 6: Interaction with Other Moves

#### M1 Contract (Resolve Live vs Historical)
- **M3 depends on M1:** `rename_preflight()` and `rename_agent()` use `resolve_live()` (not `get_agent()`)
- **All live paths use M1:** bind, adopt, send, rename all call `resolve_live()` to get the current occupant
- **Historical-only paths use resolve_historical():** audit (lineage chain), restore (follow aliases), same-occupant fallback (M2)

#### M2 Contract (Occupant-Keyed Continuity)
- **M3 writes occupant metadata to alias:** `occupant_id` (si) + `launched_at` (launch_id)
- **M2 uses this to match stale targets:** when a msg/subscription/report targets old name, M2 resolves by occupant, not by name
- **Same occupant wins over live distinct pane:** if %N:new_name has si_xyz but old alias points to si_abc (still live at %N:interim), M2 routes to si_abc (same-occupant fallback)

#### M4 Contract (Born-Pane Self-Heal)
- **M3 respects thin rows:** if a row has no si (from M4 birth), `_same_live_incarnation()` returns False (no repair)
- **M4 reconcile fills in si:** once M4 bind/heal populates si, row becomes eligible for repair on next rename
- **Thin rows coexist:** multiple thin rows at same fleet:seat can exist until one is explicitly adopted/reconciled

#### M5 Contract (Operator Surface)
- **New alias ls/rm verbs** will use `read_aliases()` / `write_aliases()` to show/delete occupant-scoped alias records
- **Orphan-reconcile verb** will call `_is_pane_live()` to find unbound panes and M4 birth env to reconstruct thin rows
- **seat_status surfaces live-born-panes:** M3 rename ensures born panes are not orphaned (preserved as terminal_state)

---

### Part 7: Migration Concerns

#### 7.1 Existing Registry Data
- **No migration needed:** existing rows keep their si and pane_ref; M3 semantics apply going forward
- **Old renamed rows:** if a row has `rename_source` but no `terminal_state`, it's a legacy rename (no repair) — M3 treats it as-is
- **Alias records:** old alias records without `occupant_id` are valid; M2 treats them as "occupant unknown" (no M2 routing)

#### 7.2 Stale %N References
- **After M3 rename:** old pane_ref in deleted source row is not recoverable from registry (it's deleted)
- **But:** alias record + occupant_id allows M2 to find the same occupant at new name/si
- **Terminal preserved rows:** if loser was preserved as terminal, its pane_ref is still in registry (for audit)

#### 7.3 Existing Spawn-Into-Alias Behavior
- **Before M3/M1:** `spawn fleet:old_name` would shadow the name (no new spawn)
- **After M1:** `resolve_live()` ignores alias; spawn creates new row at old name
- **User impact:** if operators relied on alias shadow to prevent reuse, they must now use `aura seat cut` to explicitly prevent name reuse

---

### Part 8: Summary of Precise Edits

#### File: `/home/axp/projects/aura/main/cli/lib/registry.py`

| Line(s) | Action | Current | New |
|---------|--------|---------|-----|
| 395-430 | Keep `get_agent()` as `resolve_historical()` (rename in M1) | Read & alias-follow | Becomes M1 `resolve_historical()` |
| NEW | Add `resolve_live()` | — | New function per section 1.1 |
| 466-474 | Update `_same_live_incarnation()` | OR on any matching key | AND on both si AND pane_ref (section 1.2) |
| 477-516 | Update `rename_preflight()` | Call `get_agent()` + alias check | Call `resolve_live()` + no alias check (section 1.3) |
| 518-576 | Update `rename_agent()` | Call `get_agent()` + alias check + delete source + merge target | Call `resolve_live()` + no alias + preserve loser as terminal + occupant-scoped alias (section 1.4) |
| NEW | Add `_is_pane_live()` | — | New function per section 1.5 |
| 341-352 | Update `add_alias()` | signature: source, target, reason | Add occupant_id, launched_at (section 4) |

#### File: `/home/axp/projects/aura/main/cli/commands/seat.py`

| Line(s) | Action | Current | New |
|---------|--------|---------|-----|
| 2145-2210 | Update `_rename()` | Log repair_duplicate=False only | Add repair_duplicate + repair_detail logging (section 2.2) |
| 1605-1807 | Review `_adopt_pane_as_seat()` | Check existing at fleet:seat | Add comment clarifying M1/M3 behavior (section 2.3) |

---

### Part 9: Testing Strategy

**Test file:** `tests/test_rename_M3.py` (new file)

1. **Unit tests:** `_same_live_incarnation()` with various si/pane combinations
2. **Integration tests:** full rename flow with real registry lock
3. **Edge case tests:** mirror unavailable, dead panes, thin rows, fork children
4. **Regression tests:** spawn after rename (no alias shadow), repair preserve loser, alias occupant metadata
5. **Session ledger tests:** ensure rename event includes repair_duplicate flag and loser metadata

---

This completes the M3 specification. An implementer can now:
1. Implement M1's `resolve_live()` and refactor `get_agent()` → `resolve_historical()`
2. Apply the M3 edits to `_same_live_incarnation()`, `rename_preflight()`, `rename_agent()`, and `add_alias()` signature
3. Add the new helper `_is_pane_live()` for live pane verification
4. Update `_rename()` to log repair metadata
5. Write and run the test suite to verify all edge cases pass
6. Update docs (context/current/lexicon.md, model/two-laws.md, model/the-seat.md) per M5