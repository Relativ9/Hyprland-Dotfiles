-- ~/.config/nvim/lua/config/options.lua

local opt = vim.opt

-- 1. Line Numbers (Must Have)
opt.number = true           -- Show absolute line numbers
opt.relativenumber = true   -- Show relative line numbers

-- 2. Undo Capability (Must Have)
opt.undofile = true         -- Enable persistent undo
opt.undolevels = 10000      -- High undo history

-- General Quality of Life
opt.expandtab = true        -- Convert tabs to spaces
opt.shiftwidth = 4          -- Indent width
opt.tabstop = 4             -- Tab width
opt.smartindent = true      -- Auto-indent new lines
opt.wrap = false            -- Don't wrap lines
opt.scrolloff = 8           -- Keep cursor away from edges
opt.cursorline = true       -- Highlight current line

-- Search behavior
opt.ignorecase = true       -- Ignore case when searching
opt.smartcase = true        -- Unless you use Capital letters
opt.hlsearch = false        -- Don't permanently highlight search results
opt.incsearch = true        -- Show matches as you type

-- Appearance (Crucial for Transparency)
opt.termguicolors = true    -- Enable true color support
opt.signcolumn = "yes"      -- Always show sign column
opt.background = "dark"     -- Default to dark mode


