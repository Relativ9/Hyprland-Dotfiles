#!/bin/bash
# Picks a wallpaper for a theme and spans it across the three monitors.
#   wallpaper-for-theme.sh <theme>          pick a random image from the theme's folder
#   wallpaper-for-theme.sh <theme> --next   same, but never repeats the last one
#
# Images live in ~/Pictures/wallpapers/ThemeSwitcherWallpaper/<theme>/ (jpg, jpeg, png, webp).
# Drop files in or remove them any time; the next pick uses whatever is there.
# If a theme folder is empty, falls back to the shared ThemeSwitcherWallpaper folder.

THEME="${1:?theme name}"
MODE="${2:-}"
ROOT="$HOME/Pictures/wallpapers/ThemeSwitcherWallpaper"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/theme"
LAST="$STATE/wallpaper-last"
SPAN="$HOME/.config/hypr/scripts/wallpaper.sh"
mkdir -p "$STATE"

pick() {
    find "$1" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null
}

candidates=$(pick "$ROOT/$THEME")
# Empty theme folder: use any wallpaper from the other theme folders, so the switch still changes the picture.
[ -n "$candidates" ] || candidates=$(find "$ROOT" -mindepth 2 -maxdepth 2 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null)
[ -n "$candidates" ] || { echo "no wallpapers in $ROOT" >&2; exit 0; }

if [ "$MODE" = "--next" ] && [ -f "$LAST" ]; then
    candidates=$(grep -v -x -F "$(cat "$LAST")" <<< "$candidates" || true)
    [ -n "$candidates" ] || candidates=$(pick "$ROOT/$THEME")
fi

choice=$(shuf -n1 <<< "$candidates")
echo "$choice" > "$LAST"
exec "$SPAN" span "$choice"
