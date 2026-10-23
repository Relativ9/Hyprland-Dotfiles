-- Window / layer rules and the dashboard workspace.

-- ---------------------------------------------------------------------------
-- Dashboard (Super+D): tiles are floating and placed by scripts/dashboard.sh
-- ---------------------------------------------------------------------------
hl.window_rule({
    name = "dashboard-tiles",
    match = { class = "^(dash-.*)$" },
    float = true,
    no_initial_focus = true,
})

-- ---------------------------------------------------------------------------
-- Floating helpers: dialogs, pickers, utilities
-- ---------------------------------------------------------------------------
local function float_center(name, match, w, h)
    hl.window_rule({
        name = name,
        match = match,
        float = true,
        center = true,
        size = { w, h },
    })
end

float_center("float-pavucontrol", { class = "^(org.pulseaudio.pavucontrol)$" }, 900, 600)
float_center("float-blueman", { class = "^(\\.blueman-manager-wrapped|blueman-manager)$" }, 700, 500)
float_center("float-nmconn", { class = "^(nm-connection-editor)$" }, 800, 600)
float_center("float-polkit", { class = "^(hyprpolkitagent|org.kde.polkit-kde-authentication-agent-1)$" }, 500, 250)
float_center("float-kcalc", { class = "^(org.kde.kcalc)$" }, 400, 550)
float_center("float-floatterm", { class = "^(floatterm)$" }, 1100, 700)
float_center("float-satty", { class = "^(com.gabm.satty|org.satty.satty)$" }, 1400, 900)

-- File pickers / save dialogs
hl.window_rule({
    name = "float-file-dialogs",
    match = { title = "^(Open File|Save File|Save As|Open Folder|Choose .*|Select .*)$" },
    float = true,
    center = true,
    size = { 1000, 650 },
})

-- Picture-in-picture: float, pin, bottom-right, no focus stealing
hl.window_rule({
    name = "pip",
    match = { title = "^(Picture-in-Picture|Picture in picture)$" },
    float = true,
    pin = true,
    size = { 480, 270 },
    move = { "monitor_w - 500", "monitor_h - 290" },
    no_initial_focus = true,
})

-- ---------------------------------------------------------------------------
-- Idle inhibit: never lock/blank while watching video or in fullscreen
-- ---------------------------------------------------------------------------
hl.window_rule({
    name = "idle-inhibit-fullscreen",
    match = { fullscreen = true },
    idle_inhibit = "fullscreen",
})
hl.window_rule({
    name = "idle-inhibit-vlc",
    match = { class = "^(vlc)$" },
    idle_inhibit = "focus",
})

-- ---------------------------------------------------------------------------
-- Games (Steam): no blur/shadow/animation overhead, never dim
-- ---------------------------------------------------------------------------
hl.window_rule({
    name = "steam-games",
    match = { class = "^(steam_app_.*)$" },
    idle_inhibit = "fullscreen",
    no_blur = true,
    no_shadow = true,
})

-- ---------------------------------------------------------------------------
-- Layer rules: blur the shell surfaces
-- ---------------------------------------------------------------------------
hl.layer_rule({ name = "blur-rofi", match = { namespace = "^rofi$" }, blur = true, ignore_alpha = 0.3 })
hl.layer_rule({ name = "blur-swaync", match = { namespace = "^swaync-control-center$" }, blur = true, ignore_alpha = 0.3 })
hl.layer_rule({ name = "blur-swaync-notifs", match = { namespace = "^swaync-notification-window$" }, blur = true, ignore_alpha = 0.3 })
hl.layer_rule({ name = "blur-logout", match = { namespace = "^logout_dialog$" }, blur = true, ignore_alpha = 0.3 })
