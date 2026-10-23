#!/bin/bash
# Always-open dashboard on the special workspace "dashboard" (Super+D).
#   dashboard.sh          toggle (spawns any missing tiles, then arranges them)
#   dashboard.sh respawn  spawn missing tiles + arrange, don't toggle
#   dashboard.sh arrange  only re-arrange the tiles (e.g. after changing monitor)
#
# Layout (computed from the monitor size; tiles are floating windows):
#
#   +----------------------+-----------+-----------+
#   |         htop         |  music    | calendar  |
#   +----------------------+-----------+-----------+
#   |  system (cpu/gpu)    |  weather  |   (tbd)   |
#   +----------------------+-----------+-----------+
#
# Add/remove tiles in TILES ("window-class|command") and in arrange().
WS="special:dashboard"
MON="${DASH_MONITOR:-DP-3}"        # monitor the dashboard opens on
GAP="${DASH_GAP:-16}"
S="$HOME/.config/hypr/scripts"
K="kitty -o window_padding_width=10 --class"

TILES=(
    "dash-htop|$K dash-htop env HTOPRC=$S/htoprc-dashboard htop"
    "dash-system|$K dash-system python3 $S/dashboard-tile.py system"
    "dash-nowplaying|$K dash-nowplaying python3 $S/nowplaying.py"
    "dash-cal|$K dash-cal python3 $S/dashboard-tile.py cal"
    "dash-weather|$K dash-weather python3 $S/dashboard-tile.py weather"
    "dash-inbox|$K dash-inbox python3 $S/inbox-tile.py"
)

# Spotify must be running for the now-playing tile (playerctl). It lives on a
# hidden special workspace instead of cluttering the dashboard.
BG="special:bg"

spawn() { # command workspace
    hyprctl dispatch "hl.dsp.exec_cmd(\"$1\", { workspace = \"$2 silent\" })" >/dev/null
    sleep 0.4
}

# place <class> <half:L|R> <col> <row>
# Left half = 1 column x 2 rows, right half = 2 columns x 2 rows.
place() {
    local class=$1 half=$2 col=$3 row=$4 cols
    [ "$half" = L ] && cols=1 || cols=2
    local x0=$LX; [ "$half" = R ] && x0=$RX
    local cw=$(( (HALF - (cols - 1) * GAP) / cols ))
    local ch=$(( (AH - GAP) / 2 ))
    local x=$(( x0 + col * (cw + GAP) ))
    local y=$(( AY + row * (ch + GAP) ))
    local sel="class:$class"
    hyprctl dispatch "hl.dsp.window.float({ action = \"enable\", window = \"$sel\" })" >/dev/null
    hyprctl dispatch "hl.dsp.window.resize({ x = $cw, y = $ch, relative = false, window = \"$sel\" })" >/dev/null
    hyprctl dispatch "hl.dsp.window.move({ x = $x, y = $y, relative = false, window = \"$sel\" })" >/dev/null
}

arrange() {
    local m
    m=$(hyprctl monitors -j | jq -c --arg n "$MON" '.[]|select(.name==$n)')
    [ -n "$m" ] || return 0
    local mx my mw mh rt rb rl rr
    read -r mx my mw mh rt rb rl rr < <(jq -r '[.x,.y,.width,.height,.reserved[1],.reserved[3],.reserved[0],.reserved[2]]|map(floor)|@tsv' <<< "$m")
    # usable area = monitor minus bars, minus an outer gap
    local ux=$(( mx + rl + GAP )) uy=$(( my + rt + GAP ))
    local uw=$(( mw - rl - rr - 2 * GAP )) uh=$(( mh - rt - rb - 2 * GAP ))
    HALF=$(( (uw - GAP) / 2 ))
    LX=$ux; RX=$(( ux + HALF + GAP )); AY=$uy; AH=$uh

    place dash-htop       L 0 0
    place dash-system     L 0 1
    place dash-nowplaying R 0 0
    place dash-cal        R 1 0
    place dash-weather    R 0 1
    place dash-inbox      R 1 1
}

if [ "${1:-}" != "arrange" ]; then
    classes=$(hyprctl clients -j | jq -r '.[].class')
    grep -qix "spotify" <<< "$classes" || pgrep -x spotify >/dev/null || spawn "spotify-launcher" "$BG"
    for entry in "${TILES[@]}"; do
        class=${entry%%|*}
        cmd=${entry#*|}
        grep -qix "$class" <<< "$classes" || spawn "$cmd" "$WS"
    done
fi

arrange
[ "${1:-}" = "respawn" ] || [ "${1:-}" = "arrange" ] && exit 0

# Special workspaces open on the focused monitor; focus the dashboard monitor first.
hyprctl dispatch "hl.dsp.focus({ monitor = \"$MON\" })" >/dev/null
hyprctl dispatch "hl.dsp.workspace.toggle_special(\"dashboard\")"
