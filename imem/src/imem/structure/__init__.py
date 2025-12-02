"""Structure domain - Synthesize and present results

EPIC 0: NoOp implementation only.
Later EPICs add real modules: curate, flip, reword, narrate.

STRUCTURE is the output layer that takes ranked chunks and prepares
them for presentation - selecting what to show, adjusting language,
and formatting for the target consumer.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..protocols import Module, NoOpModule

if TYPE_CHECKING:
    from ..context import QueryContext


class StructureOrchestrator:
    """Coordinates STRUCTURE sub-modules in sequence

    Flow: curate → flip → reword → narrate

    EPIC 0: All modules are NoOp. Just passes results through.
    """

    def __init__(
        self,
        curate: Optional[Module] = None,
        flip: Optional[Module] = None,
        reword: Optional[Module] = None,
        narrate: Optional[Module] = None,
    ):
        self.curate = curate or NoOpModule()
        self.flip = flip or NoOpModule()
        self.reword = reword or NoOpModule()
        self.narrate = narrate or NoOpModule()

    def present(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        """Present chunks for consumption

        Args:
            chunks: Ranked chunks from RETRIEVE
            context: Query context

        Returns:
            Presented/formatted chunks
        """
        # EPIC 0: NoOp - just return chunks unchanged
        # Note: We pass IndexContext but modules expect it as base context
        # Future EPICs will properly type this

        # For now, create a minimal context that NoOpModule can handle
        class MinimalContext:
            infrastructure = context.infrastructure

        minimal = MinimalContext()

        chunks = self.curate.execute(chunks, minimal)
        chunks = self.flip.execute(chunks, minimal)
        chunks = self.reword.execute(chunks, minimal)
        chunks = self.narrate.execute(chunks, minimal)

        return chunks


class NoOpStructureOrchestrator(StructureOrchestrator):
    """No-op structure orchestrator that passes chunks through unchanged"""

    def __init__(self):
        super().__init__()


def create_structure_orchestrator() -> StructureOrchestrator:
    """Factory for StructureOrchestrator with default NoOp plugins

    EPIC 0: All plugins are NoOp.
    """
    return NoOpStructureOrchestrator()


__all__ = [
    'StructureOrchestrator',
    'NoOpStructureOrchestrator',
    'create_structure_orchestrator',
]
