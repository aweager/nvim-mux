local M = {}

local function dict_at(location)
	local scope = location[1]
	local id = tonumber(string.sub(location, 3))

	if id == nil then
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
	local scope = location[1]
	local id = tonumber(string.sub(location, 3))

	if id == nil then
		return nil
	end

	if scope == "s" then
		return { vim.g, vim.t, vim.w, vim.b }
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
		}
	elseif scope == "w" then
		if not vim.api.nvim_win_is_valid(id) then
			return nil
		end
		local buffer = vim.api.nvim_win_get_buf(id)
		return {
			vim.w[id],
			vim.b[buffer],
		}
	elseif scope == "b" then
		if not vim.api.nvim_buf_is_valid(id) then
			return nil
		end
		return { vim.b[id] }
	else
		return nil
	end
end

local function coalesce(root, ...)
	local result = root or {}
	for _, segment in pairs(arg) do
		result = result[segment] or {}
	end
	return result
end

local function get_lines(body)
	local result = {}
	for _, line in string.gmatch(body, "[^\n]") do
		table.insert(result, line)
	end
	return result
end

function M.get(body)
	local lines = get_lines(body)
	local namespace = lines[1]
	local location = lines[2]
	local keys = { unpack(lines, 3) }

	local dict = dict_at(location)
	if dict == nil then
		return 1
	end

	if #keys == 0 then
		return ""
	end

	local values = coalesce(dict.mux, namespace)
	local records = {}
	for _, key in pairs(keys) do
		if values[key] == nil then
			table.insert(records, key)
		else
			table.insert(records, key .. " " .. values[key])
		end
	end

	return table.concat(records, "\0") .. "\0"
end

function M.resolve(body)
	local lines = get_lines(body)
	local namespace = lines[1]
	local location = lines[2]
	local keys = { unpack(lines, 3) }

	local dicts = dicts_under(location)
	if dicts == nil then
		return 1
	end

	if #keys == 0 then
		return ""
	end

	local value_dicts = {}
	for _, dict in pairs(dicts) do
		value_dicts = coalesce(dict.mux, namespace)
	end

	local records = {}
	for _, key in pairs(keys) do
		local record = key .. " "
		for _, values in pairs(value_dicts) do
			if values[key] ~= nil then
				record = record .. values[key]
				break
			end
		end
		table.insert(records, record)
	end

	return table.concat(records, "\0") .. "\0"
end

function M.list(body)
	local lines = get_lines(body)
	local namespace = lines[1]
	local location = lines[2]

	local dict = dict_at(location)
	if dict == nil then
		return 1
	end

	local keys = {}
	for key, value in pairs(coalesce(dict.mux, namespace)) do
		if value ~= nil then
			table.insert(keys, key)
		end
	end

	return table.concat(keys, "\n") .. "\n"
end

function M.set(body)
	local lines = get_lines(body)
	local namespace = lines[1]
	local location = lines[2]

	local dict = dict_at(location)
	if dict == nil then
		return 1
	end

	local mux = coalesce(dict.mux)
	if mux[namespace] == nil then
		mux[namespace] = {}
	end

	for _, record in string.gmatch(lines[3], "[^\0]") do
		if not record then
			goto continue
		end

		local space_ind = string.find(record, " ")
		if space_ind ~= nil then
			local key = string.sub(record, 1, space_ind)
			local value = string.sub(record, space_ind + 1)
			mux[namespace][key] = value
		else
			mux[namespace][record] = nil
		end

		::continue::
	end

	dict.mux = mux
	return 0
end

function M.list_parents()
	local coproc = require("mux.coproc")
	if coproc.parent_mux_socket then
		return coproc.parent_mux_socket .. "\n" .. coproc.parent_mux_buffer .. "\n"
	end
end

M.links = ""
return M
