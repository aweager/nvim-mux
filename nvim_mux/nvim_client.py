import asyncio
import logging
from collections.abc import Mapping
from concurrent import futures
from dataclasses import dataclass
from enum import StrEnum
from queue import SimpleQueue
from typing import Any, TypeVar

from jrpc.data import JsonRpcError, JsonTryLoadMixin
from mux.api import LocationInfoResult
from mux.errors import MuxApiError
from result import Err, Ok, Result

from . import nvim_thread
from .errors import InvalidNvimLocation, NvimLuaApiError, NvimLuaInvalidResponse
from .nvim_api import NothingResult, VariableValuesResult
from .nvim_thread import NvimWorkItem

_LOGGER = logging.getLogger("nvim-client")


class Scope(StrEnum):
    PID = "pid"
    BUFFER = "b"
    WINDOW = "w"
    TABPAGE = "t"
    SESSION = "s"


_SCOPE_BY_REF_PREFIX = {
    "s": Scope.SESSION,
    "t": Scope.TABPAGE,
    "w": Scope.WINDOW,
    "b": Scope.BUFFER,
    "pid": Scope.PID,
}


@dataclass
class Reference:
    raw_value: str
    target_id: int
    scope: Scope


def parse_reference(raw_value: str) -> Result[Reference, MuxApiError]:
    colon_ind = raw_value.find(":")
    if colon_ind < 0:
        return Err(MuxApiError.from_data(InvalidNvimLocation(raw_value)))

    prefix = raw_value[:colon_ind]
    suffix = raw_value[colon_ind + 1 :]
    if prefix not in _SCOPE_BY_REF_PREFIX:
        return Err(MuxApiError.from_data(InvalidNvimLocation(raw_value)))

    target_id: int
    try:
        target_id = int(suffix)
    except ValueError:
        return Err(MuxApiError.from_data(InvalidNvimLocation(raw_value)))

    return Ok(
        Reference(raw_value=raw_value, target_id=target_id, scope=_SCOPE_BY_REF_PREFIX[prefix])
    )


TOutput = TypeVar("TOutput", bound=JsonTryLoadMixin)


@dataclass
class NvimClient:
    vim_queue: SimpleQueue[NvimWorkItem]
    logging_level: int

    async def exec_lua(self, lua: str, *args: Any) -> Result[Any, NvimLuaApiError]:
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
        self, api_func: str, output_type: type[TOutput], *args: Any
    ) -> Result[TOutput, MuxApiError]:
        result = await self.exec_lua(f"return require('mux.api.internal').{api_func}(...)", *args)

        match result:
            case Ok(lua_output):
                pass
            case Err(lua_api_error):
                return Err(MuxApiError.from_data(lua_api_error))

        if not isinstance(lua_output, Mapping):
            return Err(MuxApiError.from_data(NvimLuaInvalidResponse(api_func, repr(lua_output))))

        if "result" in lua_output:
            match output_type.try_load(lua_output["result"]):
                case Ok(loaded_result):
                    return Ok(loaded_result)
                case Err():
                    return Err(
                        MuxApiError.from_data(NvimLuaInvalidResponse(api_func, repr(lua_output)))
                    )

        if "error" in lua_output:
            match JsonRpcError.try_load(lua_output["error"]):
                case Ok(json_rpc_error):
                    return Err(MuxApiError.from_json_rpc_error(json_rpc_error))
                case Err():
                    return Err(
                        MuxApiError.from_data(NvimLuaInvalidResponse(api_func, repr(lua_output)))
                    )

        return Err(MuxApiError.from_data(NvimLuaInvalidResponse(api_func, repr(lua_output))))

    async def get_all_vars(
        self, ref: Reference, namespace: str
    ) -> Result[dict[str, str], MuxApiError]:
        lua_result = await self.call_api(
            "get_all_vars",
            VariableValuesResult,
            ref.scope.value,
            ref.target_id,
            namespace,
        )
        match lua_result:
            case Ok(get_all_result):
                pass
            case Err():
                return lua_result

        if isinstance(get_all_result.values, dict):
            return Ok(get_all_result.values)
        return Ok(dict())

    async def resolve_all_vars(
        self,
        ref: Reference,
        namespace: str,
    ) -> Result[dict[str, str], MuxApiError]:
        lua_result = await self.call_api(
            "resolve_all_vars",
            VariableValuesResult,
            ref.scope.value,
            ref.target_id,
            namespace,
        )
        match lua_result:
            case Ok(resolve_all_result):
                pass
            case Err():
                return lua_result

        if isinstance(resolve_all_result.values, dict):
            return Ok(resolve_all_result.values)
        return Ok(dict())

    async def clear_and_replace_vars(
        self, ref: Reference, namespace: str, values: dict[str, str]
    ) -> Result[None, MuxApiError]:
        lua_result = await self.call_api(
            "clear_and_replace_vars",
            NothingResult,
            ref.scope.value,
            ref.target_id,
            namespace,
            values,
        )
        match lua_result:
            case Ok():
                pass
            case Err():
                return lua_result

        return Ok(None)

    async def set_multiple_vars(
        self,
        ref: Reference,
        namespace: str,
        values: dict[str, str | None],
    ) -> Result[None, MuxApiError]:
        lua_result = await self.call_api(
            "set_multiple_vars",
            NothingResult,
            ref.scope.value,
            ref.target_id,
            namespace,
            values,
        )
        match lua_result:
            case Ok():
                pass
            case Err():
                return lua_result

        return Ok(None)

    async def get_location_info(self, ref: Reference) -> Result[LocationInfoResult, MuxApiError]:
        return await self.call_api(
            "get_location_info", LocationInfoResult, ref.scope.value, ref.target_id
        )


async def connect_to_nvim() -> Result[NvimClient, NvimLuaApiError]:
    queue = nvim_thread.start_thread()
    client = NvimClient(queue, logging.DEBUG)

    result = await client.exec_lua("require('mux.api.internal')")
    match result:
        case Ok():
            return Ok(client)
        case Err() as err:
            return err
