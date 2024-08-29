import asyncio
import logging
from collections.abc import Mapping
from concurrent import futures
from dataclasses import dataclass
from queue import SimpleQueue
from typing import Any, TypeVar

from jrpc.data import JsonTryLoadMixin, ParsedJson
from result import Err, Ok, Result

from . import nvim_thread
from .errors import NvimLuaApiError, NvimLuaInvalidResponse
from .nvim_api import ERROR_TYPES_BY_CODE, LocationDne
from .nvim_thread import NvimWorkItem

_LOGGER = logging.getLogger("nvim-client")


TOutput = TypeVar("TOutput", bound=JsonTryLoadMixin)


@dataclass
class NvimClient:
    vim_queue: SimpleQueue[NvimWorkItem]
    logging_level: int

    async def exec_lua(self, lua: str, *args: ParsedJson) -> Result[Any, NvimLuaApiError]:
        _LOGGER.debug(f"Queuing up lua with args: {lua} {args}")

        future: futures.Future[Result[Any, Exception]] = futures.Future()
        self.vim_queue.put(NvimWorkItem(lua, list(args), future))

        result = await asyncio.wrap_future(future)
        _LOGGER.debug(f"Received result {result}")
        match result:
            case Ok():
                return result
            case Err(nvim_error):
                return Err(NvimLuaApiError(lua, list(args), repr(nvim_error)))

    async def call_api(
        self, api_func: str, output_type: type[TOutput], *args: ParsedJson
    ) -> Result[TOutput, NvimLuaApiError | NvimLuaInvalidResponse | LocationDne]:
        result = await self.exec_lua(f"return require('mux.api.internal').{api_func}(...)", *args)

        match result:
            case Ok(lua_output):
                pass
            case Err(lua_api_error):
                return Err(lua_api_error)

        if not isinstance(lua_output, Mapping):
            return Err(NvimLuaInvalidResponse(api_func, repr(lua_output)))

        if "result" in lua_output:
            match output_type.try_load(lua_output["result"]):
                case Ok(loaded_result):
                    return Ok(loaded_result)
                case Err():
                    return Err(NvimLuaInvalidResponse(api_func, repr(lua_output)))

        if "error" in lua_output:
            error = lua_output["error"]
            if "code" not in error or "data" not in error:
                return Err(NvimLuaInvalidResponse(api_func, repr(lua_output)))

            code = error["code"]
            if code not in ERROR_TYPES_BY_CODE:
                return Err(NvimLuaInvalidResponse(api_func, repr(lua_output)))

            match ERROR_TYPES_BY_CODE[code].try_load(error["data"]):
                case Ok(typed_error):
                    return Err(typed_error)
                case Err():
                    return Err(NvimLuaInvalidResponse(api_func, repr(lua_output)))

        return Err(NvimLuaInvalidResponse(api_func, repr(lua_output)))

    async def call_no_error(
        self, api_func: str, output_type: type[TOutput], *args: ParsedJson
    ) -> Result[TOutput, NvimLuaApiError | NvimLuaInvalidResponse]:
        match await self.call_api(api_func, output_type, *args):
            case Ok(value):
                return Ok(value)
            case Err(e):
                if isinstance(e, LocationDne):
                    return Err(NvimLuaInvalidResponse(api_func, repr(e)))
                return Err(e)


async def connect_to_nvim() -> Result[NvimClient, NvimLuaApiError]:
    queue = nvim_thread.start_thread()
    client = NvimClient(queue, logging.DEBUG)

    result = await client.exec_lua("require('mux.api.internal')")
    match result:
        case Ok():
            return Ok(client)
        case Err() as err:
            return err
