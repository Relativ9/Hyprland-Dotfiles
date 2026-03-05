-- This file is now the entry point. 
-- Since it lives INSIDE the 'lua' folder, the path is already resolved.

-- Load your modules relative to this folder
require("config.options")
require("config.keymaps")
require("config.lazy")

-- Custom keybinds -- 

vim.g.mapleader = " "

-- Usage: Space + w
-- Behavior: Writes the file. If you want to quit after, you press Space + q next.
vim.keymap.set("n", "<leader>w", ":write<CR>", { desc = "Save file (write)" })

-- Usage: Space + q
-- Behavior: Quits immediately, discarding ALL unsaved changes without prompting.
-- This replaces your need for a separate 'normal quit' bind.
vim.keymap.set("n", "<leader>q", ":quit!<CR>", { desc = "Force quit (discard changes)" })

-- Usage: Space + x (or Space + s)
-- Behavior: Saves AND quits in one go. 
-- Useful if you realize halfway through typing <leader>w that you actually wanted to leave.
vim.keymap.set("n", "<leader>x", ":x<CR>", { desc = "Save and quit" })

