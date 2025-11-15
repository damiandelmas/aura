# IMEM Structure

## Directory Layout

```
imem/
├── manage/
│   ├── nexus/
│   │   ├── registry
│   │   ├── qualification
│   │   └── access
│   │
│   └── mind/
powers the knowledge graph
powers nexus retreival (rich metadata querying)
│       ├── schema_evolution
│       ├── entity_resolution
│       ├── graph_runtime
│       ├── introspection
│       └── temporal_cortex
│
└── use/
    └── modalities/
        ├── vector
        ├── trace (mostly jsonl parsing)
        |—— nexus (just metadata)
        structures/
        ├── graph
        └── temporal

cli.py
ingest.py
```

compose.py
    multi-modality
    batch processing
    asyncio