#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
stamp="$(date +%Y%m%d-%H%M%S)"

link_file() {
  local source="$1"
  local target="$2"
  mkdir -p "$(dirname "$target")"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    mv "$target" "$target.bak-$stamp"
  elif [ -L "$target" ]; then
    rm "$target"
  fi
  ln -s "$source" "$target"
}

# Optional: install tmux.conf (backs up any existing non-symlink)
if [[ "${1:-}" == "--tmux-conf" ]]; then
  link_file "$repo/tmux.conf" "$HOME/.tmux.conf"
  tmux source-file "$HOME/.tmux.conf" 2>/dev/null || true
fi

# Symlink all scripts into ~/.local/bin/
for script in "$repo"/bin/tmux-aura-*; do
  link_file "$script" "$HOME/.local/bin/$(basename "$script")"
done

echo "installed $(ls "$repo/bin/" | grep -c tmux-aura) scripts to ~/.local/bin/"
