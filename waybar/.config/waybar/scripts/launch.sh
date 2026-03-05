#!/bin/bash

# The line above tells the file that we're using bash to interpret what comes later on.

#killall -9 waybar
#killall -9 swaync
#waybar & disown
#swaync & disown

killall -9 waybar
killall -9 swaync
sleep 0.5

# Main monitor (full bar)
waybar -c ~/.config/waybar/config.jsonc -s ~/.config/waybar/style.css &

# Side monitors (workspaces only)
waybar -c ~/.config/waybar/config-side.jsonc -s ~/.config/waybar/style.css &

swaync &

