"""Token estimation and greedy packing for context budgeting."""

from typing import Any, Dict, List


def estimate_tokens(text: str) -> int:
    """Approximate tokens. ~4 chars/token for English prose."""
    if not text:
        return 0
    return len(text) // 4


def greedy_pack(chunks: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
    """Pack ranked chunks until token budget exhausted.

    Chunks must be pre-sorted by rank (descending). Packs greedily
    in order until budget hit.

    Args:
        chunks: List of chunk dicts with 'content' field
        max_tokens: Token budget

    Returns:
        Subset of chunks that fit within budget
    """
    if not chunks or max_tokens <= 0:
        return []

    packed = []
    used = 0

    for chunk in chunks:
        tokens = estimate_tokens(chunk.get('content', ''))
        if used + tokens <= max_tokens:
            packed.append(chunk)
            used += tokens

    return packed
