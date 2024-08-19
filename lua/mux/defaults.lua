local M = {}

---Gets the default icon and color for a buffer
---@param buffer integer
---@return string
---@return string
local function get_default_icon_color(buffer)
    if vim.bo[buffer].buftype == "terminal" then
        return "", "lightgreen"
    end

    local devicons = require("nvim-web-devicons")
    local icon, color =
        devicons.get_icon_color_by_filetype(vim.bo[buffer].filetype, { default = false })
    if icon ~= nil then
        return icon, color
    end

    local default_icon = devicons.get_default_icon()
    return default_icon.icon, default_icon.color
end

---Gets the default title for a buffer
---@param buffer integer
---@return string
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

---Gets the default title style for a buffer
---@param buffer integer
---@return "italic" | "default"
local function get_default_title_style(buffer)
    if vim.bo[buffer].buftype == "terminal" then
        return "default"
    elseif vim.bo[buffer].modified then
        return "italic"
    else
        return "default"
    end
end

---Gets the default variable values for a buffer
---@param buffer integer
---@return LocationDict
function M.get_buffer_defaults(buffer)
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

return M
