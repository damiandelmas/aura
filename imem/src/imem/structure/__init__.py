"""Structure domain - Synthesize and present results for consumption

EPIC 6: STRUCTURE Domain - Presentation layer with validity-aware output.

Flow: curate → flip → reword → narrate

StructureOrchestrator coordinates four modules:
- CurateModule: Filter/dedupe based on validity/centrality
- FlipModule: Choose implementation or pattern layer
- RewordModule: Add hedging for low-validity content
- NarrateModule: Format output (markdown, JSON, context)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from ..protocols import Module, NoOpModule

if TYPE_CHECKING:
    from ..context import QueryContext


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class CuratedChunk:
    """Chunk with presentation flags from CurateModule

    Attributes:
        chunk: Original chunk dictionary
        flags: Presentation flags for downstream modules
    """
    chunk: Dict[str, Any]
    needs_hedging: bool = False      # validity < 0.5
    high_centrality: bool = False    # centrality > 0.7
    is_superseded: bool = False      # git_status == 'superseded'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary preserving chunk data with flags"""
        return {
            **self.chunk,
            '_flags': {
                'needs_hedging': self.needs_hedging,
                'high_centrality': self.high_centrality,
                'is_superseded': self.is_superseded,
            }
        }


class OutputFormat(Enum):
    """Output format options for NarrateModule"""
    MARKDOWN = "markdown"
    JSON = "json"
    CONTEXT = "context"  # Minimal for AI consumption


@dataclass
class MarkdownOutput:
    """Markdown-formatted output

    Attributes:
        content: Formatted markdown string
        sections: List of section headers for navigation
    """
    content: str
    sections: List[str] = field(default_factory=list)


@dataclass
class JSONOutput:
    """JSON-formatted output with full metadata

    Attributes:
        chunks: List of chunk DTOs with metadata
        metadata: Query metadata (timing, counts, etc.)
    """
    chunks: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextOutput:
    """Minimal output for AI consumption

    Attributes:
        context: Compact context string
        confidence: Overall confidence (0.0-1.0)
    """
    context: str
    confidence: float = 0.5


# Union type for output
Output = Union[MarkdownOutput, JSONOutput, ContextOutput, List[Dict[str, Any]]]


# ============================================================================
# StructureOrchestrator
# ============================================================================

class StructureOrchestrator:
    """Coordinates STRUCTURE sub-modules in sequence

    Flow: curate → flip → reword → narrate

    Takes ranked chunks from RETRIEVE and prepares them for presentation:
    - CurateModule: Filter by validity, dedupe, flag for hedging
    - FlipModule: Serve pattern layer for superseded chunks
    - RewordModule: Add uncertainty markers for low validity
    - NarrateModule: Format for target consumer

    Usage:
        orchestrator = StructureOrchestrator(
            curate=CurateModule(),
            flip=FlipModule(db),
            reword=RewordModule(),
            narrate=NarrateModule(),
        )
        output = orchestrator.present(chunks, context)
    """

    def __init__(
        self,
        curate: Optional[Module] = None,
        flip: Optional[Module] = None,
        reword: Optional[Module] = None,
        narrate: Optional[Module] = None,
    ):
        """Initialize StructureOrchestrator with modules

        Args:
            curate: CurateModule (default: NoOp)
            flip: FlipModule (default: NoOp)
            reword: RewordModule (default: NoOp)
            narrate: NarrateModule (default: NoOp)
        """
        self.curate = curate or NoOpModule()
        self.flip = flip or NoOpModule()
        self.reword = reword or NoOpModule()
        self.narrate = narrate or NoOpModule()

    def present(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> Output:
        """Present chunks for consumption

        Executes the four-stage pipeline:
        1. curate.execute() - Filter, dedupe, flag
        2. flip.execute() - Layer selection
        3. reword.execute() - Language adjustment
        4. narrate.execute() - Format output

        Args:
            chunks: Ranked chunks from RETRIEVE
            context: Query context with infrastructure and config

        Returns:
            Formatted output (type depends on output_format config)
        """
        # Execute pipeline stages
        chunks = self.curate.execute(chunks, context)
        chunks = self.flip.execute(chunks, context)
        chunks = self.reword.execute(chunks, context)
        output = self.narrate.execute(chunks, context)

        return output


class NoOpStructureOrchestrator(StructureOrchestrator):
    """No-op structure orchestrator that passes chunks through unchanged"""

    def __init__(self):
        super().__init__()


def create_structure_orchestrator(
    db: Optional[Any] = None,
    config: Optional[Dict[str, Any]] = None,
) -> StructureOrchestrator:
    """Factory for StructureOrchestrator with real implementations

    EPIC 6: Creates orchestrator with full module chain.

    Args:
        db: SQLiteStore for pattern lookup (FlipModule)
        config: Configuration overrides

    Returns:
        Configured StructureOrchestrator
    """
    from .curate import CurateModule
    from .flip import FlipModule
    from .reword import RewordModule
    from .narrate import NarrateModule

    effective_config = config or {}

    return StructureOrchestrator(
        curate=CurateModule(
            min_validity=effective_config.get('min_validity', 0.3),
            max_results=effective_config.get('max_results', 20),
        ),
        flip=FlipModule(db=db),
        reword=RewordModule(),
        narrate=NarrateModule(
            default_format=OutputFormat(
                effective_config.get('output_format', 'markdown')
            )
        ),
    )


__all__ = [
    # Data structures
    'CuratedChunk',
    'OutputFormat',
    'MarkdownOutput',
    'JSONOutput',
    'ContextOutput',
    'Output',
    # Orchestrator
    'StructureOrchestrator',
    'NoOpStructureOrchestrator',
    'create_structure_orchestrator',
]
