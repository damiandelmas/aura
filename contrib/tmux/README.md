# contrib/tmux

The tmux operator surface for Aura. Wires the status bar to the live fleet, binds lifecycle ops to keys, and adds a right-click system that resolves any visible text to its exact runtime transcript message.

## Install

```bash
# symlink all scripts into ~/.local/bin/
bash contrib/tmux/install.sh

# optionally install tmux.conf
cp contrib/tmux/tmux.conf ~/.tmux.conf
tmux source ~/.tmux.conf
```

## UI Contract

```
row 1          active fleet:seat address
rows 2–3       live seat roster  (index seat, folded to two rows when narrow)
pane border    active Desks identity (current_name)
right-click    resolve clicked text → transcript message → context menu
```

## Keybindings (`prefix + ...`)

```
u / f / y      copy this pane's fleet:seat identity to clipboard
U              copy all seat identities for this fleet to clipboard
i              show active Desks identity in a popup
r              rollover this seat (fresh session)
R              restart this seat (keep session)
x              cut this seat (confirm prompt)
N              rename this seat
S              spawn a new seat in this fleet  ("name [runtime]")
A              adopt this pane as a managed seat
m              toggle mouse mode (tmux owns wheel ↔ app owns wheel)
```

All lifecycle ops resolve the current pane by exact physical pane id — never by window name.

## Right-click → transcript anchor

Right-clicking a pane resolves the clicked phrase against the seat's runtime transcript JSONL (no semantic search — exact match against this session only). On a clean mint: popup shows the message, copies it to the tmux buffer and OS clipboard, offers a one-line annotation. On ambiguity: escalates to an fzf picker over the full transcript. The anchor carries a content SHA for drift detection.

Context menu verbs: **Annotate** · **Copy message** · **Copy anchor** · Patch into seat (not yet wired).

## Scripts

```
bin/
  tmux-aura-roster            renders seat roster cells for the status bar
  tmux-aura-roster-refresh    refreshes cached tmux options for one fleet/session
  tmux-aura-roster-watch      background watcher; fingerprints registry + Desks + sessions
  tmux-aura-seat-op           runs lifecycle ops against the current pane's seat
  tmux-aura-copy-identity     copies this pane's fleet:seat identity to clipboard
  tmux-aura-copy-fleet        copies all seat refs for this fleet to clipboard
  tmux-aura-show-identity     pops the active Desks identity in a centered overlay
  tmux-aura-resolve-click     right-click entry point: extract phrase → resolve → menu
  tmux-aura-resolve-message   text → transcript position resolver (read-only)
  tmux-aura-anchor-menu       native tmux context menu (annotate / copy / patch)
  tmux-aura-anchor-popup      interactive anchor finalization + note prompt
  tmux-aura-pick              fzf picker over the full transcript (ambiguity escalation)
  tmux-aura-annotate          appends one record to ~/.aura/notes/annotations.jsonl
  tmux-aura-clip              fan out stdin to tmux buffer + OS clipboard (WSL/X11/Wayland/macOS)
```
