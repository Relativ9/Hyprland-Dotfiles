#!/bin/bash
# Small self-refreshing info tiles for the dashboard. Usage: dashboard-tile.sh <tile>
#   clock | cal | weather | disks
# Weather location: export DASH_WEATHER_LOCATION=Oslo (empty = auto by IP).
B=$'\e[1m'; R=$'\e[0m'; DIM=$'\e[2m'
tile="${1:-clock}"
printf '\e[?25l'            # hide cursor
trap 'printf "\e[?25h"' EXIT

while true; do
    clear
    case "$tile" in
        clock)
            printf '\n  %s%s%s\n  %s%s%s\n' "$B" "$(date +%H:%M:%S)" "$R" "$DIM" "$(date '+%A, %d %B %Y')" "$R"
            delay=1 ;;
        cal)
            printf '%s Calendar%s\n\n' "$B" "$R"
            cal -m 2>/dev/null | sed 's/^/  /'
            delay=3600 ;;
        weather)
            printf '%s Weather%s\n\n' "$B" "$R"
            curl -s --max-time 6 "wttr.in/${DASH_WEATHER_LOCATION:-}?0&m&Q" | sed 's/^/ /' || true
            [ "${PIPESTATUS[0]}" = 0 ] || echo "  (offline)"
            delay=900 ;;
        disks)
            printf '%s Disks%s\n\n' "$B" "$R"
            df -h --output=target,size,used,pcent -x tmpfs -x devtmpfs -x efivarfs -x squashfs -x overlay 2>/dev/null \
                | sed 's/^/ /'
            printf '\n %sUptime%s %s\n' "$DIM" "$R" "$(uptime -p)"
            delay=60 ;;
        *) echo "unknown tile: $tile"; sleep 5; exit 1 ;;
    esac
    sleep "$delay"
done
