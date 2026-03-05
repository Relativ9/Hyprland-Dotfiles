return {
  -- =============================================================================
  -- 1. Catppuccin Theme
  -- =============================================================================
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000, -- Ensure this loads first
    config = function()
      require("catppuccin").setup({
        flavour = "macchiato",          -- The dark theme variant you requested
        transparent_background = true,  -- Match your Hyprland transparency
        dim_inactive = {
          enabled = false,
        },
        integrations = {
          telescope = true,
          nvimtree = true,
          indent_blankline = {
            enabled = true,
            scope_enabled = false,
          },
          -- Add more integrations here as you install plugins (e.g., mason, lightspeed)
        },
        -- Custom Highlights to fix line number readability
        custom_highlights = function(colors)
          return {
            -- Non-active line numbers (Above/Below cursor)
            -- Using Macchiato 'Subtext0' (#B8C0E0) for high contrast
            LineNr = {
              fg = "#B8C0E0",
              bold = true,
            },
            -- Optional: Explicitly set Above/Below if they behave differently
            LineNrAbove = {
              fg = "#B8C0E0",
              bold = true,
            },
            LineNrBelow = {
              fg = "#B8C0E0",
              bold = true,
            },
            -- Active line number (where cursor is)
            -- Using Macchiato 'Rosewater' (#F4DBD6) for a soft highlight
            CursorLineNr = {
              fg = "#F4DBD6",
              bold = true,
            },
          }
        end,
      })

      -- Apply the colorscheme
      vim.cmd.colorscheme("catppuccin")
    end,
  },

  -- =============================================================================
  -- 2. Nvim-Tree (File Explorer Sidebar)
  -- =============================================================================
  {
    "nvim-tree/nvim-tree.lua",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      local nvimtree = require("nvim-tree")

      nvimtree.setup({
        view = {
          side = "left",
          width = 30,
          preserve_window_proportions = true,
        },
        renderer = {
          group_empty = true,      -- Compact empty folders
          icons = {
            show = {
              git = true,
              folder = true,
              file = true,
            },
          },
        },
        filters = {
          dotfiles = false,        -- Show hidden files (like .config)
        },
      })

      -- Keymap: Toggle Explorer
      vim.keymap.set("n", "<leader>e", "<cmd>NvimTreeToggle<cr>", {
        desc = "Toggle File Explorer",
      })
    end,
  },

  -- =============================================================================
  -- 3. Indent Blankline (Visual Guides)
  -- =============================================================================
  {
    "lukas-reineke/indent-blankline.nvim",
    main = "ibl",
    opts = {
      indent = {
        char = "│",                -- The vertical bar character
        tab_char = "│",
      },
      scope = {
        enabled = false,           -- Disabled scope highlight for a cleaner look
      },
      exclude = {
        filetypes = {
          "help",
          "dashboard",
          "alpha",
        },
      },
    },
  },
}

