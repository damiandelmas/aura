# tmux-axp

Tmux utilities for monitoring aura agents and Claude Code workflows.

## Scripts

### aura-dashboard.sh
Multi-pane tmux dashboard showing all running agents.

```bash
./scripts/aura-dashboard.sh              # Default session name
./scripts/aura-dashboard.sh my-dash 3    # Custom name, 3s refresh
```

Creates:
- Pane 0: Agent list (refreshing)
- Panes 1-5: Individual agent output streams

### aura-quick.sh
Single-pane quick status view.

```bash
./scripts/aura-quick.sh      # 3s refresh (default)
./scripts/aura-quick.sh 1    # 1s refresh
```

### aura-tail.sh
Tail a specific agent's output.

```bash
./scripts/aura-tail.sh pipeline-orchestrator       # Default 50 lines, 2s
./scripts/aura-tail.sh s1-orchestrator 100 1       # 100 lines, 1s refresh
```

## Quick Setup

```bash
# Add to PATH
echo 'export PATH="$PATH:/home/axp/projects/tmux-axp/main/scripts"' >> ~/.bashrc

# Or symlink
ln -s /home/axp/projects/tmux-axp/main/scripts/aura-dashboard.sh ~/bin/aura-dash
ln -s /home/axp/projects/tmux-axp/main/scripts/aura-quick.sh ~/bin/aura-quick
ln -s /home/axp/projects/tmux-axp/main/scripts/aura-tail.sh ~/bin/aura-tail
```

## Usage

```bash
# Start dashboard when running pipeline
aura spawn pipeline-orchestrator --prompt "..."
aura-dash

# Quick check
aura-quick

# Focus on one agent
aura-tail s1-orchestrator
```
