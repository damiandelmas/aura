---
type: "design"
timestamp: "2025-10-09 16:41 PST"
---

# Multi-Conversation Isolation & Registry System

## Question
> How do we track multiple concurrent conversations per project without global state conflicts? How does the system survive project renames and support team collaboration?

## Key Insights

### 1. Project-Local Registry
- Each project has `.conversations/` directory
- No global state (no home directory configs)
- Survives project renames/moves
- Git-trackable for team sharing

### 2. Bookmark-Based Session Tracking
- Each conversation gets unique bookmark ID
- Bookmark = conversation identifier + timestamp
- Active bookmark stored in `.conversations/active.txt`
- Registry maps bookmarks to metadata

### 3. SessionStart Hook Integration
- Claude Code triggers hook on new conversation
- Hook creates bookmark and updates registry
- Fallback: Lazy initialization on first `/log:develop`
- No dependency on hook existing

### 4. Multi-Project Isolation
- Project A's conversations ≠ Project B's conversations
- Each project maintains independent registry
- Import/export for cross-project sharing
- No cross-contamination

## Explored Ideas

### Registry Architecture

**File Structure:**
```
project-root/
├── .conversations/
│   ├── registry.json          # All conversation metadata
│   ├── active.txt             # Current bookmark ID
│   └── archive/               # Completed conversations
│       └── 251007_abc123.json
```

**Registry Schema:**
```json
{
  "conversations": {
    "251007_abc123": {
      "bookmark": "251007_abc123",
      "created": "2025-10-07T14:00:00Z",
      "status": "active|archived",
      "title": "Implement PULSE agent",
      "changelog_parts": [
        ".develop/.changes/251007-1400_abc123_part-1.md",
        ".develop/.changes/251007-1400_abc123_part-2.md"
      ],
      "documents_affected": [
        ".document/architecture/02_api-design.md"
      ],
      "metadata": {
        "total_parts": 2,
        "session_duration": "45m",
        "files_modified": 12
      }
    }
  },
  "active_bookmark": "251007_abc123"
}
```

### SessionStart Hook Flow

**Hook Location:**
```bash
# ~/.claude/hooks/on_conversation_start.sh
#!/bin/bash

# Only run if in a project with .conversations/
if [ -d .conversations ]; then
    BOOKMARK=$(date +%y%m%d)_$(uuidgen | cut -c1-6)

    # Update registry
    aura bookmark create "$BOOKMARK"

    # Set as active
    echo "$BOOKMARK" > .conversations/active.txt

    echo "📌 Bookmark created: $BOOKMARK"
fi
```

**Fallback (No Hook):**
```python
# aura/core/registry.py
def get_or_create_bookmark():
    """Get active bookmark, create if missing"""

    active_file = ".conversations/active.txt"

    if os.path.exists(active_file):
        return read(active_file).strip()

    # Lazy initialization
    bookmark = generate_bookmark()
    write(active_file, bookmark)

    registry.create_conversation(bookmark)
    return bookmark
```

### Conversation Lifecycle

**1. Conversation Start**
```
SessionStart hook (or lazy init)
    ↓
Generate bookmark: 251007_abc123
    ↓
Create registry entry
    ↓
Write to .conversations/active.txt
```

**2. During Conversation**
```
User: /log:develop
    ↓
Read .conversations/active.txt → 251007_abc123
    ↓
Spawn ChangelogAgent with bookmark
    ↓
Create: .develop/.changes/251007-1400_abc123_part-1.md
    ↓
Update registry: add changelog_part
```

**3. Conversation End**
```
User: /log:finalize (or manual)
    ↓
Read active bookmark
    ↓
Archive conversation
    ↓
Move metadata to .conversations/archive/
    ↓
Clear .conversations/active.txt
```

### Multi-Project Scenarios

**Scenario 1: Same User, Multiple Projects**
```
~/project-a/.conversations/registry.json  # Independent
~/project-b/.conversations/registry.json  # Independent
~/project-c/.conversations/registry.json  # Independent
```

No conflicts, each project isolated.

**Scenario 2: Project Rename/Move**
```bash
# Before
~/projects/old-name/.conversations/registry.json

# After move
~/new-location/new-name/.conversations/registry.json

# Still works! (project-local, not absolute paths)
```

**Scenario 3: Team Collaboration**
```bash
# Developer A commits
git add .conversations/registry.json
git commit -m "Checkpoint: API simplification"

# Developer B pulls
git pull
# Now has conversation history
# Can continue from last checkpoint
```

**Scenario 4: Cross-Project Import**
```bash
# Export from project A
aura export 251007_abc123 > conversation.json

# Import to project B
cd ~/project-b
aura import conversation.json
# Creates new bookmark in project B
```

## Outcomes

### Registry Commands (AURA CLI)

**Bookmark Management:**
```bash
# Create bookmark (manual or hook)
aura bookmark create [bookmark_id]

# List conversations
aura bookmark list
# Output:
# 251007_abc123 (active)   - Implement PULSE agent
# 251006_def456 (archived) - Refactor changelog system

# Show details
aura bookmark show 251007_abc123
# Output: Full metadata, changelog parts, affected docs

# Archive conversation
aura bookmark archive 251007_abc123
```

**Import/Export:**
```bash
# Export conversation (for sharing)
aura export 251007_abc123 --format json > conv.json

# Import conversation (from teammate)
aura import conv.json
# Creates: New bookmark in local registry

# Export all (backup)
aura export --all > all_conversations.json
```

**Query:**
```bash
# Search conversations
aura bookmark search "API design"
# Returns: All conversations mentioning API design

# Show active
aura bookmark active
# Output: 251007_abc123
```

### Integration with Other Services

**TRACE Integration:**
```python
# TRACE reads bookmark to get conversation
bookmark = read(".conversations/active.txt")
conversation = trace.get(bookmark)
```

**IMEM Integration:**
```python
# IMEM indexes changelogs by bookmark
changelog_parts = registry.get_changelog_parts(bookmark)
for part in changelog_parts:
    imem.index(part, metadata={"bookmark": bookmark})
```

**PULSE Integration:**
```python
# PULSE updates registry when modifying docs
pulse.on_document_updated(doc_path, bookmark)
registry.add_affected_document(bookmark, doc_path)
```

### Registry Implementation

**Core Class:**
```python
# aura/core/registry.py
class ConversationRegistry:
    """Manage project-local conversation bookmarks"""

    def __init__(self, project_root: str):
        self.registry_path = f"{project_root}/.conversations/registry.json"
        self.active_path = f"{project_root}/.conversations/active.txt"

    def create_conversation(self, bookmark: str, title: str = None):
        """Create new conversation entry"""
        entry = {
            "bookmark": bookmark,
            "created": datetime.now().isoformat(),
            "status": "active",
            "title": title or "Untitled",
            "changelog_parts": [],
            "documents_affected": [],
            "metadata": {}
        }

        registry = self.load()
        registry["conversations"][bookmark] = entry
        registry["active_bookmark"] = bookmark
        self.save(registry)

    def get_active_bookmark(self) -> str:
        """Get current active bookmark"""
        if os.path.exists(self.active_path):
            return read(self.active_path).strip()

        # Lazy initialization fallback
        bookmark = self.generate_bookmark()
        self.create_conversation(bookmark)
        write(self.active_path, bookmark)
        return bookmark

    def add_changelog_part(self, bookmark: str, part_path: str):
        """Register new changelog part"""
        registry = self.load()
        registry["conversations"][bookmark]["changelog_parts"].append(part_path)
        self.save(registry)

    def add_affected_document(self, bookmark: str, doc_path: str):
        """Track document modifications"""
        registry = self.load()
        docs = registry["conversations"][bookmark]["documents_affected"]
        if doc_path not in docs:
            docs.append(doc_path)
        self.save(registry)

    def archive_conversation(self, bookmark: str):
        """Move conversation to archive"""
        registry = self.load()
        entry = registry["conversations"][bookmark]
        entry["status"] = "archived"
        entry["archived_at"] = datetime.now().isoformat()

        # Write to archive
        archive_path = f".conversations/archive/{bookmark}.json"
        write(archive_path, json.dumps(entry, indent=2))

        # Clear active
        if registry["active_bookmark"] == bookmark:
            write(self.active_path, "")

        self.save(registry)

    @staticmethod
    def generate_bookmark() -> str:
        """Generate unique bookmark ID"""
        import uuid
        timestamp = datetime.now().strftime("%y%m%d")
        unique_id = str(uuid.uuid4())[:6]
        return f"{timestamp}_{unique_id}"
```

### Benefits

**1. Isolation**
- No global state conflicts
- Each project independent
- Multiple concurrent conversations per project

**2. Portability**
- Survives renames/moves (project-local paths)
- Git-trackable (team sharing)
- Import/export (cross-project)

**3. Discoverability**
- Search conversations
- List all bookmarks
- Show metadata

**4. Auditability**
- Complete history in registry
- Changelog parts tracked
- Documents affected tracked

**5. Resilience**
- Lazy initialization (no hook dependency)
- Fallback mechanisms
- Graceful degradation

## References

### Key Design Decisions

**1. Project-Local Over Global**
- Rationale: Avoids conflicts, enables team sharing
- Trade-off: Each project needs `.conversations/`
- Winner: Project-local (clear benefits)

**2. Bookmark as Primary Key**
- Rationale: Unique, sortable, human-readable
- Format: `YYMMDD_<6-char-uuid>`
- Example: `251007_abc123`

**3. SessionStart Hook + Fallback**
- Primary: Hook creates bookmark automatically
- Fallback: Lazy initialization on first `/log:develop`
- Result: Works with or without hook

**4. Registry + Active File**
- `registry.json`: Complete metadata (all conversations)
- `active.txt`: Single source of truth (current bookmark)
- Simple, reliable, git-friendly

### Integration Points

**With TRACE:**
- TRACE reads bookmark from `active.txt`
- TRACE provides conversation history to agents
- No tight coupling (file-based)

**With ChangelogAgent:**
- Agent receives bookmark as parameter
- Creates: `.develop/.changes/{timestamp}_{bookmark}_part-N.md`
- Registry updated with changelog path

**With PULSE:**
- PULSE updates documents
- Registry tracks affected documents
- Enables impact analysis

**With IMEM:**
- Indexes changelogs by bookmark
- Search by bookmark or content
- Retrieve full conversation context

### Future Enhancements

**Phase 1 (MVP):**
- Basic registry (create, get, list)
- SessionStart hook (optional)
- Lazy initialization fallback

**Phase 2:**
- Archive mechanism
- Search by content
- Show statistics

**Phase 3:**
- Import/export
- Cross-project sharing
- Team collaboration features

**Phase 4+:**
- Merge conversations
- Split conversations
- Timeline visualization
