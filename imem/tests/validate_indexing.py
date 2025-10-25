#!/usr/bin/env python3
"""
IMEM Indexing Validator - Test Before Full Reindex

Quick validation of indexing pipeline changes before committing to full reindex.
Tests on sample files, shows what WOULD be indexed, validates metadata extraction.

Usage:
    python imem/tests/validate_indexing.py

    # Test specific files
    python imem/tests/validate_indexing.py file1.md file2.md file3.md
"""

import sys
import re
from pathlib import Path
from collections import defaultdict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document as LlamaDocument


class IndexingValidator:
    """Validate indexing pipeline without writing to Qdrant"""

    def __init__(self):
        self.parser = MarkdownNodeParser()
        self.stats = {
            'files_processed': 0,
            'total_nodes': 0,
            'filtered_nodes': 0,
            'kept_nodes': 0,
            'by_level': defaultdict(int),
            'by_section_type': defaultdict(int),
            'large_chunks': [],
        }

    def validate_file(self, file_path: Path) -> dict:
        """Validate indexing logic on single file"""
        with open(file_path, 'r') as f:
            content = f.read()

        # Parse frontmatter
        frontmatter = self._extract_frontmatter(content)

        # Parse with LlamaIndex
        llama_doc = LlamaDocument(text=content, metadata={'file_path': str(file_path)})
        nodes = self.parser.get_nodes_from_documents([llama_doc])

        self.stats['files_processed'] += 1
        self.stats['total_nodes'] += len(nodes)

        results = []

        for node in nodes:
            content = node.get_content()
            first_line = content.split('\n')[0] if content else ''

            # Extract header info
            header_match = re.match(r'^(#{1,6})\s+(.+)$', first_line)
            section_name = header_match.group(2).strip() if header_match else ''
            header_level = len(header_match.group(1)) if header_match else None

            # Apply filter (MUST match ingest.py logic)
            if header_level is None or header_level < 3:
                self.stats['filtered_nodes'] += 1
                self.stats['by_level'][f'H{header_level}_filtered'] += 1
                results.append({
                    'action': 'SKIP',
                    'reason': 'H1/H2/frontmatter noise',
                    'header_level': header_level,
                    'section_name': section_name,
                    'first_line': first_line[:80],
                })
                continue

            # Would be indexed - extract full metadata
            self.stats['kept_nodes'] += 1
            self.stats['by_level'][f'H{header_level}'] += 1

            # Extract H2 parent
            raw_header_path = node.metadata.get('header_path', '')
            h2_section_type = None
            if raw_header_path and header_level:
                path_parts = [p.strip() for p in raw_header_path.split('/') if p.strip()]
                if header_level == 2:
                    h2_section_type = section_name
                elif header_level >= 3 and len(path_parts) >= 2:
                    h2_section_type = path_parts[1]

            self.stats['by_section_type'][h2_section_type or 'Unknown'] += 1

            # Detect structured fields
            has_context = '**Context**' in content or '- **Context**:' in content
            has_solution = '**Solution**' in content or '- **Solution**:' in content
            has_rationale = '**Rationale**' in content or '- **Rationale**:' in content

            # Check chunk size
            char_count = len(content)
            word_count = len(content.split())
            if char_count > 2000:
                self.stats['large_chunks'].append({
                    'file': file_path.name,
                    'section': section_name,
                    'size': char_count,
                })

            results.append({
                'action': 'KEEP',
                'header_level': header_level,
                'section_type': h2_section_type,
                'section_name': section_name,
                'header_path': raw_header_path,
                'char_count': char_count,
                'word_count': word_count,
                'has_context': has_context,
                'has_solution': has_solution,
                'has_rationale': has_rationale,
                'first_line': first_line[:80],
            })

        return {
            'file': file_path.name,
            'frontmatter': frontmatter,
            'results': results,
        }

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter"""
        metadata = {}
        yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(yaml_pattern, content, re.MULTILINE | re.DOTALL)

        if match:
            yaml_content = match.group(1)
            # Extract key fields
            for pattern, field in [
                (r'type:\s*["\']?([^"\'\n]+)["\']?', 'type'),
                (r'phase:\s*["\']?([^"\'\n]+)["\']?', 'phase'),
                (r'timestamp:\s*["\']?([^"\'\n]+)["\']?', 'timestamp'),
            ]:
                m = re.search(pattern, yaml_content, re.IGNORECASE)
                if m:
                    metadata[field] = m.group(1)

        return metadata

    def print_report(self):
        """Print validation report"""
        print("=" * 80)
        print("INDEXING VALIDATION REPORT")
        print("=" * 80)

        print(f"\nFiles Processed: {self.stats['files_processed']}")
        print(f"Total Nodes Parsed: {self.stats['total_nodes']}")
        print(f"Filtered (H1/H2/frontmatter): {self.stats['filtered_nodes']}")
        print(f"Kept (H3+): {self.stats['kept_nodes']}")

        print(f"\nHeader Level Distribution:")
        for level, count in sorted(self.stats['by_level'].items()):
            print(f"  {level}: {count}")

        print(f"\nSection Type Distribution:")
        for stype, count in sorted(self.stats['by_section_type'].items(),
                                   key=lambda x: -x[1])[:10]:
            print(f"  {stype}: {count}")

        if self.stats['large_chunks']:
            print(f"\n⚠️  Large Chunks (>2000 chars):")
            for chunk in self.stats['large_chunks']:
                print(f"  {chunk['file']}: {chunk['section']} ({chunk['size']} chars)")

        print("\n" + "=" * 80)
        print("VALIDATION COMPLETE")
        print("=" * 80)

        if self.stats['kept_nodes'] > 0:
            print(f"✅ Ready to index {self.stats['kept_nodes']} chunks")
        else:
            print("⚠️  No chunks would be indexed - check filter logic!")


def main():
    """Run validation on sample files or provided paths"""
    validator = IndexingValidator()

    # Get files to test
    if len(sys.argv) > 1:
        # Use provided files
        files = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Use default sample files
        base = Path.cwd()
        patterns = [
            '.context/develop/.changes/*.md',
            '.context/design/.changes/*.md',
        ]
        files = []
        for pattern in patterns:
            files.extend(base.glob(pattern))

        # Limit to 3 samples for quick validation
        files = files[:3]

    if not files:
        print("No files found to validate!")
        print("Usage: python validate_indexing.py [file1.md file2.md ...]")
        sys.exit(1)

    print(f"Validating {len(files)} files...")
    print()

    # Validate each file
    for file_path in files:
        print(f"\n{'=' * 80}")
        print(f"FILE: {file_path.name}")
        print('=' * 80)

        result = validator.validate_file(file_path)

        print(f"\nFrontmatter:")
        for key, value in result['frontmatter'].items():
            print(f"  {key}: {value}")

        print(f"\nChunks:")
        for r in result['results']:
            if r['action'] == 'SKIP':
                print(f"  ❌ {r['action']} (H{r['header_level']}): {r['first_line']}")
            else:
                print(f"  ✅ {r['action']} (H{r['header_level']} {r['section_type']}): {r['section_name']}")
                print(f"     → {r['word_count']} words, {r['char_count']} chars")
                if r['has_context'] or r['has_solution']:
                    fields = []
                    if r['has_context']: fields.append('Context')
                    if r['has_solution']: fields.append('Solution')
                    if r['has_rationale']: fields.append('Rationale')
                    print(f"     → Fields: {', '.join(fields)}")

    # Print summary report
    print("\n\n")
    validator.print_report()


if __name__ == '__main__':
    main()
