#!/usr/bin/env bash
# Aura claude-code resume/fork launcher — repo-owned so resume is reproducible
# without a hand-placed ~/.local/bin/claude-r.
#
# Claude sessions are project-scoped under ~/.claude/projects/<encoded-cwd>/, so a
# bare `claude -r <id>` only resolves from the session's own directory. We find the
# session globally and symlink it into the CURRENT project folder so claude resolves
# it from here, then exec claude with any extra args forwarded.
#
# Aura passes `--session-id <new> --fork-session` for ALLOCATE-ON-RESUME: claude
# resume rotates the id (it forks from a leaf), so Aura resumes <old> INTO a chosen
# <new> id and born-binds <new> — same allocation semantics as a fresh claude spawn,
# no post-launch heal. Verified: `claude --resume <old> --session-id <new>
# --fork-session` requires --fork-session and carries the resumed content.
#
# Usage: aura-claude-r.sh <session-id> [extra claude args...]
set -euo pipefail

SESSION_ID="${1:-}"
[ -z "$SESSION_ID" ] && { echo "usage: aura-claude-r.sh <session-id> [args...]" >&2; exit 1; }
shift

# Honor a boxed claude home: a package-native claude seat runs with
# CLAUDE_CONFIG_DIR=<package>/.claude, so its session transcripts live there, not
# under $HOME/.claude. Fall back to the global home for plain (unboxed) seats.
PROJECTS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
SRC=$(find "$PROJECTS" -name "${SESSION_ID}*.jsonl" -type f 2>/dev/null | head -n1)
[ -z "$SRC" ] && { echo "claude session not found: $SESSION_ID" >&2; exit 1; }
[ -s "$SRC" ] || { echo "claude session is empty (interrupted before any message): $SESSION_ID" >&2; exit 1; }
FULL=$(basename "$SRC" .jsonl)

# Symlink the session into THIS cwd's project folder so `claude -r` finds it here.
# Encoding mirrors Claude's project-dir convention: leading '-' + path with '/'->'-'.
ENCODED="-$(pwd | sed 's#/#-#g; s#^-##')"
PROJ="$PROJECTS/$ENCODED"
mkdir -p "$PROJ" 2>/dev/null || true
[ -e "$PROJ/$FULL.jsonl" ] || ln -s "$SRC" "$PROJ/$FULL.jsonl" 2>/dev/null || true

exec claude -r "$FULL" "$@"
