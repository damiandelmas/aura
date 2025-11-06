#!/usr/bin/env python3
"""
Conversation Graph - DAG-based conversation analysis
Handles forks, branches, and multi-path conversations.
"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """Single message node in conversation graph"""
    uuid: str
    parent_uuid: Optional[str]
    entry: 'ConversationEntry'  # Forward reference


@dataclass
class GraphStats:
    """Statistics about conversation graph structure"""
    total_nodes: int
    root_nodes: int  # Messages with no parent
    leaf_nodes: int  # Messages with no children
    fork_points: int  # Messages with multiple children
    branches: int  # Total branch count
    max_depth: int  # Longest path from root


class ConversationGraph:
    """
    DAG representation of conversation with fork detection.

    Enables:
    - Fork detection (messages with multiple children)
    - Branch extraction (all paths from a fork)
    - Subgraph isolation (conversation fragments)
    - Path analysis (how we got from A to B)
    """

    def __init__(self, entries: List['ConversationEntry']):
        """Build graph from conversation entries"""
        self.nodes: Dict[str, GraphNode] = {}
        self.children: Dict[str, List[str]] = defaultdict(list)  # parent -> [child_uuids]
        self.roots: List[str] = []  # Nodes with no parent

        self._build_graph(entries)

    def _build_graph(self, entries: List['ConversationEntry']):
        """Construct node and edge structures"""
        # Create nodes
        for entry in entries:
            if not entry.uuid:
                continue

            self.nodes[entry.uuid] = GraphNode(
                uuid=entry.uuid,
                parent_uuid=entry.parent_uuid,
                entry=entry
            )

        # Build edges (parent -> children mapping)
        for uuid, node in self.nodes.items():
            if node.parent_uuid:
                self.children[node.parent_uuid].append(uuid)
            else:
                self.roots.append(uuid)

        logger.info(f"Built graph: {len(self.nodes)} nodes, {len(self.roots)} roots")

    def get_forks(self) -> Dict[str, List[str]]:
        """
        Find all fork points (messages with multiple children).

        Returns:
            Dict mapping parent_uuid -> [child_uuids]
        """
        return {
            parent: children
            for parent, children in self.children.items()
            if len(children) > 1
        }

    def get_branches_from_fork(self, fork_uuid: str) -> List[List[str]]:
        """
        Get all branch paths starting from a fork point.

        Args:
            fork_uuid: UUID of message that has multiple children

        Returns:
            List of branches, each branch is list of UUIDs in order
        """
        if fork_uuid not in self.children:
            return []

        branches = []
        for child_uuid in self.children[fork_uuid]:
            branch = self._get_path_forward(child_uuid)
            branches.append(branch)

        return branches

    def _get_path_forward(self, start_uuid: str) -> List[str]:
        """
        Get linear path forward from a node (follows first child at forks).

        Args:
            start_uuid: Starting node UUID

        Returns:
            List of UUIDs from start to leaf
        """
        path = []
        current = start_uuid

        while current:
            path.append(current)

            # Get children
            children = self.children.get(current, [])

            # If no children, we're at a leaf
            if not children:
                break

            # If multiple children (fork), take first one
            # (caller should use get_branches_from_fork for full analysis)
            current = children[0]

        return path

    def get_path_between(self, start_uuid: str, end_uuid: str) -> Optional[List[str]]:
        """
        Find path from start to end node.

        Args:
            start_uuid: Starting node
            end_uuid: Target node

        Returns:
            List of UUIDs from start to end, or None if no path exists
        """
        # BFS to find path
        from collections import deque

        queue = deque([(start_uuid, [start_uuid])])
        visited = {start_uuid}

        while queue:
            current, path = queue.popleft()

            if current == end_uuid:
                return path

            # Explore children
            for child in self.children.get(current, []):
                if child not in visited:
                    visited.add(child)
                    queue.append((child, path + [child]))

        return None  # No path found

    def get_subgraph(self, root_uuid: str, max_depth: Optional[int] = None) -> 'ConversationGraph':
        """
        Extract subgraph starting from a specific node.

        Args:
            root_uuid: Starting node UUID
            max_depth: Maximum depth to traverse (None = unlimited)

        Returns:
            New ConversationGraph containing only the subgraph
        """
        subgraph_entries = []
        visited = set()

        def traverse(uuid: str, depth: int):
            if uuid in visited:
                return
            if max_depth is not None and depth > max_depth:
                return
            if uuid not in self.nodes:
                return

            visited.add(uuid)
            subgraph_entries.append(self.nodes[uuid].entry)

            # Traverse children
            for child in self.children.get(uuid, []):
                traverse(child, depth + 1)

        traverse(root_uuid, 0)
        return ConversationGraph(subgraph_entries)

    def get_all_branches(self) -> List[List[str]]:
        """
        Get all linear branches in the conversation.

        A branch is a path from root to leaf with no forks.
        If there are forks, returns multiple branches.

        Returns:
            List of branches (each branch is list of UUIDs)
        """
        branches = []

        def traverse_to_leaves(uuid: str, current_path: List[str]):
            current_path = current_path + [uuid]
            children = self.children.get(uuid, [])

            if not children:
                # Leaf node - save branch
                branches.append(current_path)
            else:
                # Continue down each child (handles forks)
                for child in children:
                    traverse_to_leaves(child, current_path)

        # Start from each root
        for root in self.roots:
            traverse_to_leaves(root, [])

        return branches

    def get_stats(self) -> GraphStats:
        """Calculate graph statistics"""
        forks = self.get_forks()
        branches = self.get_all_branches()

        # Find leaf nodes (no children)
        leaves = [uuid for uuid in self.nodes.keys() if uuid not in self.children or not self.children[uuid]]

        # Calculate max depth
        max_depth = 0
        if branches:
            max_depth = max(len(branch) for branch in branches)

        return GraphStats(
            total_nodes=len(self.nodes),
            root_nodes=len(self.roots),
            leaf_nodes=len(leaves),
            fork_points=len(forks),
            branches=len(branches),
            max_depth=max_depth
        )

    def detect_dead_branches(self) -> List[Tuple[str, List[str]]]:
        """
        Find branches that were abandoned (didn't continue).

        Returns:
            List of (fork_uuid, dead_branch_path) tuples
        """
        dead_branches = []
        forks = self.get_forks()

        for fork_uuid, children in forks.items():
            branches = self.get_branches_from_fork(fork_uuid)

            # Find shortest branch (likely the abandoned one)
            if len(branches) > 1:
                branch_lengths = [(i, len(branch)) for i, branch in enumerate(branches)]
                branch_lengths.sort(key=lambda x: x[1])

                # If one branch is significantly shorter, it's probably dead
                shortest_idx, shortest_len = branch_lengths[0]
                next_len = branch_lengths[1][1]

                if shortest_len < next_len * 0.5:  # Less than 50% of next branch
                    dead_branches.append((fork_uuid, branches[shortest_idx]))

        return dead_branches

    def format_tree(self, start_uuid: Optional[str] = None, max_depth: int = 5) -> str:
        """
        Format conversation as ASCII tree.

        Args:
            start_uuid: Root node (None = use first root)
            max_depth: Maximum depth to display

        Returns:
            ASCII tree representation
        """
        if start_uuid is None:
            start_uuid = self.roots[0] if self.roots else None

        if not start_uuid or start_uuid not in self.nodes:
            return "No valid start node"

        lines = []

        def traverse(uuid: str, prefix: str, depth: int):
            if depth > max_depth:
                return

            node = self.nodes[uuid]
            entry_type = node.entry.type
            timestamp = str(node.entry.timestamp)[:16] if node.entry.timestamp else "no-time"

            # Format node line
            lines.append(f"{prefix}{uuid[:8]}... ({entry_type}) {timestamp}")

            # Get children
            children = self.children.get(uuid, [])

            # Traverse children
            for i, child in enumerate(children):
                is_last = (i == len(children) - 1)
                child_prefix = prefix + ("    " if is_last else "│   ")
                connector = "└── " if is_last else "├── "

                lines.append(f"{prefix}{connector}")
                traverse(child, child_prefix, depth + 1)

        traverse(start_uuid, "", 0)
        return "\n".join(lines)


def build_conversation_graph(entries: List['ConversationEntry']) -> ConversationGraph:
    """Convenience function to build graph from entries"""
    return ConversationGraph(entries)
