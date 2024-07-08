local M = {}

local dispatch = require("mux.dispatch")

local function dispatch_request(request)
	local newline_ind = string.find(request, "\n", 1, true)
	if not newline_ind then
		return 2
	end

	local verb = string.sub(request, 1, newline_ind - 1)
	if not dispatch[verb] then
		return 2
	end

	return dispatch[verb](string.sub(request, newline_ind + 1))
end

local function prep_files()
	local pid = vim.fn.getpid()
	M.rundir = vim.fn.stdpath("run") .. "/nvim/mux"
	M.logdir = vim.fn.stdpath("log") .. "/mux"

	-- TODO use uv
	os.execute("mkdir -p '" .. M.rundir .. "'")
	os.execute("chmod 1700 '" .. M.rundir .. "'")
	os.execute("mkdir -p '" .. M.logdir .. "'")

	M.mux_socket = M.rundir .. "/" .. pid .. ".mux.sock"
	M.ipc_socket = M.rundir .. "/" .. pid .. ".ipc.sock"
	M.coproc_log = M.logdir .. "/" .. pid .. ".server.log"
end

function M.setup()
	prep_files()

	local ipc_close = require("mux.ipc").start_server(M.ipc_socket, dispatch_request)
	if not ipc_close then
		return
	end

	local coproc_close = require("mux.coproc").start_coproc(M.mux_socket, M.ipc_socket, M.coproc_log)
	if not coproc_close then
		ipc_close()
		return
	end

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

	-- Bring down server when vim is closed
	vim.api.nvim_create_autocmd("VimLeave", {
		group = augroup,
		callback = function()
			coproc_close()
			ipc_close()
		end,
	})
end

return M
