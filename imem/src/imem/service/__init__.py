"""Service domain - External service lifecycle management

Responsible for:
- Qdrant Docker service management (start, stop, status)
- Service health checks
- Configuration generation

This domain handles external service dependencies separate from
storage backends and business logic.
"""

# Re-export Qdrant service from legacy (Docker management)
from ..legacy.v2.qdrant_service import QdrantService

__all__ = ['QdrantService']
