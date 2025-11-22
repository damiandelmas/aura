#!/usr/bin/env python3
"""
IMEM Indexing Validator - Test Before Full Reindex

Quick validation of indexing pipeline changes before committing to full reindex.
Tests on sample files, shows what WOULD be indexed, validates metadata extraction.

Uses lightweight custom parser (no ML dependencies).

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

from imem.compile.parse.markdown import MarkdownParser


class IndexingValidator:
    """Validate indexing pipeline without writing to SQLite"""

    def __init__(self):
        self.parser = MarkdownParser()
        self.stats = {
            'files_processed': 0,
            'total_chunks': 0,
            'filtered_chunks': 0,
            'kept_chunks': 0,
            'by_level': defaultdict(int),
            'by_section_type': defaultdict(int),
            'large_chunks': [],
        }

    def validate_file(self, file_path: Path) -> dict:
        """Validate indexing logic on single file"""
        # Parse with custom parser
        chunks = self.parser.parse_file(file_path)

        self.stats['files_processed'] += 1
        self.stats['total_chunks'] += len(chunks)

        results = []

        for chunk in chunks:
            content = chunk['content']
            section_name = chunk['section_name']
            section_type = chunk['section_type']

            # Skip small content
            if len(content.strip()) < 20:
                self.stats['filtered_chunks'] += 1
                results.append({
                    'action': 'SKIP',
                    'reason': 'Too short (<20 chars)',
                    'section_name': section_name,
                })
                continue

            # Would be indexed
            self.stats['kept_chunks'] += 1
            self.stats['by_section_type'][section_type or 'Unknown'] += 1

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
                'section_type': section_type,
                'section_name': section_name,
                'h2_parent': chunk.get('h2_parent'),
                'char_count': char_count,
                'word_count': word_count,
                'has_context': has_context,
                'has_solution': has_solution,
                'has_rationale': has_rationale,
            })

        # Extract frontmatter from raw file
        with open(file_path, 'r') as f:
            content = f.read()
        frontmatter = self._extract_frontmatter(content)

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
        print(f"Total Chunks Parsed: {self.stats['total_chunks']}")
        print(f"Filtered (too short): {self.stats['filtered_chunks']}")
        print(f"Kept: {self.stats['kept_chunks']}")

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

        if self.stats['kept_chunks'] > 0:
            print(f"✅ Ready to index {self.stats['kept_chunks']} chunks")
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
                print(f"  ❌ {r['action']}: {r.get('section_name', 'unknown')} - {r.get('reason', '')}")
            else:
                print(f"  ✅ {r['action']} ({r['section_type']}): {r['section_name']}")
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
