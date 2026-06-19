#!/usr/bin/env bash
# Install Aura's systemd --user supervision units.
#
# Standalone services (ingress door, cloudflared tunnel) are supervised directly
# by systemd (Restart=on-failure). The dynamically-spawned `aura event` daemons
# can't each be a unit, so a timer drives `aura event ensure-daemons` to respawn
# any running-status job whose daemon pid is dead.
#
# Idempotent. Re-run after editing any unit file in this directory.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$DEST"

UNITS=(
  aura-ingress.service
  aura-cloudflared.service
  aura-event-supervisor.service
  aura-event-supervisor.timer
)

for unit in "${UNITS[@]}"; do
  ln -sf "$SRC/$unit" "$DEST/$unit"
  echo "linked $unit"
done

systemctl --user daemon-reload

# Services + the timer (NOT the supervisor .service — the timer drives it).
systemctl --user enable --now aura-ingress.service
systemctl --user enable --now aura-cloudflared.service
systemctl --user enable --now aura-event-supervisor.timer

echo "--- status ---"
systemctl --user --no-pager --lines=0 status \
  aura-ingress.service aura-cloudflared.service aura-event-supervisor.timer || true
