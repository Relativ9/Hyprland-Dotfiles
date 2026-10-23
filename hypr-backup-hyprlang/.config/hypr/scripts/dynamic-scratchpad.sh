#!/bin/bash

# CONFIGURATION
# Define the prefix for your monitor-specific scratchpads
# Monitor 1 -> scratch_0, Monitor 2 -> scratch_1, etc.
SCRATCH_PREFIX="S"

# Get Mouse Position and Determine Monitor
# hyprctl monitors -j gives us a JSON list of monitors with their coordinates
MOUSE_X=$(hyprctl cursorpos -j | jq '.x')
MOUSE_Y=$(hyprctl cursorpos -j | jq '.y')

# Find which monitor contains the mouse cursor
CURRENT_MONITOR_ID=$(hyprctl monitors -j | jq -r --argjson x "$MOUSE_X" --argjson y "$MOUSE_Y" '
  .[] | select(.x <= $x and .x + .width > $x and .y <= $y and .y + .height > $y) | .id
')

# Fallback: If mouse coordinates detection fails (rare), default to active monitor
if [ -z "$CURRENT_MONITOR_ID" ]; then
    CURRENT_MONITOR_ID=$(hyprctl activeworkspace -j | jq '.monitorID')
fi

# Active scratchpad is indicated by S on the monitor
SCRATCH_NAME="${SCRATCH_PREFIX}"

# Get Current Workspace Name to check if we are INSIDE a special workspace
CURRENT_WS=$(hyprctl activeworkspace -j | jq -r '.name')
IS_SPECIAL=$(echo "$CURRENT_WS" | grep -c "special:${SCRATCH_NAME}")

# MODE DETECTION
# Arg 1: "toggle" (Super+S) or "move" (Super+Shift+S)
MODE="${1:-toggle}"

if [ "$MODE" == "toggle" ]; then
    hyprctl dispatch togglespecialworkspace "$SCRATCH_NAME"

elif [ "$MODE" == "move" ]; then
    if [ "$IS_SPECIAL" -gt 0 ]; then

        hyprctl dispatch movetoworkspace current
  
    else
        hyprctl dispatch movetoworkspace "special:${SCRATCH_NAME}"
    fi
fi

