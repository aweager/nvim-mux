---@diagnostic disable: redundant-parameter # to silence getreg complaints
local M = {
    ---@type table<string, table<string, integer>>
    links = {},
}

local types = require("mux.types")
local coproc = require("mux.coproc")
local internal_types = require("mux.api.internal.types")

local ok, empty_ok = internal_types.ok, internal_types.empty_ok

---Get all register values
---@return { result: VariableValues }
function M.get_all_registers()
    local values = {}
    for _, regname in pairs(types.Regname) do
        local vim_name = types.regname_to_vim_name(regname)
        local lines = vim.fn.getreg(vim_name, 1, 1)
        if #lines > 0 then
            values[regname] = vim.fn.getreg(vim_name)
        end
    end

    return ok({ values = values })
end

---Clear and replace this registry
---@param values table<Regname, string>
---@return { result: Empty }
function M.clear_and_replace_registers(values)
    local with_deletions = {}
    for _, regname in pairs(types.Regname) do
        if values[regname] == nil then
            with_deletions[regname] = {}
        else
            with_deletions[regname] = values[regname]
        end
    end

    return M.set_multiple_registers(with_deletions)
end

---Set multiple register values. A table indicates deletion.
---@param values table<Regname, string | table>
---@return { result: Empty }
function M.set_multiple_registers(values)
    -- Need to hold onto unnamed because deleting a reg implicitly deletes unnamed
    local unnamed_value
    if values["unnamed"] ~= nil then
        unnamed_value = values["unnamed"]
    else
        unnamed_value = vim.fn.getreg("", 1, 1)
    end

    for regname, value in pairs(values) do
        vim.fn.setreg(regname, value)
    end
    vim.fn.setreg("", unnamed_value)

    return empty_ok()
end

---Adds a shadowed link
---@param instance string
---@param registry string
---@return { result: Empty }
function M.add_reg_link(instance, registry)
    if M.links[instance] == nil then
        M.links[instance] = {}
    end
    if M.links[instance][registry] == nil then
        M.links[instance][registry] = 0
    end
    M.links[instance][registry] = M.links[instance][registry] + 1
    return empty_ok()
end

---Removes a shadowed link
---@param instance string
---@param registry string
---@return { result: Empty }
function M.remove_reg_link(instance, registry)
    if M.links[instance] ~= nil and M.links[instance][registry] ~= nil then
        M.links[instance][registry] = M.links[instance][registry] - 1
        if M.links[instance][registry] <= 0 then
            M.links[instance][registry] = nil
            if #M.links[instance] == 0 then
                M.links[instance] = nil
            end
        end
    end
    return empty_ok()
end

---Returns the counts on all links
---@return { result: LinkCounts }
function M.list_reg_links()
    local all_links = vim.deepcopy(M.links)
    local parent_reg = require("mux.coproc").parent_reg
    if parent_reg ~= nil then
        if all_links[parent_reg.instance] == nil then
            all_links[parent_reg.instance] = {}
        end
        if all_links[parent_reg.instance][parent_reg.registry] == nil then
            all_links[parent_reg.instance][parent_reg.registry] = 1
        else
            all_links[parent_reg.instance][parent_reg.registry] = all_links[parent_reg.instance][parent_reg.registry]
                + 1
        end
    end
    return ok({ links = all_links })
end

---Publish a sync for the given regname
---@param regname Regname
function M.publish_sync(regname)
    coproc.notify("nvim.publish-registers", string.format('{ "key": "%s" }', regname))
end

return M
