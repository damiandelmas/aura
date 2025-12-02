"""Temporal Signal - Baseline validity signal

SURVIVAL SIGNAL PHILOSOPHY:
Age is NOT decay. Survival without supersession is POSITIVE evidence.

A 2-year-old doc that hasn't been superseded has *survived* 2 years of commits.
That's not staleness — that's durability.

V1 Formula (Simple & Correct):
- IF superseded_by edge exists: validity = 0.2 (handled elsewhere)
- ELIF git_signal = contradicted: validity = git_score (low)
- ELIF git_signal = validated: validity = git_score (high)
- ELSE: validity = 0.5 (neutral baseline)

No temporal decay. Age without invalidation is neutral-to-positive, never negative.

EPIC 1 implementation.
"""

from datetime import datetime
from typing import Any, Dict, TYPE_CHECKING

from ...protocols import Signal, SignalResult

if TYPE_CHECKING:
    from ...context import IndexContext


class TemporalSignal(Signal):
    """Baseline temporal signal

    Unlike traditional decay, this implements survival signal philosophy:
    - Provides neutral baseline (0.5) for all chunks
    - Does NOT penalize age
    - Confidence is low (0.3) — other signals should dominate

    Age without invalidation = neutral-to-positive, never negative.
    """

    # Low confidence - let GitSignal dominate when available
    BASELINE_CONFIDENCE = 0.3

    @property
    def name(self) -> str:
        return "temporal"

    def applies(self, chunk: Dict[str, Any], context: 'IndexContext') -> bool:
        """Temporal signal applies to all non-git chunks

        Git-sourced chunks are ground truth (validity=1.0) and skip signals.
        """
        source = chunk.get('source', chunk.get('metadata', {}).get('source'))
        return source != 'git'

    def score(self, chunk: Dict[str, Any], context: 'IndexContext') -> SignalResult:
        """Compute temporal score

        Returns neutral baseline (0.5) with low confidence.
        No decay penalty for age - survival is evidence, not liability.
        """
        # Check for timestamp presence
        timestamp = chunk.get('timestamp')
        if not timestamp:
            return SignalResult(
                score=0.5,
                confidence=0.1,  # Very low confidence without timestamp
                reason="No timestamp available"
            )

        # Parse timestamp if string
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                return SignalResult(
                    score=0.5,
                    confidence=0.1,
                    reason="Invalid timestamp format"
                )

        # Calculate age for informational purposes
        now = datetime.now()
        if timestamp.tzinfo:
            # Make naive for comparison
            timestamp = timestamp.replace(tzinfo=None)

        age_days = (now - timestamp).days

        # SURVIVAL SIGNAL: Age is not a penalty
        # Return neutral baseline with contextual reason
        if age_days < 7:
            reason = f"Recent ({age_days}d old) - fresh"
        elif age_days < 30:
            reason = f"Recent ({age_days}d old) - stable"
        elif age_days < 90:
            reason = f"Established ({age_days}d old) - durable"
        else:
            reason = f"Long-standing ({age_days}d old) - battle-tested"

        return SignalResult(
            score=0.5,  # Neutral baseline
            confidence=self.BASELINE_CONFIDENCE,
            reason=reason
        )


__all__ = ['TemporalSignal']
