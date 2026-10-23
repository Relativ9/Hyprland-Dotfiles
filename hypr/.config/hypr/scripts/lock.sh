#!/bin/bash
# Lock the screen. Used by Super+L, hypridle (lock_cmd) and wlogout.
# Never starts a second hyprlock, and does nothing if one is already running.
pidof hyprlock >/dev/null && exit 0
exec hyprlock
