#!/bin/bash
STATE="/tmp/waybar_gpu_core_expanded"
[ "$1" = "toggle" ] && { [ -f "$STATE" ] && rm "$STATE" || touch "$STATE"; exit; }

if [ -f "$STATE" ]; then
    # 1. Get full GPU model (remove "NVIDIA ", keep "GeForce RTX ..." or "Quadro ..." etc)
    NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 | sed 's/NVIDIA //')
    
    # 2. Get top GPU process by utilization with a robust parser
    # Format:  gpu_id pid type sm% mem% enc% dec% command...
    # We want: command and sm% (field 4)
    TOP_PROC=$(nvidia-smi pmon -c 1 -s um 2>/dev/null | \
        awk '/^ [0-9]/ {
            # Reconstruct command from field 8 onwards (handles spaces in names)
            cmd=$8; for(i=9;i<=NF;i++)cmd=cmd" "$i; 
            # Print SM% and command, then exit (top line is highest due to nvidia-smi ordering)
            printf "%s %.f%%", cmd, $4; 
            exit
        }')
    
    # Fallback if nvidia-smi pmon fails or returns empty
    if [ -z "$TOP_PROC" ]; then
        # Fallback to query-compute-apps (shows processes but not %, so we add the global %)
        GLOBAL_PCT=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1)
        TOP_PID=$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader | head -1 | cut -d',' -f1)
        if [ -n "$TOP_PID" ]; then
            PROC=$(ps -p "$TOP_PID" -o comm= 2>/dev/null | head -c10)
            [ -z "$PROC" ] && PROC="GPU"
            TOP_PROC="${PROC} ${GLOBAL_PCT}%"
        else
            TOP_PROC="Idle 0%"
        fi
    fi
    
    # 3. Limit process name length if too long (keep max 10 chars before the %)
    TOP_PROC=$(echo "$TOP_PROC" | awk '{match($0, /[^ ]+ %/); name=substr($0,1,RSTART-1); pct=substr($0,RSTART); if(length(name)>10) name=substr(name,1,10); printf "%s%s", name, pct}')
    
    echo "{\"text\": \"${NAME} | ${TOP_PROC}\", \"class\": \"expanded\"}"
else
    COMPACT=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1 | xargs)
    echo "{\"text\": \"  ${COMPACT}%\", \"class\": \"compact\"}"
fi

