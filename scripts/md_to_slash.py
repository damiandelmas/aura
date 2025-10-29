#!/usr/bin/env python3
"""
Markdown to Slash Command Extractor

Extracts sections from markdown runbooks and generates Claude Code slash commands.
Eliminates documentation drift by treating markdown as source code.
"""

import re
from pathlib import Path
from typing import List, Dict
from markdown_it import MarkdownIt
from jinja2 import Template


class WorkflowExtractor:
    """Extracts workflows from trace.md Common Workflows section"""

    def __init__(self, markdown_file: Path):
        self.md_file = markdown_file
        self.md = MarkdownIt()
        self.content = markdown_file.read_text()

    def extract_workflows(self) -> List[Dict[str, str]]:
        """Extract slash commands from Slash Commands section"""
        # Find Slash Commands section
        commands_match = re.search(
            r'## Slash Commands\n\n(.*?)(?=\n## |\Z)',
            self.content,
            re.DOTALL
        )

        if not commands_match:
            return []

        commands_section = commands_match.group(1)

        # Split into individual commands by looking for **command-name** pattern
        command_blocks = re.split(r'(?=\*\*[\w-]+\*\* - )', commands_section)

        workflows = []
        for block in command_blocks:
            if not block.strip():
                continue

            # Extract command name and description
            name_match = re.search(r'\*\*([\w-]+)\*\* - (.*?)$', block, re.MULTILINE)
            if not name_match:
                continue

            command_name = name_match.group(1).strip()
            description = name_match.group(2).strip()

            # Extract Args
            args_match = re.search(r'\*\*Args:\*\* (.*?)$', block, re.MULTILINE)
            argument_hint = args_match.group(1).strip() if args_match else '<args>'

            # Extract Action
            action_match = re.search(r'\*\*Action:\*\* (.*?)$', block, re.MULTILINE)
            action_title = action_match.group(1).strip() if action_match else command_name

            # Extract Verb
            verb_match = re.search(r'\*\*Verb:\*\* (.*?)$', block, re.MULTILINE)
            action_verb = verb_match.group(1).strip() if verb_match else description

            # Extract commands
            commands_match = re.search(r'```bash\n(.*?)\n```', block, re.DOTALL)
            commands = commands_match.group(1).strip() if commands_match else ''

            # Extract Examples
            examples_match = re.search(r'\*\*Examples:\*\*\n```\n(.*?)\n```', block, re.DOTALL)
            usage_examples = examples_match.group(1).strip() if examples_match else f'/{command_name}'

            # Extract Tip
            tip_match = re.search(r'\*\*Tip:\*\* (.*?)(?=\n\*\*|\n\n|\Z)', block, re.DOTALL)
            tip = f"**Tip**: {tip_match.group(1).strip()}" if tip_match else ''

            workflows.append({
                'title': command_name,
                'description': description,
                'argument_hint': argument_hint,
                'action_title': action_title,
                'action_verb': action_verb,
                'commands': commands,
                'usage_examples': usage_examples,
                'tip': tip,
                'slug': command_name
            })

        return workflows

    def _slugify(self, text: str) -> str:
        """Convert title to slug for filename (now unused, kept for compatibility)"""
        return text.lower().replace(' and ', '-').replace(' ', '-')


class SlashCommandGenerator:
    """Generates slash command files from extracted workflows"""

    TEMPLATE = '''---
description: {{ description }}
argument-hint: {{ argument_hint }}
---

# {{ action_title }} - $ARGUMENTS

**{{ action_verb }}**: $ARGUMENTS

## Implementation
{{ commands }}

## Usage
```
{{ usage_examples }}
```

{{ tip }}
'''

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template = Template(self.TEMPLATE)

    def generate(self, workflows: List[Dict[str, str]]):
        """Generate slash command files"""
        generated = []

        for workflow in workflows:
            filename = f"{workflow['slug']}.md"
            filepath = self.output_dir / filename

            content = self.template.render(**workflow)
            filepath.write_text(content)

            generated.append(filepath)
            print(f"✓ Generated: {filepath}")

        return generated


def main():
    # Paths
    trace_md = Path("/home/axp/projects/fleet/hangar/code/aura/main/.context/document/runbooks/trace.md")
    output_dir = Path.home() / ".claude/commands/aura/trace"

    # Extract slash commands
    print("📖 Reading trace.md...")
    extractor = WorkflowExtractor(trace_md)
    workflows = extractor.extract_workflows()

    print(f"📦 Found {len(workflows)} slash commands:")
    for wf in workflows:
        print(f"   - {wf['title']}: {wf['description']}")

    # Generate slash command files
    print("\n🔨 Generating slash command files...")
    generator = SlashCommandGenerator(output_dir)
    files = generator.generate(workflows)

    print(f"\n✅ Generated {len(files)} slash commands in {output_dir}")
    print("\nUsage:")
    for wf in workflows:
        print(f"   /{wf['slug']}")


if __name__ == "__main__":
    main()
