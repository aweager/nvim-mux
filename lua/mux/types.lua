local M = {}

---Callback for listening to variable changes
---@alias CustomCallback fun(location: string, namespace: string, key: string, value: string?): any

---Allowed scopes for location references
---@alias Scope
---| "s" # global neovim scope ("session")
---| "t" # tabpage
---| "w" # window
---| "b" # buffer
---| "pid" # process ID running in a terminal buffer

---Standardized scopes
---@alias StandardizedScope
---| "s" # global neovim scope ("session")
---| "t" # tabpage
---| "w" # window
---| "b" # buffer

---Gets the buffer corresponding to a process ID
---@param pid integer
---@return integer | nil
local function pid_to_buffer(pid)
    for _, buf in pairs(vim.api.nvim_list_bufs()) do
        if vim.b[buf].terminal_job_pid == pid then
            return buf
        end
    end
    return nil
end

---Parses a location string into scope, id tuple
---@param location string
---@return Scope?
---@return integer?
function M.parse_location(location)
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

---Standardizes scope, id tuple
---@param scope Scope
---@param id integer
---@return StandardizedScope?
---@return integer?
function M.standardize_scope(scope, id)
    if scope == "pid" then
        local new_id = pid_to_buffer(id)
        if new_id == nil then
            return nil
        end
        return "b", new_id
    end

    ---@diagnostic disable-next-line: return-type-mismatch
    return scope, id
end

---Make the location string for a scope and ID
---@param scope Scope
---@param id integer
---@return string
function M.make_location_str(scope, id)
    return "" .. scope .. ":" .. id
end

return M
