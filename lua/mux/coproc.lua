local M = {}

local function command_server_dir()
    local this_file = debug.getinfo(2, "S").source:sub(2):match("(.*/)")
    return this_file .. "/../../command-server"
end

function M.start_coproc(mux_socket, ipc_socket, log_file)
    M.parent_mux_socket = vim.env.MUX_SOCKET or ""
    M.parent_mux_location = vim.env.MUX_LOCATION or ""
    vim.env.MUX_SOCKET = mux_socket
    vim.env.MUX_LOCATION = nil
    vim.env.MUX_TYPE = "nvim"

    local bin = command_server_dir()
    local pid = ""
    vim.system({
        bin .. "/start-nvim-mux",
        ipc_socket,
        log_file,
        M.parent_mux_socket,
    }, {
        stdout = function(err, data)
            if err then
                vim.print("Error starting mux server: " .. err)
            elseif data then
                pid = pid .. data
            end
        end,
    }):wait()

    M.pid = tonumber(pid)
    M.socket = mux_socket

    return function()
        vim.uv.fs_unlink(log_file)
        vim.uv.spawn(bin .. "/term-nvim-mux", {
            detached = true,
        })
    end
end

return M
