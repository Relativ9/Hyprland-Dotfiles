#!/bin/bash

# Get current layout code from the layout field
CURRENT=$(hyprctl devices -j | jq -r '.keyboards[] | select(.main == true) | .layout')

# Determine next layout in cycle: no -> ro -> us -> no
case "$CURRENT" in
    "no") NEXT="ro" ;;
    "ro") NEXT="us" ;;
    "us") NEXT="no" ;;
    *) NEXT="no" ;;
esac

# If called with "toggle", change the layout
if [ "$1" = "toggle" ]; then
    # This actually changes the system keyboard layout
    hyprctl keyword input:kb_layout "$NEXT"
    
    # Update current to display the new layout immediately
    CURRENT="$NEXT"
fi

# Output JSON
echo "{\"text\": \"$CURRENT\", \"tooltip\": \"Layout: $CURRENT (Click to cycle)\"}"

