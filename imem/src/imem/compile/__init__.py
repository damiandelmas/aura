"""Compile domain - Document parsing and indexing

Responsible for:
- Parsing markdown documents into canonical chunks
- Indexing to SQLite storage
- Collection management

Note: CompileResolver exists but not exported - needs own EPIC for integration.
      It enables indexing unstructured logs from ANY agentic workflow.
"""

from .indexer import DocumentIndexer

__all__ = ['DocumentIndexer']
