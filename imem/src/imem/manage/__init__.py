"""Manage domain - Project management and introspection

Responsible for:
- Project registration and tracking
- Metadata introspection (field schema discovery)
- Coverage statistics

Note: EntityResolver exists but not exported - needs own EPIC for integration.
"""

from .introspect import introspect, get_coverage_stats
from ..registry import SimpleRegistry

__all__ = [
    'introspect',
    'get_coverage_stats',
    'SimpleRegistry',
]
