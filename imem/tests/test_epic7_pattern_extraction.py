"""Tests for EPIC 7: Pattern Extraction Service

Tests the pattern extraction pipeline:
- PatternClient and NoOpPatternClient
- PatternExtractor and NoOpPatternExtractor
- Schema migration (pattern_layer column)
- FlipModule integration
- Graceful degradation
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile

from imem.compile.pattern_client import (
    PatternClient,
    NoOpPatternClient,
    PatternResponse,
    create_pattern_client,
)
from imem.compile.pattern import (
    PatternExtractor,
    NoOpPatternExtractor,
    create_pattern_extractor,
)
from imem.storage.sqlite import SQLiteStore
from imem.structure.flip import FlipModule


# ============================================================================
# PatternClient Tests
# ============================================================================

class TestPatternResponse:
    """Test PatternResponse dataclass"""

    def test_success_response(self):
        resp = PatternResponse(id="chunk1", pattern_layer="Abstract pattern")
        assert resp.id == "chunk1"
        assert resp.pattern_layer == "Abstract pattern"
        assert resp.error is None

    def test_error_response(self):
        resp = PatternResponse(id="chunk1", pattern_layer="", error="Timeout")
        assert resp.id == "chunk1"
        assert resp.pattern_layer == ""
        assert resp.error == "Timeout"


class TestNoOpPatternClient:
    """Test NoOpPatternClient graceful degradation"""

    def test_is_available_false(self):
        client = NoOpPatternClient()
        assert client.is_available is False

    @pytest.mark.asyncio
    async def test_check_health_false(self):
        client = NoOpPatternClient()
        assert await client.check_health() is False

    @pytest.mark.asyncio
    async def test_extract_pattern_returns_empty(self):
        client = NoOpPatternClient()
        resp = await client.extract_pattern("id1", "content")
        assert resp.id == "id1"
        assert resp.pattern_layer == ""
        assert resp.error is None

    @pytest.mark.asyncio
    async def test_extract_batch_returns_empty(self):
        client = NoOpPatternClient()
        chunks = [{"id": "c1"}, {"id": "c2"}]
        results = await client.extract_batch(chunks)
        assert len(results) == 2
        assert all(r.pattern_layer == "" for r in results)


class TestCreatePatternClient:
    """Test pattern client factory"""

    def test_disabled_returns_noop(self):
        client = create_pattern_client(enabled=False)
        assert isinstance(client, NoOpPatternClient)

    def test_no_url_returns_noop(self):
        with patch.dict('os.environ', {}, clear=True):
            client = create_pattern_client(api_url=None, enabled=True)
            assert isinstance(client, NoOpPatternClient)

    def test_with_url_returns_real(self):
        client = create_pattern_client(api_url="http://localhost:8000", enabled=True)
        assert isinstance(client, PatternClient)
        assert client.api_url == "http://localhost:8000"


# ============================================================================
# PatternExtractor Tests
# ============================================================================

class TestNoOpPatternExtractor:
    """Test NoOpPatternExtractor"""

    def test_is_available_false(self):
        extractor = NoOpPatternExtractor()
        assert extractor.is_available is False

    def test_applies_always_false(self):
        extractor = NoOpPatternExtractor()
        chunk = {"id": "1", "content": "Some content here"}
        assert extractor.applies(chunk) is False

    @pytest.mark.asyncio
    async def test_execute_noop(self):
        extractor = NoOpPatternExtractor()
        chunk = {"id": "1", "content": "Content"}
        await extractor.execute(chunk)
        assert "pattern_layer" not in chunk


class TestPatternExtractor:
    """Test PatternExtractor with mock client"""

    def test_name(self):
        extractor = PatternExtractor(client=NoOpPatternClient())
        assert extractor.name == "pattern"

    def test_applies_checks_content_length(self):
        extractor = PatternExtractor(client=NoOpPatternClient())

        # Too short
        assert extractor.applies({"id": "1", "content": "short"}) is False

        # Long enough
        long_content = "x" * 100
        assert extractor.applies({"id": "1", "content": long_content}) is True

    def test_applies_requires_content(self):
        extractor = PatternExtractor(client=NoOpPatternClient())
        assert extractor.applies({"id": "1"}) is False
        assert extractor.applies({"id": "1", "content": ""}) is False

    @pytest.mark.asyncio
    async def test_execute_populates_pattern_layer(self):
        # Mock client that returns pattern
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.extract_pattern = AsyncMock(
            return_value=PatternResponse(id="c1", pattern_layer="Abstracted pattern")
        )

        extractor = PatternExtractor(client=mock_client)
        chunk = {"id": "c1", "content": "x" * 100}

        await extractor.execute(chunk)

        assert chunk.get("pattern_layer") == "Abstracted pattern"

    @pytest.mark.asyncio
    async def test_execute_handles_error(self):
        # Mock client that returns error
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.extract_pattern = AsyncMock(
            return_value=PatternResponse(id="c1", pattern_layer="", error="Failed")
        )

        extractor = PatternExtractor(client=mock_client)
        chunk = {"id": "c1", "content": "x" * 100}

        await extractor.execute(chunk)

        # Should not set pattern_layer on error
        assert "pattern_layer" not in chunk


class TestCreatePatternExtractor:
    """Test pattern extractor factory"""

    def test_disabled_returns_noop(self):
        extractor = create_pattern_extractor(enabled=False)
        assert isinstance(extractor, NoOpPatternExtractor)


# ============================================================================
# Schema Migration Tests
# ============================================================================

class TestSchemaMigration:
    """Test pattern_layer column migration"""

    def test_pattern_layer_column_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir))

            cursor = store.conn.execute("PRAGMA table_info(chunks)")
            columns = {row[1] for row in cursor.fetchall()}

            assert "pattern_layer" in columns
            store.close()

    def test_pattern_layer_can_be_updated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStore(Path(tmpdir))

            # Insert chunk
            store.conn.execute('''
                INSERT INTO chunks (id, file_path, content)
                VALUES (?, ?, ?)
            ''', ("test1", "/test/path.md", "Test content"))
            store.conn.commit()

            # Update pattern_layer
            store.conn.execute('''
                UPDATE chunks SET pattern_layer = ? WHERE id = ?
            ''', ("Abstract pattern", "test1"))
            store.conn.commit()

            # Verify
            cursor = store.conn.execute(
                "SELECT pattern_layer FROM chunks WHERE id = ?",
                ("test1",)
            )
            result = cursor.fetchone()
            assert result[0] == "Abstract pattern"

            store.close()


# ============================================================================
# FlipModule Integration Tests
# ============================================================================

class TestFlipModuleIntegration:
    """Test FlipModule consumes pattern_layer"""

    def test_get_pattern_returns_pattern_layer(self):
        flip = FlipModule()

        chunk = {
            "id": "c1",
            "content": "Implementation details",
            "pattern_layer": "Abstract pattern",
        }

        pattern = flip._get_pattern(chunk)
        assert pattern == "Abstract pattern"

    def test_get_pattern_returns_none_without_pattern_layer(self):
        flip = FlipModule()

        chunk = {
            "id": "c1",
            "content": "Implementation details",
        }

        pattern = flip._get_pattern(chunk)
        assert pattern is None

    def test_should_flip_for_low_validity(self):
        flip = FlipModule(validity_threshold=0.3)

        # Low validity should flip
        assert flip._should_flip({"validity": 0.2}) is True

        # High validity should not flip
        assert flip._should_flip({"validity": 0.8}) is False

    def test_apply_pattern_preserves_original(self):
        flip = FlipModule()

        chunk = {"id": "c1", "content": "Original content"}
        result = flip._apply_pattern(chunk, "Pattern content")

        assert result["content"] == "Pattern content"
        assert result["_original_content"] == "Original content"


# ============================================================================
# Graceful Degradation Tests
# ============================================================================

class TestGracefulDegradation:
    """Test system works when pattern service unavailable"""

    def test_noop_client_allows_indexing(self):
        """NoOp client should not block indexing"""
        client = create_pattern_client(enabled=False)
        assert not client.is_available
        # System continues without patterns

    def test_noop_extractor_allows_indexing(self):
        """NoOp extractor should not block indexing"""
        extractor = create_pattern_extractor(enabled=False)
        assert not extractor.is_available
        # System continues without patterns

    def test_flip_module_works_without_patterns(self):
        """FlipModule should work when pattern_layer is None"""
        flip = FlipModule()

        chunk = {
            "id": "c1",
            "content": "Implementation",
            "validity": 0.1,  # Would normally flip
            # No pattern_layer
        }

        # Should not crash, just return implementation
        pattern = flip._get_pattern(chunk)
        assert pattern is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
