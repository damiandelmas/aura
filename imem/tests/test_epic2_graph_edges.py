"""EPIC 2: Graph Edges Tests

Tests for edge building between chunks:
- ValidatedByBuilder: narrative → git (proof links)
- SupersededByBuilder: old → new (replacement links)
- Validity override for superseded chunks
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from imem.protocols import Edge
from imem.manage import (
    ValidatedByBuilder,
    SupersededByBuilder,
    EdgeOrchestrator,
    ManageOrchestrator,
    create_manage_orchestrator,
)


class MockContext:
    """Mock IndexContext for testing"""

    class MockInfrastructure:
        class MockDB:
            def __init__(self):
                self.conn = MockConnection()

        def __init__(self):
            self.db = self.MockDB()

    def __init__(self):
        self.infrastructure = self.MockInfrastructure()


class MockConnection:
    """Mock database connection"""

    def __init__(self):
        self.executed = []
        self.rows = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        return self

    def fetchall(self):
        return self.rows

    def commit(self):
        pass


# ============================================================================
# ValidatedByBuilder Tests
# ============================================================================

class TestValidatedByBuilder:
    """Tests for ValidatedByBuilder"""

    def test_name_and_type(self):
        """Test builder name and edge type"""
        builder = ValidatedByBuilder()
        assert builder.name == "validated_by"
        assert builder.edge_type == "validated_by"

    def test_applies_with_valid_chunks(self):
        """Test applies returns True when narrative and git chunks exist"""
        builder = ValidatedByBuilder()
        context = MockContext()

        chunks = [
            {'id': 'narrative1', 'commit_sha': 'abc123', 'source': 'markdown'},
            {'id': 'git1', 'commit_sha': 'abc123', 'source': 'git'},
        ]

        assert builder.applies(chunks, context) is True

    def test_applies_without_git_chunks(self):
        """Test applies returns False when no git chunks"""
        builder = ValidatedByBuilder()
        context = MockContext()

        chunks = [
            {'id': 'narrative1', 'commit_sha': 'abc123', 'source': 'markdown'},
        ]

        assert builder.applies(chunks, context) is False

    def test_applies_without_narrative_sha(self):
        """Test applies returns False when no narrative chunks have commit_sha"""
        builder = ValidatedByBuilder()
        context = MockContext()

        chunks = [
            {'id': 'narrative1', 'source': 'markdown'},  # No commit_sha
            {'id': 'git1', 'commit_sha': 'abc123', 'source': 'git'},
        ]

        assert builder.applies(chunks, context) is False

    def test_build_creates_edges(self):
        """Test build creates validated_by edges"""
        builder = ValidatedByBuilder()
        context = MockContext()

        chunks = [
            {
                'id': 'narrative1',
                'commit_sha': 'abc123',
                'source': 'markdown',
                'content': 'Modified src/auth.py'
            },
            {
                'id': 'git1',
                'commit_sha': 'abc123',
                'source': 'git',
                'file_path': 'src/auth.py'
            },
        ]

        edges = builder.build(chunks, context)

        assert len(edges) == 1
        assert edges[0].from_id == 'narrative1'
        assert edges[0].to_id == 'git1'
        assert edges[0].type == 'validated_by'
        assert edges[0].weight > 0

    def test_no_edges_when_sha_mismatch(self):
        """Test no edges created when commit_sha doesn't match"""
        builder = ValidatedByBuilder()
        context = MockContext()

        chunks = [
            {'id': 'narrative1', 'commit_sha': 'abc123', 'source': 'markdown', 'content': ''},
            {'id': 'git1', 'commit_sha': 'def456', 'source': 'git', 'file_path': ''},
        ]

        edges = builder.build(chunks, context)
        assert len(edges) == 0


# ============================================================================
# SupersededByBuilder Tests
# ============================================================================

class TestSupersededByBuilder:
    """Tests for SupersededByBuilder"""

    def test_name_and_type(self):
        """Test builder name and edge type"""
        builder = SupersededByBuilder()
        assert builder.name == "superseded_by"
        assert builder.edge_type == "superseded_by"

    def test_applies_with_timestamped_chunks(self):
        """Test applies returns True when multiple timestamped chunks exist"""
        builder = SupersededByBuilder()
        context = MockContext()

        chunks = [
            {'id': 'c1', 'timestamp': '2025-01-01'},
            {'id': 'c2', 'timestamp': '2025-01-15'},
        ]

        assert builder.applies(chunks, context) is True

    def test_applies_with_single_chunk(self):
        """Test applies returns False with only one chunk"""
        builder = SupersededByBuilder()
        context = MockContext()

        chunks = [
            {'id': 'c1', 'timestamp': '2025-01-01'},
        ]

        assert builder.applies(chunks, context) is False

    def test_build_creates_supersession_edges(self):
        """Test build creates superseded_by edges for old chunks"""
        builder = SupersededByBuilder()
        context = MockContext()

        # Same directory, same section_type, >7 days apart
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        new_date = datetime.now().isoformat()

        chunks = [
            {
                'id': 'old_chunk',
                'file_path': 'context/design/auth.md',
                'section_type': 'decisions',
                'timestamp': old_date
            },
            {
                'id': 'new_chunk',
                'file_path': 'context/design/auth_v2.md',
                'section_type': 'decisions',
                'timestamp': new_date
            },
        ]

        edges = builder.build(chunks, context)

        assert len(edges) == 1
        assert edges[0].from_id == 'old_chunk'
        assert edges[0].to_id == 'new_chunk'
        assert edges[0].type == 'superseded_by'

    def test_no_supersession_within_7_days(self):
        """Test no supersession when chunks are <7 days apart"""
        builder = SupersededByBuilder()
        context = MockContext()

        # Same directory, same section_type, only 3 days apart
        old_date = (datetime.now() - timedelta(days=3)).isoformat()
        new_date = datetime.now().isoformat()

        chunks = [
            {
                'id': 'old_chunk',
                'file_path': 'context/design/auth.md',
                'section_type': 'decisions',
                'timestamp': old_date
            },
            {
                'id': 'new_chunk',
                'file_path': 'context/design/auth.md',
                'section_type': 'decisions',
                'timestamp': new_date
            },
        ]

        edges = builder.build(chunks, context)
        assert len(edges) == 0

    def test_no_supersession_across_groups(self):
        """Test no supersession between different groups"""
        builder = SupersededByBuilder()
        context = MockContext()

        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        new_date = datetime.now().isoformat()

        chunks = [
            {
                'id': 'old_chunk',
                'file_path': 'context/design/auth.md',  # Different directory
                'section_type': 'decisions',
                'timestamp': old_date
            },
            {
                'id': 'new_chunk',
                'file_path': 'context/develop/auth.md',  # Different directory
                'section_type': 'decisions',
                'timestamp': new_date
            },
        ]

        edges = builder.build(chunks, context)
        assert len(edges) == 0


# ============================================================================
# EdgeOrchestrator Tests
# ============================================================================

class TestEdgeOrchestrator:
    """Tests for EdgeOrchestrator"""

    def test_orchestrator_with_builders(self):
        """Test orchestrator runs all builders"""
        orchestrator = EdgeOrchestrator(
            builders=[
                ValidatedByBuilder(),
                SupersededByBuilder(),
            ]
        )

        context = MockContext()
        chunks = [
            {'id': 'c1', 'timestamp': '2025-01-01', 'source': 'markdown'},
        ]

        # Should not crash even with minimal chunks
        edges = orchestrator.build_edges(chunks, context)
        assert isinstance(edges, list)


# ============================================================================
# Integration Tests
# ============================================================================

class TestManageOrchestratorIntegration:
    """Integration tests for ManageOrchestrator with graph builders"""

    def test_factory_creates_with_builders(self):
        """Test factory creates orchestrator with real builders"""
        orchestrator = create_manage_orchestrator()

        # Should have real graph orchestrator, not NoOp
        # EPIC 4 adds SiblingBuilder (or NoOpSiblingBuilder)
        assert len(orchestrator.graph.builders) >= 2

        builder_names = {b.name for b in orchestrator.graph.builders}
        assert 'validated_by' in builder_names
        assert 'superseded_by' in builder_names
        # EPIC 4: sibling or sibling_noop should be present
        assert any('sibling' in name for name in builder_names)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
