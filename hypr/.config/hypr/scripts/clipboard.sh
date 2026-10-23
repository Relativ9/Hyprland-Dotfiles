#!/bin/bash
# Clipboard history picker (cliphist + rofi). History is filled by the
# `wl-paste --watch cliphist store` watchers started from hyprland.lua.
#   clipboard.sh         pick an entry and copy it
#   clipboard.sh wipe    clear the history
if [ "${1:-}" = "wipe" ]; then
    cliphist wipe && notify-send -a clipboard "Clipboard history cleared"
    exit 0
fi
sel=$(cliphist list | rofi -dmenu -i -p "Clipboard" -theme "$HOME/.config/rofi/theme/picker.rasi") || exit 0
[ -n "$sel" ] && printf '%s' "$sel" | cliphist decode | wl-copy
