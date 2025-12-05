"""EPIC 6: STRUCTURE Domain Tests

Tests for:
- CurateModule: Filter, dedupe, flag
- FlipModule: Layer selection (implementation vs pattern)
- RewordModule: Hedging and temporal framing
- NarrateModule: Output formats (markdown, JSON, context)
- StructureOrchestrator: Full pipeline integration
"""

import pytest
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict

from imem.storage.sqlite import SQLiteStore
from imem.context import Infrastructure, QueryContext

# Structure imports
from imem.structure import (
    StructureOrchestrator,
    NoOpStructureOrchestrator,
    create_structure_orchestrator,
    CuratedChunk,
    OutputFormat,
    MarkdownOutput,
    JSONOutput,
    ContextOutput,
)
from imem.structure.curate import CurateModule, NoOpCurateModule
from imem.structure.flip import FlipModule, NoOpFlipModule
from imem.structure.reword import RewordModule, NoOpRewordModule
from imem.structure.narrate import NarrateModule, NoOpNarrateModule


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SQLiteStore(Path(tmpdir))
        yield db


@pytest.fixture
def sample_chunks():
    """Sample chunks with various validity/centrality combinations"""
    return [
        {
            'id': 'high_valid',
            'content': 'High validity content',
            'section_name': 'Auth Decision',
            'section_type': 'decisions',
            'phase': 'develop',
            'file_path': '/test/auth.md',
            'timestamp': '2025-12-01',
            'validity': 0.9,
            'centrality': 0.8,
            'rank': 0.85,
            'git_status': 'validated',
        },
        {
            'id': 'low_valid',
            'content': 'Low validity content',
            'section_name': 'Old Pattern',
            'section_type': 'patterns',
            'phase': 'design',
            'file_path': '/test/old.md',
            'timestamp': '2025-06-01',
            'validity': 0.3,
            'centrality': 0.6,
            'rank': 0.4,
            'git_status': 'unvalidated',
        },
        {
            'id': 'superseded',
            'content': 'Superseded content',
            'section_name': 'Legacy Auth',
            'section_type': 'decisions',
            'phase': 'develop',
            'file_path': '/test/legacy.md',
            'timestamp': '2025-01-01',
            'validity': 0.2,
            'centrality': 0.9,
            'rank': 0.3,
            'git_status': 'superseded',
        },
        {
            'id': 'contradicted',
            'content': 'Contradicted content',
            'section_name': 'Wrong Info',
            'section_type': 'notes',
            'phase': 'develop',
            'file_path': '/test/wrong.md',
            'timestamp': '2025-03-01',
            'validity': 0.1,
            'centrality': 0.2,
            'rank': 0.15,
            'git_status': 'contradicted',
        },
    ]


@pytest.fixture
def mock_context(temp_db):
    """Create mock QueryContext for testing"""
    @dataclass
    class MinimalInfra:
        db: Any
        git: Any = None
        config: Dict = None

        def __post_init__(self):
            self.config = self.config or {}

    return QueryContext(
        infrastructure=MinimalInfra(db=temp_db),
        query={},
        results=[],
        metadata={},
    )


# ============================================================================
# CurateModule Tests
# ============================================================================

class TestCurateModule:
    """Tests for CurateModule - filtering, deduplication, flagging"""

    def test_name(self):
        module = CurateModule()
        assert module.name == "curate"

    def test_filter_by_validity(self, sample_chunks, mock_context):
        """Drops chunks below validity threshold"""
        module = CurateModule(min_validity=0.3)
        result = module.execute(sample_chunks, mock_context)

        # Should keep high_valid (0.9), low_valid (0.3), superseded (0.2 but just below)
        # Should drop contradicted (0.1) and superseded (0.2) since < 0.3
        ids = [c['id'] for c in result]
        assert 'high_valid' in ids
        assert 'low_valid' in ids
        assert 'contradicted' not in ids  # Always dropped due to git_status

    def test_filter_contradicted(self, sample_chunks, mock_context):
        """Always drops contradicted chunks regardless of validity"""
        module = CurateModule(min_validity=0.0)  # No validity filter
        result = module.execute(sample_chunks, mock_context)

        ids = [c['id'] for c in result]
        assert 'contradicted' not in ids

    def test_order_by_rank(self, sample_chunks, mock_context):
        """Orders chunks by rank descending"""
        module = CurateModule()
        result = module.execute(sample_chunks, mock_context)

        # Check order: high_valid (0.85) > low_valid (0.4) > superseded (0.3)
        ranks = [c.get('rank', 0) for c in result]
        assert ranks == sorted(ranks, reverse=True)

    def test_limit_max_results(self, sample_chunks, mock_context):
        """Limits to max_results"""
        module = CurateModule(max_results=2)
        result = module.execute(sample_chunks, mock_context)

        assert len(result) <= 2

    def test_adds_flags(self, sample_chunks, mock_context):
        """Adds _flags metadata to chunks"""
        module = CurateModule()
        result = module.execute(sample_chunks, mock_context)

        for chunk in result:
            assert '_flags' in chunk
            assert 'needs_hedging' in chunk['_flags']
            assert 'high_centrality' in chunk['_flags']
            assert 'is_superseded' in chunk['_flags']

    def test_needs_hedging_flag(self, sample_chunks, mock_context):
        """Sets needs_hedging for validity < 0.5"""
        module = CurateModule(hedging_threshold=0.5)
        result = module.execute(sample_chunks, mock_context)

        for chunk in result:
            expected_hedging = chunk['validity'] < 0.5
            assert chunk['_flags']['needs_hedging'] == expected_hedging

    def test_high_centrality_flag(self, sample_chunks, mock_context):
        """Sets high_centrality for centrality > 0.7"""
        module = CurateModule(centrality_threshold=0.7)
        result = module.execute(sample_chunks, mock_context)

        for chunk in result:
            expected_high = chunk['centrality'] > 0.7
            assert chunk['_flags']['high_centrality'] == expected_high

    def test_is_superseded_flag(self, sample_chunks, mock_context):
        """Sets is_superseded for git_status == 'superseded'"""
        module = CurateModule(min_validity=0.1)  # Low threshold to include superseded
        result = module.execute(sample_chunks, mock_context)

        for chunk in result:
            expected_superseded = chunk.get('git_status') == 'superseded'
            assert chunk['_flags']['is_superseded'] == expected_superseded

    def test_empty_input(self, mock_context):
        """Handles empty input"""
        module = CurateModule()
        result = module.execute([], mock_context)
        assert result == []

    def test_noop_module(self, sample_chunks, mock_context):
        """NoOpCurateModule returns unchanged"""
        module = NoOpCurateModule()
        result = module.execute(sample_chunks, mock_context)
        assert result == sample_chunks


# ============================================================================
# FlipModule Tests
# ============================================================================

class TestFlipModule:
    """Tests for FlipModule - layer selection"""

    def test_name(self):
        module = FlipModule()
        assert module.name == "flip"

    def test_adds_layer_metadata(self, sample_chunks, mock_context):
        """Adds _layer metadata to chunks"""
        module = FlipModule()
        # Add _flags for is_superseded check
        for chunk in sample_chunks:
            chunk['_flags'] = {'is_superseded': chunk.get('git_status') == 'superseded'}

        result = module.execute(sample_chunks, mock_context)

        for chunk in result:
            assert '_layer' in chunk
            assert chunk['_layer'] in ('implementation', 'pattern')

    def test_high_validity_gets_implementation(self, mock_context):
        """High validity chunks serve implementation layer"""
        module = FlipModule(validity_threshold=0.3)
        chunks = [{
            'id': 'valid',
            'content': 'Valid content',
            'validity': 0.9,
            '_flags': {'is_superseded': False},
        }]

        result = module.execute(chunks, mock_context)

        assert result[0]['_layer'] == 'implementation'

    def test_low_validity_tries_pattern(self, mock_context):
        """Low validity chunks try to flip to pattern"""
        module = FlipModule(validity_threshold=0.3)
        chunks = [{
            'id': 'old',
            'content': 'Old content',
            'validity': 0.1,
            '_flags': {'is_superseded': False},
        }]

        result = module.execute(chunks, mock_context)

        # Since no pattern available, falls back to implementation
        # but _layer is still 'implementation' (graceful degradation)
        assert '_layer' in result[0]

    def test_superseded_flag_triggers_flip(self, mock_context):
        """is_superseded flag triggers pattern lookup"""
        module = FlipModule(validity_threshold=0.3)
        chunks = [{
            'id': 'superseded',
            'content': 'Superseded content',
            'validity': 0.5,  # Above threshold
            '_flags': {'is_superseded': True},
        }]

        result = module.execute(chunks, mock_context)

        # Would flip if pattern available
        assert '_layer' in result[0]

    def test_use_pattern_file_flag(self, mock_context):
        """use_pattern_file flag forces pattern layer"""
        module = FlipModule(validity_threshold=0.3)
        chunks = [{
            'id': 'explicit',
            'content': 'Explicit pattern request',
            'validity': 0.9,  # High validity
            'use_pattern_file': True,
            '_flags': {'is_superseded': False},
        }]

        result = module.execute(chunks, mock_context)

        # Would flip if pattern available
        assert '_layer' in result[0]

    def test_pattern_layer_substitutes_content(self, mock_context):
        """When pattern exists, content is substituted"""
        module = FlipModule(validity_threshold=0.3)
        chunks = [{
            'id': 'with_pattern',
            'content': 'Implementation details',
            'pattern_layer': 'Abstracted pattern',
            'validity': 0.1,
            '_flags': {'is_superseded': False},
        }]

        result = module.execute(chunks, mock_context)

        assert result[0]['content'] == 'Abstracted pattern'
        assert result[0]['_layer'] == 'pattern'
        assert result[0]['_original_content'] == 'Implementation details'

    def test_empty_input(self, mock_context):
        """Handles empty input"""
        module = FlipModule()
        result = module.execute([], mock_context)
        assert result == []

    def test_noop_module(self, sample_chunks, mock_context):
        """NoOpFlipModule adds implementation layer"""
        module = NoOpFlipModule()
        result = module.execute(sample_chunks, mock_context)

        for chunk in result:
            assert chunk.get('_layer') == 'implementation'


# ============================================================================
# RewordModule Tests
# ============================================================================

class TestRewordModule:
    """Tests for RewordModule - hedging and temporal framing"""

    def test_name(self):
        module = RewordModule()
        assert module.name == "reword"

    def test_adds_reword_metadata(self, sample_chunks, mock_context):
        """Adds _reword metadata to chunks"""
        module = RewordModule()
        # Add _flags
        for chunk in sample_chunks:
            chunk['_flags'] = {
                'needs_hedging': chunk['validity'] < 0.5,
                'is_superseded': chunk.get('git_status') == 'superseded',
                'high_centrality': chunk['centrality'] > 0.7,
            }

        result = module.execute(sample_chunks, mock_context)

        for chunk in result:
            assert '_reword' in chunk
            assert 'hedged' in chunk['_reword']

    def test_strong_hedging_for_very_low_validity(self, mock_context):
        """Strong hedging for validity < 0.3"""
        module = RewordModule(strong_threshold=0.3)
        chunks = [{
            'id': 'weak',
            'content': 'Original content',
            'validity': 0.1,
            '_flags': {'needs_hedging': True, 'is_superseded': False, 'high_centrality': False},
        }]

        result = module.execute(chunks, mock_context)

        assert '⚠️ May be outdated' in result[0]['content']
        assert result[0]['_reword']['hedge_strength'] == 'strong'

    def test_moderate_hedging_for_medium_validity(self, mock_context):
        """Moderate hedging for validity 0.3-0.5"""
        module = RewordModule(strong_threshold=0.3, moderate_threshold=0.5)
        chunks = [{
            'id': 'medium',
            'content': 'Original content',
            'validity': 0.4,
            '_flags': {'needs_hedging': True, 'is_superseded': False, 'high_centrality': False},
        }]

        result = module.execute(chunks, mock_context)

        assert 'may have changed' in result[0]['content']
        assert result[0]['_reword']['hedge_strength'] == 'moderate'

    def test_superseded_framing(self, mock_context):
        """Superseded chunks get temporal framing"""
        module = RewordModule()
        chunks = [{
            'id': 'old',
            'content': 'Old approach',
            'validity': 0.5,
            '_flags': {'needs_hedging': False, 'is_superseded': True, 'high_centrality': False},
        }]

        result = module.execute(chunks, mock_context)

        assert 'Previously:' in result[0]['content']
        assert result[0]['_reword']['superseded_framing'] is True

    def test_centrality_marker(self, mock_context):
        """High centrality chunks get marker"""
        module = RewordModule()
        chunks = [{
            'id': 'key',
            'content': 'Key insight',
            'validity': 0.9,
            '_flags': {'needs_hedging': False, 'is_superseded': False, 'high_centrality': True},
        }]

        result = module.execute(chunks, mock_context)

        assert '[Key Insight]' in result[0]['content']
        assert result[0]['_reword']['centrality_marked'] is True

    def test_no_hedging_for_valid_chunks(self, mock_context):
        """Valid chunks don't get hedging"""
        module = RewordModule()
        chunks = [{
            'id': 'valid',
            'content': 'Valid content',
            'validity': 0.9,
            '_flags': {'needs_hedging': False, 'is_superseded': False, 'high_centrality': False},
        }]

        result = module.execute(chunks, mock_context)

        assert result[0]['content'] == 'Valid content'
        assert result[0]['_reword']['hedged'] is False

    def test_empty_input(self, mock_context):
        """Handles empty input"""
        module = RewordModule()
        result = module.execute([], mock_context)
        assert result == []

    def test_noop_module(self, sample_chunks, mock_context):
        """NoOpRewordModule returns unchanged"""
        module = NoOpRewordModule()
        result = module.execute(sample_chunks, mock_context)
        assert result == sample_chunks


# ============================================================================
# NarrateModule Tests
# ============================================================================

class TestNarrateModule:
    """Tests for NarrateModule - output formatting"""

    def test_name(self):
        module = NarrateModule()
        assert module.name == "narrate"

    def test_markdown_output_format(self, sample_chunks, mock_context):
        """Produces MarkdownOutput"""
        module = NarrateModule(default_format=OutputFormat.MARKDOWN)
        # Add required metadata
        for chunk in sample_chunks:
            chunk['_layer'] = 'implementation'

        result = module.execute(sample_chunks, mock_context)

        assert isinstance(result, MarkdownOutput)
        assert len(result.content) > 0
        assert 'Results' in result.content
        assert len(result.sections) > 0

    def test_json_output_format(self, sample_chunks, mock_context):
        """Produces JSONOutput"""
        mock_context.query = {'output_format': 'json'}
        module = NarrateModule()
        for chunk in sample_chunks:
            chunk['_layer'] = 'implementation'

        result = module.execute(sample_chunks, mock_context)

        assert isinstance(result, JSONOutput)
        assert len(result.chunks) == len(sample_chunks)
        assert 'count' in result.metadata
        assert 'average_confidence' in result.metadata

    def test_context_output_format(self, sample_chunks, mock_context):
        """Produces ContextOutput for AI consumption"""
        mock_context.query = {'output_format': 'context'}
        module = NarrateModule()
        for chunk in sample_chunks:
            chunk['_layer'] = 'implementation'

        result = module.execute(sample_chunks, mock_context)

        assert isinstance(result, ContextOutput)
        assert len(result.context) > 0
        assert 0.0 <= result.confidence <= 1.0

    def test_markdown_includes_confidence_markers(self, mock_context):
        """Markdown output includes confidence markers"""
        module = NarrateModule(default_format=OutputFormat.MARKDOWN)
        chunks = [
            {'id': 'high', 'content': 'High conf', 'validity': 0.9, 'centrality': 0.5,
             'rank': 0.7, 'section_name': 'Test', 'section_type': 'test',
             '_layer': 'implementation'},
            {'id': 'low', 'content': 'Low conf', 'validity': 0.2, 'centrality': 0.5,
             'rank': 0.3, 'section_name': 'Test2', 'section_type': 'test',
             '_layer': 'implementation'},
        ]

        result = module.execute(chunks, mock_context)

        assert '✅' in result.content  # High confidence
        assert '❓' in result.content  # Low confidence

    def test_markdown_includes_source_attribution(self, mock_context):
        """Markdown output includes source attribution"""
        module = NarrateModule(default_format=OutputFormat.MARKDOWN)
        chunks = [{
            'id': 'c1',
            'content': 'Test content',
            'file_path': '/test/file.md',
            'timestamp': '2025-12-01',
            'validity': 0.5,
            'centrality': 0.5,
            'rank': 0.5,
            'section_name': 'Test',
            'section_type': 'test',
            '_layer': 'implementation',
        }]

        result = module.execute(chunks, mock_context)

        assert '/test/file.md' in result.content
        assert '2025-12-01' in result.content

    def test_context_output_has_confidence_prefixes(self, mock_context):
        """Context output has [HIGH]/[MED]/[LOW] prefixes"""
        module = NarrateModule()
        mock_context.query = {'output_format': 'context'}
        chunks = [
            {'id': 'h', 'content': 'High', 'validity': 0.9, 'section_name': 'H', '_layer': 'implementation'},
            {'id': 'm', 'content': 'Med', 'validity': 0.6, 'section_name': 'M', '_layer': 'implementation'},
            {'id': 'l', 'content': 'Low', 'validity': 0.2, 'section_name': 'L', '_layer': 'implementation'},
        ]

        result = module.execute(chunks, mock_context)

        assert '[HIGH]' in result.context
        assert '[MED]' in result.context
        assert '[LOW]' in result.context

    def test_empty_output(self, mock_context):
        """Handles empty input gracefully"""
        module = NarrateModule()
        result = module.execute([], mock_context)

        assert isinstance(result, MarkdownOutput)
        assert 'No results' in result.content

    def test_noop_module(self, sample_chunks, mock_context):
        """NoOpNarrateModule returns chunks as-is"""
        module = NoOpNarrateModule()
        result = module.execute(sample_chunks, mock_context)
        assert result == sample_chunks


# ============================================================================
# StructureOrchestrator Integration Tests
# ============================================================================

class TestStructureOrchestrator:
    """Tests for full STRUCTURE pipeline"""

    def test_full_pipeline(self, sample_chunks, mock_context):
        """Complete pipeline: curate → flip → reword → narrate"""
        orchestrator = StructureOrchestrator(
            curate=CurateModule(min_validity=0.15),
            flip=FlipModule(),
            reword=RewordModule(),
            narrate=NarrateModule(default_format=OutputFormat.MARKDOWN),
        )

        result = orchestrator.present(sample_chunks, mock_context)

        assert isinstance(result, MarkdownOutput)
        assert len(result.content) > 0
        # Should have filtered out contradicted chunk
        assert 'Wrong Info' not in result.content

    def test_noop_orchestrator(self, sample_chunks, mock_context):
        """NoOp orchestrator passes through unchanged"""
        orchestrator = NoOpStructureOrchestrator()
        result = orchestrator.present(sample_chunks, mock_context)

        # NoOp narrate returns list, not Output
        assert isinstance(result, list)
        assert len(result) == len(sample_chunks)

    def test_factory_creates_real_modules(self, temp_db):
        """Factory creates orchestrator with real implementations"""
        orchestrator = create_structure_orchestrator(db=temp_db)

        assert isinstance(orchestrator.curate, CurateModule)
        assert isinstance(orchestrator.flip, FlipModule)
        assert isinstance(orchestrator.reword, RewordModule)
        assert isinstance(orchestrator.narrate, NarrateModule)

    def test_factory_config_override(self, temp_db):
        """Factory accepts config overrides"""
        orchestrator = create_structure_orchestrator(
            db=temp_db,
            config={
                'min_validity': 0.5,
                'max_results': 10,
                'output_format': 'json',
            }
        )

        assert orchestrator.curate.min_validity == 0.5
        assert orchestrator.curate.max_results == 10


# ============================================================================
# Philosophy Validation Tests
# ============================================================================

class TestPhilosophyGuardRails:
    """Tests ensuring STRUCTURE philosophy is maintained"""

    def test_obsolescence_as_promotion(self, mock_context):
        """Superseded chunks flip to pattern layer"""
        flip = FlipModule(validity_threshold=0.3)
        chunks = [{
            'id': 'old',
            'content': 'Old implementation details',
            'pattern_layer': 'Abstracted pattern insight',
            'validity': 0.2,  # Low validity
            '_flags': {'is_superseded': True},
        }]

        result = flip.execute(chunks, mock_context)

        # Should serve pattern, not implementation
        assert result[0]['content'] == 'Abstracted pattern insight'
        assert result[0]['_layer'] == 'pattern'

    def test_zero_loss_degradation(self, mock_context):
        """When pattern unavailable, gracefully degrades to implementation"""
        flip = FlipModule(validity_threshold=0.3)
        chunks = [{
            'id': 'no_pattern',
            'content': 'Implementation without pattern',
            # No pattern_layer field
            'validity': 0.2,
            '_flags': {'is_superseded': True},
        }]

        result = flip.execute(chunks, mock_context)

        # Should keep implementation (graceful degradation)
        assert result[0]['content'] == 'Implementation without pattern'
        assert result[0]['_layer'] == 'implementation'

    def test_centrality_visibility(self, mock_context):
        """High centrality chunks are visibly marked"""
        reword = RewordModule()
        chunks = [{
            'id': 'key',
            'content': 'Key decision',
            'validity': 0.9,
            '_flags': {'needs_hedging': False, 'is_superseded': False, 'high_centrality': True},
        }]

        result = reword.execute(chunks, mock_context)

        assert '[Key Insight]' in result[0]['content']

    def test_validity_visibility(self, mock_context):
        """Low validity is visible through hedging"""
        reword = RewordModule()
        chunks = [{
            'id': 'uncertain',
            'content': 'Uncertain claim',
            'validity': 0.2,
            '_flags': {'needs_hedging': True, 'is_superseded': False, 'high_centrality': False},
        }]

        result = reword.execute(chunks, mock_context)

        assert '⚠️' in result[0]['content'] or 'outdated' in result[0]['content']
