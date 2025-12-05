"""EPIC 3: Validity Propagation Tests

Tests for three-phase validity computation:
- Anchored/unanchored classification
- PropagationSignal with BFS traversal
- Three-phase ManageOrchestrator flow
"""

import pytest
from datetime import datetime, timedelta

from imem.protocols import SignalResult, Edge
from imem.manage import (
    create_manage_orchestrator,
    ManageOrchestrator,
    ValidityComputer,
    PropagationSignal,
    TemporalSignal,
    GitSignal,
    is_anchored,
    get_anchored_ids,
)


# ============================================================================
# Mock Infrastructure
# ============================================================================

class MockConnection:
    """Mock database connection"""

    def __init__(self):
        self.executed = []
        self.rows = []
        self._signatures = {}  # chunk_id -> list of signatures
        self._chunks = {}  # chunk_id -> chunk dict
        self._edges = []  # list of (from_id, to_id, type, weight)

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

        # Handle signature queries
        if 'chunk_signatures' in sql and 'COUNT' in sql:
            chunk_id = params[0] if params else None
            count = sum(1 for s in self._signatures.get(chunk_id, [])
                       if s.get('file_path') is not None)
            self.rows = [(count,)]
        elif 'chunk_signatures' in sql and 'SELECT' in sql:
            chunk_id = params[0] if params else None
            sigs = self._signatures.get(chunk_id, [])
            self.rows = [
                (s['chunk_id'], s['content'], s.get('language'),
                 s.get('file_path'), s.get('signature_hash'))
                for s in sigs
            ]
        # Handle edge queries
        elif 'FROM edges WHERE from_id' in sql:
            chunk_id = params[0] if params else None
            self.rows = [
                (e[1], e[2], e[3]) for e in self._edges
                if e[0] == chunk_id
            ]
        elif 'FROM edges WHERE to_id' in sql:
            chunk_id = params[0] if params else None
            self.rows = [
                (e[0], e[2], e[3]) for e in self._edges
                if e[1] == chunk_id
            ]
        # Handle validity queries
        elif 'validity FROM chunks' in sql:
            chunk_id = params[0] if params else None
            chunk = self._chunks.get(chunk_id, {})
            self.rows = [(chunk.get('validity', 0.5),)]
        # Handle INSERT/UPDATE
        elif 'INSERT' in sql or 'UPDATE' in sql:
            self.rows = []

        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def commit(self):
        pass


class MockDB:
    def __init__(self):
        self.conn = MockConnection()


class MockGit:
    """Mock GitInterface"""

    def __init__(self, exists=True, content=""):
        self._exists = exists
        self._content = content

    def file_exists(self, path):
        return self._exists

    def get_file_content(self, path):
        return self._content if self._exists else None

    def get_head_files(self):
        return set()


class MockInfrastructure:
    def __init__(self):
        self.db = MockDB()
        self.git = MockGit()


class MockContext:
    """Mock IndexContext for testing"""

    def __init__(self):
        self.infrastructure = MockInfrastructure()


# ============================================================================
# is_anchored Tests
# ============================================================================

class TestIsAnchored:
    """Tests for is_anchored function"""

    def test_anchored_with_file_path(self):
        """Test chunk with signature containing file_path is anchored"""
        context = MockContext()
        context.infrastructure.db.conn._signatures = {
            'chunk1': [
                {'chunk_id': 'chunk1', 'content': 'code', 'file_path': 'src/auth.py'}
            ]
        }

        assert is_anchored('chunk1', context) is True

    def test_not_anchored_without_file_path(self):
        """Test chunk with signature but no file_path is not anchored"""
        context = MockContext()
        context.infrastructure.db.conn._signatures = {
            'chunk1': [
                {'chunk_id': 'chunk1', 'content': 'code', 'file_path': None}
            ]
        }

        assert is_anchored('chunk1', context) is False

    def test_not_anchored_without_signatures(self):
        """Test chunk without signatures is not anchored"""
        context = MockContext()
        context.infrastructure.db.conn._signatures = {}

        assert is_anchored('chunk1', context) is False

    def test_anchored_with_mixed_signatures(self):
        """Test chunk is anchored if ANY signature has file_path"""
        context = MockContext()
        context.infrastructure.db.conn._signatures = {
            'chunk1': [
                {'chunk_id': 'chunk1', 'content': 'code1', 'file_path': None},
                {'chunk_id': 'chunk1', 'content': 'code2', 'file_path': 'src/auth.py'},
            ]
        }

        assert is_anchored('chunk1', context) is True


class TestGetAnchoredIds:
    """Tests for get_anchored_ids function"""

    def test_returns_anchored_ids(self):
        """Test returns set of anchored chunk IDs"""
        context = MockContext()
        context.infrastructure.db.conn._signatures = {
            'anchored1': [{'chunk_id': 'anchored1', 'content': 'x', 'file_path': 'a.py'}],
            'anchored2': [{'chunk_id': 'anchored2', 'content': 'y', 'file_path': 'b.py'}],
        }

        chunks = [
            {'id': 'anchored1'},
            {'id': 'anchored2'},
            {'id': 'unanchored'},
        ]

        result = get_anchored_ids(chunks, context)

        assert result == {'anchored1', 'anchored2'}


# ============================================================================
# PropagationSignal Tests
# ============================================================================

class TestPropagationSignal:
    """Tests for PropagationSignal"""

    def test_name(self):
        """Test signal name"""
        signal = PropagationSignal()
        assert signal.name == "propagation"

    def test_applies_to_unanchored(self):
        """Test signal applies to unanchored chunks"""
        signal = PropagationSignal()
        signal.set_anchored_ids({'anchored1'})

        context = MockContext()
        chunk = {'id': 'unanchored1', 'source': 'markdown'}

        assert signal.applies(chunk, context) is True

    def test_not_applies_to_anchored(self):
        """Test signal does not apply to anchored chunks"""
        signal = PropagationSignal()
        signal.set_anchored_ids({'anchored1'})

        context = MockContext()
        chunk = {'id': 'anchored1', 'source': 'markdown'}

        assert signal.applies(chunk, context) is False

    def test_not_applies_to_git_source(self):
        """Test signal does not apply to git-sourced chunks"""
        signal = PropagationSignal()
        signal.set_anchored_ids(set())

        context = MockContext()
        chunk = {'id': 'git1', 'source': 'git'}

        assert signal.applies(chunk, context) is False

    def test_score_with_no_neighbors(self):
        """Test score returns 0.5 when no anchored neighbors"""
        signal = PropagationSignal()
        signal.set_anchored_ids(set())

        context = MockContext()
        chunk = {'id': 'isolated'}

        result = signal.score(chunk, context)

        assert result.score == 0.5
        assert result.confidence == 0.3  # NO_NEIGHBORS_CONFIDENCE
        assert 'no anchored neighbors' in result.reason.lower()

    def test_score_with_direct_neighbor(self):
        """Test score propagates from direct anchored neighbor"""
        signal = PropagationSignal()
        signal.set_anchored_ids({'anchored1'})

        context = MockContext()
        # Set up edge: unanchored -> anchored
        context.infrastructure.db.conn._edges = [
            ('unanchored', 'anchored1', 'validated_by', 1.0)
        ]
        # Set anchored validity to 0.9
        context.infrastructure.db.conn._chunks = {
            'anchored1': {'validity': 0.9}
        }

        chunk = {'id': 'unanchored'}
        result = signal.score(chunk, context)

        # Score should be close to 0.9 (the anchored neighbor's validity)
        # with hop_decay = 1/(1+1) = 0.5
        # expected = 0.9 * 1.0 * 0.5 / (1.0 * 0.5) = 0.9
        assert result.score == pytest.approx(0.9, rel=0.01)
        assert result.confidence == 0.7  # PROPAGATION_CONFIDENCE

    def test_score_with_hop_decay(self):
        """Test hop decay reduces distant neighbor influence"""
        signal = PropagationSignal()
        signal.set_anchored_ids({'anchored1', 'anchored2'})

        context = MockContext()
        # Set up chain: unanchored -> middle -> anchored1 (2 hops)
        # and: unanchored -> anchored2 (1 hop)
        context.infrastructure.db.conn._edges = [
            ('unanchored', 'middle', 'sibling', 1.0),
            ('middle', 'anchored1', 'validated_by', 1.0),
            ('unanchored', 'anchored2', 'validated_by', 1.0),
        ]
        context.infrastructure.db.conn._chunks = {
            'anchored1': {'validity': 0.9},  # 2 hops away
            'anchored2': {'validity': 0.5},  # 1 hop away
        }

        chunk = {'id': 'unanchored'}
        result = signal.score(chunk, context)

        # anchored2 (1 hop): weight = 1.0 * 1/(1+1) = 0.5, contrib = 0.5 * 0.5 = 0.25
        # anchored1 (2 hops): weight = 1.0 * 1/(1+2) = 0.333, contrib = 0.9 * 0.333 = 0.3
        # total = (0.25 + 0.3) / (0.5 + 0.333) = 0.55 / 0.833 ≈ 0.66
        assert 0.55 < result.score < 0.75  # Closer neighbor (0.5) has more influence

    def test_skips_superseded_by_edges(self):
        """Test BFS skips superseded_by edges (they override, don't propagate)"""
        signal = PropagationSignal()
        signal.set_anchored_ids({'anchored1'})

        context = MockContext()
        # superseded_by edge should NOT be traversed
        context.infrastructure.db.conn._edges = [
            ('unanchored', 'anchored1', 'superseded_by', 1.0)
        ]
        context.infrastructure.db.conn._chunks = {
            'anchored1': {'validity': 0.9}
        }

        chunk = {'id': 'unanchored'}
        result = signal.score(chunk, context)

        # Should not find anchored1 since we skip superseded_by
        assert result.score == 0.5


# ============================================================================
# ValidityComputer Tests
# ============================================================================

class TestValidityComputerFiltering:
    """Tests for ValidityComputer signal filtering"""

    def test_compute_all_signals(self):
        """Test compute uses all signals when no filter"""
        computer = ValidityComputer(signals=[
            TemporalSignal(),
        ])

        context = MockContext()
        chunk = {'id': 'test', 'timestamp': datetime.now().isoformat()}

        result = computer.compute(chunk, context)

        assert 'score' in result
        assert 'git_status' in result

    def test_compute_with_signal_filter(self):
        """Test compute filters signals by name"""
        computer = ValidityComputer(signals=[
            TemporalSignal(),
            PropagationSignal(),
        ])

        # Mark as unanchored
        computer.signals[1].set_anchored_ids(set())

        context = MockContext()
        chunk = {'id': 'test', 'timestamp': datetime.now().isoformat()}

        # Only use temporal
        result = computer.compute(chunk, context, signal_names=['temporal'])

        assert 'score' in result


# ============================================================================
# Factory Tests
# ============================================================================

class TestCreateManageOrchestrator:
    """Tests for create_manage_orchestrator factory"""

    def test_includes_propagation_signal(self):
        """Test factory creates orchestrator with PropagationSignal"""
        orchestrator = create_manage_orchestrator()

        signal_names = {s.name for s in orchestrator.validity.signals}
        assert 'propagation' in signal_names
        assert 'temporal' in signal_names
        assert 'git' in signal_names

    def test_three_signals(self):
        """Test factory creates ValidityComputer with 3 signals"""
        orchestrator = create_manage_orchestrator()

        assert len(orchestrator.validity.signals) == 3


# ============================================================================
# Integration Test Placeholder
# ============================================================================

class TestThreePhaseFlow:
    """Integration tests for three-phase flow"""

    def test_three_phase_flow_smoke(self):
        """Smoke test: three-phase flow runs without error"""
        orchestrator = create_manage_orchestrator()

        # Verify structure
        assert hasattr(orchestrator, 'enrich')
        assert orchestrator.validity is not None
        assert orchestrator.graph is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
