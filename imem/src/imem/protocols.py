"""Plugin protocols for domain orchestrators

IMEM uses domain-specific plugin protocols rather than a universal interface.
Each orchestrator defines its own protocol for its plugins:

- Signal: Scoring plugin for validity/centrality (returns 0-1)
- Builder: Edge-creating plugin
- Processor: Retrieve chain stage
- Module: Structure/MANAGE stage

Each protocol has a NoOp implementation for graceful degradation.
The system runs end-to-end with NoOp plugins, enabling incremental implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import IndexContext, QueryContext


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class SignalResult:
    """Result from a Signal plugin

    Attributes:
        score: Value between 0.0 and 1.0
        confidence: How certain the signal is (0.0 = no info, 1.0 = certain)
        reason: Optional explanation
    """
    score: float
    confidence: float = 1.0
    reason: Optional[str] = None


@dataclass
class Edge:
    """Relationship between two chunks

    Attributes:
        from_id: Source chunk ID
        to_id: Target chunk ID
        type: Edge type (validated_by, superseded_by, sibling)
        weight: Edge strength (0.0-1.0)
    """
    from_id: str
    to_id: str
    type: str
    weight: float = 1.0


# ============================================================================
# Signal Protocol (Validity & Centrality)
# ============================================================================

class Signal(ABC):
    """Plugin protocol for scoring computations

    Signals contribute to aggregated scores (validity, centrality).
    Each signal is independently testable and can be enabled/disabled.

    Examples:
        - TemporalSignal: Decay based on age
        - GitSignal: Match against codebase
        - EdgeCountSignal: Count of incoming edges
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique signal identifier"""
        pass

    @abstractmethod
    def applies(self, chunk: Dict[str, Any], context: 'IndexContext') -> bool:
        """Check if this signal applies to the chunk

        Args:
            chunk: Chunk to evaluate
            context: Index context with infrastructure

        Returns:
            True if signal should score this chunk
        """
        pass

    @abstractmethod
    def score(self, chunk: Dict[str, Any], context: 'IndexContext') -> SignalResult:
        """Compute score for the chunk

        Args:
            chunk: Chunk to score
            context: Index context with infrastructure

        Returns:
            SignalResult with score, confidence, optional reason
        """
        pass


class NoOpSignal(Signal):
    """No-op signal that returns neutral values

    Used for graceful degradation when real signals aren't available.
    """

    @property
    def name(self) -> str:
        return "noop"

    def applies(self, chunk: Dict[str, Any], context: 'IndexContext') -> bool:
        return False

    def score(self, chunk: Dict[str, Any], context: 'IndexContext') -> SignalResult:
        return SignalResult(score=0.5, confidence=0.0, reason="NoOp signal")


# ============================================================================
# Builder Protocol (Graph Edges)
# ============================================================================

class Builder(ABC):
    """Plugin protocol for edge construction

    Builders create relationship edges between chunks.
    Each builder produces a specific edge type.

    Examples:
        - ValidatedByBuilder: Links narrative to git validation
        - SupersededByBuilder: Links old chunks to replacements
        - SiblingBuilder: Links semantically similar chunks
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique builder identifier"""
        pass

    @property
    @abstractmethod
    def edge_type(self) -> str:
        """Type of edges this builder creates"""
        pass

    @abstractmethod
    def applies(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> bool:
        """Check if this builder applies

        Args:
            chunks: All chunks in the index run
            context: Index context with infrastructure

        Returns:
            True if builder should run
        """
        pass

    @abstractmethod
    def build(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> List[Edge]:
        """Build edges between chunks

        Args:
            chunks: All chunks to consider
            context: Index context with infrastructure

        Returns:
            List of Edge objects to persist
        """
        pass


class NoOpBuilder(Builder):
    """No-op builder that creates no edges

    Used for graceful degradation when real builders aren't available.
    """

    @property
    def name(self) -> str:
        return "noop"

    @property
    def edge_type(self) -> str:
        return "noop"

    def applies(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> bool:
        return False

    def build(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> List[Edge]:
        return []


# ============================================================================
# Processor Protocol (Retrieve Chain)
# ============================================================================

class Processor(ABC):
    """Plugin protocol for retrieve chain stages

    Processors transform QueryContext in the retrieve pipeline.
    They are composable - chained together via the Chain pattern.

    Examples:
        - SearchProcessor: Initial retrieval
        - DiscoveryProcessor: Expand with related chunks
        - RankingProcessor: Order results
    """

    @abstractmethod
    def process(self, context: 'QueryContext') -> 'QueryContext':
        """Process and transform the query context

        Args:
            context: Current query context

        Returns:
            Transformed context (may be same object, mutated)
        """
        pass


class NoOpProcessor(Processor):
    """No-op processor that passes context through unchanged"""

    def process(self, context: 'QueryContext') -> 'QueryContext':
        return context


# ============================================================================
# Module Protocol (MANAGE/STRUCTURE stages)
# ============================================================================

class Module(ABC):
    """Plugin protocol for MANAGE and STRUCTURE stages

    Modules transform chunks during enrichment or presentation.
    Unlike Processors, they work on chunk lists directly.

    Examples:
        - LinkModule: Attach commit_sha
        - SignatureModule: Extract code signatures
        - CurateModule: Filter and order results
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique module identifier"""
        pass

    @abstractmethod
    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> List[Dict[str, Any]]:
        """Execute module on chunks

        Args:
            chunks: Chunks to process
            context: Index context with infrastructure

        Returns:
            Transformed chunks (may be same list, mutated)
        """
        pass


class NoOpModule(Module):
    """No-op module that returns chunks unchanged"""

    @property
    def name(self) -> str:
        return "noop"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> List[Dict[str, Any]]:
        return chunks
