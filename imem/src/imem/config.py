"""Centralized configuration for IMEM microservice"""
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class IMEMConfig:
    """IMEM configuration with environment variable overrides"""

    # Qdrant Service
    qdrant_port: int = int(os.getenv('IMEM_QDRANT_PORT', '6334'))
    qdrant_host: str = os.getenv('IMEM_QDRANT_HOST', 'localhost')
    qdrant_timeout: int = int(os.getenv('IMEM_QDRANT_TIMEOUT', '2'))

    # Paths
    context_dir: Path = Path(os.getenv('IMEM_CONTEXT_DIR', str(Path.home() / '.context')))
    registry_file: Path = context_dir / 'imem_registry.json'

    # Service startup
    service_start_retries: int = 30
    service_start_delay: int = 1

    # Search defaults
    default_limit: int = 10
    default_vector_name: str = 'e5-large-v2'
    default_model: str = 'intfloat/e5-large-v2'
    default_dimensions: int = 1024

# Global instance
config = IMEMConfig()
