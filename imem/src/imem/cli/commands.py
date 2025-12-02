"""CLI command definitions - Thin wrappers delegating to domain controllers

SQLite-first commands:
- app.get_compile_controller() → DocumentIndexer
- app.get_store() → SQLite backend
- app.get_manage_controller() → Management functions
"""

import click
import json
from pathlib import Path

from .main import app


@click.group()
def imem():
    """IMEM - Institutional memory search (SQLite-first)"""
    pass


# ============================================================================
# Indexing Commands (COMPILE domain)
# ============================================================================

@imem.command('index')
@click.argument('phase', type=click.Choice(['develop', 'design', 'document', 'designate', 'context']))
@click.option('--force', is_flag=True, help='Clear existing chunks before indexing')
@click.option('--limit', type=int, help='Limit number of documents')
@click.option('--collection', help='Override collection name for A/B testing')
def index_cmd(phase, force, limit, collection):
    """Index documentation phase to SQLite store"""
    try:
        controller = app.get_compile_controller()
        result = controller.index_phase(
            phase_name=phase,
            force=force,
            limit=limit,
            collection_override=collection
        )
        click.echo(f"✅ Indexed {result.get('indexed', 0)} documents, {result.get('chunks', 0)} chunks")
        if result.get('errors'):
            click.echo(f"⚠️  Errors: {len(result['errors'])}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


@imem.command('index-conversations')
@click.option('--force', is_flag=True, help='Clear collection before indexing')
@click.option('--limit', type=int, help='Limit conversations')
@click.option('--project', help='Filter by project path')
@click.option('--folder', help='Custom folder path')
@click.option('--session-ids', multiple=True, help='Specific session IDs')
def index_conversations_cmd(force, limit, project, folder, session_ids):
    """Index Claude Code conversations to SQLite"""
    try:
        controller = app.get_compile_controller()
        result = controller.index_conversations(
            force=force,
            limit=limit,
            project_filter=project,
            folder_path=folder,
            session_ids=list(session_ids) if session_ids else None
        )
        click.echo(f"✅ Indexed {result.get('indexed', 0)} conversations, {result.get('chunks', 0)} chunks")
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
        imem compose '{"search": {"text": "authentication", "filters": {"phase": "develop"}}}'
    """
    from ..retrieve import compose

    try:
        config = json.loads(config_json)
        store = app.get_store()

        query = config.get('search', {}).get('text', '')
        result = compose(query, config, store)

        click.echo(json.dumps(result, indent=2))

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


@imem.command('query')
@click.option('--text', help='Text query', default='')
@click.option('--phase', help='Filter by phase')
@click.option('--section-type', help='Filter by section type')
@click.option('--file-path', help='Filter by file path')
@click.option('--limit', type=int, default=10, help='Result limit')
def query_cmd(text, phase, section_type, file_path, limit):
    """Query SQLite store (fast metadata search)"""
    try:
        store = app.get_store()

        filters = {}
        if phase:
            filters['phase'] = phase
        if section_type:
            filters['section_type'] = section_type
        if file_path:
            filters['file_path'] = file_path

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


# Alias for backward compatibility
@imem.command('query-metadata')
@click.option('--text', help='Text query', default='')
@click.option('--phase', help='Filter by phase')
@click.option('--section-type', help='Filter by section type')
@click.option('--file-path', help='Filter by file path')
@click.option('--limit', type=int, default=10, help='Result limit')
def query_metadata_cmd(text, phase, section_type, file_path, limit):
    """Query SQLite store (alias for 'query')"""
    ctx = click.get_current_context()
    ctx.invoke(query_cmd, text=text, phase=phase, section_type=section_type, file_path=file_path, limit=limit)


# ============================================================================
# Management Commands (MANAGE domain)
# ============================================================================

@imem.command('introspect')
@click.option('--format', 'fmt', type=click.Choice(['json', 'text']), default='text')
@click.option('--ontology', is_flag=True, help='Include project ontology')
def introspect_cmd(fmt, ontology):
    """Introspect indexed metadata fields"""
    try:
        manage = app.get_manage_controller()
        result = manage['introspect'](enumerate_entities=ontology)

        if fmt == 'json':
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            if 'error' in result:
                click.echo(f"❌ {result['error']}")
                return

            click.echo("📊 Metadata Schema")

            if 'metadata_fields' in result:
                fields = result['metadata_fields']
                if isinstance(fields, dict) and 'error' not in fields:
                    click.echo(f"\nIndexed fields: {len(fields)}")
                    for name, info in list(fields.items())[:10]:
                        click.echo(f"  {name}: {info.get('type', '?')} - {info.get('description', '')}")

            if 'traversal' in result:
                click.echo(f"\n{result['traversal']['note']}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


@imem.command('stats')
def stats_cmd():
    """Show storage statistics"""
    try:
        store = app.get_store()
        stats = store.get_stats()

        click.echo(f"📊 SQLite Storage Stats")
        click.echo(f"\nTotal chunks: {stats.get('total_chunks', 0)}")

        phase_counts = stats.get('by_phase', {})
        if phase_counts:
            click.echo("\nBy phase:")
            for phase, count in phase_counts.items():
                click.echo(f"  {phase}: {count}")

        section_counts = stats.get('by_section_type', {})
        if section_counts:
            click.echo("\nTop section types:")
            for section_type, count in list(section_counts.items())[:10]:
                click.echo(f"  {section_type}: {count}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


# Alias for backward compatibility
@imem.command('stats-metadata')
def stats_metadata_cmd():
    """Show storage statistics (alias for 'stats')"""
    ctx = click.get_current_context()
    ctx.invoke(stats_cmd)


@imem.command('init')
@click.option('--name', help='Project name override')
def init_cmd(name):
    """Initialize IMEM for current project"""
    from ..registry import SimpleRegistry

    try:
        registry = SimpleRegistry()
        project_root = Path.cwd()

        collections = registry.register_project(project_root)

        click.echo(f"✅ Initialized IMEM for {project_root.name}")
        click.echo(f"   Collections: {', '.join(collections.values())}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise


if __name__ == '__main__':
    imem()
