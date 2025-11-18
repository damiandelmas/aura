#!/usr/bin/env python3
"""
IMEM CLI - Thin command router using composition root pattern

This is the new streamlined CLI (Phase 3 refactor).
Business logic lives in domain modules (compile/, manage/, compose/).
Commands are thin wrappers delegating to controllers via app instance.
"""

import sys
from pathlib import Path
import warnings

# Suppress Pydantic warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')

# Add package to path if running as script
if __name__ == '__main__':
    package_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(package_dir))

# Import command definitions
from imem.cli.commands import imem


if __name__ == '__main__':
    imem()
