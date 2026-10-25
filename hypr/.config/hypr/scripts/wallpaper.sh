#!/bin/bash
# Multi-monitor wallpaper for awww.
#
# Usage:
#   wallpaper.sh span    <image>   one image stretched across all monitors, lined up
#   wallpaper.sh same    <image>   the same image filling each monitor individually
#   wallpaper.sh restore           re-apply the last used wallpaper (use at login)
#
# The crop geometry is read live from `hyprctl monitors -j`, so it follows
# whatever layout nwg-displays produced (positions, scale, rotation).
# Pieces are cropped at each monitor's *logical* (rotated, scaled) size.

set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wallpaper"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/wallpaper-span"
STATE_FILE="$STATE_DIR/current"
mkdir -p "$STATE_DIR" "$CACHE_DIR"

TRANSITION="${WALLPAPER_TRANSITION:-fade}"
TRANSITION_DURATION="${WALLPAPER_TRANSITION_DURATION:-1}"

MODE="${1:-restore}"
IMAGE="${2:-}"

if [ "$MODE" = "restore" ]; then
    [ -f "$STATE_FILE" ] || { echo "No saved wallpaper in $STATE_FILE" >&2; exit 1; }
    read -r MODE IMAGE < "$STATE_FILE"
fi

[ -f "$IMAGE" ] || { echo "Image not found: $IMAGE" >&2; exit 1; }
IMAGE="$(realpath "$IMAGE")"

# Make sure the daemon is up.
if ! awww query >/dev/null 2>&1; then
    (awww-daemon >/dev/null 2>&1 & disown)
    for _ in $(seq 1 20); do
        awww query >/dev/null 2>&1 && break
        sleep 0.25
    done
fi

# name x y logical_w logical_h (rotation + scale applied)
MONITORS=$(hyprctl monitors -j | jq -r '
  .[] | (.transform % 2 == 1) as $rot
      | (if $rot then .height else .width end / .scale | floor) as $w
      | (if $rot then .width else .height end / .scale | floor) as $h
      | "\(.name) \(.x) \(.y) \($w) \($h)"')

[ -n "$MONITORS" ] || { echo "No monitors reported by hyprctl" >&2; exit 1; }

set_img() { # output file
    awww img -o "$1" --transition-type "$TRANSITION" --transition-duration "$TRANSITION_DURATION" "$2"
}

# Crops are all rendered first (in parallel), then every output is switched within
# milliseconds of each other, so the fades start together on all monitors.
if [ "$MODE" = "same" ]; then
    while read -r NAME _ _ W H; do
        OUT="$CACHE_DIR/${NAME}.png"
        magick "$IMAGE" -resize "${W}x${H}^" -gravity center -extent "${W}x${H}" +repage -define png:compression-level=0 "$OUT" &
    done <<< "$MONITORS"
    wait
    while read -r NAME _ _ _ _; do
        set_img "$NAME" "$CACHE_DIR/${NAME}.png" &
    done <<< "$MONITORS"
    wait
elif [ "$MODE" = "span" ]; then
    # Bounding box of the whole layout.
    read -r MINX MINY CW CH < <(awk '
        { x2=$2+$4; y2=$3+$5
          if (NR==1 || $2<minx) minx=$2
          if (NR==1 || $3<miny) miny=$3
          if (NR==1 || x2>maxx) maxx=x2
          if (NR==1 || y2>maxy) maxy=y2 }
        END { print minx, miny, maxx-minx, maxy-miny }' <<< "$MONITORS")

    # Fit the image over the whole canvas (cover + center crop), once.
    # png:compression-level=0 is the big win: default PNG compression on the full canvas took ~4.5s, level 0 ~0.4s.
    CANVAS="$CACHE_DIR/canvas.png"
    magick "$IMAGE" -resize "${CW}x${CH}^" -gravity center -extent "${CW}x${CH}" +repage -define png:compression-level=0 "$CANVAS"

    while read -r NAME X Y W H; do
        OUT="$CACHE_DIR/${NAME}.png"
        magick "$CANVAS" -crop "${W}x${H}+$((X - MINX))+$((Y - MINY))" +repage -define png:compression-level=0 "$OUT" &
    done <<< "$MONITORS"
    wait
    while read -r NAME _ _ _ _; do
        set_img "$NAME" "$CACHE_DIR/${NAME}.png" &
    done <<< "$MONITORS"
    wait
else
    echo "Unknown mode: $MODE (span|same|restore)" >&2
    exit 1
fi

echo "$MODE $IMAGE" > "$STATE_FILE"
