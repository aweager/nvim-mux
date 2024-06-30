local M = {}

local api = require("mux.api")

local function get_lines(body)
	local result = {}
	for line in string.gmatch(body, "[^\n]+") do
		table.insert(result, line)
	end
	return result
end

function M.get(body)
	local lines = get_lines(body)
	local namespace = lines[1]
	local location = lines[2]
	local keys = { unpack(lines, 3) }

	local values = api.get(location, namespace)
	if values == nil then
		return 1
	end

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

	local values = api.resolve(location, namespace)
	if values == nil then
		return 1
	end

	local records = {}
	for _, key in pairs(keys) do
		if values[key] == nil then
			table.insert(records, key .. " ")
		else
			table.insert(records, key .. " " .. values[key])
		end
	end

	return table.concat(records, "\0") .. "\0"
end

function M.list(body)
	local lines = get_lines(body)
	local namespace = lines[1]
	local location = lines[2]

	local values = api.get(location, namespace)

	local keys = {}
	for key, _ in pairs(values) do
		table.insert(keys, key)
	end

	return table.concat(keys, "\n") .. "\n"
end

function M.set(body)
	local lines = get_lines(body)
	local namespace = lines[1]
	local location = lines[2]

	local values = {}

	local start_ind = 1
	local records_block = lines[3]
	if records_block == nil then
		return 0
	end

	while start_ind <= #records_block do
		local end_ind = string.find(records_block, "\0", start_ind) or (#records_block + 1)
		local record = string.sub(records_block, start_ind, end_ind - 1)
		if record then
			local space_ind = string.find(record, " ")
			if space_ind ~= nil then
				local key = string.sub(record, 1, space_ind - 1)
				local value = string.sub(record, space_ind + 1)
				values[key] = value
			end
		end
		start_ind = end_ind + 1
	end

	if api.set(location, namespace, values) then
		return 0
	end

	return 1
end

return M
