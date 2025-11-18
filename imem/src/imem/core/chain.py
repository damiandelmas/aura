"""Processor chain abstraction for composable retrieval pipelines

Enables declarative, testable, reorderable retrieval stages.
Replaces hardcoded procedural pipeline in compose.py.

Example:
    chain = Chain([
        SearchProcessor(store),
        SiblingDiscovery(),
        MultiPhaseRanker([...]),
        FilterProcessor()
    ])

    result = chain.execute(RetrievalContext(query, config))
"""

from typing import Protocol, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class RetrievalContext:
    """Context passed through processor chain

    Accumulates results and metadata as it flows through pipeline stages.
    Immutable pattern - each processor returns new/modified context.
    """

    query: str
    """Search query text"""

    config: Dict[str, Any]
    """Pipeline configuration (search, discovery, ranking, etc.)"""

    results: List[Dict[str, Any]] = field(default_factory=list)
    """Accumulated search results (chunks with metadata)"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Pipeline metadata (timing, stage info, errors, etc.)"""


class Processor(Protocol):
    """Protocol for pipeline processors

    Each processor implements a single stage (search, discovery, ranking, etc.).
    Processors are composable, testable, and reorderable.
    """

    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        """Process context and return updated context

        Args:
            ctx: Current retrieval context

        Returns:
            Updated context (may be same object or new object)

        Raises:
            Exception: Processor-specific errors (caught by Chain)
        """
        ...


class Chain:
    """Sequential processor chain executor

    Executes processors in order, passing context through pipeline.
    Handles errors gracefully (logs and continues).

    Example:
        chain = Chain([
            SearchProcessor(store),
            SiblingDiscovery() if config.discovery else None,
            FilterProcessor()
        ])

        result = chain.execute(RetrievalContext(query, config))
    """

    def __init__(self, processors: List[Processor]):
        """Initialize chain

        Args:
            processors: List of processors (None values filtered out)
        """
        # Filter out None processors (for conditional stages)
        self.processors = [p for p in processors if p is not None]

    def execute(self, ctx: RetrievalContext) -> RetrievalContext:
        """Execute all processors in sequence

        Args:
            ctx: Initial retrieval context

        Returns:
            Final context after all processors
        """
        for processor in self.processors:
            try:
                ctx = processor.process(ctx)
            except Exception as e:
                # Log error but continue pipeline
                # Store error in context metadata for debugging
                errors = ctx.metadata.setdefault('errors', [])
                errors.append({
                    'processor': processor.__class__.__name__,
                    'error': str(e)
                })

        return ctx
