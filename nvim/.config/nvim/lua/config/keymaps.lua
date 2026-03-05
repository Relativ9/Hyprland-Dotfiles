-- ~/.config/nvim/lua/config/keymaps.lua

local map = vim.keymap.set

-- Set leader key to Space
vim.g.mapleader = " "
vim.g.maplocalleader = " "

-- 1. Undo/Redo
-- 'u' is undo, Ctrl+R is redo (Standard Vim)
-- Map Ctrl+Z in insert mode to undo (VS Code style)
map("i", "<C-z>", "<Esc>ua", { desc = "Undo in Insert Mode" })

-- 2. Better Window Navigation
map("n", "<C-h>", "<C-w>h", { desc = "Go to left window" })
map("n", "<C-j>", "<C-w>j", { desc = "Go to lower window" })
map("n", "<C-k>", "<C-w>k", { desc = "Go to upper window" })
map("n", "<C-l>", "<C-w>l", { desc = "Go to right window" })

-- 3. Reload Config Helper
map("n", "<leader>sr", function()
  vim.cmd("so $MYVIMRC")
  vim.notify("Configuration reloaded!", vim.log.levels.INFO)
end, { desc = "[S]ource [R]eload Config" })

