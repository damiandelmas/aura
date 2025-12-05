"""Local embedding operations via sentence-transformers

EPIC 4: sqlite-vec Vectors - Semantic similarity via local embeddings.

Embedder wraps a local embedding model (sentence-transformers) and provides
vector operations for IMEM. All operations are local - no API calls, no
network latency, no per-token cost. The only dependency is the model file (~80MB).

This is a Tier 3 component. The system works without it - semantic features
degrade to metadata-based heuristics or disable entirely.

Key design decisions:
- Batch-first API for performance
- LRU cache with 50% eviction on overflow
- Lazy model loading (~2s on first use)
- Graceful degradation via NoOpEmbedder
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmbedderConfig:
    """Configuration for embedding model

    Attributes:
        model_name: HuggingFace model identifier
        dimension: Vector dimensions (determined by model)
        cache_max_size: Maximum number of embeddings to cache
    """
    model_name: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    cache_max_size: int = 10000


class Embedder(ABC):
    """Abstract interface for embedding operations

    Protocol for local vector operations. Implementations must be
    stateless per-call (caching is internal detail).
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Batch embed texts to vectors

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each is list of floats)
        """
        pass

    @abstractmethod
    def embed_single(self, text: str) -> List[float]:
        """Embed single text to vector

        Args:
            text: Text string to embed

        Returns:
            Embedding vector as list of floats
        """
        pass

    @abstractmethod
    def similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between vectors

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity (-1.0 to 1.0, typically 0.0 to 1.0 for embeddings)
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension"""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether embedder is functional"""
        pass


class LocalEmbedder(Embedder):
    """sentence-transformers based embedder

    Loads a local model (~80MB) for embedding generation.
    Lazy loading - model not loaded until first use.

    Features:
    - Batch encoding for efficiency (~1000 texts/sec)
    - LRU cache with 50% eviction
    - Cosine similarity computation
    """

    def __init__(self, config: Optional[EmbedderConfig] = None):
        """Initialize embedder

        Args:
            config: Optional configuration (uses defaults if None)
        """
        self.config = config or EmbedderConfig()
        self._model = None  # Lazy load
        self._cache: Dict[str, List[float]] = {}
        self._available = True

    def _ensure_model(self) -> bool:
        """Lazy-load the model on first use

        Returns:
            True if model is available, False otherwise
        """
        if self._model is not None:
            return self._available

        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.config.model_name}")
            self._model = SentenceTransformer(self.config.model_name)
            self._available = True
            logger.info(f"Embedding model loaded successfully")
        except ImportError:
            logger.warning("sentence-transformers not installed, embeddings disabled")
            self._available = False
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")
            self._available = False

        return self._available

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Batch embed texts to vectors"""
        if not texts:
            return []

        if not self._ensure_model():
            return [[] for _ in texts]

        results: List[Optional[List[float]]] = [None] * len(texts)
        uncached: List[str] = []
        uncached_indices: List[int] = []

        # Check cache first
        for i, text in enumerate(texts):
            cache_key = f"{self.config.model_name}:{text}"
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                uncached.append(text)
                uncached_indices.append(i)

        # Embed uncached texts
        if uncached:
            try:
                embeddings = self._model.encode(
                    uncached,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                ).tolist()

                for idx, emb, text in zip(uncached_indices, embeddings, uncached):
                    results[idx] = emb
                    self._cache_put(f"{self.config.model_name}:{text}", emb)

            except Exception as e:
                logger.warning(f"Embedding failed: {e}")
                # Return empty vectors for failed embeddings
                for idx in uncached_indices:
                    results[idx] = []

        return [r if r is not None else [] for r in results]

    def embed_single(self, text: str) -> List[float]:
        """Embed single text to vector"""
        results = self.embed([text])
        return results[0] if results else []

    def similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between vectors"""
        if not a or not b:
            return 0.0

        try:
            import numpy as np
            a_np = np.array(a)
            b_np = np.array(b)

            norm_a = np.linalg.norm(a_np)
            norm_b = np.linalg.norm(b_np)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return float(np.dot(a_np, b_np) / (norm_a * norm_b))

        except ImportError:
            # Fallback without numpy
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

    @property
    def dimension(self) -> int:
        """Vector dimension"""
        return self.config.dimension

    @property
    def is_available(self) -> bool:
        """Whether embedder is functional"""
        return self._ensure_model()

    def _cache_put(self, key: str, value: List[float]) -> None:
        """Add to cache with LRU eviction

        When cache exceeds max size, evict 50% of oldest entries.
        """
        if len(self._cache) >= self.config.cache_max_size:
            # Evict oldest 50%
            keys_to_delete = list(self._cache.keys())[: self.config.cache_max_size // 2]
            for k in keys_to_delete:
                del self._cache[k]
        self._cache[key] = value

    def clear_cache(self) -> None:
        """Clear embedding cache"""
        self._cache.clear()


class NoOpEmbedder(Embedder):
    """No-op embedder for graceful degradation

    When embedding model is unavailable, this provides
    neutral behavior. Consumers must check for empty vectors.
    """

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return empty vectors"""
        return [[] for _ in texts]

    def embed_single(self, text: str) -> List[float]:
        """Return empty vector"""
        return []

    def similarity(self, a: List[float], b: List[float]) -> float:
        """Return zero similarity"""
        return 0.0

    @property
    def dimension(self) -> int:
        """Return expected dimension for schema compatibility"""
        return 384

    @property
    def is_available(self) -> bool:
        """NoOp embedder is never 'available' in the functional sense"""
        return False


def create_embedder(config: Optional[EmbedderConfig] = None) -> Embedder:
    """Factory function to create appropriate embedder

    Attempts to create a LocalEmbedder. If sentence-transformers
    is not installed, returns NoOpEmbedder for graceful degradation.

    Args:
        config: Optional embedder configuration

    Returns:
        Embedder instance (LocalEmbedder or NoOpEmbedder)
    """
    try:
        # Check if sentence-transformers is available
        import sentence_transformers  # noqa: F401
        return LocalEmbedder(config)
    except ImportError:
        logger.warning("sentence-transformers not installed, using NoOpEmbedder")
        return NoOpEmbedder()


__all__ = [
    'Embedder',
    'LocalEmbedder',
    'NoOpEmbedder',
    'EmbedderConfig',
    'create_embedder',
]
