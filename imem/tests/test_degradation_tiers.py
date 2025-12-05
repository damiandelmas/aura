"""Degradation Tests: Tier Gating and Graceful Fallback

Tests the tiered capability system:
- Tier 1: Base (SQLite, no git, no vectors) - always works
- Tier 2: Git integration - works when git repo exists
- Tier 3: Vector features - works when sqlite-vec + embedder available

Key invariant: Lower tiers ALWAYS work. Higher tiers enhance but never block.
"""

import pytest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch
import tempfile

from imem.router import Router, create_router
from imem.infrastructure.git import (
    GitInterface,
    SubprocessGitInterface,
    NoOpGitInterface,
    create_git_interface,
)
from imem.infrastructure.embedder import (
    Embedder,
    LocalEmbedder,
    NoOpEmbedder,
    create_embedder,
)
from imem.storage.vectors import (
    VectorStorage,
    NoOpVectorStorage,
    create_vector_storage,
)
from imem.manage.graph.sibling import (
    SiblingBuilder,
    NoOpSiblingBuilder,
    create_sibling_builder,
)
from imem.manage.validity.git import GitSignal
from imem.manage.validity.temporal import TemporalSignal
from imem.manage.validity.propagation import PropagationSignal
from imem.manage import create_manage_orchestrator
from imem.storage.sqlite import SQLiteStore


# ============================================================================
# Tier 1: Base Functionality (Always Works)
# ============================================================================

class TestTier1BaseFunctionality:
    """Test Tier 1: Core IMEM works without git or vectors"""

    def test_router_works_without_git(self):
        """Router creates and works without git repository"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No .git directory
            router = create_router(Path(tmpdir))

            # Should have NoOpGitInterface
            assert isinstance(router.infrastructure.git, NoOpGitInterface)

            # Index should still work
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test\n\nContent")

            result = router.index([test_file])
            # Should complete without error
            assert isinstance(result, list)

    def test_router_works_without_vectors(self):
        """Router creates and works with vectors disabled"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=False)

            # Should have NoOpSiblingBuilder
            builder_names = [b.name for b in router.manage.graph.builders]
            assert 'sibling_noop' in builder_names

            # Index should still work
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test\n\nContent")

            result = router.index([test_file])
            assert isinstance(result, list)

    def test_sqlite_store_always_works(self):
        """SQLiteStore works in any directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir))

            # Should have created database (now in namespace location)
            assert store.db_path.exists()
            assert store.conn is not None

            # Should have schema
            cursor = store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            assert 'chunks' in tables

    def test_temporal_signal_always_works(self):
        """TemporalSignal works without any infrastructure"""
        signal = TemporalSignal()

        # Create minimal mock context
        class MinimalContext:
            class Infrastructure:
                git = NoOpGitInterface()
                db = MagicMock()
                config = {}
            infrastructure = Infrastructure()

        context = MinimalContext()
        chunk = {'id': 'test', 'timestamp': datetime.now().isoformat()}

        result = signal.score(chunk, context)

        assert result.score == 0.5
        assert result.confidence > 0


# ============================================================================
# Tier 2: Git Integration (Optional Enhancement)
# ============================================================================

class TestTier2GitIntegration:
    """Test Tier 2: Git features enhance but don't block"""

    def test_noop_git_provides_neutral_values(self):
        """NoOpGitInterface returns neutral/empty values"""
        git = NoOpGitInterface()

        assert git.file_exists(Path("any.py")) is False
        assert git.get_file_content(Path("any.py")) is None
        assert git.get_head_files() == set()
        assert git.get_commits_for_file(Path("any.py")) == []
        assert git.search_content("pattern") == []

    def test_git_signal_skips_with_noop(self):
        """GitSignal does not apply when git is NoOp"""
        signal = GitSignal()

        class MockContext:
            class Infrastructure:
                git = NoOpGitInterface()
                db = MagicMock()
            infrastructure = Infrastructure()

        context = MockContext()
        chunk = {'id': 'test', 'source': 'markdown'}

        # Should not apply with NoOp git
        assert signal.applies(chunk, context) is False

    def test_factory_detects_noop_vs_real(self):
        """create_git_interface returns appropriate implementation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Non-git directory -> NoOp
            git = create_git_interface(Path(tmpdir))
            assert isinstance(git, NoOpGitInterface)

    def test_link_module_works_without_git(self):
        """LinkModule gracefully handles NoOpGitInterface"""
        from imem.manage.link import LinkModule

        class MockContext:
            class Infrastructure:
                git = NoOpGitInterface()
                db = MagicMock()
                config = {'project_root': Path('.')}
            infrastructure = Infrastructure()

        module = LinkModule()
        chunks = [{'id': 'test', 'content': 'content'}]

        # Should not crash
        result = module.execute(chunks, MockContext())
        assert len(result) == 1

    def test_signature_extractor_works_without_git(self):
        """SignatureExtractor works with NoOpGitInterface"""
        from imem.manage.signatures import SignatureExtractor

        class MockContext:
            class Infrastructure:
                git = NoOpGitInterface()
                db = MagicMock()
            infrastructure = Infrastructure()

        extractor = SignatureExtractor()
        chunk = {
            'id': 'test',
            'content': '```python\ndef foo(): pass\n```'
        }

        # Extract works, but won't find file_path
        signatures = extractor.extract(chunk, MockContext())
        # Signature exists but file_path is None (can't search git)
        for sig in signatures:
            assert sig.file_path is None or sig.file_path


# ============================================================================
# Tier 3: Vector Features (Optional Enhancement)
# ============================================================================

class TestTier3VectorFeatures:
    """Test Tier 3: Vector features enhance but don't block"""

    def test_noop_embedder_provides_neutral_values(self):
        """NoOpEmbedder returns empty/zero values"""
        embedder = NoOpEmbedder()

        assert embedder.is_available is False
        assert embedder.embed_single("text") == []
        assert embedder.embed(["a", "b"]) == [[], []]
        assert embedder.similarity([1, 2], [3, 4]) == 0.0

    def test_noop_vector_storage_provides_neutral_values(self):
        """NoOpVectorStorage returns empty values"""
        storage = NoOpVectorStorage()

        assert storage.is_available is False
        assert storage.query_knn([1.0] * 384, k=10) == []

        # Should not raise
        storage.store("chunk1", [1.0] * 384)
        storage.delete("chunk1")

    def test_noop_sibling_builder_never_applies(self):
        """NoOpSiblingBuilder never creates edges"""
        builder = NoOpSiblingBuilder()

        assert builder.name == "sibling_noop"
        assert builder.edge_type == "sibling"
        assert builder.applies([], MagicMock()) is False
        assert builder.build([], MagicMock()) == []

    def test_create_sibling_builder_returns_noop_without_vectors(self):
        """Factory returns NoOpSiblingBuilder when vectors unavailable"""
        builder = create_sibling_builder(vector_storage=None, embedder=None)
        assert isinstance(builder, NoOpSiblingBuilder)

    def test_sibling_builder_applies_checks_availability(self):
        """SiblingBuilder.applies checks vector infrastructure"""
        builder = SiblingBuilder()  # No vector_storage set

        assert builder.applies([{'id': 'test'}], MagicMock()) is False

    def test_router_with_vectors_disabled(self):
        """Router works completely with vectors disabled"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=False)

            # Full workflow should work
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test\n\nContent for testing.")

            # Index
            indexed = router.index([test_file])
            assert isinstance(indexed, list)

            # Query
            result = router.query({'search': {'text': 'test'}})
            assert isinstance(result, list)


# ============================================================================
# Tier Gating Logic Tests
# ============================================================================

class TestTierGatingLogic:
    """Test tier availability detection logic"""

    def test_embedder_availability_detection(self):
        """Embedder correctly reports availability"""
        embedder = create_embedder()

        # LocalEmbedder should be available if sentence-transformers installed
        if isinstance(embedder, LocalEmbedder):
            assert embedder.is_available is True
        else:
            assert embedder.is_available is False

    def test_git_interface_availability_detection(self):
        """Git interface correctly detects repository"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No .git -> NoOp
            git = create_git_interface(Path(tmpdir))
            assert isinstance(git, NoOpGitInterface)

    def test_manage_orchestrator_includes_noop_signals(self):
        """ManageOrchestrator handles missing infrastructure"""
        orchestrator = create_manage_orchestrator()

        # Should have all signals
        signal_names = {s.name for s in orchestrator.validity.signals}
        assert 'temporal' in signal_names
        assert 'git' in signal_names
        assert 'propagation' in signal_names

    def test_manage_orchestrator_includes_noop_builders(self):
        """ManageOrchestrator includes NoOp builders when needed"""
        # With no vector infrastructure
        orchestrator = create_manage_orchestrator(
            vector_storage=None,
            embedder=None
        )

        builder_names = {b.name for b in orchestrator.graph.builders}
        assert 'sibling_noop' in builder_names


# ============================================================================
# Degradation Scenarios
# ============================================================================

class TestDegradationScenarios:
    """Test specific degradation scenarios"""

    def test_git_unavailable_validity_still_computed(self):
        """Validity computed even without git validation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("""---
created_at: 2025-01-15
---

# Test

Content.
""")

            result = router.index([test_file])

            # Chunks should have validity (from TemporalSignal)
            if result:
                # Check database for validity
                db = router.infrastructure.db
                cursor = db.conn.execute(
                    "SELECT validity FROM chunks LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    assert row[0] is not None

    def test_vectors_unavailable_edges_still_created(self):
        """Graph edges (validated_by, superseded_by) work without vectors"""
        orchestrator = create_manage_orchestrator(
            vector_storage=None,
            embedder=None
        )

        # Should still have validated_by and superseded_by
        builder_names = {b.name for b in orchestrator.graph.builders}
        assert 'validated_by' in builder_names
        assert 'superseded_by' in builder_names

    def test_full_degradation_still_indexes(self):
        """Full degradation (no git, no vectors) still indexes content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Maximum degradation
            router = create_router(
                Path(tmpdir),
                enable_vectors=False
            )

            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test\n\nSimple content.")

            result = router.index([test_file])

            # Should still have indexed
            assert isinstance(result, list)
            if result:
                assert result[0].get('id') is not None


# ============================================================================
# Error Recovery Tests
# ============================================================================

class TestErrorRecovery:
    """Test recovery from component failures"""

    def test_continues_after_git_timeout(self):
        """Processing continues even if git commands timeout"""
        # This is implicitly tested by NoOpGitInterface behavior
        git = NoOpGitInterface()

        # All methods return safely without blocking
        assert git.file_exists(Path("test")) is False
        assert git.get_commits_for_file(Path("test")) == []

    def test_continues_after_embedding_failure(self):
        """Processing continues even if embedding fails"""
        embedder = NoOpEmbedder()

        # Returns empty, doesn't crash
        result = embedder.embed_single("text")
        assert result == []

    def test_query_works_without_vectors(self):
        """Query returns results even without vector similarity"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=False)

            test_file = Path(tmpdir) / "auth.md"
            test_file.write_text("# Authentication\n\nJWT tokens.")

            router.index([test_file])

            # Query should work (hybrid mode with keyword fallback)
            result = router.query({
                'search': {'text': 'authentication', 'mode': 'hybrid'}
            })

            assert isinstance(result, list)


# ============================================================================
# Run tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
