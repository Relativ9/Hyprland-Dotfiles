return {
  "nvim-telescope/telescope.nvim",
  dependencies = { 
    "nvim-lua/plenary.nvim",
    "nvim-telescope/telescope-file-browser.nvim", -- Add this dependency
  },
  config = function()
    local telescope = require("telescope")
    local actions = require("telescope.actions")

    -- Load the file_browser extension
    telescope.load_extension("file_browser")

    telescope.setup({
      defaults = {
        mappings = {
          i = { 
            ["<C-c>"] = actions.close,
            ["<C-a>"] = actions.select_all, -- Useful for bulk actions
          },
        },
        prompt_prefix = "   ",
        selection_caret = "  ",
        path_display = { "smart" },
        winblend = 10,
      },
      extensions = {
        file_browser = {
          theme = "dropdown",
          -- disables netrw and use telescope-file-browser in its place
          hijack_netrw = true, 
        },
      },
    })

    -- Keymaps
    vim.keymap.set("n", "<leader>ff", "<cmd>Telescope find_files<cr>", { desc = "Find Files" })
    vim.keymap.set("n", "<leader>fg", "<cmd>Telescope live_grep<cr>", { desc = "Grep Search" })
    
    -- NEW: File Browser Keymap
    vim.keymap.set("n", "<leader>fb", "<cmd>Telescope file_browser<cr>", { desc = "File Browser" })
  end,
}

