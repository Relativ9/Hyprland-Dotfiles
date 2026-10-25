#!/bin/bash
# Rotates the wallpaper within the current theme's folder. Used by the optional timer.
#   wallpaper-rotate.sh           pick the next wallpaper for the current theme
#   wallpaper-rotate.sh enable N  rotate every N minutes (systemd user timer)
#   wallpaper-rotate.sh disable   stop rotating
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/theme"
CUR=$(cat "$STATE/current" 2>/dev/null || echo macchiato)
UNIT=theme-wallpaper-rotate

case "${1:-next}" in
    next)
        exec "$HOME/.config/themes/wallpaper-for-theme.sh" "$CUR" --next ;;
    enable)
        mins="${2:-30}"
        mkdir -p "$HOME/.config/systemd/user"
        cat > "$HOME/.config/systemd/user/$UNIT.service" <<EOF
[Unit]
Description=Rotate theme wallpaper

[Service]
Type=oneshot
ExecStart=$HOME/.config/themes/wallpaper-rotate.sh next
EOF
        cat > "$HOME/.config/systemd/user/$UNIT.timer" <<EOF
[Unit]
Description=Rotate theme wallpaper every $mins minutes

[Timer]
OnBootSec=${mins}min
OnUnitActiveSec=${mins}min

[Install]
WantedBy=timers.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable --now "$UNIT.timer" ;;
    disable)
        systemctl --user disable --now "$UNIT.timer" 2>/dev/null
        rm -f "$HOME/.config/systemd/user/$UNIT.timer" "$HOME/.config/systemd/user/$UNIT.service"
        systemctl --user daemon-reload ;;
    *) echo "usage: $0 next|enable [minutes]|disable" >&2; exit 1 ;;
esac
