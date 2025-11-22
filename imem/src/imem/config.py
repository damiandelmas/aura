"""Centralized configuration for IMEM microservice

SQLite-first configuration. No external services required.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import subprocess


def sanitize_namespace(ns: str) -> str:
    """Convert namespace to filesystem-safe string

    Handles:
    - Branch names with slashes (feat/vectors -> feat-vectors)
    - Special characters
    - Whitespace
    """
    # Replace slashes with hyphens (feat/vectors -> feat-vectors)
    ns = ns.replace('/', '-')

    # Replace other special chars with hyphens
    ns = re.sub(r'[^a-zA-Z0-9_-]', '-', ns)

    # Remove duplicate hyphens
    ns = re.sub(r'-+', '-', ns)

    # Strip leading/trailing hyphens
    ns = ns.strip('-')

    # Limit length for filesystem safety
    ns = ns[:100]

    return ns or 'main'


def get_namespace() -> str:
    """Auto-detect namespace from git branch or worktree

    Priority chain:
    1. IMEM_NAMESPACE env var (explicit override)
    2. Git branch name (primary)
    3. Worktree directory name (fallback)
    4. "main" (default)
    """
    # Priority 1: Explicit override (testing/debugging)
    if ns := os.getenv('IMEM_NAMESPACE'):
        return sanitize_namespace(ns)

    # Priority 2: Git branch (primary)
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            check=False,
            timeout=1,
            cwd=Path.cwd()
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch:
                return sanitize_namespace(branch)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Priority 3: Worktree directory name
    cwd = Path.cwd()
    if 'worktrees' in cwd.parts:
        idx = cwd.parts.index('worktrees')
        if idx + 1 < len(cwd.parts):
            worktree_name = cwd.parts[idx + 1]
            return sanitize_namespace(worktree_name)

    # Priority 4: Default
    return 'main'


@dataclass
class IMEMConfig:
    """IMEM configuration with environment variable overrides

    SQLite-first: No external service configuration needed.
    """

    # Namespace (auto-detected from git or env)
    namespace: str = field(default_factory=get_namespace)

    # Paths - namespace-based storage
    imem_home: Path = Path(os.getenv('IMEM_HOME', str(Path.home() / '.imem')))

    # Legacy path for backward compatibility (deprecated)
    context_dir: Path = Path(os.getenv('IMEM_CONTEXT_DIR', str(Path.home() / '.context')))

    def __post_init__(self):
        """Set up namespace-based paths after initialization"""
        self.namespace_dir = self.imem_home / 'namespaces' / self.namespace
        self.registry_file = self.namespace_dir / 'registry.json'
        # Ensure directories exist
        self.namespace_dir.mkdir(parents=True, exist_ok=True)

    # Search defaults
    default_limit: int = 10
    default_vector_name: str = 'nomic-embed-v1.5'
    default_model: str = 'nomic-ai/nomic-embed-text-v1.5'
    default_dimensions: int = 768


# Model Registry - Maps vector names to full model configuration
# Used for auto-detecting which model to load based on collection's vector config
MODEL_REGISTRY = {
    "e5-large-v2": {
        "model_path": "intfloat/e5-large-v2",
        "dimensions": 1024,
        "trust_remote_code": False
    },
    "nomic-embed-v1.5": {
        "model_path": "nomic-ai/nomic-embed-text-v1.5",
        "dimensions": 768,
        "trust_remote_code": True
    }
}

# Global instance
config = IMEMConfig()
