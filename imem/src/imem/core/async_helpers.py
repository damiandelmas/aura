"""Async helpers for safe concurrent operations

Provides bounded concurrency primitive (from Graphiti pattern) to prevent
SQLite connection pool exhaustion during parallel discovery queries.
"""

import asyncio
from typing import Coroutine, List, Any, TypeVar

T = TypeVar('T')


async def semaphore_gather(
    *coroutines: Coroutine[Any, Any, T],
    max_coroutines: int = 20
) -> List[T]:
    """Execute coroutines with bounded concurrency

    Prevents resource exhaustion by limiting concurrent operations.
    Critical for SQLite backends which have bounded write concurrency.

    Args:
        *coroutines: Coroutines to execute in parallel
        max_coroutines: Maximum concurrent operations (default: 20)
            - SQLite WAL mode: ~30 concurrent readers safe
            - Conservative default: 20 for safety

    Returns:
        List of results in same order as input coroutines

    Example:
        # Safe parallel sibling queries (prevents SQLite errors)
        sibling_tasks = [
            get_siblings(chunk_id)
            for chunk_id in result_ids
        ]
        siblings = await semaphore_gather(*sibling_tasks, max_coroutines=30)

    Why this matters:
        Without bounded concurrency, 200 parallel SQLite queries will crash:
        - Connection pool exhausted
        - "database is locked" errors
        - Performance degradation

        With semaphore_gather, queries are throttled:
        - Max 20-30 concurrent operations
        - No connection pool exhaustion
        - Predictable performance
    """
    semaphore = asyncio.Semaphore(max_coroutines)

    async def _wrap_coroutine(coro: Coroutine[Any, Any, T]) -> T:
        """Wrap coroutine with semaphore acquisition"""
        async with semaphore:
            return await coro

    return await asyncio.gather(*(_wrap_coroutine(c) for c in coroutines))
