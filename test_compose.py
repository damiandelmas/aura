#!/usr/bin/env python3
"""
Test compose functionality with 5 critical queries
This validates Phase 6 implementation before proceeding to Phase 7
"""

import json
import sys
import asyncio
from pathlib import Path

# Add imem to path
sys.path.insert(0, str(Path(__file__).parent / 'imem' / 'src'))

from imem.compose import compose
from imem.registry import SimpleRegistry


def test_query_1_explain_decision():
    """Query 1: Explain decision (siblings + genealogy)"""
    print("=" * 80)
    print("TEST 1: Explain Decision (siblings + genealogy)")
    print("=" * 80)

    config = {
        "search": {
            "text": "JWT authentication",
            "filters": {"phase": "develop"},
            "limit": 1
        },
        "discovery": {
            "siblings": True,
            "genealogy": True
        }
    }

    # Get collection name
    registry = SimpleRegistry()
    project_root = registry.get_project_root()
    info = registry.get_project_info(project_root)

    if not info:
        print("❌ Project not registered. Run 'imem init' first.")
        return False

    collection_name = info['collection']
    print(f"Collection: {collection_name}")
    print(f"Config: {json.dumps(config, indent=2)}")
    print()

    try:
        result = asyncio.run(compose(collection_name, config))

        if result['results']:
            primary = result['results'][0]
            print(f"✅ Found primary result:")
            print(f"   Section: {primary['payload'].get('section_name', 'N/A')}")
            print(f"   Siblings: {len(primary.get('siblings', []))}")
            print(f"   Genealogy: {len(primary.get('genealogy', []))}")
            return True
        else:
            print("❌ No results found")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_2_trace_evolution():
    """Query 2: Trace evolution (temporal)"""
    print("\n" + "=" * 80)
    print("TEST 2: Trace Evolution (temporal)")
    print("=" * 80)

    config = {
        "search": {
            "text": "caching",
            "filters": {"phase": "develop"},
            "limit": 1
        },
        "discovery": {
            "temporal": True,
            "siblings": True
        }
    }

    registry = SimpleRegistry()
    project_root = registry.get_project_root()
    info = registry.get_project_info(project_root)
    collection_name = info['collection']

    print(f"Config: {json.dumps(config, indent=2)}")
    print()

    try:
        result = asyncio.run(compose(collection_name, config))

        if result['results']:
            primary = result['results'][0]
            print(f"✅ Found primary result:")
            print(f"   Section: {primary['payload'].get('section_name', 'N/A')}")
            print(f"   Temporal: {len(primary.get('temporal', []))}")
            print(f"   Siblings: {len(primary.get('siblings', []))}")
            return True
        else:
            print("❌ No results found")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_3_cross_phase():
    """Query 3: Cross-phase journey (design→develop)"""
    print("\n" + "=" * 80)
    print("TEST 3: Cross-Phase Journey (design→develop)")
    print("=" * 80)

    config = {
        "search": {
            "text": "template-aware chunking",
            "filters": {"phase": "develop"},
            "limit": 1
        },
        "discovery": {
            "cross_phase": "design",
            "genealogy": True,
            "siblings": True
        }
    }

    registry = SimpleRegistry()
    project_root = registry.get_project_root()
    info = registry.get_project_info(project_root)
    collection_name = info['collection']

    print(f"Config: {json.dumps(config, indent=2)}")
    print()

    try:
        result = asyncio.run(compose(collection_name, config))

        if result['results']:
            primary = result['results'][0]
            print(f"✅ Found primary result:")
            print(f"   Section: {primary['payload'].get('section_name', 'N/A')}")
            print(f"   Cross-phase: {len(primary.get('cross_phase', []))}")
            print(f"   Genealogy: {len(primary.get('genealogy', []))}")
            print(f"   Siblings: {len(primary.get('siblings', []))}")
            return True
        else:
            print("❌ No results found")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_4_multi_phase():
    """Query 4: Multi-phase search"""
    print("\n" + "=" * 80)
    print("TEST 4: Multi-Phase Search")
    print("=" * 80)

    config = {
        "search": {
            "queries": [
                {"text": "authentication", "filters": {"phase": "design"}},
                {"text": "authentication", "filters": {"phase": "develop"}}
            ]
        }
    }

    registry = SimpleRegistry()
    project_root = registry.get_project_root()
    info = registry.get_project_info(project_root)
    collection_name = info['collection']

    print(f"Config: {json.dumps(config, indent=2)}")
    print()

    try:
        result = asyncio.run(compose(collection_name, config))

        print(f"✅ Found {len(result['results'])} results across phases")
        for r in result['results'][:3]:
            print(f"   - {r['payload'].get('section_name', 'N/A')} ({r['payload'].get('phase', 'N/A')})")
        return len(result['results']) > 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_5_authority():
    """Query 5: Authority test (CRITICAL - decides on graphs)"""
    print("\n" + "=" * 80)
    print("TEST 5: Authority Ranking (CRITICAL)")
    print("=" * 80)
    print("This test determines if we need full graph operations")
    print()

    config = {
        "search": {
            "text": "caching decisions",
            "filters": {"phase": "develop"},
            "limit": 5
        },
        "discovery": {
            "siblings": True,
            "genealogy": True
        },
        "graph": {
            "algorithm": "authority",
            "top": 5
        }
    }

    registry = SimpleRegistry()
    project_root = registry.get_project_root()
    info = registry.get_project_info(project_root)
    collection_name = info['collection']

    print(f"Config: {json.dumps(config, indent=2)}")
    print()

    try:
        result = asyncio.run(compose(collection_name, config))

        print(f"✅ Found {len(result['results'])} results, ranked by authority:\n")

        for i, r in enumerate(result['results'], 1):
            authority = r.get('authority_score', 0)
            print(f"{i}. {r['payload'].get('section_name', 'N/A')}")
            print(f"   Authority: {authority} (siblings: {len(r.get('siblings', []))}, genealogy: {len(r.get('genealogy', []))})")
            print(f"   Semantic score: {r.get('score', 0):.3f}")
            print()

        # Analysis
        print("=" * 80)
        print("AUTHORITY ANALYSIS:")
        print("=" * 80)

        # Check if authority ranking differs from semantic ranking
        semantic_order = sorted(result['results'], key=lambda r: r.get('score', 0), reverse=True)
        authority_order = result['results']  # Already sorted by authority

        differs = [s['id'] for s in semantic_order] != [a['id'] for a in authority_order]

        if differs:
            print("✅ Authority ranking DIFFERS from semantic ranking")
            print("   → Graph operations may provide value")
            print("   → Consider implementing full PageRank")
        else:
            print("✅ Authority ranking MATCHES semantic ranking")
            print("   → Reference counting sufficient")
            print("   → Skip full graph operations for MVP")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("IMEM Phase 6 Validation Tests")
    print("=" * 80)
    print()

    tests = [
        ("Explain Decision", test_query_1_explain_decision),
        ("Trace Evolution", test_query_2_trace_evolution),
        ("Cross-Phase", test_query_3_cross_phase),
        ("Multi-Phase", test_query_4_multi_phase),
        ("Authority (CRITICAL)", test_query_5_authority),
    ]

    results = []
    for name, test_func in tests:
        passed = test_func()
        results.append((name, passed))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n✅ All tests passed! Phase 6 implementation validated.")
        print("\nNext: Review authority test results to decide on graph operations.")
    else:
        print("\n❌ Some tests failed. Review errors above.")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
