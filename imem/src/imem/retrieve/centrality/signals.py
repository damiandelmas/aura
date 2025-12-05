"""Centrality signal protocol and base structures

Centrality signals measure "how important is this chunk?" through connectivity.
This is SEPARATE from validity which measures "is this true?".

Critical distinction (graph-epistemology):
- Validity: truth (git-backed, MANAGE domain)
- Centrality: importance (structure-based, RETRIEVE domain)

Never conflate connectivity with truthfulness.
A chunk can be highly central but outdated (low validity).
A chunk can be valid but peripheral (low centrality).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...context import QueryContext


@dataclass
class CentralityResult:
    """Result from a centrality signal

    Attributes:
        score: Centrality value (0.0-1.0)
        confidence: How certain the signal is (0.0-1.0)
        reason: Optional explanation for debugging
    """
    score: float
    confidence: float = 1.0
    reason: Optional[str] = None


class CentralitySignal(ABC):
    """Protocol for centrality scoring plugins

    Centrality signals compute "how important?" from graph structure.
    Multiple signals contribute, each capturing different aspects:
    - EdgeCountSignal: inbound reference count
    - CrossPhaseSignal: diversity of referencing phases
    - SiblingDensitySignal: semantic cluster density (Tier 3)

    Mirrors ValiditySignal pattern for consistency.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique signal identifier"""
        pass

    @abstractmethod
    def applies(self, chunk: Dict[str, Any], context: 'QueryContext') -> bool:
        """Check if this signal applies to the chunk

        Args:
            chunk: Chunk to evaluate
            context: Query context with infrastructure

        Returns:
            True if signal should score this chunk
        """
        pass

    @abstractmethod
    def score(self, chunk: Dict[str, Any], context: 'QueryContext') -> CentralityResult:
        """Compute centrality score for the chunk

        Args:
            chunk: Chunk to score
            context: Query context with infrastructure

        Returns:
            CentralityResult with score, confidence, optional reason
        """
        pass


class NoOpCentralitySignal(CentralitySignal):
    """No-op signal that returns neutral values

    Used for graceful degradation when real signals aren't available.
    """

    @property
    def name(self) -> str:
        return "noop"

    def applies(self, chunk: Dict[str, Any], context: 'QueryContext') -> bool:
        return False

    def score(self, chunk: Dict[str, Any], context: 'QueryContext') -> CentralityResult:
        return CentralityResult(score=0.5, confidence=0.0, reason="NoOp signal")


__all__ = [
    'CentralityResult',
    'CentralitySignal',
    'NoOpCentralitySignal',
]
