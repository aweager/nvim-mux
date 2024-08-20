local M = {}

local function prep_files()
    local pid = vim.fn.getpid()
    M.rundir = vim.fn.stdpath("run") .. "/nvim/mux"
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

        vim.api.nvim_create_autocmd("WinEnter", {
            group = augroup,
            callback = api.publish,
        })
        vim.api.nvim_create_autocmd("BufWinEnter", {
            group = augroup,
            callback = api.publish,
        })
        vim.api.nvim_create_autocmd("VimLeave", {
            group = augroup,
            callback = function()
                handle:kill()
            end,
        })
    end
end

return M
