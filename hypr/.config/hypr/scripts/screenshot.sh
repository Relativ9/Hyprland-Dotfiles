#!/bin/bash
# Screenshot + annotate with satty.
#   screenshot.sh region|window|output     capture, then edit in satty
#   screenshot.sh quick-region             capture straight to clipboard+file (no editor)
MODE="${1:-region}"
DIR="$HOME/Pictures/Screenshots"
mkdir -p "$DIR"
FILE="$DIR/screenshot-$(date +%Y-%m-%d_%H-%M-%S).png"

case "$MODE" in
    quick-region) exec hyprshot -m region -o "$DIR" ;;
    region|window|output) ;;
    *) echo "usage: $0 region|window|output|quick-region" >&2; exit 1 ;;
esac

if ! command -v satty >/dev/null; then
    notify-send -a screenshot -u critical "satty is not installed" "sudo pacman -S satty"
    exec hyprshot -m "$MODE" -o "$DIR"
fi

hyprshot -m "$MODE" -z --raw -s | satty --filename - --output-filename "$FILE" \
    --early-exit --copy-command wl-copy --actions-on-enter save-to-clipboard \
    --save-after-copy --initial-tool arrow
