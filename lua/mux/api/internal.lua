local vars_api = require("mux.api.internal.vars")
local reg_api = require("mux.api.internal.reg")
local notify_api = require("mux.api.internal.notify")

return {
    get_all_vars = vars_api.get_all_vars,
    resolve_all_vars = vars_api.resolve_all_vars,
    set_multiple_vars = vars_api.set_multiple_vars,
    clear_and_replace_vars = vars_api.clear_and_replace_vars,
    get_location_info = vars_api.get_location_info,
    register_user_callback = vars_api.register_user_callback,
    get_all_registers = reg_api.get_all_registers,
    set_multiple_registers = reg_api.set_multiple_registers,
    clear_and_replace_registers = reg_api.clear_and_replace_registers,
    add_reg_link = reg_api.add_reg_link,
    remove_reg_link = reg_api.remove_reg_link,
    list_reg_links = reg_api.list_reg_links,
    mark_loaded = notify_api.mark_loaded,
}
