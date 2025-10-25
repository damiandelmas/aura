"""Centralized configuration for Qdrant service manager"""
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class QdrantConfig:
    """Qdrant service configuration with environment variable overrides"""

    # Qdrant Service
    qdrant_port: int = int(os.getenv('QDRANT_PORT', '6334'))
    qdrant_host: str = os.getenv('QDRANT_HOST', 'localhost')
    qdrant_timeout: int = int(os.getenv('QDRANT_TIMEOUT', '2'))

    # Paths
    context_dir: Path = Path(os.getenv('QDRANT_CONTEXT_DIR', str(Path.home() / '.context')))

    # Service startup
    service_start_retries: int = 30
    service_start_delay: int = 1

# Global instance
config = QdrantConfig()
