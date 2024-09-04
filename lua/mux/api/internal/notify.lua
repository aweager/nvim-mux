local M = {}

local coproc = require("mux.coproc")

---@type { method: string, params_json: string }[]
M.queued_notifications = {}

vim.g.mux_loaded = false

---Queue a notification to be sent to the server once it is ready.
---Sent immediately if it's already ready.
---@param method string
---@param params_json string
function M.queue_notification(method, params_json)
    if vim.g.mux_loaded then
        coproc.notify({ { method = method, params_json = params_json } })
        return
    end

    for _, notification in pairs(M.queued_notifications) do
        if notification.method == method and notification.params_json == params_json then
            return
        end
    end

    table.insert(M.queued_notifications, {
        method = method,
        params_json = params_json,
    })
end

---Mark the server as loaded, and enqueue pending notifications.
---@return { result: Empty }
function M.mark_loaded()
    vim.g.mux_loaded = true
    if #M.queued_notifications > 0 then
        coproc.notify(M.queued_notifications)
        M.queued_notifications = {}
    end

    return { result = {} }
end

return M
