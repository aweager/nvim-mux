local M = {}

---@alias LocationDict { mux: { INFO: table<string, string>?, USER: table<string, string>? }? }

---@class VariableValues
---@field values table<string, string>

---@class LinkCounts
---@field links table<string, table<string, integer>>

---@class LocationInfo
---@field exists boolean
---@field id string?

---@class Empty : table<string, string>

---@enum NvimErrorCode
local NvimErrorCode = {
    LOCATION_DNE = 10003,
}

---@class NvimError
---@field code NvimErrorCode
---@field data LocationDne

---@class LocationDne
---@field scope Scope
---@field id integer

---@generic T
---@param value `T`
---@returns { result: T }
function M.ok(value)
    return { result = value }
end

---Returns an empty ok response
---@return Empty
function M.empty_ok()
    return { result = { unused = true } }
end

---@generic E
---@param error `E`
---@returns { error: E }
function M.err(error)
    return { error = error }
end

---Makes a LocationDne
---@param scope Scope
---@param id integer
---@return NvimError
function M.location_dne(scope, id)
    return {
        code = NvimErrorCode.LOCATION_DNE,
        data = {
            scope = scope,
            id = id,
        },
    }
end

return M
