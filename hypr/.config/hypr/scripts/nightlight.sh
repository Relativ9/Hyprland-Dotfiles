#!/bin/bash
# Night light toggle (wlsunset). Usage: nightlight.sh [toggle|on|off]
# Fixed schedule so no location is needed: warm 20:00-07:00.
# Override with NIGHT_TEMP (default 4000K), NIGHT_START / NIGHT_END.
TEMP="${NIGHT_TEMP:-4000}"
START="${NIGHT_START:-20:00}"
END="${NIGHT_END:-07:00}"

on()  { pgrep -x wlsunset >/dev/null || (setsid wlsunset -t "$TEMP" -T 6500 -s "$START" -S "$END" >/dev/null 2>&1 &); }
off() { pkill -x wlsunset; }

case "${1:-toggle}" in
    on)  on;  notify-send -a nightlight "Night light ON" "${TEMP}K from $START to $END" ;;
    off) off; notify-send -a nightlight "Night light OFF" ;;
    toggle)
        if pgrep -x wlsunset >/dev/null; then off; notify-send -a nightlight "Night light OFF"
        else on; notify-send -a nightlight "Night light ON" "${TEMP}K from $START to $END"; fi ;;
esac
