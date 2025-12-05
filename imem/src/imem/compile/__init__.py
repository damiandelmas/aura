"""Compile domain - Document parsing and indexing

Responsible for:
- Parsing markdown documents into canonical chunks
- Indexing to SQLite storage
- Collection management
- Pattern extraction (EPIC 7)

Note: CompileResolver exists but not exported - needs own EPIC for integration.
      It enables indexing unstructured logs from ANY agentic workflow.
"""

from .indexer import DocumentIndexer
from .pattern import PatternExtractor, NoOpPatternExtractor, create_pattern_extractor
from .pattern_client import PatternClient, NoOpPatternClient, PatternResponse, create_pattern_client

__all__ = [
    'DocumentIndexer',
    # EPIC 7: Pattern Extraction
    'PatternExtractor',
    'NoOpPatternExtractor',
    'create_pattern_extractor',
    'PatternClient',
    'NoOpPatternClient',
    'PatternResponse',
    'create_pattern_client',
]
