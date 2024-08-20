local M = {}

function M.start_coproc(mux_socket, log_file)
    M.parent_mux_instance = vim.env.MUX_SOCKET
    M.parent_mux_location = vim.env.MUX_LOCATION
    M.log_file = log_file

    vim.env.MUX_SOCKET = mux_socket
    vim.env.MUX_LOCATION = nil
    vim.env.MUX_TYPE = "nvim"

    local cmd = { "python3", "-m", "nvim_mux.nvim_mux_server", mux_socket, log_file }
    if M.parent_mux_location then
        table.insert(cmd, M.parent_mux_instance)
        table.insert(cmd, M.parent_mux_location)
    end

    M.coproc_handle = vim.system(cmd, {})

    return M.coproc_handle
end

return M
