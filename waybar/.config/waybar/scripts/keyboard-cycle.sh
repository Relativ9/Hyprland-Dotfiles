#!/bin/bash

# Main keyboard device (the one Hyprland reports as main)
KBD=$(hyprctl devices -j | jq -r '.keyboards[] | select(.main == true) | .name')

# If called with "toggle", switch to the next configured layout (input:kb_layout = no,us).
# "keyword" is not usable on Hyprland 0.56+ (Lua parser), so use switchxkblayout.
if [ "$1" = "toggle" ] && [ -n "$KBD" ]; then
    hyprctl switchxkblayout "$KBD" next > /dev/null
fi

# Read the ACTIVE layout name (e.g. "Norwegian" / "English (US)") and shorten it for display
ACTIVE=$(hyprctl devices -j | jq -r '.keyboards[] | select(.main == true) | .active_keymap')
case "$ACTIVE" in
    "Norwegian") CURRENT="no" ;;
    "English (US)") CURRENT="us" ;;
    *) CURRENT=$(echo "$ACTIVE" | tr '[:upper:]' '[:lower:]' | cut -c1-2) ;;
esac

# Output JSON
echo "{\"text\": \"$CURRENT\", \"tooltip\": \"Layout: $ACTIVE (Click to cycle)\"}"

