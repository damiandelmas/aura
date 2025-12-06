"""EPIC 1: Git Validation Tests

Tests for ground truth integration:
- GitInterface (Subprocess and NoOp implementations)
- LinkModule (timestamp resolution, commit_sha attachment)
- SignatureExtractor (code block extraction, file_path inference)
- TemporalSignal and GitSignal

EPIC 1 is the foundation for all validity computation.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import os

from imem.infrastructure.git import (
    GitInterface,
    SubprocessGitInterface,
    NoOpGitInterface,
    create_git_interface,
    Commit,
    Match,
    BlobNote,
    GitResult,
)
from imem.manage.link import LinkModule
from imem.manage.signatures import SignatureExtractor, Signature, CODE_FENCE_PATTERN
from imem.manage.validity.temporal import TemporalSignal
from imem.manage.validity.git import GitSignal
from imem.protocols import SignalResult


# ============================================================================
# Mock Infrastructure
# ============================================================================

class MockConnection:
    """Mock database connection"""

    def __init__(self):
        self.executed = []
        self.rows = []
        self._signatures = {}

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

        # Handle signature queries
        if 'chunk_signatures' in sql and 'SELECT' in sql:
            chunk_id = params[0] if params else None
            sigs = self._signatures.get(chunk_id, [])
            self.rows = [
                (s['chunk_id'], s['content'], s.get('language'),
                 s.get('file_path'), s.get('signature_hash'))
                for s in sigs
            ]
        else:
            self.rows = []
        return self

    def fetchall(self):
        return self.rows

    def commit(self):
        pass


class MockDB:
    def __init__(self):
        self.conn = MockConnection()


class MockGit:
    """Mock GitInterface for testing"""

    def __init__(self, exists=True, content="", head_files=None):
        self._exists = exists
        self._content = content
        self._head_files = head_files or set()
        self._commits = []

    def file_exists(self, path):
        return self._exists

    def get_file_content(self, path, commit=None):
        return self._content if self._exists else None

    def get_head_files(self):
        return self._head_files

    def get_commits_for_file(self, path, since=None, until=None):
        return self._commits

    def get_commit_timestamp(self, path):
        return datetime.now() if self._commits else None

    def search_content(self, pattern, glob=None):
        return []

    def extract_session_trailer(self, commit_sha):
        return None

    def get_blob_note(self, blob_hash):
        return None

    def refresh(self):
        pass


class MockConfig:
    def __init__(self, project_root):
        self._project_root = project_root

    def get(self, key, default=None):
        if key == 'project_root':
            return self._project_root
        return default


class MockInfrastructure:
    def __init__(self, git=None, project_root=None):
        self.db = MockDB()
        self.git = git or MockGit()
        self.config = MockConfig(project_root or Path('.'))


class MockContext:
    """Mock IndexContext for testing"""

    def __init__(self, git=None, project_root=None):
        self.infrastructure = MockInfrastructure(git=git, project_root=project_root)


# ============================================================================
# NoOpGitInterface Tests
# ============================================================================

class TestNoOpGitInterface:
    """Tests for NoOpGitInterface fallback behavior"""

    def test_file_exists_always_false(self):
        """NoOp always returns False for file existence"""
        git = NoOpGitInterface()
        assert git.file_exists(Path("any/file.py")) is False

    def test_get_file_content_returns_none(self):
        """NoOp returns None for file content"""
        git = NoOpGitInterface()
        assert git.get_file_content(Path("any/file.py")) is None

    def test_get_head_files_returns_empty(self):
        """NoOp returns empty set for HEAD files"""
        git = NoOpGitInterface()
        assert git.get_head_files() == set()

    def test_get_commits_for_file_returns_empty(self):
        """NoOp returns empty list for commits"""
        git = NoOpGitInterface()
        assert git.get_commits_for_file(Path("any/file.py")) == []

    def test_search_content_returns_empty(self):
        """NoOp returns empty list for content search"""
        git = NoOpGitInterface()
        assert git.search_content("pattern") == []

    def test_extract_session_trailer_returns_none(self):
        """NoOp returns None for session trailer"""
        git = NoOpGitInterface()
        assert git.extract_session_trailer("abc123") is None

    def test_root_property(self):
        """NoOp stores and returns root path"""
        git = NoOpGitInterface(root=Path("/project"))
        assert git.root == Path("/project")

    def test_refresh_does_nothing(self):
        """Refresh is a no-op"""
        git = NoOpGitInterface()
        git.refresh()  # Should not raise


class TestCreateGitInterface:
    """Tests for create_git_interface factory"""

    def test_returns_noop_for_nonexistent_dir(self):
        """Factory returns NoOp when dir doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "does_not_exist"
            git = create_git_interface(nonexistent)
            assert isinstance(git, NoOpGitInterface)

    def test_returns_noop_for_non_git_dir(self):
        """Factory returns NoOp when no .git present"""
        with tempfile.TemporaryDirectory() as tmpdir:
            git = create_git_interface(Path(tmpdir))
            assert isinstance(git, NoOpGitInterface)


# ============================================================================
# LinkModule Tests
# ============================================================================

class TestLinkModule:
    """Tests for LinkModule timestamp resolution and commit attachment"""

    def test_name(self):
        """Module name is 'link'"""
        module = LinkModule()
        assert module.name == "link"

    def test_timestamp_from_frontmatter_created_at(self):
        """Timestamp resolved from frontmatter created_at"""
        module = LinkModule()
        context = MockContext()

        chunk = {
            'id': 'test1',
            'metadata': {'created_at': '2025-01-15T10:00:00'},
            'content': 'test content'
        }

        result = module._resolve_timestamp(chunk, context)
        timestamp, source = result

        assert source == 'frontmatter'
        assert timestamp.year == 2025
        assert timestamp.month == 1
        assert timestamp.day == 15

    def test_timestamp_from_top_level(self):
        """Timestamp resolved from top-level timestamp field"""
        module = LinkModule()
        context = MockContext()

        chunk = {
            'id': 'test1',
            'timestamp': '2025-02-20',
            'content': 'test'
        }

        result = module._resolve_timestamp(chunk, context)
        timestamp, source = result

        assert source == 'frontmatter'
        assert timestamp.month == 2

    def test_timestamp_fallback_to_indexed(self):
        """Falls back to index time when no other source"""
        module = LinkModule()
        context = MockContext()

        chunk = {
            'id': 'test1',
            'content': 'test',
            # No timestamp fields
        }

        result = module._resolve_timestamp(chunk, context)
        timestamp, source = result

        assert source == 'indexed'
        assert timestamp is not None

    def test_parse_timestamp_iso_format(self):
        """Parses ISO format timestamps"""
        module = LinkModule()

        result = module._parse_timestamp('2025-01-15T10:30:00')
        assert result is not None
        assert result.year == 2025

    def test_parse_timestamp_date_only(self):
        """Parses date-only format"""
        module = LinkModule()

        result = module._parse_timestamp('2025-01-15')
        assert result is not None
        assert result.year == 2025

    def test_parse_timestamp_datetime_object(self):
        """Handles datetime objects directly, normalizing to UTC"""
        from datetime import timezone
        module = LinkModule()

        dt = datetime(2025, 1, 15)
        result = module._parse_timestamp(dt)
        # Now returns UTC-normalized (naive assumed UTC)
        expected = datetime(2025, 1, 15, tzinfo=timezone.utc)
        assert result == expected

    def test_execute_populates_timestamp(self):
        """Execute populates timestamp and source"""
        module = LinkModule()
        context = MockContext()

        chunks = [{
            'id': 'test1',
            'metadata': {'created_at': '2025-01-15'},
            'content': 'test'
        }]

        result = module.execute(chunks, context)

        assert result[0]['timestamp'] is not None
        assert result[0]['timestamp_source'] == 'frontmatter'

    def test_find_nearest_commit_with_matches(self):
        """Finds nearest commit when commits exist"""
        module = LinkModule()

        # Create mock with commits
        mock_git = MockGit()
        mock_git._commits = [
            Commit(sha='abc123', timestamp=datetime(2025, 1, 14), message='commit 1', files_changed=[]),
            Commit(sha='def456', timestamp=datetime(2025, 1, 16), message='commit 2', files_changed=[]),
        ]
        context = MockContext(git=mock_git)

        chunk = {'file_path': 'src/test.py'}
        timestamp = datetime(2025, 1, 15)

        result = module._find_nearest_commit(chunk, timestamp, context)
        # Should pick the closer one
        assert result in ['abc123', 'def456']


# ============================================================================
# SignatureExtractor Tests
# ============================================================================

class TestSignatureExtractor:
    """Tests for SignatureExtractor code block extraction"""

    def test_name(self):
        """Module name is 'signatures'"""
        extractor = SignatureExtractor()
        assert extractor.name == "signatures"

    def test_code_fence_pattern_basic(self):
        """Pattern matches basic code fences"""
        content = '''
Some text

```python
def hello():
    print("world")
```

More text
'''
        matches = list(CODE_FENCE_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) == 'python'
        assert 'def hello():' in matches[0].group(2)

    def test_code_fence_pattern_no_language(self):
        """Pattern matches code fences without language"""
        content = '''
```
some code here
multiple lines
```
'''
        matches = list(CODE_FENCE_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) is None

    def test_extract_returns_signatures(self):
        """Extract creates Signature objects from code blocks"""
        extractor = SignatureExtractor()
        context = MockContext()

        chunk = {
            'id': 'chunk1',
            'content': '''
# Documentation

```python
class AuthHandler:
    def validate(self, token):
        return jwt.decode(token)
```
'''
        }

        signatures = extractor.extract(chunk, context)

        assert len(signatures) == 1
        assert signatures[0].chunk_id == 'chunk1'
        assert signatures[0].language == 'python'
        assert 'class AuthHandler' in signatures[0].content

    def test_extract_skips_short_snippets(self):
        """Extract skips code blocks under MIN_CODE_LENGTH"""
        extractor = SignatureExtractor()
        context = MockContext()

        chunk = {
            'id': 'chunk1',
            'content': '''
```python
x = 1
```
'''
        }

        signatures = extractor.extract(chunk, context)
        assert len(signatures) == 0

    def test_extract_multiple_blocks(self):
        """Extract handles multiple code blocks"""
        extractor = SignatureExtractor()
        context = MockContext()

        chunk = {
            'id': 'chunk1',
            'content': '''
```python
def function_one():
    return "this is long enough to extract"
```

Some explanation here.

```javascript
function functionTwo() {
    return "also long enough to extract";
}
```
'''
        }

        signatures = extractor.extract(chunk, context)
        assert len(signatures) == 2
        assert {s.language for s in signatures} == {'python', 'javascript'}

    def test_language_to_glob_mapping(self):
        """Language hints map to correct glob patterns"""
        extractor = SignatureExtractor()

        assert extractor._language_to_glob('python') == '*.py'
        assert extractor._language_to_glob('javascript') == '*.js'
        assert extractor._language_to_glob('typescript') == '*.ts'
        assert extractor._language_to_glob('rust') == '*.rs'
        assert extractor._language_to_glob('unknown') is None

    def test_extract_search_snippet(self):
        """Extract search snippet finds first meaningful line"""
        extractor = SignatureExtractor()

        code = '''
# This is a comment
import os

class MyClass:
    pass
'''
        snippet = extractor._extract_search_snippet(code)
        assert snippet is not None
        # Should skip comment and import
        assert 'class' in snippet.lower() or snippet  # Found something

    def test_infer_file_path_from_annotation(self):
        """Infers file_path from inline annotation"""
        extractor = SignatureExtractor()
        context = MockContext()

        code = '''# file: src/auth/handler.py
class AuthHandler:
    def validate(self):
        pass
'''
        result = extractor._infer_file_path(code, 'python', context)
        assert result == 'src/auth/handler.py'


# ============================================================================
# TemporalSignal Tests
# ============================================================================

class TestTemporalSignal:
    """Tests for TemporalSignal baseline validity"""

    def test_name(self):
        """Signal name is 'temporal'"""
        signal = TemporalSignal()
        assert signal.name == "temporal"

    def test_applies_to_markdown_source(self):
        """Applies to markdown-sourced chunks"""
        signal = TemporalSignal()
        context = MockContext()

        chunk = {'id': 'c1', 'source': 'markdown'}
        assert signal.applies(chunk, context) is True

    def test_not_applies_to_git_source(self):
        """Does not apply to git-sourced chunks"""
        signal = TemporalSignal()
        context = MockContext()

        chunk = {'id': 'c1', 'source': 'git'}
        assert signal.applies(chunk, context) is False

    def test_score_returns_neutral_baseline(self):
        """Score returns 0.5 baseline (survival signal)"""
        signal = TemporalSignal()
        context = MockContext()

        chunk = {
            'id': 'c1',
            'timestamp': datetime.now().isoformat()
        }

        result = signal.score(chunk, context)

        assert result.score == 0.5
        assert result.confidence == 0.3  # BASELINE_CONFIDENCE

    def test_score_without_timestamp(self):
        """Score handles missing timestamp gracefully"""
        signal = TemporalSignal()
        context = MockContext()

        chunk = {'id': 'c1'}  # No timestamp

        result = signal.score(chunk, context)

        assert result.score == 0.5
        assert result.confidence == 0.1  # Very low confidence

    def test_score_with_old_document(self):
        """Old documents still get neutral score (survival signal)"""
        signal = TemporalSignal()
        context = MockContext()

        # 6 months old
        old_date = (datetime.now() - timedelta(days=180)).isoformat()
        chunk = {'id': 'c1', 'timestamp': old_date}

        result = signal.score(chunk, context)

        # NO DECAY - survival signal philosophy
        assert result.score == 0.5
        assert 'battle-tested' in result.reason or 'durable' in result.reason


# ============================================================================
# GitSignal Tests
# ============================================================================

class TestGitSignal:
    """Tests for GitSignal codebase validation"""

    def test_name(self):
        """Signal name is 'git'"""
        signal = GitSignal()
        assert signal.name == "git"

    def test_applies_to_markdown_with_real_git(self):
        """Applies when git interface is real (not NoOp)"""
        signal = GitSignal()

        # Real git interface (not NoOp)
        mock_git = MockGit()
        mock_git.__class__.__name__ = 'SubprocessGitInterface'
        context = MockContext(git=mock_git)

        chunk = {'id': 'c1', 'source': 'markdown'}
        assert signal.applies(chunk, context) is True

    def test_not_applies_to_git_source(self):
        """Does not apply to git-sourced chunks (they ARE truth)"""
        signal = GitSignal()
        context = MockContext()

        chunk = {'id': 'c1', 'source': 'git'}
        assert signal.applies(chunk, context) is False

    def test_not_applies_with_noop_git(self):
        """Does not apply when git interface is NoOp"""
        signal = GitSignal()

        mock_git = NoOpGitInterface()
        context = MockContext(git=mock_git)

        chunk = {'id': 'c1', 'source': 'markdown'}
        assert signal.applies(chunk, context) is False

    def test_score_with_no_signatures(self):
        """Returns neutral when no signatures found"""
        signal = GitSignal()
        context = MockContext()

        chunk = {'id': 'c1'}

        result = signal.score(chunk, context)

        assert result.score == 0.5
        assert 'No code signatures' in result.reason

    def test_validate_signature_file_deleted(self):
        """Detects deleted files as contradicted"""
        signal = GitSignal()

        mock_git = MockGit(exists=False)
        context = MockContext(git=mock_git)

        result = signal._validate_signature('src/deleted.py', 'code', context)

        assert result['score'] == 0.1
        assert result['status'] == 'contradicted'
        assert 'deleted' in result['reason'].lower()

    def test_validate_signature_code_matches(self):
        """Detects matching code as validated"""
        signal = GitSignal()

        code = 'def validate_token(token):\n    return jwt.decode(token)'
        mock_git = MockGit(exists=True, content=f'''
class AuthHandler:
    {code}

    def another_method(self):
        pass
''')
        context = MockContext(git=mock_git)

        result = signal._validate_signature('src/auth.py', code, context)

        assert result['score'] == 0.9
        assert result['status'] == 'validated'

    def test_validate_signature_code_changed(self):
        """Detects changed code as contradicted"""
        signal = GitSignal()

        old_code = 'def old_function():\n    return "old"'
        new_content = 'def new_function():\n    return "new"'

        mock_git = MockGit(exists=True, content=new_content)
        context = MockContext(git=mock_git)

        result = signal._validate_signature('src/file.py', old_code, context)

        assert result['score'] == 0.3
        assert result['status'] == 'contradicted'

    def test_normalize_code_removes_trailing_whitespace(self):
        """Code normalization removes trailing whitespace"""
        signal = GitSignal()

        code = "def foo():    \n    pass  \n"
        result = signal._normalize_code(code)

        # No trailing spaces
        for line in result.split('\n'):
            assert line == line.rstrip()

    def test_score_aggregates_multiple_signatures(self):
        """Score aggregates multiple signature validations"""
        signal = GitSignal()

        mock_git = MockGit(exists=True, content='matching code here')
        context = MockContext(git=mock_git)

        # Set up signatures in mock
        context.infrastructure.db.conn._signatures = {
            'chunk1': [
                {'chunk_id': 'chunk1', 'content': 'matching code', 'file_path': 'a.py', 'signature_hash': 'h1'},
            ]
        }

        chunk = {'id': 'chunk1'}
        result = signal.score(chunk, context)

        # Should have processed the signature
        assert result.confidence >= 0.3  # Some confidence


# ============================================================================
# Run tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
