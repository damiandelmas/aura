"""CLI command definitions - Thin wrappers delegating to domain controllers

Commands use the composition root (app) to access shared resources:
- app.get_compile_controller() → DocumentIndexer
- app.get_sqlite_store() → SQLite backend
- app.get_qdrant_store() → Qdrant backend
- app.get_manage_controller() → Management functions
"""

import click
import json
from pathlib import Path

# Import composition root
from .main import app


@click.group()
def imem():
    """IMEM - Vector search for institutional memory"""
    pass


# ============================================================================
# Indexing Commands (COMPILE domain)
# ============================================================================

@imem.command('index')
@click.argument('phase', type=click.Choice(['develop', 'design', 'document', 'context']))
@click.option('--force', is_flag=True, help='Recreate collection if exists')
@click.option('--limit', type=int, help='Limit number of documents')
@click.option('--collection', help='Override collection name for A/B testing')
def index_cmd(phase, force, limit, collection):
    """Index documentation phase to vector store"""
    try:
        controller = app.get_compile_controller()
        result = controller.index_phase(
            phase_name=phase,
            force=force,
            limit=limit,
            collection_override=collection
        )
        click.echo(f"✅ Indexed {result.get('indexed', 0)} documents")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


@imem.command('index-conversations')
@click.option('--force', is_flag=True, help='Recreate collection')
@click.option('--limit', type=int, help='Limit conversations')
@click.option('--project', help='Filter by project path')
@click.option('--folder', help='Custom folder path')
@click.option('--session-ids', multiple=True, help='Specific session IDs')
def index_conversations_cmd(force, limit, project, folder, session_ids):
    """Index Claude Code conversations"""
    try:
        controller = app.get_compile_controller()
        result = controller.index_conversations(
            force=force,
            limit=limit,
            project_filter=project,
            folder_path=folder,
            session_ids=list(session_ids) if session_ids else None
        )
        click.echo(f"✅ Indexed {result.get('indexed', 0)} conversations")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


@imem.command('index-metadata')
@click.argument('phase', type=click.Choice(['develop', 'design', 'document', 'designate']))
@click.option('--limit', type=int, help='Limit documents')
def index_metadata_cmd(phase, limit):
    """Index phase to SQLite metadata store (fast, no vectors)"""
    from ..parse import MarkdownParser

    try:
        project_root = app.get_project_root()
        if not project_root:
            click.echo("❌ Not in registered project. Run 'imem init' first.", err=True)
            return

        store = app.get_sqlite_store()
        parser = MarkdownParser()

        phase_path = project_root / '.context' / phase
        if not phase_path.exists():
            click.echo(f"❌ Phase directory not found: {phase_path}", err=True)
            return

        md_files = list(phase_path.rglob("*.md"))
        if limit:
            md_files = md_files[:limit]

        chunks = []
        for md_file in md_files:
            try:
                # MarkdownParser auto-detects phase from path, no parameter needed
                file_chunks = parser.parse_file(md_file)
                chunks.extend(file_chunks)
                click.echo(f"   ✅ {md_file.relative_to(project_root)}")
            except Exception as e:
                click.echo(f"   ❌ {md_file.name}: {e}")

        # SQLiteVectorStore uses upsert() not upsert_chunks()
        store.upsert(chunks)
        click.echo(f"\n✅ Indexed {len(chunks)} chunks to SQLite")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


# ============================================================================
# Query Commands (COMPOSE domain)
# ============================================================================

@imem.command('compose')
@click.argument('config_json')
def compose_cmd(config_json):
    """Execute retrieval pipeline with config

    Example:
        imem compose '{"search": {"mode": "metadata", "filters": {"phase": "develop"}}}'
    """
    from ..compose.orchestrator import compose

    try:
        config = json.loads(config_json)
        store = app.get_sqlite_store()

        query = config.get('search', {}).get('text', '')
        result = compose(query, config, store)

        click.echo(json.dumps(result, indent=2))

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


@imem.command('query-metadata')
@click.option('--text', help='Text query', default='')
@click.option('--phase', help='Filter by phase')
@click.option('--section-type', help='Filter by section type')
@click.option('--file-path', help='Filter by file path')
@click.option('--limit', type=int, default=10, help='Result limit')
def query_metadata_cmd(text, phase, section_type, file_path, limit):
    """Query SQLite metadata store (fast, no semantic search)"""
    try:
        store = app.get_sqlite_store()

        filters = {}
        if phase:
            filters['phase'] = phase
        if section_type:
            filters['section_type'] = section_type
        if file_path:
            filters['file_path'] = file_path

        # Use VectorStore.search() protocol method with use_vector=False
        results = store.search(
            query=text,
            limit=limit,
            filters=filters,
            use_vector=False
        )

        for i, result in enumerate(results, 1):
            click.echo(f"\n{i}. {result.metadata.get('file_path', 'unknown')}")
            click.echo(f"   Phase: {result.metadata.get('phase', 'N/A')} | Section: {result.metadata.get('section_type', 'N/A')}")
            content = result.content[:200] if result.content else ''
            click.echo(f"   {content}...")

        click.echo(f"\n✅ Found {len(results)} results")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


# ============================================================================
# Management Commands (MANAGE domain)
# ============================================================================

@imem.command('introspect')
@click.option('--format', type=click.Choice(['json', 'text']), default='text')
def introspect_cmd(format):
    """Introspect indexed corpus"""
    try:
        manage = app.get_manage_controller()
        result = manage['introspect']()

        if format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            # Text format
            click.echo("📊 Corpus Introspection")
            click.echo(f"\nTotal chunks: {result.get('total_chunks', 0)}")
            click.echo(f"Phases: {', '.join(result.get('phases', []))}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


@imem.command('stats-metadata')
def stats_metadata_cmd():
    """Show SQLite metadata statistics"""
    try:
        store = app.get_sqlite_store()

        # Use VectorStore.get_stats() protocol method
        stats = store.get_stats()

        click.echo(f"📊 SQLite Metadata Stats")
        click.echo(f"\nTotal chunks: {stats.get('total_chunks', 0)}")

        phase_counts = stats.get('by_phase', {})
        if phase_counts:
            click.echo("\nBy phase:")
            for phase, count in phase_counts.items():
                click.echo(f"  {phase}: {count}")

        section_counts = stats.get('by_section_type', {})
        if section_counts:
            click.echo("\nBy section type:")
            for section_type, count in list(section_counts.items())[:10]:
                click.echo(f"  {section_type}: {count}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


@imem.command('init')
@click.option('--name', help='Project name override')
def init_cmd(name):
    """Initialize IMEM for current project"""
    from ..registry import SimpleRegistry

    try:
        registry = SimpleRegistry()
        project_root = Path.cwd()

        # Note: SimpleRegistry.register_project() doesn't accept name parameter
        # It auto-generates from project root
        collections = registry.register_project(project_root)

        click.echo(f"✅ Initialized IMEM for {project_root.name}")
        click.echo(f"   Collections: {', '.join(collections.values())}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


# ============================================================================
# Service Commands
# ============================================================================

@imem.command('service')
@click.argument('action', type=click.Choice(['start', 'stop', 'status']))
def service_cmd(action):
    """Manage Qdrant service"""
    from ..service import QdrantService

    try:
        service = QdrantService()

        if action == 'start':
            service.start()
            click.echo("✅ Qdrant service started")
        elif action == 'stop':
            service.stop()
            click.echo("✅ Qdrant service stopped")
        elif action == 'status':
            status = service.status()
            click.echo(f"Qdrant: {status}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


if __name__ == '__main__':
    imem()
