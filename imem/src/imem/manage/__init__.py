"""Manage domain - Chunk enrichment orchestration

EPIC 0 establishes ManageOrchestrator with NoOp plugins.
Enriches chunks after parsing: link → signatures → validity → graph.

Responsible for:
- Provenance attachment (commit_sha, timestamp)
- Code signature extraction (validation anchors)
- Validity computation (temporal, git, propagation)
- Edge building (validated_by, superseded_by, sibling)
- Entity resolution (vocabulary normalization)

Legacy exports for backward compatibility:
- introspect, get_coverage_stats (from root introspect.py)
- SimpleRegistry
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

from ..protocols import Signal, Builder, Module, NoOpSignal, NoOpBuilder, NoOpModule, Edge

if TYPE_CHECKING:
    from ..context import IndexContext

logger = logging.getLogger(__name__)


# ============================================================================
# Validity Computer (aggregates signals)
# ============================================================================

class ValidityComputer:
    """Aggregates validity signals into a single score

    Two-phase computation:
    1. Anchored chunks (have signatures with file_path): direct validation
    2. Unanchored chunks: propagation through edges

    EPIC 0: NoOp signals only.
    """

    def __init__(self, signals: Optional[List[Signal]] = None):
        self.signals = signals or [NoOpSignal()]

    def compute(self, chunk: Dict[str, Any], context: 'IndexContext') -> Dict[str, Any]:
        """Compute validity for a chunk

        Returns:
            Dict with 'score' (0.0-1.0) and 'git_status' string
        """
        total_score = 0.0
        total_weight = 0.0

        for signal in self.signals:
            if signal.applies(chunk, context):
                result = signal.score(chunk, context)
                # Weight by confidence
                weight = result.confidence
                total_score += result.score * weight
                total_weight += weight

        if total_weight > 0:
            validity = total_score / total_weight
        else:
            validity = 0.5  # Neutral default

        # Determine git_status from validity
        if validity >= 0.8:
            git_status = 'validated'
        elif validity <= 0.2:
            git_status = 'contradicted'
        else:
            git_status = 'unvalidated'

        return {
            'score': validity,
            'git_status': git_status
        }


class NoOpValidityComputer(ValidityComputer):
    """No-op validity computer returning neutral values"""

    def __init__(self):
        super().__init__([NoOpSignal()])


# ============================================================================
# Edge Orchestrator (coordinates builders)
# ============================================================================

class EdgeOrchestrator:
    """Coordinates edge builders to create relationships

    EPIC 0: NoOp builders only.
    """

    def __init__(self, builders: Optional[List[Builder]] = None):
        self.builders = builders or [NoOpBuilder()]

    def build_edges(
        self,
        chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> List[Edge]:
        """Build all edges using configured builders

        Returns:
            List of Edge objects to persist
        """
        all_edges: List[Edge] = []

        for builder in self.builders:
            if builder.applies(chunks, context):
                edges = builder.build(chunks, context)
                all_edges.extend(edges)
                logger.debug(f"Builder {builder.name} created {len(edges)} edges")

        return all_edges


class NoOpEdgeOrchestrator(EdgeOrchestrator):
    """No-op edge orchestrator creating no edges"""

    def __init__(self):
        super().__init__([NoOpBuilder()])


# ============================================================================
# ManageOrchestrator (main entry point)
# ============================================================================

class ManageOrchestrator:
    """Coordinates MANAGE sub-modules in sequence

    Flow: link → signatures → validity → graph

    EPIC 0: All modules are NoOp except basic wiring.
    """

    def __init__(
        self,
        link: Optional[Module] = None,
        signatures: Optional[Module] = None,
        validity: Optional[ValidityComputer] = None,
        graph: Optional[EdgeOrchestrator] = None,
    ):
        self.link = link or NoOpModule()
        self.signatures = signatures or NoOpModule()
        self.validity = validity or NoOpValidityComputer()
        self.graph = graph or NoOpEdgeOrchestrator()

    def enrich(
        self,
        chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> None:
        """Enrich chunks with metadata, scores, and edges

        Mutates chunks in place. Creates edges in database.

        Args:
            chunks: Chunks to enrich
            context: Index context with infrastructure
        """
        # 1. Attach git provenance (commit_sha, timestamp)
        chunks = self.link.execute(chunks, context)
        logger.debug(f"Link module processed {len(chunks)} chunks")

        # 2. Extract code signatures (validation anchors)
        chunks = self.signatures.execute(chunks, context)
        logger.debug(f"Signatures module processed {len(chunks)} chunks")

        # 3. Compute validity scores
        for chunk in chunks:
            result = self.validity.compute(chunk, context)
            chunk['validity'] = result['score']
            chunk['git_status'] = result['git_status']

        logger.debug(f"Validity computed for {len(chunks)} chunks")

        # 4. Build edges
        edges = self.graph.build_edges(chunks, context)
        if edges:
            self._persist_edges(edges, context)
        logger.debug(f"Created {len(edges)} edges")

    def _persist_edges(self, edges: List[Edge], context: 'IndexContext') -> None:
        """Persist edges to database"""
        db = context.infrastructure.db
        for edge in edges:
            try:
                db.conn.execute('''
                    INSERT OR REPLACE INTO edges (from_id, to_id, type, weight)
                    VALUES (?, ?, ?, ?)
                ''', (edge.from_id, edge.to_id, edge.type, edge.weight))
            except Exception as e:
                logger.warning(f"Failed to persist edge: {e}")
        db.conn.commit()


def create_manage_orchestrator() -> ManageOrchestrator:
    """Factory for ManageOrchestrator with default NoOp plugins

    EPIC 0: All plugins are NoOp.
    Later EPICs add real implementations.
    """
    return ManageOrchestrator(
        link=NoOpModule(),
        signatures=NoOpModule(),
        validity=NoOpValidityComputer(),
        graph=NoOpEdgeOrchestrator(),
    )


# ============================================================================
# Legacy exports for backward compatibility
# ============================================================================

# Note: introspect is at root level (imem/introspect.py), not in manage/
# This import was broken - fixing by importing from correct location
try:
    from ..introspect import introspect, get_coverage_stats
except ImportError:
    # Fallback if introspect module not available
    def introspect(*args, **kwargs):
        return {"error": "introspect module not available"}

    def get_coverage_stats(*args, **kwargs):
        return {"error": "get_coverage_stats not available"}

from ..registry import SimpleRegistry


__all__ = [
    # New EPIC 0 exports
    'ManageOrchestrator',
    'create_manage_orchestrator',
    'ValidityComputer',
    'NoOpValidityComputer',
    'EdgeOrchestrator',
    'NoOpEdgeOrchestrator',
    # Legacy exports
    'introspect',
    'get_coverage_stats',
    'SimpleRegistry',
]
