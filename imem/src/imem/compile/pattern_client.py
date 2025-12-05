"""PatternClient - Async client for Pattern Extraction Service

EPIC 7: Client SDK for calling pattern extraction service.

Features:
- Async batch extraction with bounded concurrency
- Graceful degradation when service unavailable
- Configurable API URL and key
- Retry logic for transient failures

Usage:
    client = PatternClient(api_url="http://localhost:8000")
    patterns = await client.extract_batch(chunks)
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger(__name__)


@dataclass
class PatternResponse:
    """Response from pattern extraction"""
    id: str
    pattern_layer: str
    error: Optional[str] = None


class PatternClient:
    """Async client for pattern extraction service

    Handles:
    - Batch extraction with bounded concurrency
    - Retry logic for transient failures
    - Graceful degradation when service unavailable

    Attributes:
        api_url: Pattern extraction service URL
        api_key: Optional API key for authentication
        max_concurrent: Maximum concurrent requests (default 50)
        timeout: Request timeout in seconds (default 30)
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_concurrent: int = 50,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize pattern client

        Args:
            api_url: Service URL (default from PATTERN_SERVICE_URL env var)
            api_key: API key (default from PATTERN_SERVICE_KEY env var)
            max_concurrent: Max concurrent requests
            timeout: Request timeout in seconds
            max_retries: Max retry attempts for transient failures
        """
        self.api_url = api_url or os.environ.get(
            "PATTERN_SERVICE_URL", "http://localhost:8000"
        )
        self.api_key = api_key or os.environ.get("PATTERN_SERVICE_KEY", "")
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._session: Optional['aiohttp.ClientSession'] = None
        self._available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        """Check if pattern service is available

        Lazy check - caches result after first call.
        """
        if not HAS_AIOHTTP:
            return False
        if self._available is None:
            # Will be set on first request
            return True  # Assume available until proven otherwise
        return self._available

    async def _get_session(self) -> 'aiohttp.ClientSession':
        """Get or create aiohttp session"""
        if not HAS_AIOHTTP:
            raise RuntimeError("aiohttp not installed")

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the client session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def check_health(self) -> bool:
        """Check if service is healthy

        Returns:
            True if service responds to health check
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self.api_url}/health") as response:
                self._available = response.status == 200
                return self._available
        except Exception as e:
            logger.debug(f"Pattern service health check failed: {e}")
            self._available = False
            return False

    async def extract_pattern(
        self,
        chunk_id: str,
        content: str,
    ) -> PatternResponse:
        """Extract pattern from single chunk

        Args:
            chunk_id: Unique chunk identifier
            content: Implementation content to abstract

        Returns:
            PatternResponse with pattern_layer or error
        """
        async with self.semaphore:
            return await self._extract_with_retry(chunk_id, content)

    async def _extract_with_retry(
        self,
        chunk_id: str,
        content: str,
    ) -> PatternResponse:
        """Extract pattern with retry logic"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                async with session.post(
                    f"{self.api_url}/v1/extract-patterns",
                    headers=headers,
                    json={"chunks": [{"id": chunk_id, "content": content}]},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        last_error = f"HTTP {response.status}: {error_text[:200]}"
                        if response.status >= 500:
                            # Retry on server errors
                            await asyncio.sleep(2 ** attempt)
                            continue
                        # Don't retry client errors
                        return PatternResponse(
                            id=chunk_id,
                            pattern_layer="",
                            error=last_error,
                        )

                    data = await response.json()
                    self._available = True
                    patterns = data.get("patterns", [])
                    if patterns:
                        p = patterns[0]
                        return PatternResponse(
                            id=p["id"],
                            pattern_layer=p.get("pattern_layer", ""),
                            error=p.get("error"),
                        )
                    return PatternResponse(
                        id=chunk_id,
                        pattern_layer="",
                        error="No pattern returned",
                    )

            except asyncio.TimeoutError:
                last_error = "Timeout"
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = str(e)
                self._available = False
                await asyncio.sleep(2 ** attempt)

        return PatternResponse(id=chunk_id, pattern_layer="", error=last_error)

    async def extract_batch(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[PatternResponse]:
        """Extract patterns from batch of chunks

        Chunks must have 'id' and 'content' keys.

        Args:
            chunks: List of chunk dicts with id and content

        Returns:
            List of PatternResponse in same order as input
        """
        if not chunks:
            return []

        # Filter chunks with sufficient content
        valid_chunks = [
            c for c in chunks
            if c.get('content') and len(c.get('content', '')) > 50
        ]

        if not valid_chunks:
            logger.debug("No chunks with sufficient content for pattern extraction")
            return []

        # Check health first (fast fail)
        if not await self.check_health():
            logger.warning("Pattern service unavailable - skipping extraction")
            return [
                PatternResponse(id=c['id'], pattern_layer="", error="Service unavailable")
                for c in valid_chunks
            ]

        # Extract in parallel with bounded concurrency
        tasks = [
            self.extract_pattern(c['id'], c['content'])
            for c in valid_chunks
        ]
        results = await asyncio.gather(*tasks)

        # Log summary
        success_count = sum(1 for r in results if not r.error)
        logger.info(f"Pattern extraction: {success_count}/{len(valid_chunks)} successful")

        return results


class NoOpPatternClient:
    """No-op pattern client for graceful degradation

    Used when pattern service is unavailable or disabled.
    Returns empty pattern layers without errors.
    """

    @property
    def is_available(self) -> bool:
        return False

    async def check_health(self) -> bool:
        return False

    async def extract_pattern(
        self,
        chunk_id: str,
        content: str,
    ) -> PatternResponse:
        return PatternResponse(id=chunk_id, pattern_layer="")

    async def extract_batch(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[PatternResponse]:
        return [
            PatternResponse(id=c.get('id', ''), pattern_layer="")
            for c in chunks
        ]

    async def close(self):
        pass


def create_pattern_client(
    api_url: Optional[str] = None,
    enabled: bool = True,
) -> PatternClient:
    """Factory for pattern client

    Returns NoOpPatternClient if:
    - enabled=False
    - aiohttp not installed
    - No API URL configured

    Args:
        api_url: Optional service URL override
        enabled: Whether to enable pattern extraction

    Returns:
        PatternClient or NoOpPatternClient
    """
    if not enabled:
        logger.info("Pattern extraction disabled")
        return NoOpPatternClient()

    if not HAS_AIOHTTP:
        logger.warning("aiohttp not installed - pattern extraction disabled")
        return NoOpPatternClient()

    effective_url = api_url or os.environ.get("PATTERN_SERVICE_URL", "")
    if not effective_url:
        logger.info("PATTERN_SERVICE_URL not set - pattern extraction disabled")
        return NoOpPatternClient()

    return PatternClient(api_url=effective_url)


__all__ = [
    'PatternClient',
    'NoOpPatternClient',
    'PatternResponse',
    'create_pattern_client',
]
