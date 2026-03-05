#!/bin/bash

# Check for VPN interface (works for both GUI and CLI connections)
IFACE=$(ip link show 2>/dev/null | grep -E "proton|tun|vpn" | head -1 | awk '{print $2}' | tr -d ':')

if [ -n "$IFACE" ]; then
    # VPN is active
    ICON="󱠽"
    CLASS="proton-connected"
    
    # Get IP if available
    IP=$(ip addr show "$IFACE" 2>/dev/null | grep "inet " | head -1 | awk '{print $2}' | cut -d/ -f1)
    [ -n "$IP" ] && TOOLTIP="Connected\nIP: $IP" || TOOLTIP="VPN Active"
else
    ICON="󰌾"
    CLASS="proton-disconnected"  
    TOOLTIP="Disconnected\nClick to open Proton VPN"
fi

echo "{\"text\": \"$ICON\", \"class\": \"$CLASS\", \"tooltip\": \"$TOOLTIP\"}"

