"""Manage domain - Project management and introspection

Responsible for:
- Project registration and tracking
- Metadata introspection
- Coverage statistics
- Concept topology analysis

This domain handles project-level management tasks separate from
indexing (compile) and retrieval (compose).
"""

# Re-export introspection functions (already in separate module)
from ..introspect import (
    introspect,
    get_system_and_landscape,
    get_concept_topology,
    get_coverage_stats
)

# Re-export registry (will move here in future)
from ..registry import SimpleRegistry

__all__ = [
    'introspect',
    'get_system_and_landscape',
    'get_concept_topology',
    'get_coverage_stats',
    'SimpleRegistry',
]
