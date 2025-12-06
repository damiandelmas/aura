"""NarrateModule - Format final output for the target consumer

EPIC 6: Format output for different consumers (markdown, JSON, context).

NarrateModule is the fourth and final stage in the STRUCTURE pipeline. It:
1. Transforms reworded chunks into appropriate output format
2. Adds structural elements (headers, indicators, attribution)
3. Builds lineage narratives if requested

Different consumers need different formats:
- AI agents want minimal context strings
- Humans want readable markdown with headers
- APIs want JSON with metadata
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from ..protocols import Module
from . import OutputFormat, MarkdownOutput, JSONOutput, ContextOutput, Output

if TYPE_CHECKING:
    from ..context import QueryContext

logger = logging.getLogger(__name__)


# ============================================================================
# Confidence Markers
# ============================================================================

CONFIDENCE_MARKERS = {
    'high': '✅',      # validity >= 0.8
    'medium': '⚠️',    # validity 0.5-0.8
    'low': '❓',       # validity < 0.5
}

LAYER_MARKERS = {
    'implementation': '📄',
    'pattern': '🔷',
}


class NarrateModule(Module):
    """Format final output for the target consumer

    Supports three output formats:
    - MARKDOWN: Human-readable with headers, indicators, content
    - JSON: Structured with full metadata for APIs
    - CONTEXT: Minimal for AI consumption

    Attributes:
        default_format: Default output format (MARKDOWN)
    """

    def __init__(
        self,
        default_format: OutputFormat = OutputFormat.MARKDOWN,
    ):
        """Initialize NarrateModule

        Args:
            default_format: Default output format
        """
        self.default_format = default_format

    @property
    def name(self) -> str:
        return "narrate"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> Output:
        """Execute output formatting

        Determines output format from context.query.output_format,
        then applies appropriate formatter.

        Args:
            chunks: Reworded chunks from RewordModule
            context: Query context

        Returns:
            Formatted output (MarkdownOutput, JSONOutput, or ContextOutput)
        """
        # Determine output format from query config (needed for empty results too)
        query_config = getattr(context, 'query', {}) or {}
        format_str = query_config.get('output_format', self.default_format.value)

        try:
            output_format = OutputFormat(format_str)
        except ValueError:
            output_format = self.default_format

        if not chunks:
            return self._empty_output(output_format)

        # Apply formatter
        if output_format == OutputFormat.MARKDOWN:
            return self._format_markdown(chunks, context)
        elif output_format == OutputFormat.JSON:
            return self._format_json(chunks, context)
        elif output_format == OutputFormat.CONTEXT:
            return self._format_context(chunks, context)
        else:
            return self._format_markdown(chunks, context)

    def _empty_output(self, output_format: OutputFormat = OutputFormat.MARKDOWN) -> Output:
        """Return empty output for no chunks, respecting requested format

        Args:
            output_format: Desired output format

        Returns:
            Empty output in the requested format
        """
        if output_format == OutputFormat.JSON:
            return JSONOutput(
                chunks=[],
                metadata={'count': 0, 'message': 'No results found'},
            )
        elif output_format == OutputFormat.CONTEXT:
            return ContextOutput(
                context='',
                confidence=0.0,
            )
        else:
            return MarkdownOutput(
                content="*No results found.*",
                sections=[],
            )

    # ========================================================================
    # Markdown Formatter
    # ========================================================================

    def _format_markdown(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> MarkdownOutput:
        """Format chunks as readable markdown

        Structure:
        - Header with result count
        - Chunks grouped by section_type (optional)
        - Each chunk with confidence indicator, content, source

        Args:
            chunks: Processed chunks
            context: Query context

        Returns:
            MarkdownOutput with formatted content
        """
        lines = []
        sections = []

        # Header
        lines.append(f"# Results ({len(chunks)} chunks)\n")

        # Group chunks by section_type for better organization
        grouped = self._group_by_section_type(chunks)

        for section_type, section_chunks in grouped.items():
            # Section header
            section_title = self._format_section_title(section_type)
            lines.append(f"\n## {section_title}\n")
            sections.append(section_title)

            for chunk in section_chunks:
                chunk_md = self._format_chunk_markdown(chunk)
                lines.append(chunk_md)
                lines.append("")  # Blank line between chunks

        content = '\n'.join(lines)

        return MarkdownOutput(
            content=content,
            sections=sections,
        )

    def _format_chunk_markdown(self, chunk: Dict[str, Any]) -> str:
        """Format a single chunk as markdown

        Args:
            chunk: Chunk to format

        Returns:
            Markdown string
        """
        lines = []

        # Confidence and layer indicators
        validity = chunk.get('validity', 0.5)
        layer = chunk.get('_layer', 'implementation')

        confidence_marker = self._get_confidence_marker(validity)
        layer_marker = LAYER_MARKERS.get(layer, '')

        # Section name as h3
        section_name = chunk.get('section_name', 'Untitled')
        lines.append(f"### {confidence_marker} {layer_marker} {section_name}\n")

        # Content (already has hedging prefixes from RewordModule)
        content = chunk.get('content', '')
        lines.append(content)
        lines.append("")

        # Source attribution
        file_path = chunk.get('file_path', '')
        timestamp = chunk.get('timestamp', '')
        if file_path:
            source_line = f"*Source: {file_path}"
            if timestamp:
                source_line += f" ({timestamp})"
            source_line += "*"
            lines.append(source_line)

        # Metadata footer (validity, centrality, rank)
        validity_pct = int(validity * 100)
        centrality = chunk.get('centrality', 0.5)
        centrality_pct = int(centrality * 100)
        rank = chunk.get('rank', 0.5)

        lines.append(f"\n`validity: {validity_pct}% | centrality: {centrality_pct}% | rank: {rank:.2f}`")

        return '\n'.join(lines)

    def _get_confidence_marker(self, validity: float) -> str:
        """Get confidence marker based on validity

        Args:
            validity: Validity score (0.0-1.0)

        Returns:
            Emoji marker
        """
        if validity >= 0.8:
            return CONFIDENCE_MARKERS['high']
        elif validity >= 0.5:
            return CONFIDENCE_MARKERS['medium']
        else:
            return CONFIDENCE_MARKERS['low']

    def _format_section_title(self, section_type: Optional[str]) -> str:
        """Format section type as title

        Args:
            section_type: Raw section type

        Returns:
            Formatted title
        """
        if not section_type:
            return "Other"
        return section_type.replace('_', ' ').title()

    def _group_by_section_type(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group chunks by section_type

        Args:
            chunks: Chunks to group

        Returns:
            Dict mapping section_type to chunks
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for chunk in chunks:
            section_type = chunk.get('section_type') or 'other'
            if section_type not in grouped:
                grouped[section_type] = []
            grouped[section_type].append(chunk)

        return grouped

    # ========================================================================
    # JSON Formatter
    # ========================================================================

    def _format_json(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> JSONOutput:
        """Format chunks as JSON with full metadata

        Args:
            chunks: Processed chunks
            context: Query context

        Returns:
            JSONOutput with chunks and metadata
        """
        # Convert chunks to DTOs (clean up internal fields)
        chunk_dtos = [self._chunk_to_dto(chunk) for chunk in chunks]

        # Build metadata
        metadata = {
            'count': len(chunks),
            'formatted_at': datetime.now(timezone.utc).isoformat(),
            'query': getattr(context, 'query', {}),
        }

        # Add aggregate confidence
        if chunks:
            avg_validity = sum(c.get('validity', 0.5) for c in chunks) / len(chunks)
            metadata['average_confidence'] = round(avg_validity, 2)

        return JSONOutput(
            chunks=chunk_dtos,
            metadata=metadata,
        )

    def _chunk_to_dto(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Convert chunk to clean DTO

        Removes internal fields (_flags, _reword, etc.)
        and structures for API consumption.

        Args:
            chunk: Raw chunk

        Returns:
            Clean DTO
        """
        return {
            'id': chunk.get('id'),
            'content': chunk.get('content'),
            'section_name': chunk.get('section_name'),
            'section_type': chunk.get('section_type'),
            'phase': chunk.get('phase'),
            'file_path': chunk.get('file_path'),
            'timestamp': chunk.get('timestamp'),
            'validity': chunk.get('validity', 0.5),
            'centrality': chunk.get('centrality', 0.5),
            'rank': chunk.get('rank', 0.5),
            'git_status': chunk.get('git_status', 'unvalidated'),
            'layer': chunk.get('_layer', 'implementation'),
            'flags': chunk.get('_flags', {}),
        }

    # ========================================================================
    # Context Formatter (for AI consumption)
    # ========================================================================

    def _format_context(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> ContextOutput:
        """Format chunks as minimal context for AI consumption

        Compact format with confidence markers.
        Strips metadata, focuses on content.

        Args:
            chunks: Processed chunks
            context: Query context

        Returns:
            ContextOutput with compact string
        """
        lines = []

        for chunk in chunks:
            validity = chunk.get('validity', 0.5)
            content = chunk.get('content', '').strip()
            section_name = chunk.get('section_name', '')

            # Confidence prefix
            if validity >= 0.8:
                conf = "[HIGH]"
            elif validity >= 0.5:
                conf = "[MED]"
            else:
                conf = "[LOW]"

            # Compact format: [CONF] Section: Content
            if section_name:
                lines.append(f"{conf} {section_name}: {content}")
            else:
                lines.append(f"{conf} {content}")

            lines.append("")  # Separator

        context_str = '\n'.join(lines).strip()

        # Calculate overall confidence
        if chunks:
            avg_validity = sum(c.get('validity', 0.5) for c in chunks) / len(chunks)
        else:
            avg_validity = 0.0

        return ContextOutput(
            context=context_str,
            confidence=round(avg_validity, 2),
        )


class NoOpNarrateModule(Module):
    """No-op narrate module that returns chunks as-is"""

    @property
    def name(self) -> str:
        return "noop_narrate"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        return chunks


__all__ = ['NarrateModule', 'NoOpNarrateModule']
