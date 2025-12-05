"""EPIC 5: Centrality & Ranking Tests

Tests for:
- CentralityComputer and signals (edge_count, cross_phase, sibling_density)
- RankingModule with formula: rank = validity × w + centrality × w + recency × w
- Integration with Router query flow
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from imem.router import create_router, Router
from imem.storage.sqlite import SQLiteStore
from imem.context import Infrastructure, QueryContext

# Centrality imports
from imem.retrieve.centrality import (
    CentralityComputer,
    NoOpCentralityComputer,
    create_centrality_computer,
    CentralitySignal,
    CentralityResult,
    NoOpCentralitySignal,
    DEFAULT_WEIGHTS,
)
from imem.retrieve.centrality.edge_count import EdgeCountSignal
from imem.retrieve.centrality.cross_phase import CrossPhaseSignal
from imem.retrieve.centrality.sibling_density import SiblingDensitySignal, NoOpSiblingDensitySignal

# Ranking imports
from imem.retrieve.processors.ranking import (
    RankingModule,
    NoOpRankingModule,
    compute_rank,
    compute_recency,
    DEFAULT_RANKING_WEIGHTS,
)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SQLiteStore(Path(tmpdir))
        yield db


@pytest.fixture
def temp_db_with_data(temp_db):
    """Create database with test chunks and edges"""
    db = temp_db

    # Insert test chunks
    db.conn.execute('''
        INSERT INTO chunks (id, content, file_path, phase, section_type, validity, timestamp)
        VALUES
            ('central', 'Central hub chunk', '/test/hub.md', 'develop', 'decisions', 0.9, '2025-12-04'),
            ('ref1', 'References central', '/test/ref1.md', 'design', 'patterns', 0.7, '2025-11-15'),
            ('ref2', 'Also references central', '/test/ref2.md', 'document', 'context', 0.5, '2025-10-01'),
            ('isolated', 'No references', '/test/isolated.md', 'develop', 'notes', 0.3, '2024-01-01')
    ''')

    # Insert edges (central is referenced by ref1 and ref2)
    db.conn.execute('''
        INSERT INTO edges (from_id, to_id, type, weight) VALUES
            ('ref1', 'central', 'validated_by', 0.9),
            ('ref2', 'central', 'superseded_by', 0.7),
            ('ref1', 'ref2', 'sibling', 0.8)
    ''')
    db.conn.commit()

    return db


@pytest.fixture
def mock_context(temp_db_with_data):
    """Create mock QueryContext for testing"""
    class MinimalInfra:
        def __init__(self, db):
            self.db = db
            self.git = None
            self.config = {}

    return QueryContext(
        infrastructure=MinimalInfra(temp_db_with_data),
        query={},
        results=[],
        metadata={},
    )


# ============================================================================
# EdgeCountSignal Tests
# ============================================================================

class TestEdgeCountSignal:
    """Tests for EdgeCountSignal"""

    def test_name(self, temp_db):
        signal = EdgeCountSignal(temp_db)
        assert signal.name == "edge_count"

    def test_applies_with_id(self, temp_db):
        signal = EdgeCountSignal(temp_db)
        assert signal.applies({'id': 'chunk1'}, None) is True

    def test_applies_without_id(self, temp_db):
        signal = EdgeCountSignal(temp_db)
        assert signal.applies({}, None) is False

    def test_score_central_chunk(self, temp_db_with_data, mock_context):
        """Central chunk has 2 inbound edges"""
        signal = EdgeCountSignal(temp_db_with_data)
        result = signal.score({'id': 'central'}, mock_context)

        assert result.score == 0.2  # 2 edges / max_edges(10) = 0.2
        assert result.confidence == 0.8
        assert "2 inbound edges" in result.reason

    def test_score_isolated_chunk(self, temp_db_with_data, mock_context):
        """Isolated chunk has 0 inbound edges"""
        signal = EdgeCountSignal(temp_db_with_data)
        result = signal.score({'id': 'isolated'}, mock_context)

        assert result.score == 0.0
        assert "0 inbound edges" in result.reason

    def test_score_normalization_cap(self, temp_db_with_data, mock_context):
        """Score is capped at 1.0"""
        signal = EdgeCountSignal(temp_db_with_data, max_edges=2)
        result = signal.score({'id': 'central'}, mock_context)

        assert result.score == 1.0  # 2 edges / 2 max = 1.0


# ============================================================================
# CrossPhaseSignal Tests
# ============================================================================

class TestCrossPhaseSignal:
    """Tests for CrossPhaseSignal"""

    def test_name(self, temp_db):
        signal = CrossPhaseSignal(temp_db)
        assert signal.name == "cross_phase"

    def test_applies_with_id(self, temp_db):
        signal = CrossPhaseSignal(temp_db)
        assert signal.applies({'id': 'chunk1'}, None) is True

    def test_score_multi_phase(self, temp_db_with_data, mock_context):
        """Central chunk is referenced from design and document phases"""
        signal = CrossPhaseSignal(temp_db_with_data)
        result = signal.score({'id': 'central'}, mock_context)

        # Referenced from 2 phases (design, document)
        assert result.score == 0.2
        assert "2 phases" in result.reason

    def test_score_single_phase(self, temp_db_with_data, mock_context):
        """Chunk referenced from only one phase"""
        signal = CrossPhaseSignal(temp_db_with_data)
        result = signal.score({'id': 'ref2'}, mock_context)

        # Only has sibling edge from ref1 (design phase)
        assert result.score <= 0.2

    def test_score_isolated(self, temp_db_with_data, mock_context):
        """Isolated chunk has no cross-phase references"""
        signal = CrossPhaseSignal(temp_db_with_data)
        result = signal.score({'id': 'isolated'}, mock_context)

        assert result.score == 0.0


# ============================================================================
# SiblingDensitySignal Tests
# ============================================================================

class TestSiblingDensitySignal:
    """Tests for SiblingDensitySignal and NoOp variant"""

    def test_noop_name(self):
        signal = NoOpSiblingDensitySignal()
        assert signal.name == "sibling_density"

    def test_noop_never_applies(self):
        signal = NoOpSiblingDensitySignal()
        assert signal.applies({'id': 'chunk1'}, None) is False

    def test_noop_returns_neutral(self):
        signal = NoOpSiblingDensitySignal()
        result = signal.score({'id': 'chunk1'}, None)

        assert result.score == 0.5
        assert result.confidence == 0.0
        assert "Tier 3" in result.reason


# ============================================================================
# CentralityComputer Tests
# ============================================================================

class TestCentralityComputer:
    """Tests for CentralityComputer orchestrator"""

    def test_default_weights(self):
        assert DEFAULT_WEIGHTS['edge_count'] == 0.5
        assert DEFAULT_WEIGHTS['cross_phase'] == 0.3
        assert DEFAULT_WEIGHTS['sibling_density'] == 0.2

    def test_noop_computer(self):
        computer = NoOpCentralityComputer()
        result = computer.compute({'id': 'chunk1'}, None)
        assert result == 0.5

    def test_compute_with_signals(self, temp_db_with_data, mock_context):
        """CentralityComputer aggregates signals"""
        computer = CentralityComputer(
            signals=[EdgeCountSignal(temp_db_with_data)]
        )

        result = computer.compute({'id': 'central'}, mock_context)
        assert 0.0 <= result <= 1.0

    def test_factory_creates_signals(self, temp_db):
        """create_centrality_computer creates appropriate signals"""
        computer = create_centrality_computer(db=temp_db)

        signal_names = [s.name for s in computer.signals]
        assert 'edge_count' in signal_names
        assert 'cross_phase' in signal_names
        assert 'sibling_density' in signal_names  # NoOp version


# ============================================================================
# RankingModule Tests
# ============================================================================

class TestComputeRecency:
    """Tests for recency computation"""

    def test_today_is_maximum(self):
        today = datetime.now().strftime('%Y-%m-%d')
        recency = compute_recency(today)
        assert recency >= 0.95  # Very close to 1.0

    def test_old_date_decays(self):
        old = '2024-01-01'
        recency = compute_recency(old)
        assert recency < 0.2  # Significantly decayed

    def test_none_returns_neutral(self):
        assert compute_recency(None) == 0.5

    def test_invalid_format_returns_neutral(self):
        assert compute_recency('not-a-date') == 0.5

    def test_half_life_behavior(self):
        """30 days ago should be approximately 0.5"""
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        recency = compute_recency(thirty_days_ago, half_life_days=30)
        assert 0.4 <= recency <= 0.6


class TestComputeRank:
    """Tests for rank formula"""

    def test_default_weights(self):
        assert DEFAULT_RANKING_WEIGHTS['validity'] == 0.4
        assert DEFAULT_RANKING_WEIGHTS['centrality'] == 0.3
        assert DEFAULT_RANKING_WEIGHTS['recency'] == 0.3

    def test_formula_calculation(self):
        # rank = 0.8*0.4 + 0.6*0.3 + 0.9*0.3 = 0.32 + 0.18 + 0.27 = 0.77
        rank = compute_rank(0.8, 0.6, 0.9)
        assert abs(rank - 0.77) < 0.01

    def test_all_zeros(self):
        rank = compute_rank(0.0, 0.0, 0.0)
        assert rank == 0.0

    def test_all_ones(self):
        rank = compute_rank(1.0, 1.0, 1.0)
        assert rank == 1.0

    def test_custom_weights(self):
        # All validity: 0.8*1.0 = 0.8
        rank = compute_rank(0.8, 0.6, 0.9, weights={'validity': 1.0, 'centrality': 0.0, 'recency': 0.0})
        assert abs(rank - 0.8) < 0.01


class TestRankingModule:
    """Tests for RankingModule"""

    def test_rank_sorts_by_score(self):
        module = RankingModule()
        chunks = [
            {'id': 'low', 'validity': 0.2, 'centrality': 0.2, 'timestamp': '2024-01-01'},
            {'id': 'high', 'validity': 0.9, 'centrality': 0.8, 'timestamp': '2025-12-04'},
            {'id': 'mid', 'validity': 0.5, 'centrality': 0.5, 'timestamp': '2025-06-01'},
        ]

        ranked = module.rank(chunks, None)

        assert ranked[0]['id'] == 'high'
        assert ranked[1]['id'] == 'mid'
        assert ranked[2]['id'] == 'low'

    def test_rank_field_populated(self):
        module = RankingModule()
        chunks = [{'id': 'c1', 'validity': 0.5, 'centrality': 0.5, 'timestamp': '2025-12-01'}]

        ranked = module.rank(chunks, None)

        assert 'rank' in ranked[0]
        assert 'recency' in ranked[0]
        assert 0.0 <= ranked[0]['rank'] <= 1.0

    def test_noop_ranking(self):
        module = NoOpRankingModule()
        chunks = [{'id': 'c1'}, {'id': 'c2'}]

        ranked = module.rank(chunks, None)

        assert ranked == chunks  # Unchanged


# ============================================================================
# Router Integration Tests
# ============================================================================

class TestRouterCentralityIntegration:
    """Tests for Router with EPIC 5 centrality & ranking"""

    def test_router_has_centrality(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=False)
            assert router.centrality is not None
            assert isinstance(router.centrality, CentralityComputer)

    def test_router_has_ranking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=False)
            assert router.ranking is not None
            assert isinstance(router.ranking, RankingModule)

    def test_centrality_signals_configured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=False)

            signal_names = [s.name for s in router.centrality.signals]
            assert 'edge_count' in signal_names
            assert 'cross_phase' in signal_names


# ============================================================================
# Philosophy Validation Tests
# ============================================================================

class TestPhilosophyGuardRails:
    """Tests ensuring validity ≠ centrality (graph-epistemology.md)"""

    def test_valid_but_isolated(self, temp_db_with_data, mock_context):
        """High validity + low centrality = true but peripheral"""
        # isolated chunk: validity=0.3, 0 inbound edges
        edge_signal = EdgeCountSignal(temp_db_with_data)
        centrality_result = edge_signal.score({'id': 'isolated'}, mock_context)

        # Isolated has low centrality (0.0)
        assert centrality_result.score == 0.0

        # But validity is independent (would be computed by MANAGE, not here)
        # The test validates the separation exists

    def test_central_but_outdated(self, temp_db_with_data, mock_context):
        """High centrality + low validity = important but stale"""
        edge_signal = EdgeCountSignal(temp_db_with_data)
        centrality_result = edge_signal.score({'id': 'central'}, mock_context)

        # Central has high(er) centrality (0.2)
        assert centrality_result.score > 0.0

        # Validity is stored separately in chunks table
        # This tests they don't conflate

    def test_centrality_not_truthfulness(self):
        """Ranking formula combines but doesn't conflate validity and centrality"""
        # A chunk with low validity but high centrality still ranks lower
        # than a valid central chunk

        outdated_central = compute_rank(validity=0.2, centrality=0.8, recency=0.9)
        valid_central = compute_rank(validity=0.9, centrality=0.8, recency=0.9)

        # Valid chunk ranks higher despite same centrality
        assert valid_central > outdated_central
