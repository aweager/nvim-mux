local M = {}

local coproc = require("mux.coproc")
local types = require("mux.types")
local api_internal = require("mux.api.internal")

---Gets the values at the specified locations for a namespace
---@param location string
---@param namespace string
---@return table<string, string>
function M.get(location, namespace)
    local scope, id = types.parse_location(location)
    if scope == nil or id == nil then
        error(string.format("Location %s is invalid", location))
    end

    local result = api_internal.get_all_vars(scope, id, namespace)

    if result.result == nil then
        error(string.format("Location %s does not exist", location))
    end
    return result.result.values
end

---Gets the info at the specified location
---@param location string
---@return table<string, string>
function M.get_info(location)
    return M.get(location, "INFO")
end

---Resolves the values for the specified location and namespace
---@param location string
---@param namespace string
---@return table<string, string>
function M.resolve(location, namespace)
    local scope, id = types.parse_location(location)
    if scope == nil or id == nil then
        error(string.format("Location %s is invalid", location))
    end

    local result = api_internal.resolve_all_vars(scope, id, namespace)

    if result.result == nil then
        error(string.format("Location %s does not exist", location))
    end
    return result.result.values
end

---Resolves the info for the specified location
---@param location any
---@return table<string, string>
function M.resolve_info(location)
    return M.resolve(location, "INFO")
end

---Clears and replaces the values at the specified location for a namespace
---@param location string
---@param namespace string
---@param values table<string, string>
function M.set(location, namespace, values)
    local scope, id = types.parse_location(location)
    if scope == nil or id == nil then
        error(string.format("Location %s is invalid", location))
    end

    local result = api_internal.clear_and_replace_vars(scope, id, namespace, values)

    if result.result == nil then
        error(string.format("Location %s does not exist", location))
    end

    if namespace == "INFO" then
        M.publish()
    end
end

---Clears and replaces the info at the specified location
---@param location string
---@param values table<string, string>
function M.set_info(location, values)
    M.set(location, "INFO", values)
end

---Merges values into the table at the specified location for the specified namespace
---@param location string
---@param namespace string
---@param values table<string, string>
function M.merge(location, namespace, values)
    local scope, id = types.parse_location(location)
    if scope == nil or id == nil then
        error(string.format("Location %s is invalid", location))
    end

    local result = api_internal.set_multiple_vars(scope, id, namespace, values)

    if result.result == nil then
        error(string.format("Location %s does not exist", location))
    end
end

---Merges info into the specified location
---@param location string
---@param values table<string, string>
function M.merge_info(location, values)
    M.merge(location, "INFO", values)
end

---Registers a callback for when a USER value is changed
---@param key string
---@param callback CustomCallback
function M.register_user_callback(key, callback)
    api_internal.register_user_callback(key, callback)
end

---Publishes session-level values to the parent mux, if it exists
function M.publish()
    -- TODO use API method?
    if coproc.parent_mux_location ~= nil then
        local command = {
            "mux",
            "-I",
            coproc.parent_mux_instance,
            "set-info",
            coproc.parent_mux_location,
        }

        for key, val in pairs(assert(M.resolve_info("s:0"))) do
            table.insert(command, key)
            table.insert(command, val)
        end

        vim.system(command):wait()
    end
end

return M
