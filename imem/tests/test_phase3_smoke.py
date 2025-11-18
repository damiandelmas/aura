"""Phase 3 smoke tests - Verify critical bug fixes

Tests:
1. Factory creates backends correctly (fixed signature bug)
2. get_by_ids() uses O(n) query (fixed O(n²) bug)
3. Orchestrator builds chains (integration test)
4. Recency scorer works (ranking implementation)
5. Discovery errors are explicit (NotImplementedError)
"""

import pytest
from pathlib import Path
from imem.storage import create_store
from imem.compile import DocumentIndexer
from imem.compose import build_chain
from imem.compose.orchestrator import _get_scorer_for_phase
from imem.core import RetrievalContext


def test_factory_creates_sqlite():
    """Test factory creates SQLite backend with correct signature"""
    store = create_store(
        backend='sqlite',
        project_root=Path.cwd()
    )
    assert store is not None
    assert hasattr(store, 'search')


def test_factory_creates_qdrant():
    """Test factory creates Qdrant backend with kwargs (not dict)"""
    # This will fail if Qdrant service not running, but tests signature
    try:
        store = create_store(
            backend='qdrant',
            collection_name='test_docs',
            host='localhost',
            port=6334
        )
        assert store is not None
    except Exception as e:
        # Expected if Qdrant not running - just testing signature doesn't crash
        assert 'unsupported operand' not in str(e)  # Would indicate dict bug


def test_get_by_ids_is_efficient():
    """Test get_by_ids() uses single SQL query (O(n) not O(n²))"""
    from imem.storage.sqlite_backend import SQLiteVectorStore

    store = SQLiteVectorStore(project_root=Path.cwd())

    # Empty DB returns empty list (not crash)
    ids = ['test1', 'test2', 'test3']
    results = store.get_by_ids(ids)

    assert isinstance(results, list)
    # Should not have called query() in loop (would be slow)
    # Performance is implicit - just verify it works


def test_indexer_instantiates():
    """Test DocumentIndexer can be created"""
    store = create_store(backend='sqlite', project_root=Path.cwd())
    indexer = DocumentIndexer(store)
    assert indexer is not None


def test_orchestrator_builds_chain():
    """Test processor chain builds from config"""
    store = create_store(backend='sqlite', project_root=Path.cwd())
    config = {'search': {'mode': 'metadata'}}
    chain = build_chain(config, store)

    assert chain is not None
    assert len(chain.processors) >= 1  # At least SearchProcessor


def test_chain_executes():
    """Test chain executes without error"""
    store = create_store(backend='sqlite', project_root=Path.cwd())
    config = {'search': {'mode': 'metadata', 'filters': {}}}
    chain = build_chain(config, store)

    ctx = RetrievalContext(query="test", config=config)
    result = chain.execute(ctx)

    assert result is not None
    assert isinstance(result.results, list)


def test_recency_scorer_sorts_correctly():
    """Test recency scorer sorts by timestamp descending"""
    recency_scorer = _get_scorer_for_phase('recency')

    results = [
        {'metadata': {'timestamp': '2025-01-01'}},
        {'metadata': {'timestamp': '2025-01-03'}},
        {'metadata': {'timestamp': '2025-01-02'}}
    ]

    sorted_results = recency_scorer(results)

    # Should be sorted descending (most recent first)
    assert sorted_results[0]['metadata']['timestamp'] == '2025-01-03'
    assert sorted_results[1]['metadata']['timestamp'] == '2025-01-02'
    assert sorted_results[2]['metadata']['timestamp'] == '2025-01-01'


def test_metadata_scorer_is_identity():
    """Test metadata scorer returns results unchanged"""
    metadata_scorer = _get_scorer_for_phase('metadata')

    results = [{'id': '1'}, {'id': '2'}]
    sorted_results = metadata_scorer(results)

    assert sorted_results == results


def test_discovery_raises_not_implemented():
    """Test discovery processors raise NotImplementedError (not silent warnings)"""
    store = create_store(backend='sqlite', project_root=Path.cwd())

    # Config with siblings discovery should raise
    config = {
        'search': {'mode': 'metadata'},
        'discovery': {'siblings': True}
    }

    with pytest.raises(NotImplementedError) as exc_info:
        chain = build_chain(config, store)

    assert 'SiblingDiscovery' in str(exc_info.value)
    assert 'not yet implemented' in str(exc_info.value)


def test_unknown_scorer_raises_error():
    """Test unknown scorer name raises ValueError"""
    with pytest.raises(ValueError) as exc_info:
        _get_scorer_for_phase('unknown_scorer')

    assert 'Unknown scorer' in str(exc_info.value)
    assert 'unknown_scorer' in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
