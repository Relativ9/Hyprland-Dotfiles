#!/bin/bash
# One clickable workspace button for waybar (custom module, return-type json).
#   ws-button.sh <id>           print {text, class, tooltip} for waybar
#   ws-button.sh focus <id>     switch to that workspace (waybar on-click)
#
# Waybar's built-in hyprland/workspaces click sends `dispatch workspace N`, which
# Hyprland 0.56's Lua dispatcher rejects, so clicks did nothing. This uses the
# `hl.dispatch(hl.dsp.focus({ workspace = N }))` form the keybinds already use.

if [ "${1:-}" = "focus" ]; then
    hyprctl dispatch "hl.dispatch(hl.dsp.focus({ workspace = ${2:?id} }))" >/dev/null 2>&1
    exit 0
fi

ID="${1:?workspace id}"
ACTIVE=$(hyprctl activeworkspace -j | jq -r .id)
INFO=$(hyprctl workspaces -j | jq -c --argjson id "$ID" '.[] | select(.id == $id)')

if [ -z "$INFO" ]; then
    # Persistent workspace with no windows and not yet created: still show it, dimmed.
    cls="empty"; wins=0; mon="-"
else
    wins=$(jq -r '.windows' <<< "$INFO")
    mon=$(jq -r '.monitor' <<< "$INFO")
    cls="occupied"; [ "$wins" = 0 ] && cls="empty"
fi
# Waybar applies the class string as a single class name (it does not split on spaces),
# so emit exactly one class: active wins over occupied/empty.
[ "$ACTIVE" = "$ID" ] && cls="active"

jq -nc --arg t "$ID" --arg c "$cls" --arg tip "workspace $ID on $mon: $wins window(s)" \
    '{text: $t, class: $c, tooltip: $tip}'
