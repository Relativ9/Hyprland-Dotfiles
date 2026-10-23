-- Workspaces & monitor assignment (was modules/workspace.conf)

-- LEFT MONITOR (vertical) — workspaces 11-13
hl.workspace_rule({ workspace = "11", monitor = "HDMI-A-2", default = true, persistent = true })
hl.workspace_rule({ workspace = "12", monitor = "HDMI-A-2", default = true, persistent = true })
hl.workspace_rule({ workspace = "13", monitor = "HDMI-A-2", default = true, persistent = true })

-- CENTER MONITOR (main) — workspaces 1-5
hl.workspace_rule({ workspace = "1", monitor = "DP-3", default = true, persistent = true })
hl.workspace_rule({ workspace = "2", monitor = "DP-3", default = true, persistent = true })
hl.workspace_rule({ workspace = "3", monitor = "DP-3", default = true, persistent = true })
hl.workspace_rule({ workspace = "4", monitor = "DP-3", default = true, persistent = true })
hl.workspace_rule({ workspace = "5", monitor = "DP-3", default = true, persistent = true })

-- RIGHT MONITOR (vertical) — workspaces 21-23
hl.workspace_rule({ workspace = "21", monitor = "DP-2", default = true, persistent = true })
hl.workspace_rule({ workspace = "22", monitor = "DP-2", default = true, persistent = true })
hl.workspace_rule({ workspace = "23", monitor = "DP-2", default = true, persistent = true })

-- SPECIAL WORKSPACES (scratchpads)
hl.workspace_rule({
    workspace = "special:scratchpad",
    on_created_empty = "kitty --class floatterm",
})
hl.workspace_rule({
    workspace = "special:media",
    on_created_empty = "spotify",
})
hl.workspace_rule({
    workspace = "special:reference",
    on_created_empty = "firefox --new-window about:blank",
})
