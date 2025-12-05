"""Manage domain - Chunk enrichment orchestration

EPIC 3: Validity Propagation - Three-phase validity computation.
Enriches chunks after parsing with three-phase flow:

PHASE 1: Direct enrichment
    1. link.execute()           → attach commit_sha
    2. signatures.extract()     → extract code blocks
    3. Identify anchored_ids    → chunks with signatures.file_path
    4. validity.compute()       → score ANCHORED chunks only (temporal + git)

PHASE 2: Build edges
    5. graph.build_edges()      → create validated_by, superseded_by
    6. validity.override_superseded() → set superseded chunks to 0.2

PHASE 3: Propagate to unanchored
    7. validity.compute()       → score UNANCHORED chunks (temporal + propagation)

Responsible for:
- Provenance attachment (commit_sha, timestamp) - LinkModule
- Code signature extraction (validation anchors) - SignatureExtractor
- Validity computation (temporal, git, propagation) - ValidityComputer
- Edge building (validated_by, superseded_by, sibling) - EdgeOrchestrator
- Validity override for superseded chunks
- Entity resolution (vocabulary normalization) - future EPIC

Legacy exports for backward compatibility:
- introspect, get_coverage_stats (from root introspect.py)
- SimpleRegistry
"""

from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
import logging

from ..protocols import Signal, Builder, Module, NoOpSignal, NoOpBuilder, NoOpModule, Edge

# EPIC 1 imports
from .link import LinkModule
from .signatures import SignatureExtractor
from .validity import TemporalSignal, GitSignal

# EPIC 2 imports
from .graph import ValidatedByBuilder, SupersededByBuilder

# EPIC 4 imports
from .graph import SiblingBuilder, NoOpSiblingBuilder, create_sibling_builder

# EPIC 3 imports
from .validity.propagation import PropagationSignal, is_anchored, get_anchored_ids

if TYPE_CHECKING:
    from ..context import IndexContext

logger = logging.getLogger(__name__)


# ============================================================================
# Validity Computer (aggregates signals)
# ============================================================================

class ValidityComputer:
    """Aggregates validity signals into a single score

    Three-phase computation (EPIC 3):
    1. Phase 1: Score ANCHORED chunks (temporal + git signals)
    2. Phase 2: Build edges (needs anchored validity)
    3. Phase 3: Score UNANCHORED chunks (temporal + propagation signals)

    Signal filtering enables phase-specific computation:
    - Phase 1: signals=['temporal', 'git']
    - Phase 3: signals=['temporal', 'propagation']
    """

    def __init__(self, signals: Optional[List[Signal]] = None):
        self.signals = signals or [NoOpSignal()]

    def compute(
        self,
        chunk: Dict[str, Any],
        context: 'IndexContext',
        signal_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Compute validity for a chunk

        Args:
            chunk: Chunk to score
            context: Index context with infrastructure
            signal_names: Optional filter - only use signals with these names.
                         If None, use all signals.

        Returns:
            Dict with 'score' (0.0-1.0) and 'git_status' string
        """
        total_score = 0.0
        total_weight = 0.0

        for signal in self.signals:
            # Apply signal name filter if provided
            if signal_names is not None and signal.name not in signal_names:
                continue

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
    """Coordinates MANAGE sub-modules in three-phase flow

    EPIC 3: Three-Phase Validity Computation

    PHASE 1: Direct enrichment
        1. link.execute()           → attach commit_sha
        2. signatures.extract()     → extract code blocks
        3. Identify anchored_ids    → chunks with signatures.file_path
        4. validity.compute()       → score ANCHORED chunks only (temporal + git)

    PHASE 2: Build edges
        5. graph.build_edges()      → create validated_by, superseded_by
        6. validity.override_superseded() → set superseded chunks to 0.2

    PHASE 3: Propagate to unanchored
        7. validity.compute()       → score UNANCHORED chunks (temporal + propagation)

    This ordering resolves the circular dependency between edges and validity.
    """

    # Supersession validity override constants
    SUPERSEDED_VALIDITY = 0.2  # Hard cap for superseded chunks

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

        Three-phase flow for validity computation.
        Mutates chunks in place. Creates edges in database.

        Args:
            chunks: Chunks to enrich
            context: Index context with infrastructure
        """
        # ===== PHASE 1: Direct enrichment =====

        # 1. Attach git provenance (commit_sha, timestamp)
        chunks = self.link.execute(chunks, context)
        logger.debug(f"Link module processed {len(chunks)} chunks")

        # 2. Extract code signatures (validation anchors)
        chunks = self.signatures.execute(chunks, context)
        logger.debug(f"Signatures module processed {len(chunks)} chunks")

        # 3. Identify anchored chunks (have signatures with file_path)
        anchored_ids = get_anchored_ids(chunks, context)
        logger.debug(f"Identified {len(anchored_ids)} anchored chunks")

        # Set anchored_ids on PropagationSignal if present
        for signal in self.validity.signals:
            if hasattr(signal, 'set_anchored_ids'):
                signal.set_anchored_ids(anchored_ids)

        # 4. Compute validity for ANCHORED chunks only (temporal + git)
        anchored_count = 0
        for chunk in chunks:
            if chunk.get('id') in anchored_ids:
                result = self.validity.compute(
                    chunk, context,
                    signal_names=['temporal', 'git']  # Phase 1: direct signals only
                )
                chunk['validity'] = result['score']
                chunk['git_status'] = result['git_status']
                anchored_count += 1

        logger.debug(f"Phase 1: Computed validity for {anchored_count} anchored chunks")

        # ===== PHASE 2: Build edges =====

        # 5. Build edges (now we have anchored validity for supersession detection)
        edges = self.graph.build_edges(chunks, context)
        if edges:
            self._persist_edges(edges, context)
        logger.debug(f"Phase 2: Created {len(edges)} edges")

        # 6. Override validity for superseded chunks
        superseded_count = self._override_superseded_validity(edges, chunks, context)
        if superseded_count:
            logger.info(f"Marked {superseded_count} chunks as superseded (validity={self.SUPERSEDED_VALIDITY})")

        # ===== PHASE 3: Propagate to unanchored =====

        # 7. Compute validity for UNANCHORED chunks (temporal + propagation)
        unanchored_count = 0
        for chunk in chunks:
            chunk_id = chunk.get('id')
            if chunk_id and chunk_id not in anchored_ids:
                # Skip superseded chunks - they already have overridden validity
                if chunk.get('git_status') == 'superseded':
                    continue

                result = self.validity.compute(
                    chunk, context,
                    signal_names=['temporal', 'propagation']  # Phase 3: propagation
                )
                chunk['validity'] = result['score']
                chunk['git_status'] = result['git_status']
                unanchored_count += 1

        logger.debug(f"Phase 3: Computed validity for {unanchored_count} unanchored chunks")

        # Update all chunks in database
        self._persist_validity(chunks, context)

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

    def _override_superseded_validity(
        self,
        edges: List[Edge],
        chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> int:
        """Override validity for chunks with superseded_by edges

        When a chunk is superseded by a newer version:
        - validity = 0.2 (hard cap)
        - git_status = 'superseded'

        This happens AFTER edge building, BEFORE propagation.

        Args:
            edges: Edges just created
            chunks: Chunks being indexed
            context: Index context with infrastructure

        Returns:
            Count of chunks marked as superseded
        """
        # Find superseded chunk IDs
        superseded_ids = {
            edge.from_id
            for edge in edges
            if edge.type == 'superseded_by'
        }

        if not superseded_ids:
            return 0

        # Build ID-to-chunk map for in-memory updates
        chunk_map = {c['id']: c for c in chunks}

        # Update in-memory chunks
        for chunk_id in superseded_ids:
            if chunk_id in chunk_map:
                chunk_map[chunk_id]['validity'] = self.SUPERSEDED_VALIDITY
                chunk_map[chunk_id]['git_status'] = 'superseded'

        # Update database
        db = context.infrastructure.db
        try:
            for chunk_id in superseded_ids:
                db.conn.execute('''
                    UPDATE chunks
                    SET validity = ?, git_status = ?
                    WHERE id = ?
                ''', (self.SUPERSEDED_VALIDITY, 'superseded', chunk_id))
            db.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update superseded chunks: {e}")

        return len(superseded_ids)

    def _persist_validity(
        self,
        chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> None:
        """Persist validity scores to database

        Called at the end of enrichment to update all chunks.
        """
        db = context.infrastructure.db
        try:
            for chunk in chunks:
                chunk_id = chunk.get('id')
                validity = chunk.get('validity')
                git_status = chunk.get('git_status')

                if chunk_id and validity is not None:
                    db.conn.execute('''
                        UPDATE chunks
                        SET validity = ?, git_status = ?
                        WHERE id = ?
                    ''', (validity, git_status, chunk_id))

            db.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to persist validity scores: {e}")


def create_manage_orchestrator(
    vector_storage=None,
    embedder=None,
) -> ManageOrchestrator:
    """Factory for ManageOrchestrator with EPIC 4 implementations

    EPIC 4: sqlite-vec Vectors
    - Link: Real timestamp cascade, commit_sha attachment
    - Signatures: Real code block extraction
    - Validity: Temporal + Git + Propagation signals (three-phase)
    - Graph: ValidatedBy + SupersededBy + SiblingBuilder (Tier 3)

    Three-phase flow:
    1. Phase 1: Anchored chunks scored with temporal + git
    2. Phase 2: Edges built (includes sibling if vectors available)
    3. Phase 3: Unanchored chunks scored with temporal + propagation

    Args:
        vector_storage: Optional VectorStorage for sibling edges (Tier 3)
        embedder: Optional Embedder for sibling edges (Tier 3)
    """
    # Create validity computer with all signals (EPIC 3)
    validity_computer = ValidityComputer(
        signals=[
            TemporalSignal(),
            GitSignal(),
            PropagationSignal(),  # EPIC 3: propagation for unanchored
        ]
    )

    # Build list of edge builders
    builders = [
        ValidatedByBuilder(),
        SupersededByBuilder(),
    ]

    # EPIC 4: Add SiblingBuilder if vector infrastructure available
    sibling_builder = create_sibling_builder(
        vector_storage=vector_storage,
        embedder=embedder,
    )
    builders.append(sibling_builder)

    # Create edge orchestrator with all builders
    edge_orchestrator = EdgeOrchestrator(builders=builders)

    return ManageOrchestrator(
        link=LinkModule(),
        signatures=SignatureExtractor(),
        validity=validity_computer,
        graph=edge_orchestrator,
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
    # Core exports
    'ManageOrchestrator',
    'create_manage_orchestrator',
    'ValidityComputer',
    'NoOpValidityComputer',
    'EdgeOrchestrator',
    'NoOpEdgeOrchestrator',
    # EPIC 1 modules
    'LinkModule',
    'SignatureExtractor',
    'TemporalSignal',
    'GitSignal',
    # EPIC 2 modules
    'ValidatedByBuilder',
    'SupersededByBuilder',
    # EPIC 3 modules
    'PropagationSignal',
    'is_anchored',
    'get_anchored_ids',
    # EPIC 4 modules
    'SiblingBuilder',
    'NoOpSiblingBuilder',
    'create_sibling_builder',
    # Legacy exports
    'introspect',
    'get_coverage_stats',
    'SimpleRegistry',
]
