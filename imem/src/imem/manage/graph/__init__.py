"""Graph module - Edge building for chunk relationships

EPIC 2: Graph Edges
Explicit relationships between chunks stored in edges table.

Edge Types:
- validated_by: narrative → git (proof links)
- superseded_by: old → new (replacement links)
- sibling: bidirectional similarity (EPIC 4, needs vectors)

EdgeOrchestrator coordinates builders to create typed edges.
"""

from .validated_by import ValidatedByBuilder
from .superseded_by import SupersededByBuilder

__all__ = [
    'ValidatedByBuilder',
    'SupersededByBuilder',
]
