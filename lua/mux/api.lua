local M = {}

local coproc = require("mux.coproc")

local function get_default_icon_color(buffer)
	if vim.bo[buffer].buftype == "terminal" then
		return "", "lightgreen"
	end

	local devicons = require("nvim-web-devicons")
	local icon, color = devicons.get_icon_color_by_filetype(vim.bo[buffer].filetype, { default = false })
	if icon ~= nil then
		return icon, color
	end

	local default_icon = devicons.get_default_icon()
	return default_icon.icon, default_icon.color
end

local function get_default_title(buffer)
	if vim.bo[buffer].buftype == "terminal" then
		return vim.b[buffer].term_title
	end

	local bufname = vim.api.nvim_buf_get_name(buffer)
	local basename = vim.fn.fnamemodify(bufname, ":t")
	if basename == nil or basename == "" then
		return "[No Name]"
	end
	return basename
end

local function get_default_title_style(buffer)
	if vim.bo[buffer].buftype == "terminal" then
		return "default"
	elseif vim.bo[buffer].modified then
		return "italic"
	else
		return "default"
	end
end

local function get_defaults(buffer)
	local icon, icon_color = get_default_icon_color(buffer)
	local title = get_default_title(buffer)
	local title_style = get_default_title_style(buffer)
	return {
		mux = {
			USER = {},
			INFO = {
				icon = icon,
				icon_color = icon_color,
				title = title,
				title_style = title_style,
			},
		},
	}
end

local function pid_to_buffer(pid)
	for _, buf in pairs(vim.api.nvim_list_bufs()) do
		if vim.b[buf].terminal_job_pid == pid then
			return buf
		end
	end
	return nil
end

local function parse_location(location)
	local colon_ind = string.find(location, ":")
	if colon_ind == nil then
		return nil
	end

	local scope = string.sub(location, 1, colon_ind - 1)
	local id = tonumber(string.sub(location, colon_ind + 1))
	if scope == nil or id == nil then
		return nil
	end

	if scope == "pid" then
		scope = "b"
		id = pid_to_buffer(id)
		if id == nil then
			return nil
		end
	end

	return scope, id
end

local function dict_at(location)
	local scope, id = parse_location(location)

	if scope == nil or id == nil then
		return nil
	end

	if scope == "s" then
		return vim.g
	elseif scope == "t" then
		if not vim.api.nvim_tabpage_is_valid(id) then
			return nil
		end
		return vim.t[id]
	elseif scope == "w" then
		if not vim.api.nvim_win_is_valid(id) then
			return nil
		end
		return vim.w[id]
	elseif scope == "b" then
		if not vim.api.nvim_buf_is_valid(id) then
			return nil
		end
		return vim.b[id]
	else
		return nil
	end
end

local function dicts_under(location)
	local scope, id = parse_location(location)

	if scope == nil or id == nil then
		return nil
	end

	if scope == "s" then
		return {
			vim.g,
			vim.t[0],
			vim.w[0],
			vim.b[0],
			get_defaults(0),
		}
	elseif scope == "t" then
		if not vim.api.nvim_tabpage_is_valid(id) then
			return nil
		end
		local window = vim.api.nvim_tabpage_get_win(id)
		local buffer = vim.api.nvim_win_get_buf(window)
		return {
			vim.t[id],
			vim.w[window],
			vim.b[buffer],
			get_defaults(buffer),
		}
	elseif scope == "w" then
		if not vim.api.nvim_win_is_valid(id) then
			return nil
		end
		local buffer = vim.api.nvim_win_get_buf(id)
		return {
			vim.w[id],
			vim.b[buffer],
			get_defaults(buffer),
		}
	elseif scope == "b" then
		if not vim.api.nvim_buf_is_valid(id) then
			return nil
		end
		return {
			vim.b[id],
			get_defaults(id),
		}
	else
		return nil
	end
end

local function coalesce(root, ...)
	local result = root or {}
	for _, segment in pairs({ ... }) do
		result = result[segment] or {}
	end
	return result
end

function M.get(location, namespace)
	local dict = dict_at(location)
	if dict == nil then
		return nil
	end

	return coalesce(location, namespace)
end

function M.get_info(location)
	return M.get(location, "INFO")
end

function M.resolve(location, namespace)
	local dicts = dicts_under(location)
	if dicts == nil then
		return nil
	end

	local result = {}
	for _, dict in ipairs(dicts) do
		local values = coalesce(dict.mux, namespace)
		for key, value in pairs(values) do
			if result[key] == nil then
				result[key] = value
			end
		end
	end

	return result
end

function M.resolve_info(location)
	return M.resolve(location, "INFO")
end

function M.set(location, namespace, values)
	local dict = dict_at(location)
	if dict == nil then
		return false
	end

	local mux = coalesce(dict.mux)
	mux[namespace] = values
	dict.mux = mux
	vim.cmd.redrawtabline()
	M.publish()
	return true
end

function M.set_info(location, values)
	return M.set(location, "INFO", values)
end

function M.merge(location, namespace, values)
	local dict = dict_at(location)
	if dict == nil then
		return false
	end

	local mux = dict.mux
	for key, value in pairs(values) do
		mux[namespace][key] = value
	end
	dict.mux = mux
	vim.cmd.redrawtabline()
	M.publish()
	return true
end

function M.merge_info(location, values)
	return M.merge(location, "INFO", values)
end

function M.publish()
	if coproc.parent_mux_socket then
		local handle
		handle = vim.uv.spawn("mux", {
			args = {
				"publish",
				"s:0",
				coproc.parent_mux_socket,
				coproc.parent_mux_location,
				"icon",
				"icon_color",
				"title",
				"title_style",
			},
		}, function(err, signal)
			if handle ~= nil then
				handle:close()
			end
		end)
	end
end

return M
