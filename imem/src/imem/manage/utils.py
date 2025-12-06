"""Timestamp utilities for MANAGE domain

Normalizes all timestamps to UTC-aware for consistent comparison.
Fixes: "can't subtract offset-naive and offset-aware datetimes"
"""

from datetime import datetime, timezone
from typing import Optional


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetime to UTC-aware

    - If naive: assume UTC, add tzinfo
    - If aware: convert to UTC
    - If None: return None

    Args:
        dt: Datetime to normalize

    Returns:
        UTC-aware datetime or None
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)

    # Aware datetime - convert to UTC
    return dt.astimezone(timezone.utc)


def utc_now() -> datetime:
    """Get current time as UTC-aware datetime"""
    return datetime.now(timezone.utc)


__all__ = ['to_utc', 'utc_now']
