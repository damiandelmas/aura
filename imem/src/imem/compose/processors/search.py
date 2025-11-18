"""Search processor - Initial retrieval stage

Executes search against storage backend (SQLite or Qdrant).
Backend-agnostic via VectorStore protocol.
"""

from typing import Optional
import logging

from ...core.chain import Processor, RetrievalContext
from ...storage.protocol import VectorStore

logger = logging.getLogger(__name__)


class SearchProcessor(Processor):
    """Execute search query against storage backend

    Modes:
    - 'metadata': Fast SQLite queries (< 10ms)
    - 'semantic': Vector similarity search (Qdrant)

    Example:
        # Metadata-only search (fast)
        processor = SearchProcessor(store, mode='metadata')
        ctx = processor.process(RetrievalContext(
            query="authentication",
            config={'search': {'filters': {'phase': 'develop'}, 'limit': 10}}
        ))

        # Semantic search (slower, higher quality)
        processor = SearchProcessor(store, mode='semantic')
    """

    def __init__(self, store: VectorStore, mode: str = 'metadata'):
        """Initialize search processor

        Args:
            store: VectorStore backend (SQLite or Qdrant)
            mode: 'metadata' (fast SQL) or 'semantic' (vector similarity)
        """
        self.store = store
        self.mode = mode

    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        """Execute search and populate context.results

        Args:
            ctx: Retrieval context with query and config

        Returns:
            Updated context with results populated

        Config format:
            {
                'search': {
                    'text': 'query text',
                    'filters': {'phase': 'develop', 'section_type': 'Decision'},
                    'limit': 10
                }
            }
        """
        search_config = ctx.config.get('search', {})

        # Extract search parameters
        query_text = search_config.get('text', ctx.query or '')
        filters = search_config.get('filters', {})
        limit = search_config.get('limit', 10)

        # Determine vector mode
        use_vector = (self.mode == 'semantic')

        try:
            # Execute search
            results = self.store.search(
                query=query_text,
                filters=filters,
                limit=limit,
                use_vector=use_vector
            )

            # Convert SearchResult objects to dicts
            ctx.results = [r.to_dict() for r in results]

            # Add metadata
            ctx.metadata['search'] = {
                'mode': self.mode,
                'query': query_text,
                'filters': filters,
                'result_count': len(ctx.results)
            }

            logger.info(f"Search ({self.mode}): {len(ctx.results)} results for '{query_text}'")

        except Exception as e:
            logger.error(f"Search failed: {e}")
            # Context will have empty results, error logged in Chain
            raise

        return ctx
