#!/bin/bash
STATE="/tmp/waybar_net_expanded"
CACHE="/tmp/waybar_net_cache"

[ "$1" = "toggle" ] && { [ -f "$STATE" ] && rm "$STATE" || touch "$STATE"; exit; }

IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
[ -z "$IFACE" ] && IFACE="eth0"

# Determine type and WiFi signal
if [ -d "/sys/class/net/${IFACE}/wireless" ]; then
    CONN_TYPE="WiFi"
    ICON="󰤨"
    SIGNAL_RAW=$(awk '/^\s*\w+:/ {gsub(/\./,""); print int($3 * 100 / 70)}' /proc/net/wireless 2>/dev/null | head -1)
    [ -z "$SIGNAL_RAW" ] && SIGNAL_RAW="0"
    
    if [ "$SIGNAL_RAW" -ge 75 ]; then SIG_ICON="▂▄▆█";
    elif [ "$SIGNAL_RAW" -ge 50 ]; then SIG_ICON="▂▄▆ ";
    elif [ "$SIGNAL_RAW" -ge 25 ]; then SIG_ICON="▂▄  ";
    else SIG_ICON="▂   "; fi
else
    CONN_TYPE="Eth"
    ICON="󰈀"
    SIG_ICON=""
fi

# Get current RX/TX instantly
read -r RX_NOW TX_NOW < <(awk "/${IFACE}:/ {print \$2, \$10}" /proc/net/dev)

# Calculate speeds using cache (no sleep needed!)
if [ -f "$CACHE" ]; then
    read -r RX_PREV TX_TIME < <(cat "$CACHE")
    TIME_DELTA=$(($(date +%s%N) - TX_TIME))
    TIME_SECS=$(echo "scale=3; $TIME_DELTA / 1000000000" | bc 2>/dev/null || echo "1")
    
    RX_SPEED=$(awk "BEGIN {printf \"%d\", ($RX_NOW - $RX_PREV) / $TIME_SECS / 1024}")
    TX_SPEED=$(awk "BEGIN {printf \"%d\", ($TX_NOW - $TX_PREV) / $TIME_SECS / 1024}")
else
    RX_SPEED="0"
    TX_SPEED="0"
fi

# Update cache for next run (RX value and timestamp)
echo "$RX_NOW $(date +%s%N)" > "$CACHE"

# Human readable
format_speed() {
    local speed=$1
    if [ "$speed" -gt 1024 ]; then echo "$((speed/1024))MB"
    elif [ "$speed" -gt 0 ]; then echo "${speed}KB"
    else echo "0KB"; fi
}

DOWN=$(format_speed $RX_SPEED)
UP=$(format_speed $TX_SPEED)

if [ -f "$STATE" ]; then
    # Expanded - instant display using cached calculation
    if [ "$CONN_TYPE" = "WiFi" ]; then
        TEXT="WiFi ${SIG_ICON} | ▼${DOWN}/s ▲${UP}/s"
    else
        TEXT="Eth | ▼${DOWN}/s ▲${UP}/s"
    fi
    echo "{\"text\": \"${TEXT}\", \"class\": \"expanded\"}"
else
    # Compact
    if [ "$RX_SPEED" -gt 1 ]; then
        echo "{\"text\": \"${ICON} ${DOWN}/s\", \"class\": \"compact\"}"
    else
        echo "{\"text\": \"${ICON}\", \"class\": \"compact\"}"
    fi
fi

