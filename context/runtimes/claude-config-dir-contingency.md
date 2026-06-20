# Runtime adapter contingency — `CLAUDE_CONFIG_DIR`

**Status: load-bearing, vendor-undocumented. Owner: claude-code runtime adapter.**

`CLAUDE_CONFIG_DIR` is the **entire isolation primitive** for the claude-code durable
body. It relocates `~/.claude` (config + `projects/<encoded-cwd>/` session transcripts +
statusline state) under `<package>/.claude`, which is what makes a claude package boxed,
body-gate-valid (`native_state_ref` under the package root), and resumable in place —
exactly the role `CODEX_HOME` plays for codex. **Anthropic does not document it.** It is
observed/empirical behavior of the `claude` CLI; there is no contract that it persists.
Everything claude-package depends on it: `claude_box.prepare_package_box`,
`agent_packages._spawn_env` (`CLAUDE_CONFIG_DIR=.claude`), the spawn env scrub, and
`aura-claude-r.sh` (`PROJECTS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"`).

## Contingencies

**If Anthropic ships an official mechanism** (a documented `--config-dir`/profile flag or
a supported env var): migrate to it. It is a localized change — the env key in
`agent_packages._spawn_env`, the box path in `claude_box`, the scrub list in `spawn.py`,
and the `PROJECTS` root in `aura-claude-r.sh`. The body shape (`<package>/.claude`) and
the bind/statusline FK are unaffected; only the *lever name* changes.

**If Anthropic removes/breaks it** (claude stops honoring `CLAUDE_CONFIG_DIR`): claude
native state reverts to global `~/.claude`, so per-package isolation is lost. Fallback,
in preference order: (1) **`HOME` redirection** — set `HOME=<box>` for the seat if claude
resolves `~/.claude` off `HOME` (mirror the legacy boxed-capsule approach); (2) **degrade
to plain claude seats** — spawn/bind/messaging still work against global `~/.claude`, but
`agent create --runtime claude-code` loses durable-body isolation and should refuse or
warn rather than silently share state; (3) keep codex as the isolated-body reference
runtime. A canary that asserts a boxed claude writes its transcript under
`<package>/.claude` (not `~/.claude`) is the early-warning signal — if it flips, the
primitive broke.
