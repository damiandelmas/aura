---
session_id: eee3b7a5-3870-4b50-984c-19eb2e2fa729
date: 2025-10-27
type: implementation.specification
resolution: level-2b
keywords: "cli-primitives json-output usage-logging pattern-detection"
---

# Runtime Composition: Implementation Specification

## Primitive Interface (CLI)

```bash
# Core primitives return structured JSON

# 1. Search
imem search "query" --decisions --limit 10
# Returns: {"results": [{"id": "...", "score": 0.85, "payload": {...}}]}

# 2. Filter
imem filter --file-path "path" --section-type "Decisions"
# Returns: {"results": [...]}

# 3. Graph build
imem graph build <result-ids> --id my-graph
# Returns: {"graph_id": "my-graph", "node_count": 20, "edge_count": 45}

# 4. Graph apply
imem graph apply my-graph pagerank
# Returns: {"ranked_results": [...]}

# 5. Combine
imem combine <result-set-1> <result-set-2>
# Returns: {"merged_results": [...]}
```

---

## JSON Output Format

```python
# Standard response envelope
{
    "operation": "search",
    "success": true,
    "timestamp": "2025-10-27T17:15:00Z",
    "results": [
        {
            "id": "abc123",
            "score": 0.85,
            "payload": {
                "content": "...",
                "file_path": "...",
                "section_type": "Decisions",
                # ... 23 metadata fields
            }
        }
    ],
    "metadata": {
        "query_time_ms": 45,
        "collection": "imem_abc123",
        "filters_applied": ["phase=develop", "section_type=Decisions"]
    }
}
```

---

## Usage Logging

```python
# ~/.context/imem_usage.log (JSONL format)
{"timestamp": "2025-10-27T17:15:00Z", "operation": "search", "params": {"query": "JWT", "filters": {"decisions": true}}, "result_count": 10, "duration_ms": 45}
{"timestamp": "2025-10-27T17:15:02Z", "operation": "filter", "params": {"file_path": "...", "section_type": "Constraints"}, "result_count": 3, "duration_ms": 12}
{"timestamp": "2025-10-27T17:15:05Z", "operation": "filter", "params": {"session_id": "abc123"}, "result_count": 5, "duration_ms": 18}

# Sequence detection:
# search → filter(file) → filter(session) = "explain pattern"
```

---

## Pattern Detection

```python
def detect_patterns(log_file, min_occurrences=10, success_threshold=0.8):
    """Detect composition patterns from usage log."""
    sequences = parse_log_sequences(log_file, window=5)

    # Group by operation sequence
    pattern_groups = defaultdict(list)
    for seq in sequences:
        signature = tuple(op['operation'] for op in seq)
        pattern_groups[signature].append(seq)

    # Filter by frequency and success
    validated_patterns = []
    for signature, occurrences in pattern_groups.items():
        if len(occurrences) >= min_occurrences:
            success_rate = sum(1 for seq in occurrences if seq_successful(seq)) / len(occurrences)
            if success_rate >= success_threshold:
                validated_patterns.append({
                    'signature': signature,
                    'count': len(occurrences),
                    'success_rate': success_rate,
                    'example': occurrences[0]
                })

    return validated_patterns

# Example output:
# [
#     {
#         'signature': ('search', 'filter', 'filter'),
#         'count': 13,
#         'success_rate': 0.92,
#         'example': [search JWT, filter file_path, filter session]
#     }
# ]
```

---

## Shortcut Generation

```python
def generate_shortcut(pattern, name):
    """Generate markdown slash command from pattern."""
    template = f"""---
pattern: {pattern['signature']}
validated: {pattern['count']} uses, {pattern['success_rate']:.0%} success
generated: {datetime.now()}
---

# /{name}

**Usage:** `/{name} "query"`

**What it does:**
{describe_pattern(pattern)}

**Implementation:**
"""

    # Generate command sequence
    for i, op in enumerate(pattern['example'], 1):
        template += f"\n{i}. `imem {format_operation(op)}`"

    # Write to .claude/commands/
    with open(f".claude/commands/{name}.md", "w") as f:
        f.write(template)
```

---

## Batch Operations (JSON Config)

```bash
# For complex compositions, use JSON batch
imem query config.json

# config.json
{
    "queries": [
        {"text": "auth security", "filters": {"section_type": "Decisions"}},
        {"text": "auth impl", "filters": {"layer": "implementation"}},
        {"text": "auth patterns", "filters": {"layer": "pattern"}}
    ],
    "combine": true,
    "graph": {
        "algorithm": "centrality",
        "top": 10
    }
}

# Internally:
# - Spawns 3 searches in parallel
# - Merges results
# - Builds graph
# - Applies algorithm
# - Returns single JSON response
```

---

## CLI Documentation (Slash Command)

```bash
# Document CLI via slash command
/imem-guide

# Expands to explanation of:
# - Available primitives
# - JSON batch format
# - Config examples
# - Usage patterns

# Claude Code reads guide, composes operations
```

---

## Result Chaining

```bash
# Option A: Explicit variable binding
result1=$(imem search "JWT" --json)
file_path=$(echo $result1 | jq -r '.results[0].payload.file_path')
imem filter --file-path "$file_path"

# Option B: Pipe model (future)
imem search "JWT" | imem filter --by-file

# Option C: JSON batch with references
{
    "operations": [
        {"op": "search", "query": "JWT", "store": "result1"},
        {"op": "filter", "file_path": "$result1.file_path", "store": "result2"}
    ]
}
```

---

## Performance

**Primitive call:** O(1) CLI invocation + O(log n) query
**JSON parsing:** O(k) where k = result count
**Composition overhead:** Minimal (bash process spawning)
**Logging:** Async, no query latency impact

**Optimization:** JSON batch reduces CLI invocations (1 vs N).
