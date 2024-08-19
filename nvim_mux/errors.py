from dataclasses import dataclass
from enum import Enum

from dataclasses_json import DataClassJsonMixin
from jrpc.data import ParsedJsonPrimitive
from mux import errors


class NvimErrorCode(Enum):
    INVALID_NVIM_LOCATION = 30001
    NVIM_LUA_API_ERROR = 30002
    NVIM_LUA_INVALID_RESPONSE = 30003


@dataclass
class InvalidNvimLocation(DataClassJsonMixin):
    raw_value: str


errors.register_error_type(
    NvimErrorCode.INVALID_NVIM_LOCATION.value,
    "Invalid neovim location reference",
    InvalidNvimLocation,
)


@dataclass
class NvimLuaApiError(DataClassJsonMixin):
    lua: str
    args: list[ParsedJsonPrimitive]
    nvim_error_repr: str


errors.register_error_type(
    NvimErrorCode.NVIM_LUA_API_ERROR.value,
    "Neovim lua execution failed",
    NvimLuaApiError,
)


@dataclass
class NvimLuaInvalidResponse(DataClassJsonMixin):
    api_func: str
    invalid_response_repr: str


errors.register_error_type(
    NvimErrorCode.NVIM_LUA_INVALID_RESPONSE.value,
    "Neovim lua API call returned an invalid response",
    NvimLuaInvalidResponse,
)
