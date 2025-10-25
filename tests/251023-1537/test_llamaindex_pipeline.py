#!/usr/bin/env python3
"""
Test LlamaIndex markdown parsing pipeline for TRACE conversations
Verifies that structured markdown exports chunk correctly into H2 sections
"""

import sys
from pathlib import Path
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document as LlamaDocument

# Add trace to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'trace' / 'src'))

from aura_trace.finder import ConversationFinder
from aura_trace.query import ConversationQuery

def test_conversation_chunking(session_id: str):
    """Test full pipeline: JSONL -> Structured MD -> LlamaIndex nodes"""

    print(f"=" * 80)
    print(f"Testing LlamaIndex Pipeline for Session: {session_id[:12]}")
    print(f"=" * 80)

    # 1. Find conversation file
    finder = ConversationFinder()
    conversations = finder.list_all()
    conv_file = None

    for conv in conversations:
        info = finder.get_conversation_info(conv)
        if info['session_id'] == session_id:
            conv_file = conv
            break

    if not conv_file:
        print(f"❌ Conversation {session_id} not found")
        return False

    print(f"\n✅ Found conversation: {conv_file}")
    print(f"   Size: {conv_file.stat().st_size // 1024}KB")

    # 2. Export to structured markdown
    query = ConversationQuery()

    try:
        structured_md = query.export_structured_markdown(conv_file)
        print(f"\n✅ Exported structured markdown: {len(structured_md)} chars")

        # Save for inspection
        test_md_path = Path(__file__).parent / f"test_{session_id[:12]}.md"
        test_md_path.write_text(structured_md, encoding='utf-8')
        print(f"   Saved to: {test_md_path}")

    except Exception as e:
        print(f"\n❌ Failed to export markdown: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 3. Parse with LlamaIndex
    print(f"\n{'='*80}")
    print("LlamaIndex Parsing Results")
    print(f"{'='*80}")

    try:
        parser = MarkdownNodeParser()
        llama_doc = LlamaDocument(
            text=structured_md,
            metadata={'session_id': session_id}
        )

        nodes = parser.get_nodes_from_documents([llama_doc])

        print(f"\n📊 Total nodes created: {len(nodes)}")

        if not nodes:
            print("❌ No nodes created - parsing failed!")
            return False

        # 4. Analyze each node
        print(f"\n{'='*80}")
        print("Node Breakdown")
        print(f"{'='*80}")

        section_counts = {}

        for i, node in enumerate(nodes, 1):
            header_path = node.metadata.get('header_path', 'NO_HEADER')
            header_level = node.metadata.get('header_level', 0)
            content = node.get_content()
            content_len = len(content)

            # Track sections
            section_counts[header_path] = section_counts.get(header_path, 0) + 1

            print(f"\nNode {i}/{len(nodes)}:")
            print(f"  📌 Header Path: {header_path}")
            print(f"  📊 Level: H{header_level}")
            print(f"  📏 Length: {content_len} chars")
            print(f"  📝 Preview (first 150 chars):")
            print(f"     {content[:150].replace(chr(10), ' ')[:150]}...")

            # Warn about very large chunks
            if content_len > 5000:
                print(f"  ⚠️  WARNING: Large chunk ({content_len} chars) - might need splitting")

            # Warn about very small chunks
            if content_len < 50:
                print(f"  ⚠️  WARNING: Very small chunk - might be empty section")

        # 5. Summary statistics
        print(f"\n{'='*80}")
        print("Summary Statistics")
        print(f"{'='*80}")

        print(f"\nSections found:")
        for section, count in sorted(section_counts.items()):
            print(f"  - {section}: {count} node(s)")

        # Expected sections for conversations
        expected_sections = [
            'Conversation',
            'User Messages',
            'Assistant Responses',
            'Code Changes',
            'Tools Used',
            'Files Modified'
        ]

        print(f"\nExpected section check:")
        for expected in expected_sections:
            found = any(expected in section for section in section_counts.keys())
            status = "✅" if found else "⚠️"
            print(f"  {status} {expected}")

        # 6. Validate chunking quality
        print(f"\n{'='*80}")
        print("Chunking Quality Analysis")
        print(f"{'='*80}")

        total_chars = sum(len(node.get_content()) for node in nodes)
        avg_chunk_size = total_chars / len(nodes)

        print(f"\n  Total content: {total_chars:,} chars")
        print(f"  Average chunk: {avg_chunk_size:.0f} chars")
        print(f"  Nodes created: {len(nodes)}")

        # Quality checks
        issues = []

        if len(nodes) < 2:
            issues.append("Too few nodes - chunking might not be working")

        if avg_chunk_size > 3000:
            issues.append("Average chunk too large - might hurt search precision")

        if avg_chunk_size < 100:
            issues.append("Average chunk too small - might be over-chunking")

        if issues:
            print(f"\n⚠️  Quality Issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"\n✅ Chunking quality looks good!")

        return True

    except Exception as e:
        print(f"\n❌ LlamaIndex parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Use the current session (most recent)
    test_session = "67f63a89-04ab-4aa3-80da-a995c6816e37"

    if len(sys.argv) > 1:
        test_session = sys.argv[1]

    success = test_conversation_chunking(test_session)

    print(f"\n{'='*80}")
    if success:
        print("✅ Pipeline test PASSED")
        print("\nNext steps:")
        print("  1. Review the saved markdown file")
        print("  2. Verify nodes match expected H2 sections")
        print("  3. Proceed with implementing trace --index")
    else:
        print("❌ Pipeline test FAILED")
        print("\nFix issues before implementing trace --index")
    print(f"{'='*80}\n")

    sys.exit(0 if success else 1)
