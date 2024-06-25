local M = {}

function M.start_server(socket_path, processor)
	local socket = vim.uv.new_pipe(false)
	local success, err_name, err_string = socket:bind(socket_path)
	if not success then
		vim.print("Error binding mux IPC to " .. socket_path .. ": " .. err_name .. " " .. err_string)
		return nil
	end

	local function process_request(request, response_stream)
		local result = processor(request)
		local response
		if type(result) == "number" then
			response = "" .. result .. "\n"
		else
			response = "0\n" .. result
		end

		vim.uv.write(response_stream, response, function(err)
			if err then
				vim.print("Error responding to mux request: " .. err)
			end
			vim.uv.close(response_stream)
		end)
	end

	success, err_name, err_string = socket:listen(256, function(listen_err)
		if listen_err then
			vim.print("Error received in mux listen callback: " .. listen_err)
			return
		end

		local client_stream = vim.uv.new_pipe(false)
		socket:accept(client_stream)

		local data = ""
		client_stream:read_start(function(read_err, chunk)
			if read_err then
				vim.print("Error in mux client stream: " .. read_err)
				vim.uv.close(client_stream)
			elseif chunk then
				data = data .. chunk
				if string.sub(data, -1) == "\0" then
					data = string.sub(data, 1, -2)
					client_stream:read_stop()
					vim.schedule(function()
						process_request(data, client_stream)
					end)
				end
			else
				client_stream:read_stop()
				vim.schedule(function()
					process_request(data, client_stream)
				end)
			end
		end)
	end)

	if not success then
		vim.print("Error listening for mux IPC: " .. err_name .. " " .. err_string)
		return nil
	end

	return function()
		socket:close()
	end
end

return M
