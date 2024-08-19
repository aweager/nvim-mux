local M = {}

---@alias LocationDict { mux: { INFO: table<string, string>?, USER: table<string, string>? }? }

---@type table<string, table<string, CustomCallback[]>>
local custom_callbacks = {}

---@class VariableValuesResult
---@field values table<string, string>

---@class LocationInfoResult
---@field exists boolean
---@field id string?

---@class JsonRpcError
---@field code integer
---@field message string
---@field data table<string, any>

local defaults = require("mux.defaults")
local types = require("mux.types")

---Makes a location DNE error
---@param scope Scope
---@param id integer
---@return JsonRpcError
local function location_dne(scope, id)
    return {
        code = 10003,
        message = "Location does not exist",
        data = {
            reference = types.make_location_str(scope, id),
        },
    }
end

---Return the variable accessor for a location
---@param scope StandardizedScope
---@param id integer
---@return LocationDict?
local function dict_at(scope, id)
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

---Return the variable accessors for a location and it's children
---@param scope StandardizedScope
---@param id integer
---@return LocationDict?
local function dicts_under(scope, id)
    if scope == "s" then
        return {
            vim.g,
            vim.t[0],
            vim.w[0],
            vim.b[0],
            defaults.get_buffer_defaults(0),
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
            defaults.get_buffer_defaults(buffer),
        }
    elseif scope == "w" then
        if not vim.api.nvim_win_is_valid(id) then
            return nil
        end
        local buffer = vim.api.nvim_win_get_buf(id)
        return {
            vim.w[id],
            vim.b[buffer],
            defaults.get_buffer_defaults(buffer),
        }
    elseif scope == "b" then
        if not vim.api.nvim_buf_is_valid(id) then
            return nil
        end
        return {
            vim.b[id],
            defaults.get_buffer_defaults(id),
        }
    else
        return nil
    end
end

---Repeatedly access dicts downward with a default of {}
---@param root table<string, any>
---@param ... string
---@return table<string, any>
local function coalesce(root, ...)
    local result = root or {}
    for _, segment in pairs({ ... }) do
        result = result[segment] or {}
    end
    return result
end

---Gets the values of variables at the specified location
---@param scope Scope
---@param id integer
---@param namespace string
---@return { result: VariableValuesResult?, error: JsonRpcError? }
function M.get_all_vars(scope, id, namespace)
    local std_scope, std_id = types.standardize_scope(scope, id)
    if std_scope == nil or std_id == nil then
        return {
            error = location_dne(scope, id),
        }
    end

    local dict = dict_at(std_scope, std_id)
    if dict == nil then
        return {
            error = location_dne(scope, id),
        }
    end

    return {
        result = {
            values = coalesce(dict, "mux", namespace),
        },
    }
end

---Resolves the values of variables at the specified location
---@param scope Scope
---@param id integer
---@param namespace string
---@return { result: VariableValuesResult?, error: JsonRpcError? }
function M.resolve_all_vars(scope, id, namespace)
    local std_scope, std_id = types.standardize_scope(scope, id)
    if std_scope == nil or std_id == nil then
        return {
            error = location_dne(scope, id),
        }
    end

    local dicts = dicts_under(std_scope, std_id)
    if dicts == nil then
        return {
            error = location_dne(std_scope, std_id),
        }
    end

    local resolved_values = {}
    for _, dict in ipairs(dicts) do
        local local_values = coalesce(dict, "mux", namespace)
        for key, value in pairs(local_values) do
            if resolved_values[key] == nil then
                resolved_values[key] = value
            end
        end
    end

    return {
        result = {
            values = resolved_values,
        },
    }
end

---Clears out the existing values and replaces them
---@param scope Scope
---@param id integer
---@param namespace string
---@param values table<string, string>
---@return { result: table<string, string>?, error: JsonRpcError? }
function M.clear_and_replace_vars(scope, id, namespace, values)
    local std_scope, std_id = types.standardize_scope(scope, id)
    if std_scope == nil or std_id == nil then
        return {
            error = location_dne(scope, id),
        }
    end

    local dict = dict_at(std_scope, std_id)
    if dict == nil then
        return {
            error = location_dne(scope, id),
        }
    end

    -- TODO invoke callbacks
    local mux = coalesce(dict.mux)
    mux[namespace] = values
    dict.mux = mux
    vim.cmd.redrawtabline()
    return {
        result = {
            unused = "",
        },
    }
end

---Sets multiple values
---@param scope Scope
---@param id integer
---@param namespace string
---@param values table<string, string>
---@return { result: table<string, string>?, error: JsonRpcError? }
function M.set_multiple_vars(scope, id, namespace, values)
    local std_scope, std_id = types.standardize_scope(scope, id)
    if std_scope == nil or std_id == nil then
        return {
            error = location_dne(scope, id),
        }
    end

    local dict = dict_at(std_scope, std_id)
    if dict == nil then
        return {
            error = location_dne(scope, id),
        }
    end

    local mux = coalesce(dict, "mux")
    if mux[namespace] == nil then
        mux[namespace] = {}
    end

    local location = types.make_location_str(std_scope, std_id)
    for key, value in pairs(values) do
        mux[namespace][key] = value
        for _, callback in pairs(coalesce(custom_callbacks, namespace, key)) do
            callback(location, key, value)
        end
    end
    dict.mux = mux
    vim.cmd.redrawtabline()
    return {
        result = {
            unused = "",
        },
    }
end

---Get info on a location
---@param scope Scope
---@param id integer
---@return { result: LocationInfoResult }
function M.get_location_info(scope, id)
    local std_scope, std_id = types.standardize_scope(scope, id)
    if std_scope == nil or std_id == nil then
        return {
            result = {
                exists = false,
            },
        }
    end

    if dict_at(std_scope, std_id) == nil then
        return {
            result = {
                exists = false,
            },
        }
    end

    return {
        result = {
            exists = true,
            id = types.make_location_str(std_scope, std_id),
        },
    }
end

---Register a callback for whenever a USER value is changed
---@param key string
---@param callback CustomCallback
function M.register_user_callback(key, callback)
    local callback_list = coalesce(custom_callbacks, "USER", key)
    table.insert(callback_list, callback)
    custom_callbacks["USER"] = coalesce(custom_callbacks, "USER")
    custom_callbacks["USER"][key] = callback_list
end

return M
