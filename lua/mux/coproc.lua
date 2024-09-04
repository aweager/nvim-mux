local M = {}

function M.start_coproc(mux_socket, log_file)
    M.socket = mux_socket

    if vim.env.MUX_INSTANCE and vim.env.MUX_LOCATION then
        M.parent_mux = {
            instance = vim.env.MUX_INSTANCE,
            location = vim.env.MUX_LOCATION,
        }
    end
    if vim.env.REG_INSTANCE and vim.env.REG_REGISTRY then
        M.parent_reg = {
            instance = vim.env.REG_INSTANCE,
            registry = vim.env.REG_REGISTRY,
        }
    end

    M.log_file = log_file

    local nvim_pid = vim.fn.getpid()
    local host = vim.fn.hostname()
    vim.env.MUX_INSTANCE = string.format("mux@nvim.%s@%s", nvim_pid, host)
    vim.env.MUX_LOCATION = nil
    vim.env.MUX_TYPE = "nvim"

    vim.env.REG_INSTANCE = string.format("reg@nvim.%s@%s", nvim_pid, host)
    vim.env.REG_REGISTRY = "0"
    vim.env.REG_TYPE = "nvim"

    local cmd = {
        "python3",
        "-m",
        "nvim_mux.nvim_mux_server",
        mux_socket,
        vim.env.MUX_INSTANCE,
        vim.env.REG_INSTANCE,
        log_file,
        vim.env.JRPC_ROUTER_SOCKET or "",
    }

    if M.parent_mux then
        table.insert(cmd, M.parent_mux.instance)
        table.insert(cmd, M.parent_mux.location)
    else
        table.insert(cmd, "")
        table.insert(cmd, "")
    end

    if M.parent_reg then
        table.insert(cmd, M.parent_reg.instance)
        table.insert(cmd, M.parent_reg.registry)
    else
        table.insert(cmd, "")
        table.insert(cmd, "")
    end

    M.coproc_handle = vim.system(cmd, {})

    return M.coproc_handle
end

---Sends JSON RPC notifications to the mux server
---@param notifications { method: string, params_json: string }[]
function M.notify(notifications)
    local pipe = vim.uv.new_pipe()
    pipe:connect(M.socket, function(err)
        if err then
            vim.print("Failed to connect to mux server: " .. err)
            return
        end

        local text = ""
        for _, notification in pairs(notifications) do
            text = text
                .. string.format(
                    '{ "jsonrpc": "2.0", "method": "%s", "params": %s }\n',
                    notification.method,
                    notification.params_json
                )
        end

        pipe:write(text, function(write_error)
            if write_error then
                vim.print("Failed to send notifications to mux server: " .. err)
            end
            pipe:close()
        end)
    end)
end

return M
