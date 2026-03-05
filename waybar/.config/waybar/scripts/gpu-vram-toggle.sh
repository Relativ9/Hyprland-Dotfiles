#!/bin/bash
STATE="/tmp/waybar_gpu_vram_expanded"
[ "$1" = "toggle" ] && { [ -f "$STATE" ] && rm "$STATE" || touch "$STATE"; exit; }

if [ -f "$STATE" ]; then
    NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 | cut -d' ' -f1-2)
    TOP3=$(ps -eo comm:10,pmem --sort=-pmem | head -4 | tail -3 | awk '{print $1}' | tr '\n' ' ')
    echo "{\"text\": \"${NAME} | ${TOP3}\", \"class\": \"expanded\"}"
else
    read -r TOTAL USED <<< $(nvidia-smi --query-gpu=memory.total,memory.used --format=csv,noheader,nounits | head -1 | tr ',' ' ')
    PCT=$((USED * 100 / TOTAL))
    echo "{\"text\": \"  ${PCT}%\", \"class\": \"compact\"}"
fi

