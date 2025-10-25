#!/usr/bin/env python3
"""Show actual node content samples for validation"""

import sys
from pathlib import Path
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document as LlamaDocument

# Read the test markdown
md_path = Path(__file__).parent / "test_67f63a89-04a.md"
md_content = md_path.read_text()

# Parse with LlamaIndex
parser = MarkdownNodeParser()
llama_doc = LlamaDocument(text=md_content, metadata={'session_id': '67f63a89'})
nodes = parser.get_nodes_from_documents([llama_doc])

print("=" * 80)
print("SAMPLE NODES FOR VALIDATION")
print("=" * 80)

# Show specific interesting nodes
interesting_nodes = [
    (2, "User Messages Section"),
    (3, "Assistant Responses Section"),
    (40, "Tools Used Section"),
    (41, "Files Modified Section"),
    (23, "Code Changes - First File"),
]

for node_num, description in interesting_nodes:
    if node_num <= len(nodes):
        node = nodes[node_num - 1]
        content = node.get_content()

        print(f"\n{'='*80}")
        print(f"NODE {node_num}: {description}")
        print(f"{'='*80}")
        print(f"Header Path: {node.metadata.get('header_path')}")
        print(f"Header Level: H{node.metadata.get('header_level', 0)}")
        print(f"Content Length: {len(content)} chars")
        print(f"\nFULL CONTENT:")
        print("-" * 80)
        print(content)
        print("-" * 80)

print(f"\n{'='*80}")
print("WHAT YOU SHOULD VALIDATE:")
print(f"{'='*80}")
print("""
1. ✅ Each H2 section (User Messages, Tools Used, etc.) is in its own node
2. ✅ Content is complete and makes sense
3. ✅ Node sizes are reasonable (not too big, not too small)
4. ✅ Code Changes subsections (H3) are separated into individual nodes
5. ✅ When searching, you'd want to retrieve these specific chunks

If you see these patterns, the chunking is working correctly!
""")
