# Search Convenience Flags

## Current
```bash
imem search develop "auth" --section "Decisions"
imem search conversations "bug" --section "User Messages"
```

## Proposed
```bash
imem search develop "auth" --decisions
imem search develop "pattern" --patterns
imem search develop "error" --failures
imem search develop "limit" --constraints

imem search conversations "bug" --messages-only
imem search conversations "fix" --patches-only
imem search conversations "help" --user-only
imem search conversations "impl" --assistant-only
```

## Implementation
Shortcut flags map to `--section` values:
- `--decisions` → `--section "Decisions"`
- `--patterns` → `--section "Patterns"`
- `--failures` → `--section "Failures"`
- `--constraints` → `--section "Constraints"`
- `--messages-only` → `--section` filter for message chunks
- `--patches-only` → `--section` filter for patch chunks
- `--user-only` → `--section` filter + role metadata
- `--assistant-only` → `--section` filter + role metadata
