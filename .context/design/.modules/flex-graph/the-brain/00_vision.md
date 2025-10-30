  ---
  Point 1: LLM Prune Agent (Entity Consistency)

  What you're describing:

  Changelog 1: keywords: "variant-system"
  Changelog 2: keywords: "variant system"
  Changelog 50: keywords: "prompt-variants"

  Prune Agent:
  - Detects: All three = same concept
  - Resolves to: "variant-system" (canonical dot notation)
  - Question: Update preceding changelogs?

  My Take: Don't Rewrite History

  Don't:
  ❌ LLM changes Changelog 2's keywords from "variant system" → "variant-system"
  ❌ Modifies stored changelogs

  Instead:
  ✅ Maintain entity resolution map (separate from changelogs):

  entity_map = {
    "variant-system": ["variant-system", "variant system", "prompt-variants"],
    "metadata-enrichment": ["metadata enrichment", "metadata-enrichment"]
  }

  ✅ At query time:
  search("variant system") 
    → Resolve to canonical: "variant-system"
    → Find all: ["variant-system", "variant system", "prompt-variants"]

  Why this is better:
  - Changelogs stay immutable (archaeological precision)
  - Entity map evolves independently
  - Query-time resolution (no reindexing)
  - Complexity in ONE place (entity map), not scattered

  Cost: One LLM pass over all keywords → build entity map → done.

  ---
  Point 2: BRAIN as Secondary Metadata (Ephemeral at Retrieval)

  From vision docs + your insight:

  Layer 1: Qdrant (permanent)
    - Chunks with base metadata
    - Immutable

  Layer 2: BRAIN (persistent but separate)
    - reference_count
    - superseded_by
    - pagerank_score
    - age_months
    - Updated continuously

  Layer 3: Graph API (ephemeral)
    - Builds graph from chunks
    - Looks up BRAIN state
    - Composes contextualized view
    - Runtime only, not stored

  This is perfect separation:

  # At query time:
  chunks = qdrant.search("caching")  # Permanent storage

  brain_state = brain.lookup(chunk_ids)  # Persistent metadata
  # Returns: {reference_count: 87, superseded_by: [...]}

  graph = build_from_chunks(chunks, brain_state)  # Ephemeral
  topology = detect_topology(graph)  # Ephemeral
  annotated = llm_annotate(chunks, brain_state)  # Ephemeral

  # Serve ephemeral composed view
  return render(annotated, topology)

  Why this works:
  - Qdrant = immutable truth (changelogs as written)
  - BRAIN = learned metadata (accumulates over time)
  - Graph API = ephemeral composition (runtime intelligence)
  - Clean separation, no rewriting history

  ---
  The Architecture (My Recommendation)

  Storage Layers

  Layer 1: Qdrant (Immutable)
  {
    "content": "Decision: Use Redis...",
    "keywords": "redis caching", // AS WRITTEN, never changed
    "timestamp": "2023-10-15",
    "file_path": "...",
    "session_id": "..."
  }

  Layer 2: Entity Resolution Map (Evolves)
  {
    "canonical_entities": {
      "caching.redis": ["redis", "Redis", "redis-cache", "Redis caching"],
      "caching.memcached": ["memcached", "Memcached"],
      "architecture.variant-system": ["variant-system", "variant system", "prompt variants"]
    }
  }

  Updated by LLM Prune Agent:
  - Runs periodically (weekly?)
  - Reads all keywords across changelogs
  - Clusters similar terms
  - Maintains canonical map
  - Doesn't modify changelogs

  Layer 3: BRAIN (Persistent, Separate)
  {
    "chunk_stats": {
      "redis-decision-id": {
        "reference_count": 23,
        "superseded_by": ["memcached-decision-id"],
        "supersession_confidence": 0.89,
        "pagerank_score": 0.72,
        "age_months": 18,
        "last_referenced": "2024-10-27"
      }
    }
  }

  Updated continuously:
  - Every query increments reference_count
  - Graph ops update pagerank_score
  - Time updates age_months
  - New changelogs trigger supersession detection

  ---
  Query Time (Ephemeral Composition)

  def query_with_intelligence(query):
      # 1. Resolve entities
      canonical = entity_map.resolve(query)
      # "variant system" → "variant-system" + aliases

      # 2. Retrieve from Qdrant (immutable)
      chunks = qdrant.search(canonical + aliases)

      # 3. Lookup BRAIN state
      brain_state = brain.lookup([c['id'] for c in chunks])

      # 4. Build ephemeral graph
      graph = build_graph(chunks)
      topology = detect_topology(graph)

      # 5. Enrich with BRAIN context
      for chunk in chunks:
          chunk['brain'] = brain_state[chunk['id']]
          chunk['temporal_position'] = detect_position(chunk, brain_state)

      # 6. LLM annotation (optional, endstate)
      if enable_annotation:
          annotated = llm_annotate(chunks, brain_state)

      # 7. Structure by topology
      structured = structure_by_topology(chunks, topology)

      # 8. Render
      return render(structured, template)

  Everything after step 2 is ephemeral. Nothing stored.

  ---
  Answers to Your Questions

  Q1: Does LLM update preceding changelogs when terms change?

  No.
  - Changelogs stay immutable
  - Entity resolution map evolves separately
  - Query-time resolution finds all variants

  Q2: How do we maintain consistent pool of terms?

  Separate entity map with dot notation:
  architecture.variant-system
  caching.redis
  caching.memcached

  Updated by periodic LLM pass (not per-changelog):
  - Weekly batch job
  - Read all keywords
  - Cluster + canonicalize
  - Update map

  Cost: 1 LLM call per week over aggregated keywords, ~$0.01

  Q3: Where does BRAIN metadata live?

  Separate persistence layer:
  - JSON file or lightweight DB
  - NOT in Qdrant
  - Looked up at query time
  - Ephemeral composition in graph API

  ---
  The Clean Architecture

  Immutable Storage (Qdrant)
    ↓
  Entity Resolution (separate map, evolves weekly)
    ↓
  BRAIN Metadata (separate persistence, updates continuously)
    ↓
  Query Time Composition (ephemeral graph + annotation)
    ↓
  Structured Serving

  No rewriting history. Clean separation. Complexity isolated.