"""Vector storage for semantic similarity queries

EPIC 4: sqlite-vec Vectors - Semantic similarity via sqlite-vec.

VectorStorage provides semantic similarity queries via sqlite-vec extension.
Store embeddings at index time, query by similarity at runtime.

This is a Tier 3 component - the system works without it. Vectors enable
sibling edges, supersession detection, and semantic search. They enhance
but don't enable core functionality.

Key design decisions:
- Static metadata only in vec0 (phase, section_type) - NOT validity
- Graceful degradation required - system works without sqlite-vec
- Embedding at index time, not query time
- Sorted normalization for sibling edges

Schema:
    CREATE VIRTUAL TABLE chunk_vectors USING vec0(
        chunk_id INTEGER PRIMARY KEY,
        embedding float[384],
        phase TEXT,
        section_type TEXT,
        +content_preview TEXT
    );
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import struct
import logging

if TYPE_CHECKING:
    from .sqlite import SQLiteStore
    from ..infrastructure.embedder import Embedder

logger = logging.getLogger(__name__)


@dataclass
class Neighbor:
    """Result from a KNN query

    Attributes:
        chunk_id: ID of the similar chunk
        similarity: Cosine similarity (0.0-1.0)
        distance: L2 distance (lower = more similar)
    """
    chunk_id: str
    similarity: float
    distance: float = 0.0


@dataclass
class VectorFilters:
    """Filters for vector queries

    Attributes:
        phase: Filter by phase (design, develop, etc.)
        section_type: Filter by section type
    """
    phase: Optional[str] = None
    section_type: Optional[str] = None


class VectorStorage(ABC):
    """Abstract interface for vector storage

    Protocol for storing and querying embeddings.
    Implementations must handle graceful degradation.
    """

    @abstractmethod
    def store(
        self,
        chunk_id: str,
        embedding: List[float],
        phase: Optional[str] = None,
        section_type: Optional[str] = None,
        content_preview: Optional[str] = None,
    ) -> None:
        """Store an embedding for a chunk

        Args:
            chunk_id: Chunk identifier
            embedding: Vector representation
            phase: Optional phase metadata
            section_type: Optional section type metadata
            content_preview: First 200 chars for quick display
        """
        pass

    @abstractmethod
    def store_batch(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> None:
        """Batch store embeddings

        Args:
            chunks: List of chunk dicts with id, phase, section_type, content
            embeddings: Corresponding embedding vectors
        """
        pass

    @abstractmethod
    def query_knn(
        self,
        embedding: List[float],
        k: int = 20,
        threshold: float = 0.0,
        filters: Optional[VectorFilters] = None,
    ) -> List[Neighbor]:
        """Query k nearest neighbors

        Args:
            embedding: Query vector
            k: Number of neighbors to return
            threshold: Minimum similarity threshold (0.0-1.0)
            filters: Optional metadata filters

        Returns:
            List of Neighbor results sorted by similarity (desc)
        """
        pass

    @abstractmethod
    def delete(self, chunk_id: str) -> None:
        """Delete embedding for a chunk

        Args:
            chunk_id: Chunk identifier to delete
        """
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether vector storage is functional"""
        pass


class SQLiteVecStorage(VectorStorage):
    """sqlite-vec based vector storage

    Uses sqlite-vec extension for HNSW-based similarity search.
    Falls back gracefully if extension not available.

    Note: sqlite-vec is the successor to sqlite-vss with better API.
    See: https://github.com/asg017/sqlite-vec
    """

    def __init__(self, db: 'SQLiteStore', embedder: 'Embedder'):
        """Initialize vector storage

        Args:
            db: SQLite store for database connection
            embedder: Embedder for dimension info
        """
        self.db = db
        self.embedder = embedder
        self._has_vec0 = self._check_vec0_available()

        if self._has_vec0:
            self._create_vector_table()

    def _check_vec0_available(self) -> bool:
        """Check if sqlite-vec extension is available"""
        try:
            # Enable extension loading
            self.db.conn.enable_load_extension(True)

            # Try to load sqlite-vec
            # The extension name varies by platform
            try:
                self.db.conn.load_extension('vec0')
            except Exception:
                try:
                    self.db.conn.load_extension('sqlite_vec')
                except Exception:
                    try:
                        # Try loading from common paths
                        import sqlite_vec
                        sqlite_vec.load(self.db.conn)
                    except Exception:
                        pass

            # Test if vec0 functions are available
            cursor = self.db.conn.execute("SELECT vec_version()")
            version = cursor.fetchone()[0]
            logger.info(f"sqlite-vec extension loaded: v{version}")
            return True

        except Exception as e:
            logger.warning(f"sqlite-vec not available: {e}")
            return False

    def _create_vector_table(self) -> None:
        """Create the chunk_vectors virtual table"""
        if not self._has_vec0:
            return

        dim = self.embedder.dimension

        try:
            # Create vec0 virtual table
            # Note: vec0 syntax differs from vss0
            self.db.conn.execute(f'''
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vectors USING vec0(
                    embedding float[{dim}]
                )
            ''')

            # Create metadata table (vec0 doesn't support all column types)
            self.db.conn.execute('''
                CREATE TABLE IF NOT EXISTS vector_meta (
                    chunk_id TEXT PRIMARY KEY,
                    rowid INTEGER NOT NULL,
                    phase TEXT,
                    section_type TEXT,
                    content_preview TEXT,
                    embedded_at INTEGER DEFAULT (strftime('%s', 'now')),
                    model_id TEXT
                )
            ''')

            self.db.conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_vmeta_rowid ON vector_meta(rowid)'
            )
            self.db.conn.commit()
            logger.info("Vector storage tables created")

        except Exception as e:
            logger.warning(f"Failed to create vector tables: {e}")
            self._has_vec0 = False

    def store(
        self,
        chunk_id: str,
        embedding: List[float],
        phase: Optional[str] = None,
        section_type: Optional[str] = None,
        content_preview: Optional[str] = None,
    ) -> None:
        """Store an embedding for a chunk"""
        if not self._has_vec0 or not embedding:
            return

        try:
            # Serialize embedding to bytes
            blob = self._serialize_f32(embedding)

            # Insert into vec0 table
            cursor = self.db.conn.execute(
                'INSERT INTO chunk_vectors(embedding) VALUES (?)',
                (blob,)
            )
            rowid = cursor.lastrowid

            # Insert metadata
            self.db.conn.execute('''
                INSERT OR REPLACE INTO vector_meta
                (chunk_id, rowid, phase, section_type, content_preview, model_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                chunk_id,
                rowid,
                phase,
                section_type,
                (content_preview or '')[:200],
                'all-MiniLM-L6-v2',
            ))
            self.db.conn.commit()

        except Exception as e:
            logger.warning(f"Failed to store embedding for {chunk_id}: {e}")

    def store_batch(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> None:
        """Batch store embeddings"""
        if not self._has_vec0:
            return

        for chunk, embedding in zip(chunks, embeddings):
            if embedding:  # Skip empty embeddings
                self.store(
                    chunk_id=chunk['id'],
                    embedding=embedding,
                    phase=chunk.get('phase'),
                    section_type=chunk.get('section_type'),
                    content_preview=chunk.get('content', '')[:200],
                )

    def query_knn(
        self,
        embedding: List[float],
        k: int = 20,
        threshold: float = 0.0,
        filters: Optional[VectorFilters] = None,
    ) -> List[Neighbor]:
        """Query k nearest neighbors"""
        if not self._has_vec0 or not embedding:
            return []

        try:
            blob = self._serialize_f32(embedding)

            # Query vec0 for neighbors
            # Note: vec0 uses MATCH syntax
            results = self.db.conn.execute('''
                SELECT cv.rowid, cv.distance, vm.chunk_id
                FROM chunk_vectors cv
                JOIN vector_meta vm ON cv.rowid = vm.rowid
                WHERE cv.embedding MATCH ?
                  AND k = ?
                ORDER BY cv.distance
            ''', (blob, k)).fetchall()

            neighbors = []
            for row in results:
                distance = row[1]
                chunk_id = row[2]

                # Convert distance to similarity
                # For cosine distance: similarity = 1 - distance
                similarity = 1.0 - distance

                if similarity >= threshold:
                    neighbors.append(Neighbor(
                        chunk_id=chunk_id,
                        similarity=similarity,
                        distance=distance,
                    ))

            # Apply metadata filters if needed
            if filters:
                neighbors = self._apply_filters(neighbors, filters)

            return neighbors

        except Exception as e:
            logger.warning(f"KNN query failed: {e}")
            return self._query_brute_force(embedding, k, threshold, filters)

    def _query_brute_force(
        self,
        embedding: List[float],
        k: int,
        threshold: float,
        filters: Optional[VectorFilters],
    ) -> List[Neighbor]:
        """Fallback brute-force search when vec0 query fails"""
        try:
            # Get all embeddings with metadata
            cursor = self.db.conn.execute('''
                SELECT vm.chunk_id, cv.embedding, vm.phase, vm.section_type
                FROM chunk_vectors cv
                JOIN vector_meta vm ON cv.rowid = vm.rowid
            ''')

            neighbors = []
            for row in cursor:
                chunk_id = row[0]
                stored_blob = row[1]
                phase = row[2]
                section_type = row[3]

                # Apply filters
                if filters:
                    if filters.phase and phase != filters.phase:
                        continue
                    if filters.section_type and section_type != filters.section_type:
                        continue

                # Compute similarity
                stored_emb = self._deserialize_f32(stored_blob)
                similarity = self._cosine_similarity(embedding, stored_emb)

                if similarity >= threshold:
                    neighbors.append(Neighbor(
                        chunk_id=chunk_id,
                        similarity=similarity,
                        distance=1.0 - similarity,
                    ))

            # Sort by similarity and take top k
            neighbors.sort(key=lambda n: n.similarity, reverse=True)
            return neighbors[:k]

        except Exception as e:
            logger.warning(f"Brute force query failed: {e}")
            return []

    def _apply_filters(
        self,
        neighbors: List[Neighbor],
        filters: VectorFilters,
    ) -> List[Neighbor]:
        """Apply metadata filters to neighbors (post-filter)"""
        if not filters.phase and not filters.section_type:
            return neighbors

        filtered = []
        for neighbor in neighbors:
            # Look up metadata
            cursor = self.db.conn.execute('''
                SELECT phase, section_type FROM vector_meta
                WHERE chunk_id = ?
            ''', (neighbor.chunk_id,))
            row = cursor.fetchone()

            if row:
                phase, section_type = row
                if filters.phase and phase != filters.phase:
                    continue
                if filters.section_type and section_type != filters.section_type:
                    continue
                filtered.append(neighbor)

        return filtered

    def delete(self, chunk_id: str) -> None:
        """Delete embedding for a chunk"""
        if not self._has_vec0:
            return

        try:
            # Get rowid from metadata
            cursor = self.db.conn.execute(
                'SELECT rowid FROM vector_meta WHERE chunk_id = ?',
                (chunk_id,)
            )
            row = cursor.fetchone()

            if row:
                rowid = row[0]
                # Delete from vec0 (sets embedding to NULL)
                self.db.conn.execute(
                    'DELETE FROM chunk_vectors WHERE rowid = ?',
                    (rowid,)
                )
                # Delete metadata
                self.db.conn.execute(
                    'DELETE FROM vector_meta WHERE chunk_id = ?',
                    (chunk_id,)
                )
                self.db.conn.commit()

        except Exception as e:
            logger.warning(f"Failed to delete embedding for {chunk_id}: {e}")

    @property
    def is_available(self) -> bool:
        """Whether vector storage is functional"""
        return self._has_vec0

    def _serialize_f32(self, vector: List[float]) -> bytes:
        """Serialize float vector to bytes"""
        return struct.pack(f'{len(vector)}f', *vector)

    def _deserialize_f32(self, blob: bytes) -> List[float]:
        """Deserialize bytes to float vector"""
        n = len(blob) // 4
        return list(struct.unpack(f'{n}f', blob))

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between vectors"""
        if len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)


class NoOpVectorStorage(VectorStorage):
    """No-op vector storage for graceful degradation

    When sqlite-vec is unavailable, this provides neutral behavior.
    All operations are no-ops. Consumers must check is_available.
    """

    def store(
        self,
        chunk_id: str,
        embedding: List[float],
        phase: Optional[str] = None,
        section_type: Optional[str] = None,
        content_preview: Optional[str] = None,
    ) -> None:
        """No-op: does nothing"""
        pass

    def store_batch(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> None:
        """No-op: does nothing"""
        pass

    def query_knn(
        self,
        embedding: List[float],
        k: int = 20,
        threshold: float = 0.0,
        filters: Optional[VectorFilters] = None,
    ) -> List[Neighbor]:
        """No-op: returns empty list"""
        return []

    def delete(self, chunk_id: str) -> None:
        """No-op: does nothing"""
        pass

    @property
    def is_available(self) -> bool:
        """NoOp is never available"""
        return False


def create_vector_storage(
    db: 'SQLiteStore',
    embedder: 'Embedder',
) -> VectorStorage:
    """Factory function to create appropriate vector storage

    Attempts to create SQLiteVecStorage. If sqlite-vec is not
    available, returns NoOpVectorStorage for graceful degradation.

    Args:
        db: SQLite store
        embedder: Embedder for dimension info

    Returns:
        VectorStorage instance
    """
    storage = SQLiteVecStorage(db, embedder)
    if storage.is_available:
        return storage

    logger.info("Using NoOpVectorStorage (sqlite-vec not available)")
    return NoOpVectorStorage()


__all__ = [
    'VectorStorage',
    'SQLiteVecStorage',
    'NoOpVectorStorage',
    'Neighbor',
    'VectorFilters',
    'create_vector_storage',
]
