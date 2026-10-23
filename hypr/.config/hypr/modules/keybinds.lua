-- Keybinds module (was modules/keybinds.conf)
-- require() scopes are isolated, so mainMod is local here.

local mainMod = "SUPER"

-- ------------------------------------------------------------------------------
-- 1. WORKSPACE: Navigation
-- ------------------------------------------------------------------------------

-- CENTER MONITOR (1-5) -> SUPER + 1-5
hl.bind("SUPER + 1", hl.dsp.focus({ workspace = 1 }))
hl.bind("SUPER + 2", hl.dsp.focus({ workspace = 2 }))
hl.bind("SUPER + 3", hl.dsp.focus({ workspace = 3 }))
hl.bind("SUPER + 4", hl.dsp.focus({ workspace = 4 }))
hl.bind("SUPER + 5", hl.dsp.focus({ workspace = 5 }))

-- LEFT MONITOR (11-13) -> SUPER + CTRL + 1-3
hl.bind("SUPER + CTRL + 1", hl.dsp.focus({ workspace = 11 }))
hl.bind("SUPER + CTRL + 2", hl.dsp.focus({ workspace = 12 }))
hl.bind("SUPER + CTRL + 3", hl.dsp.focus({ workspace = 13 }))

-- RIGHT MONITOR (21-23) -> SUPER + ALT + 1-3
hl.bind("SUPER + ALT + 1", hl.dsp.focus({ workspace = 21 }))
hl.bind("SUPER + ALT + 2", hl.dsp.focus({ workspace = 22 }))
hl.bind("SUPER + ALT + 3", hl.dsp.focus({ workspace = 23 }))

-- Scroll through existing workspaces with mainMod + scroll
hl.bind(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }))
hl.bind(mainMod .. " + mouse_up", hl.dsp.focus({ workspace = "e-1" }))

-- Move/resize windows with mainMod + LMB/RMB and dragging
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Move focus with mainMod + arrow keys
hl.bind(mainMod .. " + left", hl.dsp.focus({ direction = "left" }))
hl.bind(mainMod .. " + right", hl.dsp.focus({ direction = "right" }))
hl.bind(mainMod .. " + up", hl.dsp.focus({ direction = "up" }))
hl.bind(mainMod .. " + down", hl.dsp.focus({ direction = "down" }))

-- ------------------------------------------------------------------------------
-- 2. WORKSPACE: Moving Windows
-- ------------------------------------------------------------------------------

-- CENTER (SUPER + SHIFT + 1-5)
hl.bind("SUPER + SHIFT + 1", hl.dsp.window.move({ workspace = 1 }))
hl.bind("SUPER + SHIFT + 2", hl.dsp.window.move({ workspace = 2 }))
hl.bind("SUPER + SHIFT + 3", hl.dsp.window.move({ workspace = 3 }))
hl.bind("SUPER + SHIFT + 4", hl.dsp.window.move({ workspace = 4 }))
hl.bind("SUPER + SHIFT + 5", hl.dsp.window.move({ workspace = 5 }))

-- LEFT (SUPER + CTRL + SHIFT + 1-3)
hl.bind("SUPER + CTRL + SHIFT + 1", hl.dsp.window.move({ workspace = 11 }))
hl.bind("SUPER + CTRL + SHIFT + 2", hl.dsp.window.move({ workspace = 12 }))
hl.bind("SUPER + CTRL + SHIFT + 3", hl.dsp.window.move({ workspace = 13 }))

-- RIGHT (SUPER + ALT + SHIFT + 1-3)
hl.bind("SUPER + ALT + SHIFT + 1", hl.dsp.window.move({ workspace = 21 }))
hl.bind("SUPER + ALT + SHIFT + 2", hl.dsp.window.move({ workspace = 22 }))
hl.bind("SUPER + ALT + SHIFT + 3", hl.dsp.window.move({ workspace = 23 }))

-- ------------------------------------------------------------------------------
-- 3. WORKSPACE: Special Workspaces (Scratchpads)
-- ------------------------------------------------------------------------------

local scratch = os.getenv("HOME") .. "/.config/hypr/scripts/dynamic-scratchpad.sh"
hl.bind(mainMod .. " + S", hl.dsp.workspace.toggle_special("S"))
hl.bind(mainMod .. " + SHIFT + S", hl.dsp.exec_cmd(scratch .. " move"))

-- ------------------------------------------------------------------------------
-- 4. Tools: Hyprshot
-- ------------------------------------------------------------------------------


-- ------------------------------------------------------------------------------
-- 5. Tools: Media Keys
-- ------------------------------------------------------------------------------

hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { locked = true })
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("pactl set-sink-volume @DEFAULT_SINK@ +2%"), { locked = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("pactl set-sink-volume @DEFAULT_SINK@ -2%"), { locked = true })

-- ------------------------------------------------------------------------------
-- 6. Apps: Zen Browser
-- ------------------------------------------------------------------------------

hl.bind(mainMod .. " + Z", hl.dsp.exec_cmd("zen-browser"))

-- ------------------------------------------------------------------------------
-- 7. Dashboard / Theme / Wallpaper / Lock / Clipboard / Notifications
--    (all keys checked against existing binds: W is waybar restart, so wallpaper = B)
-- ------------------------------------------------------------------------------

local scripts = os.getenv("HOME") .. "/.config/hypr/scripts/"
local themes = os.getenv("HOME") .. "/.config/themes/theme-switch.sh"

hl.bind(mainMod .. " + D", hl.dsp.exec_cmd(scripts .. "dashboard.sh"))          -- dashboard
hl.bind(mainMod .. " + T", hl.dsp.exec_cmd(themes .. " pick"))                   -- theme picker
hl.bind(mainMod .. " + SHIFT + T", hl.dsp.exec_cmd(themes .. " cycle"))          -- next theme
hl.bind(mainMod .. " + B", hl.dsp.exec_cmd(scripts .. "wallpaper-pick.sh span")) -- wallpaper across all monitors
hl.bind(mainMod .. " + SHIFT + B", hl.dsp.exec_cmd(scripts .. "wallpaper-pick.sh same")) -- same wallpaper per monitor
hl.bind(mainMod .. " + L", hl.dsp.exec_cmd(scripts .. "lock.sh"))                    -- lock
hl.bind(mainMod .. " + X", hl.dsp.exec_cmd(scripts .. "clipboard.sh"))           -- clipboard history
hl.bind(mainMod .. " + SHIFT + X", hl.dsp.exec_cmd(scripts .. "clipboard.sh wipe"))
hl.bind(mainMod .. " + N", hl.dsp.exec_cmd("swaync-client -t -sw"))              -- notification center
hl.bind(mainMod .. " + SHIFT + N", hl.dsp.exec_cmd(scripts .. "nightlight.sh toggle")) -- night light (wlsunset)

-- ------------------------------------------------------------------------------
-- 8. Screenshots with annotation (satty). Super+Print / Super+Shift+Print now open the editor.
-- ------------------------------------------------------------------------------

hl.bind(mainMod .. " + Print", hl.dsp.exec_cmd(scripts .. "screenshot.sh window"))
hl.bind(mainMod .. " + SHIFT + Print", hl.dsp.exec_cmd(scripts .. "screenshot.sh region"))
hl.bind(mainMod .. " + CTRL + Print", hl.dsp.exec_cmd(scripts .. "screenshot.sh quick-region")) -- no editor
hl.bind(mainMod .. " + ALT + Print", hl.dsp.exec_cmd(scripts .. "screenshot.sh output"))

-- ------------------------------------------------------------------------------
-- 9. Window management
-- ------------------------------------------------------------------------------

hl.bind(mainMod .. " + SHIFT + P", hl.dsp.window.pin({ action = "toggle" }))
-- Move window to the neighbouring monitor
hl.bind(mainMod .. " + SHIFT + left", hl.dsp.window.move({ monitor = "l" }))
hl.bind(mainMod .. " + SHIFT + right", hl.dsp.window.move({ monitor = "r" }))
-- Swap windows
hl.bind(mainMod .. " + CTRL + left", hl.dsp.window.swap({ direction = "left" }))
hl.bind(mainMod .. " + CTRL + right", hl.dsp.window.swap({ direction = "right" }))
hl.bind(mainMod .. " + CTRL + up", hl.dsp.window.swap({ direction = "up" }))
hl.bind(mainMod .. " + CTRL + down", hl.dsp.window.swap({ direction = "down" }))

-- Resize mode: Super+Shift+R, arrows to resize, Esc/Enter to leave
hl.bind(mainMod .. " + SHIFT + R", hl.dsp.submap("resize"))
hl.define_submap("resize", function()
    hl.bind("right", hl.dsp.window.resize({ x = 40, y = 0, relative = true }), { repeating = true })
    hl.bind("left", hl.dsp.window.resize({ x = -40, y = 0, relative = true }), { repeating = true })
    hl.bind("up", hl.dsp.window.resize({ x = 0, y = -40, relative = true }), { repeating = true })
    hl.bind("down", hl.dsp.window.resize({ x = 0, y = 40, relative = true }), { repeating = true })
    hl.bind("escape", hl.dsp.submap("reset"))
    hl.bind("return", hl.dsp.submap("reset"))
end)

-- ------------------------------------------------------------------------------
-- 10. More media keys
-- ------------------------------------------------------------------------------

hl.bind("XF86AudioMute", hl.dsp.exec_cmd("pactl set-sink-mute @DEFAULT_SINK@ toggle"), { locked = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("pactl set-source-mute @DEFAULT_SOURCE@ toggle"), { locked = true })

