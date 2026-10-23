# ~/.config/hypr/scripts/start-swww.sh
#!/bin/bash

# Wait for Wayland socket to be ready
for i in {1..30}; do
    if [ -n "$WAYLAND_DISPLAY" ] && [ -S "/run/user/$(id -u)/wayland-1" ]; then
        break
    fi
    sleep 0.5
done

# Extra buffer
sleep 2

# Kill any stale daemon
killall swww-daemon 2>/dev/null
sleep 1

# Start with init flag
swww-daemon --init

# Keep it running (swww-daemon should daemonize itself, but this ensures it)
exec swww-daemon
