"""
TRACE: Clean 2-Component Conversation Intelligence Architecture

Components:
- ConversationFinder: Project-specific conversation discovery
- ConversationRetrieval: Direct JSONL access with fixed parsing

Data Flow: Finder → Retrieval → CLI/Agents
"""

from .retrieval import (
    ConversationRetrieval,
    ConversationEntry,
    RetrievalOptions
)

from .finder import ConversationFinder

__all__ = [
    'ConversationRetrieval',
    'ConversationEntry',
    'RetrievalOptions',
    'ConversationFinder',
]
