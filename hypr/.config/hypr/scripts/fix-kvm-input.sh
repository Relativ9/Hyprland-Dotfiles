# ~/.config/hypr/scripts/fix-kvm-input.sh
#!/bin/bash

# Wait for Hyprland to fully start
sleep 3

# Check if we have input devices
if ! hyprctl devices | grep -q "Keyboard"; then
    echo "No keyboard detected, reloading input..."
    # Try to trigger device re-detection
    udevadm trigger --subsystem-match=input --action=add
    sleep 2
    hyprctl reload
fi

# Monitor for input loss (optional - run in background)
# This can be added to your autostart
 
