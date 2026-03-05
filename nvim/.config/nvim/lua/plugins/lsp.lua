return {
  "neovim/nvim-lspconfig",
  dependencies = {
    "williamboman/mason.nvim",
    "williamboman/mason-lspconfig.nvim",
    "hrsh7th/nvim-cmp",
    "hrsh7th/cmp-nvim-lsp",
    "L3MON4D3/LuaSnip",
    "saadparwaiz1/cmp_luasnip",
  },
  config = function()
    -- 1. Initialize Mason
    require("mason").setup()

    -- 2. Initialize Mason-LSPConfig
    local mason_lspconfig = require("mason-lspconfig")
    mason_lspconfig.setup({
      ensure_installed = { "lua_ls", "bashls", "pyright", "html", "cssls" },
    })

    -- 3. Capabilities & On Attach
    local capabilities = require("cmp_nvim_lsp").default_capabilities()
    local on_attach = function(client, bufnr)
      local nmap = function(keys, func, desc)
        if desc then desc = "LSP: " .. desc end
        vim.keymap.set("n", keys, func, { buffer = bufnr, desc = desc })
      end
      nmap("gd", vim.lsp.buf.definition, "[G]oto [D]efinition")
      nmap("gr", vim.lsp.buf.references, "[G]oto [R]eferences")
      nmap("K", vim.lsp.buf.hover, "Hover Docs")
      nmap("<leader>rn", vim.lsp.buf.rename, "[R]e[n]ame")
    end

    -- 4. Setup Handlers (Safe Check)
    -- If setup_handlers is still nil, we fallback to manual setup
    if mason_lspconfig.setup_handlers then
      mason_lspconfig.setup_handlers({
        function(server_name)
          require("lspconfig")[server_name].setup({
            capabilities = capabilities,
            on_attach = on_attach,
          })
        end,
      })
    else
      -- Fallback for very old versions (unlikely if updated, but safe)
      vim.notify("mason-lspconfig is outdated. Please run :Lazy sync mason-lspconfig.nvim", vim.log.levels.WARN)
    end

    -- 5. CMP Setup
    local cmp = require("cmp")
    cmp.setup({
      mapping = cmp.mapping.preset.insert({
        ["<C-b>"] = cmp.mapping.scroll_docs(-4),
        ["<C-f>"] = cmp.mapping.scroll_docs(4),
        ["<C-Space>"] = cmp.mapping.complete(),
        ["<C-e>"] = cmp.mapping.abort(),
        ["<CR>"] = cmp.mapping.confirm({ select = true }),
      }),
      sources = cmp.config.sources({ { name = "nvim_lsp" } }),
    })
  end,
}

