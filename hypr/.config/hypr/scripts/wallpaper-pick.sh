#!/bin/bash
# Rofi picker for wallpapers. Usage: wallpaper-pick.sh [span|same]
MODE="${1:-span}"
DIR="${WALLPAPER_DIR:-$HOME/Pictures/wallpapers}"

CHOICE=$(find "$DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -printf '%f\n' \
    | sort | rofi -dmenu -i -p "Wallpaper ($MODE)" -theme "$HOME/.config/rofi/theme/picker.rasi")

[ -n "$CHOICE" ] && exec "$HOME/.config/hypr/scripts/wallpaper.sh" "$MODE" "$DIR/$CHOICE"
