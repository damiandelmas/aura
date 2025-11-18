"""Compile domain - Document parsing and indexing

Responsible for:
- Parsing markdown documents into canonical chunks
- Indexing to vector storage backends
- Collection management
- Template-based extraction (changelog, conversations, ADR)
- Structural resolution (phase, section_type normalization)

This domain handles the "compilation" of raw documentation into
searchable, structured chunks with metadata.
"""

from .indexer import DocumentIndexer
from .resolver import CompileResolver

__all__ = ['DocumentIndexer', 'CompileResolver']
