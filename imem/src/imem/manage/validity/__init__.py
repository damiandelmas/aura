"""Validity Module - Compute "is this chunk still true?"

EPIC 3: Three-phase validity computation.

ValidityComputer aggregates signals into 0.0-1.0 score:
- TemporalSignal: Baseline (survival philosophy - NOT decay)
- GitSignal: Validate signatures against codebase (anchored chunks)
- PropagationSignal: Derive validity via graph traversal (unanchored chunks)

Three-phase flow:
1. Phase 1: Anchored chunks scored with temporal + git
2. Phase 2: Edges built (needs anchored validity)
3. Phase 3: Unanchored chunks scored with temporal + propagation

Philosophy (from survival-signal.md):
- Age is NOT decay - survival without supersession is POSITIVE
- Git chunks = 1.0 validity (ground truth)
- Supersession override to 0.2 (handled by edge)
- Propagation: transitive trust from anchored neighbors
"""

from .temporal import TemporalSignal
from .git import GitSignal
from .propagation import PropagationSignal, is_anchored, get_anchored_ids

__all__ = [
    'TemporalSignal',
    'GitSignal',
    'PropagationSignal',
    'is_anchored',
    'get_anchored_ids',
]
