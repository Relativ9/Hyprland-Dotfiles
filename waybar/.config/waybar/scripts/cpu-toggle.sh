#!/bin/bash
STATE="/tmp/waybar_cpu_expanded"
[ "$1" = "toggle" ] && { [ -f "$STATE" ] && rm "$STATE" || touch "$STATE"; exit; }

if [ -f "$STATE" ]; then
    # EXPANDED VIEW: CPU Name + Avg Clock + Top Process
    CPU=$(grep "model name" /proc/cpuinfo | head -1 | cut -d':' -f2 | xargs | cut -d' ' -f1-3)
    
    # Average clock speed (convert MHz to GHz, 1 decimal)
    AVG_MHZ=$(awk '/cpu MHz/ {sum+=$4; count++} END {printf "%.0f", sum/count}' /proc/cpuinfo 2>/dev/null || echo "0")
    AVG_GHZ=$(awk "BEGIN {printf \"%.1f\", $AVG_MHZ/1000}")
    
    # Top 1 process only (truncate to 10 chars, show 0 decimal places for %)
    TOP1=$(ps -eo comm:10,pcpu --sort=-pcpu | head -2 | tail -1 | awk '{printf "%s %.0f%%", $1, $2}')
    
    echo "{\"text\": \"$CPU ${AVG_GHZ}GHz | $TOP1\", \"class\": \"expanded\", \"tooltip\": \"Click to collapse\"}"
else
    # COMPACT VIEW: Proper CPU usage calculation
    # Read first snapshot
    read -r CPU_USER1 CPU_NICE1 CPU_SYSTEM1 CPU_IDLE1 CPU_IOWAIT1 CPU_IRQ1 CPU_SOFTIRQ1 CPU_STEAL1 < <(awk '/^cpu / {print $2, $3, $4, $5, $6, $7, $8, $9}' /proc/stat)
    
    sleep 0.1
    
    # Read second snapshot  
    read -r CPU_USER2 CPU_NICE2 CPU_SYSTEM2 CPU_IDLE2 CPU_IOWAIT2 CPU_IRQ2 CPU_SOFTIRQ2 CPU_STEAL2 < <(awk '/^cpu / {print $2, $3, $4, $5, $6, $7, $8, $9}' /proc/stat)
    
    # Calculate deltas
    USER=$((CPU_USER2 - CPU_USER1))
    NICE=$((CPU_NICE2 - CPU_NICE1))
    SYSTEM=$((CPU_SYSTEM2 - CPU_SYSTEM1))
    IDLE=$((CPU_IDLE2 - CPU_IDLE1))
    IOWAIT=$((CPU_IOWAIT2 - CPU_IOWAIT1))
    IRQ=$((CPU_IRQ2 - CPU_IRQ1))
    SOFTIRQ=$((CPU_SOFTIRQ2 - CPU_SOFTIRQ1))
    STEAL=$((CPU_STEAL2 - CPU_STEAL1))
    
    # Total used and total time
    TOTAL_USED=$((USER + NICE + SYSTEM + IOWAIT + IRQ + SOFTIRQ + STEAL))
    TOTAL_TIME=$((TOTAL_USED + IDLE))
    
    # Calculate percentage (avoid division by zero)
    if [ "$TOTAL_TIME" -eq 0 ]; then
        USAGE=0
    else
        USAGE=$((100 * TOTAL_USED / TOTAL_TIME))
    fi
    
    echo "{\"text\": \"  ${USAGE}%\", \"class\": \"compact\", \"tooltip\": \"CPU: ${USAGE}%\"}"
fi

