#!/usr/bin/env python3
"""
AURA CLI - Unified project initialization for v3

Simplified version that just creates .context/ structure
and delegates to imem/trace for actual functionality.
"""

import sys
import json
import click
from pathlib import Path


@click.command()
@click.option('--force', is_flag=True, help='Overwrite existing structure')
def aura(force):
    """Initialize AURA for current project

    Creates .context/ directory structure:
    - .context/design/.changes/      (Exploration/R&D logs)
    - .context/designate/            (Staged execution plans)
    - .context/develop/.changes/     (Ground truth changelogs)
    - .context/document/             (Stable documentation)

    Example:
        cd /my/project
        aura                # Create structure
        imem init           # Index changelogs
        imem search "query" # Search
    """
    try:
        project_root = Path.cwd()
        context_dir = project_root / ".context"

        click.echo(f"🚀 Initializing AURA for: {project_root.name}\n")

        # Check if already initialized
        if context_dir.exists() and not force:
            click.echo(f"✅ .context/ already exists at {project_root}")
            click.echo("   Use --force to recreate")
            click.echo("\nNext steps:")
            click.echo("  • Create changelogs in .context/develop/.changes/")
            click.echo("  • Run 'imem init' to index them")
            click.echo("  • Run 'imem search \"query\"' to search")
            return

        # Create directory structure
        click.echo("📁 Creating .context/ structure...")
        directories = [
            context_dir / "design" / ".changes",
            context_dir / "designate",
            context_dir / "develop" / ".changes",
            context_dir / "document",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            click.echo(f"   ✅ {directory.relative_to(project_root)}")

        # Create README in .context/
        readme_content = """# AURA Institutional Memory

This directory contains your project's institutional memory:

## Directories

- **design/.changes/** - Exploration logs, R&D sessions, planning documents
- **designate/** - Staged execution plans, consolidated specs
- **develop/.changes/** - Ground truth changelogs (what actually happened)
- **document/** - Stable, authoritative documentation

## Usage

### Create a changelog
```bash
# Create changelog in .context/develop/.changes/
# Use template from assets/changelogs/template/00_TEMPLATE.md
```

### Index your changelogs
```bash
imem init
```

### Search your knowledge
```bash
imem search "authentication" --in develop
imem search "decisions about JWT" --section "Decisions"
```

### Index conversations
```bash
imem index-all-conversations
imem search "database" --in conversations --section "Code Changes"
```

## Changelog Template

See `assets/changelogs/template/00_TEMPLATE.md` for the changelog structure.
All changelogs use H2/H3 hierarchy for LlamaIndex section-level retrieval.

## Learn More

- Run `imem --help` for search options
- Run `trace --help` for conversation archaeology
- Check `.context/develop/.changes/` for example changelogs
"""

        readme_file = context_dir / "README.md"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        click.echo(f"   ✅ {readme_file.relative_to(project_root)}")

        # Success!
        click.echo("\n✅ AURA initialized successfully!\n")
        click.echo("Next steps:")
        click.echo("  1. Create changelogs in .context/develop/.changes/")
        click.echo("     (Use template: assets/changelogs/template/00_TEMPLATE.md)")
        click.echo("  2. Run 'imem init' to index your changelogs")
        click.echo("  3. Run 'imem search \"query\"' to search")
        click.echo("\nOptional:")
        click.echo("  • Run 'imem index-all-conversations' to index Claude conversations")
        click.echo("  • Use 'trace --list' to browse conversation history")

    except Exception as e:
        click.echo(f"\n❌ Initialization failed: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    aura()
