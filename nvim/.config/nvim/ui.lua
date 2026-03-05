return {
  -- Theme: Catppuccin
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000, -- Load first
    config = function()
      require("catppuccin").setup({
        flavour = "mocha", -- Options: latte, frappe, macchiato, mocha
        transparent_background = true, -- MUST HAVE #3: Transparency
        integrations = {
          telescope = true,
          nvimtree = true,
          lsp_trouble = true,
          indent_blankline = { enabled = true },
        },
      })
      vim.cmd.colorscheme("catppuccin")
    end,
  },

  -- File Explorer (VS Code Sidebar)
  {
    "nvim-tree/nvim-tree.lua",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("nvim-tree").setup({
        view = { side = "left", width = 30 },
        renderer = {
          group_empty = true,
          icons = { show = { git = true, folder = true, file = true } },
        },
      })
      -- Keybind to toggle: Leader + e
      vim.keymap.set("n", "<leader>e", "<cmd>NvimTreeToggle<cr>", { desc = "Toggle File Explorer" })
    end,
  },

  -- Indent Guides (Visual structure)
  {
    "lukas-reineke/indent-blankline.nvim",
    main = "ibl",
    opts = {
      indent = { char = "│" },
      scope = { enabled = false },
    },
  },
}

