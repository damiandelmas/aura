.PHONY: slash-commands clean-slash help

# Build slash commands from markdown runbooks
slash-commands:
	@echo "🔨 Building slash commands from trace.md..."
	@venv/bin/python scripts/md_to_slash.py

# Clean generated slash commands
clean-slash:
	@echo "🗑️  Cleaning slash commands..."
	@rm -rf ~/.claude/commands/aura/trace/*.md
	@echo "✓ Cleaned"

# Help
help:
	@echo "AURA Build System"
	@echo ""
	@echo "Targets:"
	@echo "  slash-commands  - Generate slash commands from runbooks (anti-drift)"
	@echo "  clean-slash     - Remove generated slash commands"
	@echo "  help            - Show this help"
	@echo ""
	@echo "Philosophy: Markdown is code. Docs are source of truth."
