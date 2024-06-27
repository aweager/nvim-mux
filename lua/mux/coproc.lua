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
	local out = vim.uv.new_pipe(false)
	local data = ""
	out:read_start(function(err, chunk)
		if err then
			vim.print("Error starting mux server: " .. err)
			out:read_stop()
			out:close()
		elseif chunk then
			data = data .. chunk
		else
			out:read_stop()
			out:close()
			vim.schedule(function()
				-- TODO: this never seems to execute?
				M.pid = tonumber(data)
				M.socket = mux_socket
			end)
		end
	end)

	local handle
	handle = vim.uv.spawn(bin .. "/start-nvim-mux", {
		args = {
			ipc_socket,
			log_file,
			M.parent_mux_socket,
		},
		stdio = { nil, out, nil },
		function(code, signal)
			assert(handle):close()
		end,
	})

	return function()
		vim.uv.fs_unlink(log_file)
		vim.uv.spawn(bin .. "/term-nvim-mux", {
			detached = true,
		})
	end
end

return M
