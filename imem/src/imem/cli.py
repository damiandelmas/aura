#!/usr/bin/env python3
"""
IMEM CLI - Vector search for institutional memory

This CLI provides commands for initializing, searching, and managing
vector search collections for project documentation.
"""

import sys
import os
import json
import click
import hashlib
import warnings
from pathlib import Path
from datetime import datetime

# Suppress Pydantic warnings from LlamaIndex
warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')

# Microservice imports (within imem package)
from .config import config
from .ingest import EnhancedModularIngest
from .enhanced import EnhancedQdrantSearch
from .qdrant_service import QdrantService
from .registry import SimpleRegistry
from .compose import compose as compose_pipeline


@click.group()
def imem():
    """IMEM - Vector search for institutional memory"""
    pass


# ============================================================================
# Helper Functions
# ============================================================================

def _index_phase(phase_name: str, force: bool = False, limit: int = None, collection_override: str = None):
    """
    Index a specific phase (develop, design, document) or all context

    Args:
        phase_name: Phase to index ('develop', 'design', 'document', 'context')
        force: If True, recreate collection
        limit: Optional limit for number of documents
        collection_override: Optional collection name override for A/B testing
    """
    from .ingest import EnhancedModularIngest

    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not project_root:
        click.echo("❌ Not in a registered project. Run 'imem init' first.", err=True)
        return

    # Get or create collection
    if collection_override:
        # Manual override for A/B testing
        collection_name = collection_override
        click.echo(f"📝 Using custom collection: {collection_name}")
    else:
        # Normal path: get from registry
        collections = registry.get_project_info(project_root).get('collections')
        if not collections:
            collections = registry.register_project(project_root)
        collection_name = collections['context']

    # Determine paths to index
    if phase_name == 'context':
        # Index all phases
        phases_to_index = ['develop', 'design', 'document']
    else:
        phases_to_index = [phase_name]

    # Initialize ingester
    ingester = EnhancedModularIngest()

    # Create collection if needed
    from qdrant_client.models import Distance, VectorParams, HnswConfigDiff

    try:
        # Create both impl and pattern collections
        impl_collection = f"{collection_name}_impl"
        pattern_collection = f"{collection_name}_pattern"

        for coll_name in [impl_collection, pattern_collection]:
            collection_exists = ingester.client.collection_exists(coll_name)

            if force and collection_exists:
                # Force recreate: delete then create
                click.echo(f"🔄 Recreating collection {coll_name}...")
                ingester.client.delete_collection(coll_name)
                collection_exists = False

            if not collection_exists:
                # Auto-create if doesn't exist
                click.echo(f"📦 Creating collection {coll_name}...")
                ingester.client.create_collection(
                    collection_name=coll_name,
                    vectors_config={
                        config.default_vector_name: VectorParams(
                            size=config.default_dimensions,
                            distance=Distance.COSINE,
                            hnsw_config=HnswConfigDiff(m=16, ef_construct=100)
                        )
                    }
                )
                click.echo(f"✅ Collection created")
    except Exception as e:
        click.echo(f"❌ Error with collection: {e}", err=True)
        return

    # Index each phase
    total_indexed = 0
    for phase in phases_to_index:
        phase_path = project_root / '.context' / phase
        if not phase_path.exists():
            click.echo(f"⚠️  Phase directory not found: {phase_path}")
            continue

        click.echo(f"📚 Indexing {phase} phase...")

        # Find all .md files
        md_files = list(phase_path.rglob("*.md"))
        if limit:
            md_files = md_files[:limit]

        for md_file in md_files:
            try:
                ingester.ingest_markdown_chunked(
                    md_file,
                    phase=phase,
                    base_collection=collection_name
                )
                total_indexed += 1
                layer_badge = "[pattern]" if '.pattern.md' in str(md_file) else "[impl]"
                click.echo(f"   ✅ {layer_badge:10} {md_file.relative_to(project_root)}")
            except Exception as e:
                click.echo(f"   ❌ {md_file.name}: {e}")

        click.echo(f"✅ Indexed {total_indexed} documents from {phase}")

    # Update registry
    registry.update_doc_count(project_root, 'context', total_indexed)

    click.echo(f"\n🎉 Total indexed: {total_indexed} documents")
    return total_indexed


def _index_conversations(force: bool = False, limit: int = None, collection_override: str = None,
                         project_filter: str = None, folder_path: str = None):
    """
    Index Claude Code conversations

    Args:
        force: If True, recreate collection
        limit: Optional limit for number of conversations
        collection_override: Optional collection name override for A/B testing
        project_filter: If provided, filter conversations by project path (empty string = current project)
        folder_path: If provided, search custom folder for conversations
    """
    from .ingest import EnhancedModularIngest
    import sys as _sys

    # Import TRACE components
    trace_path = Path(__file__).parent.parent.parent.parent / 'trace' / 'src'
    _sys.path.insert(0, str(trace_path))
    from aura_trace.finder import ConversationFinder

    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not project_root:
        click.echo("❌ Not in a registered project. Run 'imem init' first.", err=True)
        return

    # Get or create collection
    if collection_override:
        # Manual override for A/B testing
        collection_name = collection_override
        click.echo(f"📝 Using custom collection: {collection_name}")
    else:
        # Normal path: get from registry
        collections = registry.get_project_info(project_root).get('collections')
        if not collections:
            collections = registry.register_project(project_root)
        collection_name = collections['conversation']

    # Initialize ingester
    ingester = EnhancedModularIngest()

    # Create collection if needed
    from qdrant_client.models import Distance, VectorParams, HnswConfigDiff

    try:
        collection_exists = ingester.client.collection_exists(collection_name)

        if force and collection_exists:
            # Force recreate: delete then create
            click.echo(f"🔄 Recreating collection {collection_name}...")
            ingester.client.delete_collection(collection_name)
            collection_exists = False

        if not collection_exists:
            # Auto-create if doesn't exist
            click.echo(f"📦 Creating collection {collection_name}...")
            ingester.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    config.default_vector_name: VectorParams(
                        size=config.default_dimensions,
                        distance=Distance.COSINE,
                        hnsw_config=HnswConfigDiff(m=16, ef_construct=100)
                    )
                }
            )
            click.echo(f"✅ Collection created")
    except Exception as e:
        click.echo(f"❌ Error with collection: {e}", err=True)
        return

    # Find conversations with filtering
    finder = ConversationFinder()

    # Determine filter parameters
    filter_project_path = None
    filter_folder_path = None

    if folder_path:
        # Custom folder takes priority
        filter_folder_path = Path(folder_path)
        click.echo(f"🔍 Searching custom folder: {filter_folder_path}")
    elif project_filter is not None:
        if project_filter == "":
            # Empty string means current project (DEFAULT behavior)
            filter_project_path = project_root
            click.echo(f"🔍 Indexing conversations for current project: {project_root.name}")
        else:
            # Specific project path provided
            filter_project_path = Path(project_filter)
            click.echo(f"🔍 Indexing conversations for project: {filter_project_path}")
    else:
        # None means --all-projects flag was used (EXPLICIT global search)
        click.echo(f"🔍 Indexing conversations from ALL projects (--all-projects)")

    conversation_files = finder.list_all(
        project_filter=filter_project_path,
        folder_path=filter_folder_path
    )

    # Get existing session IDs for incremental indexing
    click.echo(f"🔍 Checking for existing sessions...")
    existing_sessions = set()
    try:
        if collection_exists:
            offset = None
            while True:
                points, next_offset = ingester.client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True
                )

                for point in points:
                    session_id = point.payload.get('session_id')
                    if session_id:
                        existing_sessions.add(session_id)

                if next_offset is None:
                    break
                offset = next_offset

            click.echo(f"   Found {len(existing_sessions)} already indexed sessions")
    except Exception as e:
        click.echo(f"⚠️  Could not check existing sessions: {e}")

    # Filter out already-indexed conversations
    conversations_to_index = []
    skipped_count = 0
    for conv_file in conversation_files:
        session_id = conv_file.stem
        if session_id not in existing_sessions:
            conversations_to_index.append(conv_file)
        else:
            skipped_count += 1

    click.echo(f"📚 Indexing {len(conversations_to_index)} new conversations (skipping {skipped_count} existing)...")

    if limit:
        conversations_to_index = conversations_to_index[:limit]

    # Index each conversation (needs JSONL → markdown conversion)
    total_chunks = 0
    success_count = 0

    # Import TRACE components for conversion
    from aura_trace.retrieval import ConversationRetrieval
    from aura_trace.formatter import ConversationFormatter
    import tempfile

    retrieval = ConversationRetrieval()
    formatter = ConversationFormatter()

    for i, conv_file in enumerate(conversations_to_index, 1):
        session_id = conv_file.stem

        try:
            # Load and convert JSONL to markdown
            entries = retrieval.load_conversation(conv_file)
            timeline = retrieval.get_timeline(
                entries,
                include_messages=True,
                include_patches=True,
                include_files=False,
                include_tools=False
            )
            conv_metadata = retrieval.get_metadata(entries)
            structured_md = formatter.format(timeline, conv_metadata.get('session_id'), conv_metadata)

            # Write to temp file for ingestion
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                f.write(structured_md)
                temp_md_path = Path(f.name)

            # Prepare metadata
            metadata = {
                'start_time': conv_metadata.get('start_time'),
                'duration_minutes': conv_metadata.get('duration_minutes'),
                'message_count': conv_metadata.get('message_count'),
            }

            # Index conversation
            chunks = ingester.ingest_conversation_chunked(
                temp_md_path,
                session_id,
                metadata,
                collection_name=collection_name
            )

            # Clean up
            temp_md_path.unlink()

            if chunks:
                total_chunks += chunks
                success_count += 1
                click.echo(f"  [{i}/{len(conversations_to_index)}] ✅ {session_id[:12]} ({chunks} chunks)")
            else:
                click.echo(f"  [{i}/{len(conversations_to_index)}] ⚠️  {session_id[:12]}: No chunks indexed")

        except Exception as e:
            click.echo(f"  [{i}/{len(conversations_to_index)}] ⚠️  {session_id[:12]}: {e}")

    # Update registry with total chunks (not conversation count)
    registry.update_doc_count(project_root, 'conversation', total_chunks)

    click.echo(f"\n🎉 Indexed {success_count}/{len(conversations_to_index)} new conversations ({total_chunks} chunks)")
    if skipped_count > 0:
        click.echo(f"   Skipped {skipped_count} already-indexed conversations")
    return success_count


# ============================================================================
# Phase-based subcommands for structured search
# ============================================================================


def _execute_search(query: str, filters: dict, limit: int, after_date: str = None):
    """Shared search execution logic"""
    # Ensure service is running
    service = QdrantService()
    if not service.is_running():
        click.echo("Qdrant service not running. Run 'imem service start' first", err=True)
        sys.exit(1)

    # Get project info
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        click.echo("Project not initialized. Run 'imem init' first", err=True)
        sys.exit(1)

    # Determine collection type from source filter
    source = filters.get('source', 'context')
    if source == 'context':
        collection_name = registry.get_collection_by_type(project_root, 'context')
    elif source == 'conversation':
        collection_name = registry.get_collection_by_type(project_root, 'conversation')
    else:
        raise ValueError(f"Unknown source type: {source}")

    # Perform search
    searcher = EnhancedQdrantSearch(
        port=config.qdrant_port,
        collection_name=collection_name
    )

    try:
        results = searcher.search(
            query,
            limit=limit,
            after_date=after_date,
            filters=filters
        )

        if not results:
            click.echo("No results found")
            return

        # Display results
        for i, result in enumerate(results, 1):
            click.echo(f"\n[{i}] Score: {result['score']:.3f}")

            # Show source-specific metadata
            if 'file_path' in result:
                click.echo(f"    File: {result['file_path']}")

            # Show phase/layer for context
            payload = result.get('original_metadata', {})
            if payload.get('source') == 'context':
                phase = payload.get('phase', 'N/A')
                layer = payload.get('layer', 'N/A')
                section_type = payload.get('section_type', 'N/A')
                click.echo(f"    Phase: {phase} | Layer: {layer} | Section: {section_type}")

            # Show session info for conversations
            elif payload.get('source') == 'conversation':
                session_id = payload.get('session_id', 'N/A')
                click.echo(f"    Session: {session_id[:12]}...")

            # Show content
            content = result.get('content', '')
            if content:
                indented = '\n    '.join(content.split('\n'))
                click.echo(f"    {indented}")
                click.echo()

    except Exception as e:
        click.echo(f"Search failed: {e}", err=True)
        sys.exit(1)


# ============================================================================
# New Unified Commands (verb-noun structure)
# ============================================================================

@imem.command('index')
@click.argument('source', type=click.Choice(['develop', 'design', 'document', 'conversations', 'context']))
@click.option('--force', is_flag=True, help='Recreate collection if exists')
@click.option('--limit', type=int, help='Limit number of documents/conversations to index')
@click.option('--collection', help='Override collection name (for A/B testing different models)')
@click.option('--all-projects', is_flag=True, help='Index conversations from ALL projects (default: current project only)')
@click.option('--project', 'project_path', type=str, help='Index specific project path conversations')
@click.option('--folder', type=str, help='Custom folder path to search for conversations')
def index_source(source, force, limit, collection, all_projects, project_path, folder):
    """
    Index content from a specific source

    Sources:
      develop       - .context/develop/ phase
      design        - .context/design/ phase
      document      - .context/document/ phase
      context       - All phases (develop + design + document)
      conversations - Claude Code conversations (DEFAULT: current project only)

    Examples:
      imem index develop
      imem index context --force
      imem index conversations                           # Current project only (DEFAULT)
      imem index conversations --limit 50                # First 50 from current project
      imem index conversations --all-projects            # All projects
      imem index conversations --project /path/to/project
      imem index conversations --folder /custom/path
      imem index develop --collection imem_abc123_nomic  # A/B test with Nomic
    """
    if source == 'conversations':
        # Determine project filter
        # DEFAULT: Current project (project-scoped)
        # EXPLICIT: --all-projects for global indexing
        project_filter = ""  # Default to current project

        if all_projects:
            project_filter = None  # None signals global search
        elif project_path:
            project_filter = project_path

        _index_conversations(
            force=force,
            limit=limit,
            collection_override=collection,
            project_filter=project_filter,
            folder_path=folder
        )
    else:
        _index_phase(phase_name=source, force=force, limit=limit, collection_override=collection)


@imem.command()
@click.argument('config_json')
def compose(config_json):
    """Execute composition pipeline with search + discovery + graph + rendering.

    Config format (JSON):
    {
        "search": {
            "text": "query",
            "filters": {"phase": "develop"},
            "limit": 10
        },
        "discovery": {
            "siblings": true,
            "genealogy": true,
            "temporal": true,
            "cross_phase": "design"
        },
        "graph": {
            "algorithm": "authority",
            "top": 5
        },
        "output": {
            "template": "genealogy"
        }
    }

    Examples:
        # Full genealogy for JWT decision
        imem compose '{"search": {"text": "JWT", "filters": {"phase": "develop"}, "limit": 1}, "discovery": {"siblings": true, "genealogy": true}, "output": {"template": "genealogy"}}'

        # Timeline evolution
        imem compose '{"search": {"text": "caching", "limit": 1}, "discovery": {"temporal": true}, "output": {"template": "timeline"}}'

        # Authority ranking
        imem compose '{"search": {"text": "decisions", "limit": 5}, "discovery": {"siblings": true}, "graph": {"algorithm": "authority"}}'
    """
    import asyncio

    try:
        # Parse config
        config_dict = json.loads(config_json)

        # Get collection
        registry = SimpleRegistry()
        project_root = registry.get_project_root()

        if not registry.is_registered(project_root):
            click.echo("Project not registered. Run 'imem init' first.", err=True)
            sys.exit(1)

        # Get collection based on source field (defaults to context)
        source = config_dict.get('source', 'context')
        if source == 'conversations':
            collection_name = registry.get_collection_by_type(project_root, 'conversation')
        else:
            collection_name = registry.get_collection_by_type(project_root, 'context')

        # Execute composition (async)
        result = asyncio.run(compose_pipeline(collection_name, config_dict))

        # Output
        if 'rendered' in result:
            click.echo(result['rendered'])
        else:
            click.echo(json.dumps(result, indent=2))

    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON config: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Composition failed: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@imem.command()
@click.option('--force', is_flag=True, help='Force re-indexing even if already registered')
@click.option('--vscode', is_flag=True, help='Setup VS Code integration with IMEM Auto-Sync extension')
@click.option('--include-design', is_flag=True, help='Include design phase files (excluded by default)')
def init(force, vscode, include_design):
    """Initialize and index current project.

    Sets up vector search indexing for the current project by detecting
    the .context/ directory structure, registering the project, creating
    a dedicated Qdrant collection, and ingesting all documentation.

    Args:
        force: If True, force re-indexing even if project is already registered.
               This recreates the collection from scratch.
        vscode: If True, configure VS Code settings for IMEM Auto-Sync extension
                integration and attempt to install the extension.

    Returns:
        None. Exits with status code 1 on failure.

    Raises:
        SystemExit: If Qdrant service fails to start, project root cannot be
                   detected, or no context folder is found.
    """
    # Ensure service is running
    service = QdrantService()
    if not service.ensure_running():
        click.echo("Failed to start Qdrant service", err=True)
        sys.exit(1)

    # Get project info
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if project_root is None:
        click.echo("Could not detect project root", err=True)
        sys.exit(1)

    # Inline path detection (simplified - check for .context/ structure)
    context_root = project_root / ".context"
    dev_folder = None

    # Try develop/changes first (ground truth), then design/changes (R&D)
    if (context_root / "develop" / ".changes").exists():
        dev_folder = context_root / "develop"
    elif (context_root / "design" / ".changes").exists():
        dev_folder = context_root / "design"
    elif (context_root / "develop" / "changes").exists():
        dev_folder = context_root / "develop"
    elif (context_root / "design" / "changes").exists():
        dev_folder = context_root / "design"

    if not dev_folder:
        click.echo(f"No context folder found at {project_root}", err=True)
        click.echo("Create a .context/ folder with design/changes/ or develop/changes/ to index")
        sys.exit(1)

    # Check if already registered
    if registry.is_registered(project_root) and not force:
        info = registry.get_project_info(project_root)
        click.echo(f"Project already registered: {project_root}")
        collections = info.get('collections', {})
        doc_counts = info.get('doc_counts', {})
        if collections:
            click.echo(f"Collections:")
            click.echo(f"  - context: {collections.get('context', 'N/A')} ({doc_counts.get('context', 0)} docs)")
            click.echo(f"  - conversation: {collections.get('conversation', 'N/A')} ({doc_counts.get('conversation', 0)} docs)")
        click.echo("Use --force to re-index")
        return

    # Register project (returns dict with both collections)
    collections = registry.register_project(project_root)
    click.echo(f"📁 Project: {project_root}")
    click.echo(f"🏷️  Collections:")
    click.echo(f"   - context: {collections['context']}")
    click.echo(f"   - conversation: {collections['conversation']}")

    # Index context documents using new helper
    click.echo(f"\n📚 Indexing context documents...")
    phases_to_index = ['develop', 'document']
    if include_design:
        phases_to_index.append('design')

    # Use the new _index_phase helper for each phase
    total_indexed = 0
    for phase in phases_to_index:
        phase_path = project_root / '.context' / phase
        if phase_path.exists():
            click.echo(f"\n📂 Indexing {phase} phase...")
            count = _index_phase(phase, force=force, limit=None)
            if count:
                total_indexed += count

    click.echo(f"\n✅ Indexed {total_indexed} documents with section-level chunking")

    # Setup VS Code integration if requested
    if vscode:
        setup_vscode_integration(project_root)

    click.echo(f"\nUse 'imem search <query>' to search your documentation")


@imem.command()
@click.argument('source', type=click.Choice(['develop', 'design', 'document', 'conversations', 'context']))
@click.argument('query', nargs=-1, required=True)
@click.option('--limit', default=5, help='Number of results')
@click.option('--sort-by', default='similarity', type=click.Choice(['similarity', 'date', 'hybrid']))
@click.option('--show-metadata', is_flag=True, help='Show document metadata')
@click.option('--after', default=None, help='Filter results after date (YYYY-MM-DD)')
@click.option('--split-terms', is_flag=True, help='Split query into individual terms for multi-term search')
@click.option('--operator', default='AND', type=click.Choice(['AND', 'OR']),
              help='Operator for combining multiple terms (default: AND)')
@click.option('--layer',
              type=click.Choice(['implementation', 'pattern', 'both']),
              default='implementation',
              help='Filter by layer: implementation (code-specific), pattern (language-agnostic), both')
@click.option('--section', help='Filter by section type (e.g., "Decisions", "User Messages")')
@click.option('--session', help='Filter by conversation session ID (full or partial)')
@click.option('--chunk-type',
              type=click.Choice(['message', 'thinking', 'tools', 'patch']),
              help='Filter by chunk type (conversations only): message, thinking, tools, patch')
@click.option('--role',
              type=click.Choice(['user', 'assistant']),
              help='Filter by role (conversations only): user or assistant')
@click.option('--collection', help='Override collection name (for A/B testing different models)')
def search(source, query, limit, sort_by, show_metadata, after, split_terms, operator, layer, section, session, chunk_type, role, collection):
    """Search documentation in current project.

    Performs vector similarity search across the project's indexed documentation
    using the configured embedding model. Supports multi-term queries with AND/OR
    logic, date filtering, and multiple sorting strategies.

    Args:
        query: One or more search terms. Multiple arguments are automatically
               joined and enable multi-term search.
        limit: Maximum number of results to return (default: 5).
        sort_by: Result sorting strategy - 'similarity' (cosine score),
                'date' (timestamp), or 'hybrid' (weighted combination).
        show_metadata: If True, display extracted YAML frontmatter metadata
                      for each result.
        after: Filter to show only documents after this date (YYYY-MM-DD format).
        split_terms: If True, split query into individual terms for separate
                    vector searches combined with AND/OR logic.
        operator: Combining logic for multi-term search - 'AND' requires all
                 terms match, 'OR' requires at least one term match.

    Returns:
        None. Prints search results to stdout.

    Raises:
        SystemExit: If Qdrant service is not running or project is not initialized.

    Examples:
        imem search develop "authentication flow"
        imem search conversations "bug fix" --split-terms
        imem search context "JWT" --operator=AND
        imem search design "architecture decision"
    """
    # Handle multiple query arguments
    if len(query) > 1:
        # Multiple arguments provided - join them and enable multi-term search
        search_query = " ".join(query)
        split_terms = True
    else:
        # Single argument
        search_query = query[0]

    # Ensure service is running
    service = QdrantService()
    if not service.is_running():
        click.echo("Qdrant service not running. Run 'imem service start' first", err=True)
        sys.exit(1)

    # Get project info
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        click.echo("Project not initialized. Run 'imem init' first", err=True)
        sys.exit(1)

    # Build filters based on source
    filters = {}

    # Allow manual collection override for A/B testing
    if collection:
        collection_name = collection
        # Try to infer source/phase from collection name or use provided source
        if source == 'conversations':
            filters['source'] = 'conversation'
        elif source in ['develop', 'design', 'document']:
            filters['source'] = 'context'
            filters['phase'] = source
        else:  # source == 'context'
            filters['source'] = 'context'
    else:
        # Normal path: get collection from registry
        if source == 'conversations':
            filters['source'] = 'conversation'
            collection_name = registry.get_collection_by_type(project_root, 'conversation')
        elif source in ['develop', 'design', 'document']:
            filters['source'] = 'context'
            filters['phase'] = source
            base_collection = registry.get_collection_by_type(project_root, 'context')
            # Route to impl or pattern collection based on layer
            if layer == 'pattern':
                collection_name = f"{base_collection}_pattern"
            else:  # layer == 'implementation' or 'both'
                collection_name = f"{base_collection}_impl"
        else:  # source == 'context'
            filters['source'] = 'context'
            base_collection = registry.get_collection_by_type(project_root, 'context')
            # Route to impl or pattern collection based on layer
            if layer == 'pattern':
                collection_name = f"{base_collection}_pattern"
            else:  # layer == 'implementation' or 'both'
                collection_name = f"{base_collection}_impl"

    # Layer filter no longer needed - collection name determines layer

    if section:
        filters['section_type'] = section

    if session:
        # Support partial session ID matching (requires exact match in Qdrant)
        # User should provide full session ID or we need to find it first
        filters['session_id'] = session

    if chunk_type:
        filters['chunk_type'] = chunk_type

    if role:
        filters['role'] = role

    # Perform search
    searcher = EnhancedQdrantSearch(
        port=config.qdrant_port,
        collection_name=collection_name
    )

    try:
        results = searcher.search(
            search_query,
            limit=limit,
            sort_by=sort_by,
            after_date=after,
            split_terms=split_terms,
            operator=operator,
            filters=filters if filters else None
        )

        if not results:
            click.echo("No results found")
            return

        # Display results
        for i, result in enumerate(results, 1):
            click.echo(f"\n[{i}] Score: {result['score']:.3f}")
            if 'file_path' in result:
                click.echo(f"    File: {result['file_path']}")

            # Show multi-term search info if applicable
            if 'matching_terms' in result:
                click.echo(f"    Matching terms: {', '.join(result['matching_terms'])}")
                if 'combined_score_method' in result:
                    click.echo(f"    Score method: {result['combined_score_method']}")

            if show_metadata and result.get('metadata'):
                click.echo(f"    Metadata: {json.dumps(result['metadata'], indent=6)}")

            # Show full section content (no truncation - sections are already optimal chunks)
            content = result.get('content', '')
            if content:
                # Indent each line for readability
                indented = '\n    '.join(content.split('\n'))
                click.echo(f"    {indented}")
                click.echo()  # Blank line between results

    except Exception as e:
        click.echo(f"Search failed: {e}", err=True)
        sys.exit(1)


@imem.command()
def update():
    """Re-index current project (incremental).

    Performs incremental re-indexing of the current project by scanning for
    new or modified documents. Only adds documents that don't already exist
    in the collection, making it much faster than full re-indexing.

    This is equivalent to calling 'imem init' without the --force flag.

    Returns:
        None. Delegates to init() command with force=False and vscode=False.
    """
    # Just call init without force flag for incremental update
    ctx = click.get_current_context()
    ctx.invoke(init, force=False, vscode=False)


@imem.command()
@click.option('--dry-run', is_flag=True, help='Show what would be removed without actually removing')
@click.confirmation_option(prompt='Are you sure you want to remove duplicate documents?')
def dedupe(dry_run):
    """Remove duplicate content based on file hashes.

    Finds documents with identical content (same MD5 hash) but different paths,
    and removes older duplicates while keeping the most recent version. Uses
    the ingestion_timestamp and path_updated_at fields to determine recency.

    Requires user confirmation unless run in dry-run mode.

    Args:
        dry_run: If True, show what would be removed without actually deleting
                any documents. Useful for previewing deduplication impact.

    Returns:
        None. Prints summary of duplicates found/removed to stdout.

    Raises:
        SystemExit: If Qdrant service is not running or project is not initialized.

    Examples:
        imem dedupe --dry-run     # Preview what would be removed
        imem dedupe               # Remove duplicates (with confirmation)
    """
    # Ensure service is running
    service = QdrantService()
    if not service.is_running():
        click.echo("Qdrant service not running. Run 'imem service start' first", err=True)
        sys.exit(1)

    # Get project info
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        click.echo("Project not initialized. Run 'imem init' first", err=True)
        sys.exit(1)

    info = registry.get_project_info(project_root)
    collection_name = info['collection']

    try:
        # Initialize ingester for deduplication functionality
        ingester = EnhancedModularIngest()

        # Run deduplication
        result = ingester.deduplicate_collection(collection_name, dry_run=dry_run)

        if result['removed'] > 0:
            if dry_run:
                click.echo(f"\n📋 Summary: Would remove {result['removed']} duplicate documents")
                click.echo("Run without --dry-run to actually remove duplicates")
            else:
                click.echo(f"\n✅ Successfully removed {result['removed']} duplicate documents")
                click.echo("Run 'imem update' to refresh search results if needed")
        else:
            click.echo("✅ No duplicates found - collection is clean!")

    except Exception as e:
        click.echo(f"Deduplication failed: {e}", err=True)
        sys.exit(1)


@imem.command()
def status():
    """Show status of all indexed projects.

    Displays the current state of the Qdrant service and lists all projects
    registered in the IMEM registry with their collection names, document
    counts, and last indexing timestamps.

    Returns:
        None. Prints status information to stdout.
    """
    service = QdrantService()
    registry = SimpleRegistry()

    # Service status
    service_status = service.status()
    if service_status['running']:
        click.echo(f"✅ Service running on port {service_status['port']}")
    else:
        click.echo(f"❌ Service not running")

    # Projects status
    projects = registry.list_projects()
    if not projects:
        click.echo("\nNo projects indexed yet")
        return

    click.echo(f"\n📚 Indexed Projects ({len(projects)}):")
    for path, info in projects.items():
        click.echo(f"\n  {path}")

        # Handle both old (single collection) and new (dual collection) format
        if 'collections' in info:
            # New format: dual collections
            collections = info['collections']
            doc_counts = info.get('doc_counts', {})
            click.echo(f"    Collections:")
            click.echo(f"      Context:      {collections['context']} ({doc_counts.get('context', 0)} docs)")
            click.echo(f"      Conversation: {collections['conversation']} ({doc_counts.get('conversation', 0)} docs)")
        else:
            # Old format: single collection (backward compatibility)
            click.echo(f"    Collection: {info['collection']}")
            click.echo(f"    Documents: {info.get('doc_count', 0)}")

        click.echo(f"    Indexed: {info['indexed_at'][:19]}")


@imem.group()
def collections():
    """Manage collections and lifecycle"""
    pass


@collections.command('list')
def collections_list():
    """List all collections with status"""
    from qdrant_client import QdrantClient

    client = QdrantClient(host='localhost', port=6334)
    registry = SimpleRegistry()

    # Get all IMEM collections
    all_collections = client.get_collections().collections
    imem_collections = [c for c in all_collections if c.name.startswith('imem_')]

    # Get registered collections
    registered = set()
    for project_path, info in registry.list_projects().items():
        if 'collections' in info:
            registered.add(info['collections']['context'])
            registered.add(info['collections']['conversation'])
        elif 'collection' in info:
            registered.add(info['collection'])

    if not imem_collections:
        click.echo("No IMEM collections found")
        return

    click.echo(f"📦 Collections ({len(imem_collections)}):\n")

    # Registered collections
    registered_found = []
    for c in imem_collections:
        if c.name in registered:
            registered_found.append(c)

    if registered_found:
        click.echo("✅ Registered:")
        for c in sorted(registered_found, key=lambda x: x.name):
            info = client.get_collection(c.name)
            click.echo(f"  {c.name} ({info.points_count} points)")

    # Orphaned collections
    orphaned = [c for c in imem_collections if c.name not in registered]
    if orphaned:
        click.echo(f"\n⚠️  Orphaned ({len(orphaned)}):")
        for c in sorted(orphaned, key=lambda x: x.name):
            info = client.get_collection(c.name)
            click.echo(f"  {c.name} ({info.points_count} points)")


@collections.command('clean')
@click.option('--dry-run', is_flag=True, help='Show what would be deleted')
def collections_clean(dry_run):
    """Remove orphaned collections"""
    from qdrant_client import QdrantClient

    client = QdrantClient(host='localhost', port=6334)
    registry = SimpleRegistry()

    # Get registered collections
    registered = set()
    for project_path, info in registry.list_projects().items():
        if 'collections' in info:
            registered.add(info['collections']['context'])
            registered.add(info['collections']['conversation'])
        elif 'collection' in info:
            registered.add(info['collection'])

    # Find orphans
    all_collections = client.get_collections().collections
    orphaned = [c for c in all_collections if c.name.startswith('imem_') and c.name not in registered]

    if not orphaned:
        click.echo("✅ No orphaned collections found")
        return

    click.echo(f"🗑️  Found {len(orphaned)} orphaned collections:\n")
    for c in orphaned:
        info = client.get_collection(c.name)
        click.echo(f"  {c.name} ({info.points_count} points)")

    if dry_run:
        click.echo(f"\n📋 Dry run - would delete {len(orphaned)} collections")
        click.echo("Run without --dry-run to actually delete")
    else:
        # Confirm deletion
        if not click.confirm(f"\n⚠️  Delete {len(orphaned)} orphaned collections?"):
            click.echo("Cancelled")
            return

        click.echo()
        for c in orphaned:
            try:
                client.delete_collection(c.name)
                click.echo(f"  ✅ Deleted {c.name}")
            except Exception as e:
                click.echo(f"  ❌ Failed to delete {c.name}: {e}")

        click.echo(f"\n🎉 Cleaned up {len(orphaned)} collections")


@imem.command('remove')
@click.option('--session', type=str, help='Remove by session ID')
@click.option('--project', type=str, help='Remove by project path')
@click.option('--before', type=str, help='Remove conversations before date (YYYY-MM-DD)')
@click.option('--source', type=click.Choice(['context', 'conversation']), help='Remove by source type')
@click.option('--dry-run', is_flag=True, help='Preview what would be deleted')
def remove_points(session, project, before, source, dry_run):
    """Remove indexed content by filters

    Examples:
      imem remove --session abc123 --dry-run
      imem remove --project /path/to/project
      imem remove --before 2025-01-01
      imem remove --source conversation --before 2024-12-01
    """
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
    from datetime import datetime

    # Build filter conditions
    filter_conditions = []

    if session:
        filter_conditions.append(FieldCondition(key='session_id', match=MatchValue(value=session)))

    if project:
        # Note: project_path might not be in metadata, but file_path contains it
        filter_conditions.append(FieldCondition(key='file_path', match=MatchValue(value=project)))

    if before:
        # Parse date and convert to timestamp
        try:
            date_obj = datetime.strptime(before, '%Y-%m-%d')
            timestamp_str = date_obj.isoformat()
            filter_conditions.append(
                FieldCondition(
                    key='timestamp',
                    range=Range(lt=timestamp_str)
                )
            )
        except ValueError:
            click.echo(f"❌ Invalid date format: {before}. Use YYYY-MM-DD", err=True)
            return

    if source:
        filter_conditions.append(FieldCondition(key='source', match=MatchValue(value=source)))

    if not filter_conditions:
        click.echo("❌ No filter specified. Use --session, --project, --before, or --source", err=True)
        return

    # Get collection info
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not project_root:
        click.echo("❌ Not in a registered project. Run 'imem init' first.", err=True)
        return

    collections = registry.get_project_info(project_root).get('collections')
    if not collections:
        click.echo("❌ No collections found for this project", err=True)
        return

    # Determine which collections to query
    collection_names = []
    if source == 'conversation':
        collection_names = [collections['conversation']]
    elif source == 'context':
        collection_names = [collections['context']]
    else:
        # Query both
        collection_names = [collections['context'], collections['conversation']]

    client = QdrantClient(host='localhost', port=6334)

    # Build Qdrant filter
    qdrant_filter = Filter(must=filter_conditions)

    total_points = 0
    collection_counts = {}

    # Preview matching points
    click.echo("🔍 Searching for matching points...")
    for coll_name in collection_names:
        try:
            if not client.collection_exists(coll_name):
                continue

            # Scroll through matching points
            matching_points = []
            offset = None

            while True:
                points, next_offset = client.scroll(
                    collection_name=coll_name,
                    scroll_filter=qdrant_filter,
                    limit=100,
                    offset=offset,
                    with_payload=True
                )

                matching_points.extend(points)

                if next_offset is None:
                    break
                offset = next_offset

            if matching_points:
                collection_counts[coll_name] = len(matching_points)
                total_points += len(matching_points)

        except Exception as e:
            click.echo(f"⚠️  Error querying {coll_name}: {e}")

    if total_points == 0:
        click.echo("No matching points found")
        return

    # Display results
    click.echo(f"\n📊 Found {total_points} matching points:")
    for coll_name, count in collection_counts.items():
        click.echo(f"   {coll_name}: {count} points")

    # Show sample points
    if dry_run or not dry_run:
        click.echo("\n📋 Sample points:")
        for coll_name in collection_names:
            if coll_name not in collection_counts:
                continue

            points, _ = client.scroll(
                collection_name=coll_name,
                scroll_filter=qdrant_filter,
                limit=3,
                with_payload=True
            )

            for point in points:
                session_id = point.payload.get('session_id', 'N/A')
                section = point.payload.get('section_name', point.payload.get('section_type', 'N/A'))
                click.echo(f"   - {session_id[:12] if session_id != 'N/A' else 'N/A'}: {section}")

    if dry_run:
        click.echo(f"\n📋 Dry run - would delete {total_points} points")
        click.echo("Run without --dry-run to actually delete")
        return

    # Confirm deletion
    if not click.confirm(f"\n⚠️  Delete {total_points} points?"):
        click.echo("Cancelled")
        return

    # Perform deletion
    click.echo("\n🗑️  Deleting points...")
    deleted_count = 0

    for coll_name in collection_counts.keys():
        try:
            # Delete using filter
            result = client.delete(
                collection_name=coll_name,
                points_selector=qdrant_filter
            )

            click.echo(f"   ✅ Deleted from {coll_name}")
            deleted_count += collection_counts[coll_name]

        except Exception as e:
            click.echo(f"   ❌ Failed to delete from {coll_name}: {e}")

    click.echo(f"\n🎉 Deleted {deleted_count} points")

    # Update registry doc counts
    for coll_name in collection_counts.keys():
        try:
            info = client.get_collection(coll_name)
            # Determine collection type from name
            coll_type = 'conversation' if '_conversation' in coll_name else 'context'
            registry.update_doc_count(project_root, coll_type, info.points_count)
        except Exception as e:
            click.echo(f"⚠️  Could not update registry for {coll_name}: {e}")


@imem.group()
def service():
    """Manage the global Qdrant service"""
    pass


@service.command()
def start():
    """Start the global Qdrant service.

    Launches the Qdrant vector database using Docker Compose. Creates the
    docker-compose.yml configuration if it doesn't exist, starts the container,
    and waits for the service to become responsive.

    Returns:
        None. Prints status messages to stdout.

    Raises:
        SystemExit: If the service fails to start within the timeout period.
    """
    service_obj = QdrantService()
    if service_obj.start():
        status = service_obj.status()
        click.echo(f"Service running on port {status['port']}")
        click.echo(f"Collections: {status.get('collections', 0)}")
    else:
        click.echo("Failed to start service", err=True)
        sys.exit(1)


@service.command()
def stop():
    """Stop the global Qdrant service.

    Gracefully stops the Qdrant Docker container using Docker Compose.
    All data is preserved in the persistent storage directory at
    ~/.context/qdrant_storage.

    Returns:
        None. Prints status messages to stdout.
    """
    service_obj = QdrantService()
    service_obj.stop()


@service.command(name='status')
def service_status():
    """Check service status.

    Queries the Qdrant service to determine if it's running and displays
    information about available collections. Shows the service port and
    lists all collection names if the service is accessible.

    Returns:
        None. Prints detailed status information to stdout.
    """
    service_obj = QdrantService()
    status_info = service_obj.status()

    if status_info['running']:
        click.echo(f"✅ Qdrant running on port {status_info['port']}")
        click.echo(f"   Collections: {status_info.get('collections', 0)}")
        if status_info.get('collection_names'):
            for name in status_info['collection_names']:
                click.echo(f"   - {name}")
    else:
        click.echo(f"❌ Qdrant not running (port {status_info['port']})")


def setup_vscode_integration(project_root: Path):
    """Setup VS Code settings for IMEM Auto-Sync extension integration.

    Creates or updates the .vscode/settings.json file with IMEM configuration
    to enable automatic synchronization of changelogs. Also attempts to install
    the bundled IMEM Auto-Sync VS Code extension.

    Args:
        project_root: Path to the project root directory where .vscode/
                     directory should be created.

    Returns:
        None. Prints setup progress and instructions to stdout.

    Notes:
        - Creates .vscode directory if it doesn't exist
        - Merges with existing settings.json if present
        - Configures autoSync, showNotifications, syncOnSave settings
        - Sets changelogPath to .context/design/changes
        - Attempts to install VS Code extension from bundled .vsix file
        - Falls back to manual installation instructions if auto-install fails
    """
    try:
        vscode_dir = project_root / ".vscode"
        settings_file = vscode_dir / "settings.json"

        # Create .vscode directory if it doesn't exist
        vscode_dir.mkdir(exist_ok=True)

        # Load existing settings or create new
        settings = {}
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
            except json.JSONDecodeError:
                # Invalid JSON, start fresh
                settings = {}

        # Add/update IMEM configuration
        # Use .context/design/changes for changelog path
        imem_settings = {
            "imem.autoSync": True,
            "imem.showNotifications": True,
            "imem.syncOnSave": True,
            "imem.changelogPath": ".context/design/changes",
            "files.associations": {
                "*.md": "markdown"
            }
        }

        # Merge with existing settings (IMEM settings take precedence)
        settings.update(imem_settings)

        # Save settings with proper formatting
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)

        click.echo("")
        click.echo("🔧 VS Code Integration Setup:")
        click.echo(f"   ✅ Created/updated {settings_file.relative_to(project_root)}")
        click.echo("   ✅ Configured IMEM Auto-Sync settings")

        # Auto-install VS Code extension
        try:
            # Find bundled extension
            import pkg_resources
            import subprocess

            # FIXED: Changed from 'imem' to 'aura'
            extension_path = pkg_resources.resource_filename('aura', 'assets/imem-auto-sync-1.0.0.vsix')

            if os.path.exists(extension_path):
                click.echo("   🔄 Installing IMEM Auto-Sync extension...")
                result = subprocess.run([
                    'code', '--install-extension', extension_path
                ], capture_output=True, text=True)

                if result.returncode == 0:
                    click.echo("   ✅ VS Code extension installed successfully!")
                else:
                    click.echo("   ⚠️  Extension install failed (VS Code might not be in PATH)")
                    click.echo(f"   Manual install: code --install-extension {extension_path}")
            else:
                click.echo("   ⚠️  Extension file not found - using manual install")
                click.echo("   Manual install: code --install-extension imem-auto-sync")

        except Exception as ext_error:
            click.echo(f"   ⚠️  Could not auto-install extension: {ext_error}")
            click.echo("   Manual install: code --install-extension imem-auto-sync")

        click.echo("")
        click.echo("🚀 Setup Complete!")
        click.echo("   1. Open this project in VS Code: code .")
        click.echo("   2. Extension will auto-activate and sync changelogs on save!")

    except Exception as e:
        click.echo(f"⚠️  Warning: Could not setup VS Code integration: {e}", err=True)
        click.echo("   You can manually create .vscode/settings.json with IMEM configuration")


if __name__ == '__main__':
    imem()
