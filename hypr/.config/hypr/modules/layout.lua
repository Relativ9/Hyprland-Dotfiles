-- Layout config (was modules/layout.conf)

hl.config({
    general = {
        gaps_in = 5,
        gaps_out = 20,
        col = {
            active_border = { colors = { "rgba(b7bdf8ee)", "rgba(eed49faa)" }, angle = 45 },
            inactive_border = "rgba(595959aa)",
        },
        resize_on_border = true,
        layout = "dwindle",
    },
    dwindle = {
        force_split = 2,
        preserve_split = true,
        smart_split = false,
        default_split_ratio = 0.8,
    },
})
