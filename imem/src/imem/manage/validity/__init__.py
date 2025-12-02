"""Validity Module - Compute "is this chunk still true?"

ValidityComputer aggregates signals into 0.0-1.0 score.
Two signals in EPIC 1:
- TemporalSignal: Baseline (survival philosophy - NOT decay)
- GitSignal: Validate signatures against codebase

Philosophy (from survival-signal.md):
- Age is NOT decay - survival without supersession is POSITIVE
- Git chunks = 1.0 validity (ground truth)
- Supersession override to 0.2 (handled by edge in EPIC 2-3)
"""

from .temporal import TemporalSignal
from .git import GitSignal

__all__ = [
    'TemporalSignal',
    'GitSignal',
]
