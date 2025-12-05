"""Tests for EPIC 4: sqlite-vec Vectors

Tests cover:
1. Embedder - local sentence-transformers embedding
2. VectorStorage - sqlite-vec wrapper with graceful degradation
3. SiblingBuilder - semantic similarity edges

Note: These tests work regardless of sqlite-vec availability.
Graceful degradation is a core feature - tests verify both paths.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


# ============================================================================
# Embedder Tests
# ============================================================================

class TestEmbedder:
    """Test LocalEmbedder and NoOpEmbedder"""

    def test_create_embedder_returns_local_when_available(self):
        """create_embedder should return LocalEmbedder when sentence-transformers available"""
        from imem.infrastructure.embedder import create_embedder, LocalEmbedder

        embedder = create_embedder()
        assert isinstance(embedder, LocalEmbedder)
        assert embedder.dimension == 384

    def test_embedder_is_available(self):
        """Embedder should report availability correctly"""
        from imem.infrastructure.embedder import create_embedder

        embedder = create_embedder()
        assert embedder.is_available is True

    def test_embed_single(self):
        """embed_single should return vector of correct dimension"""
        from imem.infrastructure.embedder import create_embedder

        embedder = create_embedder()
        vec = embedder.embed_single("Hello world")
        assert len(vec) == 384
        assert all(isinstance(x, float) for x in vec)

    def test_embed_batch(self):
        """embed should batch process texts efficiently"""
        from imem.infrastructure.embedder import create_embedder

        embedder = create_embedder()
        texts = ["Hello world", "Test sentence", "Another example"]
        vecs = embedder.embed(texts)

        assert len(vecs) == 3
        assert all(len(v) == 384 for v in vecs)

    def test_similarity_computation(self):
        """similarity should compute cosine similarity correctly"""
        from imem.infrastructure.embedder import create_embedder

        embedder = create_embedder()
        vec1 = embedder.embed_single("cat")
        vec2 = embedder.embed_single("dog")
        vec3 = embedder.embed_single("computer programming")

        # Cat and dog should be more similar than cat and computer
        sim_cat_dog = embedder.similarity(vec1, vec2)
        sim_cat_computer = embedder.similarity(vec1, vec3)

        assert 0 <= sim_cat_dog <= 1
        assert 0 <= sim_cat_computer <= 1
        assert sim_cat_dog > sim_cat_computer

    def test_embedding_cache(self):
        """Embedder should cache embeddings"""
        from imem.infrastructure.embedder import create_embedder

        embedder = create_embedder()

        # Embed same text twice
        _ = embedder.embed_single("cached text")
        cache_size_after_first = len(embedder._cache)

        _ = embedder.embed_single("cached text")
        cache_size_after_second = len(embedder._cache)

        # Should not add duplicate
        assert cache_size_after_first == cache_size_after_second

    def test_noop_embedder(self):
        """NoOpEmbedder should return empty vectors"""
        from imem.infrastructure.embedder import NoOpEmbedder

        embedder = NoOpEmbedder()
        assert embedder.is_available is False
        assert embedder.embed_single("test") == []
        assert embedder.embed(["a", "b"]) == [[], []]
        assert embedder.similarity([1, 2], [3, 4]) == 0.0


# ============================================================================
# VectorStorage Tests
# ============================================================================

class TestVectorStorage:
    """Test VectorStorage with graceful degradation"""

    def test_noop_vector_storage(self):
        """NoOpVectorStorage should provide neutral behavior"""
        from imem.storage.vectors import NoOpVectorStorage

        storage = NoOpVectorStorage()
        assert storage.is_available is False
        assert storage.query_knn([1.0] * 384, k=10) == []

        # Should not raise
        storage.store("chunk1", [1.0] * 384)
        storage.delete("chunk1")

    def test_create_vector_storage_graceful_degradation(self):
        """create_vector_storage should degrade gracefully without sqlite-vec"""
        from imem.infrastructure.embedder import create_embedder
        from imem.storage.vectors import create_vector_storage, NoOpVectorStorage
        from imem.storage.sqlite import SQLiteStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteStore(Path(tmpdir))
            embedder = create_embedder()

            storage = create_vector_storage(db, embedder)

            # Without sqlite-vec, should get NoOpVectorStorage
            # (this test assumes sqlite-vec is not installed)
            if not storage.is_available:
                assert isinstance(storage, NoOpVectorStorage)


# ============================================================================
# SiblingBuilder Tests
# ============================================================================

class TestSiblingBuilder:
    """Test SiblingBuilder with and without vectors"""

    def test_noop_sibling_builder(self):
        """NoOpSiblingBuilder should never apply"""
        from imem.manage.graph.sibling import NoOpSiblingBuilder

        builder = NoOpSiblingBuilder()
        assert builder.name == "sibling_noop"
        assert builder.edge_type == "sibling"
        assert builder.applies([], MagicMock()) is False
        assert builder.build([], MagicMock()) == []

    def test_create_sibling_builder_without_vectors(self):
        """create_sibling_builder should return NoOp when vectors unavailable"""
        from imem.manage.graph.sibling import create_sibling_builder, NoOpSiblingBuilder

        builder = create_sibling_builder(vector_storage=None, embedder=None)
        assert isinstance(builder, NoOpSiblingBuilder)

    def test_sibling_builder_applies_requires_vectors(self):
        """SiblingBuilder.applies should return False without vector infrastructure"""
        from imem.manage.graph.sibling import SiblingBuilder

        builder = SiblingBuilder()  # No vectors
        chunks = [{"id": "1", "content": "test"}]
        context = MagicMock()

        assert builder.applies(chunks, context) is False

    def test_sibling_builder_pair_normalization(self):
        """SiblingBuilder should normalize pairs for bidirectional edges"""
        from imem.manage.graph.sibling import SiblingBuilder

        builder = SiblingBuilder()

        # Test sorted normalization
        assert builder._normalize_pair("a", "b") == ("a", "b")
        assert builder._normalize_pair("b", "a") == ("a", "b")
        assert builder._normalize_pair("z", "a") == ("a", "z")


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test full integration with Router"""

    def test_router_creates_with_vector_infrastructure(self):
        """Router should include SiblingBuilder (NoOp if no sqlite-vec)"""
        from imem.router import create_router

        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=True)

            # Check manage orchestrator has sibling builder
            builder_names = [b.name for b in router.manage.graph.builders]
            assert 'validated_by' in builder_names
            assert 'superseded_by' in builder_names
            # Either 'sibling' or 'sibling_noop' depending on sqlite-vec
            assert any('sibling' in name for name in builder_names)

    def test_router_respects_enable_vectors_false(self):
        """Router should skip vector infrastructure when disabled"""
        from imem.router import create_router

        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=False)

            # Should have NoOpSiblingBuilder
            builder_names = [b.name for b in router.manage.graph.builders]
            assert 'sibling_noop' in builder_names

    def test_manage_orchestrator_factory(self):
        """create_manage_orchestrator should include SiblingBuilder"""
        from imem.manage import create_manage_orchestrator

        orchestrator = create_manage_orchestrator()

        builder_names = [b.name for b in orchestrator.graph.builders]
        assert 'validated_by' in builder_names
        assert 'superseded_by' in builder_names
        assert any('sibling' in name for name in builder_names)


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
