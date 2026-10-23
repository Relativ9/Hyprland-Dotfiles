#!/bin/bash
# Usage: special-indicator.sh <monitor-name>
# Prints "S" when a special workspace (scratchpad) is open on that monitor, nothing otherwise.
MON="$1"
NAME=$(hyprctl monitors -j | jq -r --arg mon "$MON" '.[] | select(.name == $mon) | .specialWorkspace.name // empty')
if [ "$NAME" = "special:dashboard" ]; then
    echo "{\"text\": \"D\", \"tooltip\": \"Dashboard (Super+D to close)\", \"class\": \"dashboard-open\"}"
elif [ -n "$NAME" ]; then
    echo "{\"text\": \"S\", \"tooltip\": \"Special workspace: $NAME\", \"class\": \"special-open\"}"
else
    echo "{\"text\": \"\", \"tooltip\": \"\", \"class\": \"special-closed\"}"
fi
