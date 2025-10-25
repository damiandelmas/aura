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
from .search import ModularSearch, SearchConfig
from .enhanced import EnhancedQdrantSearch
from .qdrant_service import QdrantService
from .registry import SimpleRegistry


@click.group()
def imem():
    """IMEM - Vector search for institutional memory"""
    pass


# ============================================================================
# Phase-based subcommands for structured search
# ============================================================================

@imem.group()
def develop():
    """Search develop phase (what we built)"""
    pass


@develop.command(name='search')
@click.argument('query')
@click.option('--decisions', is_flag=True, help='Only Decision sections')
@click.option('--constraints', is_flag=True, help='Only Constraint sections')
@click.option('--failures', is_flag=True, help='Only Failure sections')
@click.option('--patterns', is_flag=True, help='Only Pattern sections')
@click.option('--implementation', is_flag=True, help='Only Implementation sections')
@click.option('--pattern', is_flag=True, help='Search pattern layer only')
@click.option('--impl', is_flag=True, help='Search implementation layer only')
@click.option('--limit', default=5, help='Number of results')
@click.option('--after', help='Only docs after date (YYYY-MM-DD)')
def develop_search(query, decisions, constraints, failures, patterns, implementation, pattern, impl, limit, after):
    """Search develop phase changelogs with section filtering

    Examples:
        imem develop search "database approach" --decisions
        imem develop search "JSONB limitations" --constraints
        imem develop search "provider agnostic" --pattern
    """
    filters = {
        'source': 'changelog',
        'phase': 'develop'
    }

    # Layer filter
    if pattern:
        filters['layer'] = 'pattern'
    elif impl:
        filters['layer'] = 'implementation'

    # Section type filter
    if decisions:
        filters['section_type'] = 'Decisions'
    elif constraints:
        filters['section_type'] = 'Constraints'
    elif failures:
        filters['section_type'] = 'Failures'
    elif patterns:
        filters['section_type'] = 'Patterns'
    elif implementation:
        filters['section_type'] = 'Implementation'

    _execute_search(query, filters, limit, after)


@imem.group()
def conversations():
    """Search conversations (how we got there)"""
    pass


@conversations.command(name='search')
@click.argument('query')
@click.option('--limit', default=5, help='Number of results')
@click.option('--after', help='Only conversations after date (YYYY-MM-DD)')
@click.option('--session', help='Filter by session ID (full or partial)')
@click.option('--messages-only', is_flag=True, help='Show only message chunks (exclude patches)')
@click.option('--patches-only', is_flag=True, help='Show only code patch chunks (exclude messages)')
@click.option('--user-only', is_flag=True, help='Show only user messages')
@click.option('--assistant-only', is_flag=True, help='Show only assistant messages')
@click.option('--file', help='Filter patches by file path (e.g., src/cli.py)')
def conversations_search(query, limit, after, session, messages_only, patches_only, user_only, assistant_only, file):
    """Search conversation transcripts with rich filtering

    Examples:
        imem conversations search "database discussion"
        imem conversations search "authentication" --session cb91d93d
        imem conversations search "bug fix" --patches-only
        imem conversations search "error handling" --file src/cli.py
        imem conversations search "question" --user-only
    """
    filters = {'source': 'conversation'}

    if session:
        filters['session_id'] = session

    # Chunk type filtering
    if messages_only:
        filters['chunk_type'] = 'message'
    elif patches_only:
        filters['chunk_type'] = 'patch'

    # Role filtering (for messages)
    if user_only:
        filters['chunk_type'] = 'message'
        filters['role'] = 'user'
    elif assistant_only:
        filters['chunk_type'] = 'message'
        filters['role'] = 'assistant'

    # File path filtering (for patches)
    if file:
        filters['chunk_type'] = 'patch'
        filters['file_path'] = file

    _execute_search(query, filters, limit, after)


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

    info = registry.get_project_info(project_root)
    collection_name = info['collection']

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

            # Show phase/layer for changelogs
            payload = result.get('original_metadata', {})
            if payload.get('source') == 'changelog':
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
        click.echo(f"Collection: {info['collection']}")
        click.echo(f"Documents: {info['doc_count']}")
        click.echo("Use --force to re-index")
        return

    # Register project
    collection_name = registry.register_project(project_root)
    click.echo(f"📁 Project: {project_root}")
    click.echo(f"🏷️  Collection: {collection_name}")

    # Create search config for this project
    config = SearchConfig(
        name="project",
        model_name="intfloat/e5-large-v2",
        collection_name=collection_name,
        vector_name="e5-large-v2",
        dimensions=1024
    )

    # Ingest documents with section-level chunking
    click.echo(f"📚 Indexing {dev_folder}...")
    ingester = EnhancedModularIngest()

    # Create collection with E5-Large-v2 vector config
    from qdrant_client.models import Distance, VectorParams, HnswConfigDiff
    try:
        if force:
            # Recreate collection
            ingester.client.delete_collection(collection_name)

        ingester.client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "e5-large-v2": VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                    hnsw_config=HnswConfigDiff(
                        m=16,  # Links per node (higher = better recall)
                        ef_construct=100,  # Build-time search depth
                        on_disk=False  # Keep vectors in RAM for speed
                    )
                )
            }
        )
        click.echo(f"   ✅ Created collection: {collection_name}")
    except Exception as e:
        # Collection already exists
        pass

    # Index markdown files with chunking
    from pathlib import Path as PathlibPath

    # Define phases to index (design excluded by default)
    indexed_phases = ['develop', 'designate', 'document']
    if include_design:
        indexed_phases.append('design')

    doc_count = 0
    for phase in indexed_phases:
        phase_dir = context_root / phase
        if not phase_dir.exists():
            continue

        # Find all .md files (including .pattern.md)
        md_files = list(phase_dir.rglob("*.md"))

        for md_file in md_files:
            try:
                # Index with chunking (will auto-detect layer from filename)
                ingester.ingest_markdown_chunked(
                    md_file,
                    phase=phase,
                    collection_name=collection_name
                )
                doc_count += 1

                # Show layer badge in output
                layer_badge = "[pattern]" if '.pattern.md' in str(md_file) else "[impl]"
                click.echo(f"   ✅ {layer_badge:10} {md_file.relative_to(project_root)}")
            except Exception as e:
                click.echo(f"   ❌ {md_file.name}: {e}")

    # Update registry with doc count
    registry.update_doc_count(project_root, doc_count)

    click.echo(f"\n✅ Indexed {doc_count} documents with section-level chunking")

    # Setup VS Code integration if requested
    if vscode:
        setup_vscode_integration(project_root)

    click.echo(f"\nUse 'imem search <query>' to search your documentation")


@imem.command()
@click.argument('query', nargs=-1, required=True)
@click.option('--limit', default=5, help='Number of results')
@click.option('--sort-by', default='similarity', type=click.Choice(['similarity', 'date', 'hybrid']))
@click.option('--show-metadata', is_flag=True, help='Show document metadata')
@click.option('--after', default=None, help='Filter results after date (YYYY-MM-DD)')
@click.option('--split-terms', is_flag=True, help='Split query into individual terms for multi-term search')
@click.option('--operator', default='AND', type=click.Choice(['AND', 'OR']),
              help='Operator for combining multiple terms (default: AND)')
@click.option('--in', 'phase_filter',
              type=click.Choice(['develop', 'designate', 'document', 'conversations', 'all']),
              default='develop',
              help='Filter by phase: develop (ground truth), designate (specs), document (stable), conversations')
@click.option('--layer',
              type=click.Choice(['implementation', 'pattern', 'both']),
              default='implementation',
              help='Filter by layer: implementation (code-specific), pattern (language-agnostic), both')
@click.option('--section', help='Filter by section type (e.g., "Decisions", "User Messages")')
@click.option('--session', help='Filter by conversation session ID (full or partial)')
def search(query, limit, sort_by, show_metadata, after, split_terms, operator, phase_filter, layer, section, session):
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
        imem search "registry collection mapping" --split-terms
        imem search "relative paths" "project root" --operator=AND
        imem search documentation
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

    info = registry.get_project_info(project_root)
    collection_name = info['collection']

    # Build filters based on phase, layer, section, and session
    filters = {}
    if phase_filter == 'conversations':
        filters['source'] = 'conversation'
    elif phase_filter != 'all':
        filters['source'] = 'changelog'
        filters['phase'] = phase_filter

    # Add layer filter (only applies to develop phase changelogs)
    if layer != 'both' and phase_filter == 'develop':
        filters['layer'] = layer

    if section:
        filters['section_type'] = section

    if session:
        # Support partial session ID matching (requires exact match in Qdrant)
        # User should provide full session ID or we need to find it first
        filters['session_id'] = session

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
        click.echo(f"    Collection: {info['collection']}")
        click.echo(f"    Documents: {info['doc_count']}")
        click.echo(f"    Indexed: {info['indexed_at'][:19]}")


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


@imem.command()
@click.argument('conversation_id')
@click.option('--collection', default='institutional_memory', help='Target collection name')
def index_conversation(conversation_id, collection):
    """Index a conversation by session ID or JSONL path.

    Accepts either:
    - Session ID (e.g., abc123 or abc123-def4-5678-9012-34567890abcd)
    - Path to JSONL file (e.g., ~/.claude/projects/.../session.jsonl)

    Automatically:
    1. Finds the conversation file (if session ID provided)
    2. Exports to structured markdown (H2 sections)
    3. Indexes with LlamaIndex section-level chunking
    4. Stores in Qdrant with metadata for filtering

    Args:
        conversation_id: Session ID or path to conversation JSONL file
        collection: Qdrant collection name (default: institutional_memory)

    Examples:
        imem index-conversation abc123
        imem index-conversation 67f63a89-04ab-4aa3-80da-a995c6816e37
        imem index-conversation ~/.claude/projects/.../session.jsonl
    """
    # Import TRACE components
    import sys as _sys
    trace_path = Path(__file__).parent.parent.parent.parent / 'trace' / 'src'
    _sys.path.insert(0, str(trace_path))

    from aura_trace.finder import ConversationFinder
    from aura_trace.retrieval import ConversationRetrieval
    from aura_trace.formatter import ConversationFormatter

    # Ensure service is running
    service = QdrantService()
    if not service.ensure_running():
        click.echo("❌ Failed to start Qdrant service", err=True)
        sys.exit(1)

    # Determine if input is session ID or file path
    conversation_path = Path(conversation_id)

    if conversation_path.exists() and conversation_path.suffix == '.jsonl':
        # Direct path to JSONL file
        conv_file = conversation_path
        # Extract session ID from file content
        finder = ConversationFinder()
        info = finder.get_conversation_info(conv_file)
        session_id = info['session_id']
    else:
        # Session ID provided - find the file
        finder = ConversationFinder()
        conversations = finder.list_all()

        conv_file = None
        for conv in conversations:
            info = finder.get_conversation_info(conv)
            # Match full or partial session ID
            if info['session_id'].startswith(conversation_id):
                conv_file = conv
                session_id = info['session_id']
                break

        if not conv_file:
            click.echo(f"❌ Conversation not found: {conversation_id}", err=True)
            click.echo("Run 'trace --list' to see available conversations")
            sys.exit(1)

    click.echo(f"📁 Found conversation: {session_id[:12]}...")

    # Export to structured markdown using retrieval + formatter directly
    retrieval = ConversationRetrieval()
    formatter = ConversationFormatter()

    try:
        # Load conversation and get timeline
        entries = retrieval.load_conversation(conv_file)
        timeline = retrieval.get_timeline(
            entries,
            include_messages=True,
            include_patches=True,
            include_files=False,
            include_tools=False
        )

        # Get metadata
        conv_metadata = retrieval.get_metadata(entries)

        # Format as markdown
        structured_md = formatter.format(timeline, conv_metadata.get('session_id'), conv_metadata)

        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(structured_md)
            temp_md_path = Path(f.name)

        click.echo(f"📝 Exported structured markdown: {len(structured_md)} chars")

        # Prepare metadata for ingestion
        metadata = {
            'start_time': conv_metadata.get('start_time'),
            'duration_minutes': conv_metadata.get('duration_minutes'),
            'message_count': conv_metadata.get('message_count'),
            'has_changelog': False,  # TODO: detect if changelog exists
            'changelog_path': None
        }

        # Index conversation
        ingester = EnhancedModularIngest()
        ingester.ingest_conversation_chunked(
            temp_md_path,
            session_id,
            metadata,
            collection_name=collection
        )

        # Clean up temp file
        temp_md_path.unlink()

        click.echo(f"✅ Indexed conversation {session_id[:12]} into {collection}")

    except Exception as e:
        click.echo(f"❌ Indexing failed: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@imem.command()
@click.option('--limit', type=int, help='Limit number of conversations to index')
@click.option('--recent', type=int, help='Index only N most recent conversations')
@click.option('--min-size', type=int, default=2, help='Skip conversations smaller than N KB (default: 2)')
@click.option('--collection', default='institutional_memory', help='Target collection name')
@click.option('--dry-run', is_flag=True, help='Show what would be indexed without actually indexing')
def index_all_conversations(limit, recent, min_size, collection, dry_run):
    """Batch index all conversations into IMEM.

    Finds all Claude Code conversations, exports them to structured markdown,
    and indexes them with LlamaIndex section-level chunking.

    This enables semantic search across all your conversation history:
    - "What tools did I use for authentication?"
    - "Show conversations where I modified cli.py"
    - "Find discussions about LlamaIndex"

    Options:
        --limit: Process only first N conversations (for testing)
        --recent: Process only N most recent conversations
        --min-size: Skip conversations smaller than N KB (default: 10KB)
        --dry-run: Preview what would be indexed without actually indexing

    Examples:
        imem index-all-conversations --dry-run
        imem index-all-conversations --recent 10
        imem index-all-conversations --limit 100
        imem index-all-conversations --min-size 50  # Only conversations > 50KB
    """
    # Import TRACE components
    import sys as _sys
    trace_path = Path(__file__).parent.parent.parent.parent / 'trace' / 'src'
    _sys.path.insert(0, str(trace_path))

    from aura_trace.finder import ConversationFinder
    from aura_trace.retrieval import ConversationRetrieval
    from aura_trace.formatter import ConversationFormatter

    # Ensure service is running
    service = QdrantService()
    if not dry_run and not service.ensure_running():
        click.echo("❌ Failed to start Qdrant service", err=True)
        sys.exit(1)

    # Find all conversations
    finder = ConversationFinder()
    all_conversations = finder.list_all()

    # Filter by size
    conversations = []
    skipped_count = 0
    for conv in all_conversations:
        size_kb = conv.stat().st_size // 1024
        if size_kb >= min_size:
            conversations.append(conv)
        else:
            skipped_count += 1

    click.echo(f"📚 Found {len(all_conversations)} conversations")
    if skipped_count > 0:
        click.echo(f"⏭️  Skipping {skipped_count} conversations < {min_size}KB")

    if recent:
        conversations = conversations[:recent]
    if limit:
        conversations = conversations[:limit]

    total = len(conversations)
    click.echo(f"📁 Indexing {total} conversations")

    if dry_run:
        click.echo("\n🔍 Dry run - showing what would be indexed:\n")
        for i, conv_file in enumerate(conversations[:10], 1):
            info = finder.get_conversation_info(conv_file)
            session_id = info['session_id']
            modified = info['modified_time'].strftime('%Y-%m-%d %H:%M')
            size_kb = info['file_size'] // 1024
            click.echo(f"  {i}. {session_id[:12]} - {modified} ({size_kb}KB)")

        if total > 10:
            click.echo(f"  ... and {total - 10} more")

        click.echo(f"\nRun without --dry-run to index {total} conversations")
        return

    # Index conversations with progress using retrieval + formatter directly
    retrieval = ConversationRetrieval()
    formatter = ConversationFormatter()
    ingester = EnhancedModularIngest()

    success_count = 0
    error_count = 0

    import tempfile

    for i, conv_file in enumerate(conversations, 1):
        info = finder.get_conversation_info(conv_file)
        session_id = info['session_id']

        try:
            click.echo(f"[{i}/{total}] Indexing {session_id[:12]}...", nl=False)

            # Export to structured markdown using retrieval + formatter
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

            # Save to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                f.write(structured_md)
                temp_md_path = Path(f.name)

            # Prepare metadata for ingestion
            metadata = {
                'start_time': conv_metadata.get('start_time'),
                'duration_minutes': conv_metadata.get('duration_minutes'),
                'message_count': conv_metadata.get('message_count'),
                'has_changelog': False,
                'changelog_path': None
            }

            # Index
            ingester.ingest_conversation_chunked(
                temp_md_path,
                session_id,
                metadata,
                collection_name=collection
            )

            # Clean up
            temp_md_path.unlink()

            click.echo(" ✅")
            success_count += 1

        except Exception as e:
            click.echo(f" ❌ Error: {e}")
            error_count += 1
            continue

    # Summary
    click.echo(f"\n{'='*60}")
    click.echo(f"📊 Indexing Complete")
    click.echo(f"{'='*60}")
    click.echo(f"✅ Successfully indexed: {success_count}")
    click.echo(f"❌ Failed: {error_count}")
    click.echo(f"📁 Total processed: {total}")
    click.echo(f"\nSearch your conversations:")
    click.echo(f"  imem search \"your query\" --in conversations")


if __name__ == '__main__':
    imem()
