local M = {}

local function prep_files()
    local pid = vim.fn.getpid()
    M.rundir = vim.fn.stdpath("run") .. "/mux"
    M.logdir = vim.fn.stdpath("log") .. "/mux"

    -- TODO use uv
    os.execute("mkdir -p '" .. M.rundir .. "'")
    os.execute("chmod 1700 '" .. M.rundir .. "'")
    os.execute("mkdir -p '" .. M.logdir .. "'")

    M.mux_socket = M.rundir .. "/" .. pid .. ".nvim.mux.sock"
    M.coproc_log = M.logdir .. "/" .. pid .. ".nvim.mux.server.log"
end

function M.setup()
    prep_files()

    local handle = require("mux.coproc").start_coproc(M.mux_socket, M.coproc_log)

    if handle ~= nil then
        local augroup = vim.api.nvim_create_augroup("MuxApi", {})
        local api = require("mux.api")
        local internal_reg_api = require("mux.api.internal.reg")
        local types = require("mux.types")

        vim.api.nvim_create_autocmd("WinEnter", {
            group = augroup,
            callback = api.publish,
        })
        vim.api.nvim_create_autocmd("BufWinEnter", {
            group = augroup,
            callback = api.publish,
        })
        vim.api.nvim_create_autocmd("BufModifiedSet", {
            group = augroup,
            callback = api.publish,
        })

        vim.api.nvim_create_autocmd("TextYankPost", {
            group = augroup,
            callback = function()
                local regname = types.regname_from_vim_name(vim.v.event.regname)
                if regname then
                    internal_reg_api.publish_sync(regname)
                end
            end,
        })

        vim.api.nvim_create_autocmd("VimEnter", {
            group = augroup,
            callback = function()
                vim.defer_fn(api.publish, 100)
            end,
        })
        vim.api.nvim_create_autocmd("VimLeave", {
            group = augroup,
            callback = function()
                ---@diagnostic disable-next-line: missing-parameter # this is the correct way to call
                handle:kill()
            end,
        })
    end
end

return M
