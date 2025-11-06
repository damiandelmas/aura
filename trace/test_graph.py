#!/usr/bin/env python3
"""Test graph fork detection on real conversation"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from aura_trace.retrieval import ConversationRetrieval
from aura_trace.graph import ConversationGraph

# Find conversation with fork
from pathlib import Path
conv_file = list(Path.home().glob('.claude/projects/*/6eb05e9b-be4a-44b0-9*.jsonl'))[0]

print(f"Loading: {conv_file.name}\n")

# Load conversation
retrieval = ConversationRetrieval()
entries = retrieval.load_conversation(conv_file)

print(f"Loaded {len(entries)} entries\n")

# Build graph
graph = ConversationGraph(entries)

# Get stats
stats = graph.get_stats()
print("Graph Statistics:")
print(f"  Total nodes: {stats.total_nodes}")
print(f"  Root nodes: {stats.root_nodes}")
print(f"  Leaf nodes: {stats.leaf_nodes}")
print(f"  Fork points: {stats.fork_points}")
print(f"  Total branches: {stats.branches}")
print(f"  Max depth: {stats.max_depth}")
print()

# Find forks
forks = graph.get_forks()
print(f"Found {len(forks)} fork(s):\n")

for fork_uuid, children in forks.items():
    fork_node = graph.nodes[fork_uuid]
    print(f"Fork at: {fork_uuid[:8]}...")
    print(f"  Type: {fork_node.entry.type}")
    print(f"  Timestamp: {fork_node.entry.timestamp}")
    print(f"  Children: {len(children)}")
    print()

    # Get branches from this fork
    branches = graph.get_branches_from_fork(fork_uuid)

    for i, branch in enumerate(branches, 1):
        print(f"  Branch {i}: {len(branch)} messages")

        # Show first few messages in branch
        for j, uuid in enumerate(branch[:5]):
            node = graph.nodes[uuid]
            print(f"    {j+1}. {uuid[:8]}... ({node.entry.type})")

        if len(branch) > 5:
            print(f"    ... ({len(branch) - 5} more)")
        print()

# Detect dead branches
dead = graph.detect_dead_branches()
if dead:
    print(f"\nDead branches detected: {len(dead)}")
    for fork_uuid, dead_path in dead:
        print(f"  Fork {fork_uuid[:8]}... has dead branch of length {len(dead_path)}")
else:
    print("\nNo dead branches (both branches continued)")
