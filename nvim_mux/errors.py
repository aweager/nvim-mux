from dataclasses import dataclass, field
from enum import Enum

from dataclasses_json import DataClassJsonMixin, config
from jrpc.data import ParsedJson
from marshmallow import fields
from mux import errors as mux_errors
from mux.errors import MuxApiError
from reg import errors as reg_errors
from reg.errors import RegApiError


class NvimErrorCode(Enum):
    INVALID_NVIM_LOCATION = 30001
    NVIM_LUA_API_ERROR = 30002
    NVIM_LUA_INVALID_RESPONSE = 30003
    NVIM_OTHER_MUX_SERVER_ERROR = 30004


@dataclass
class InvalidNvimLocation(DataClassJsonMixin):
    raw_value: str


mux_errors.register_error_type(
    NvimErrorCode.INVALID_NVIM_LOCATION.value,
    "Invalid neovim location reference",
    InvalidNvimLocation,
)


@dataclass
class NvimLuaApiError(DataClassJsonMixin):
    lua: str
    args: list[ParsedJson] = field(
        metadata=config(
            mm_field=fields.List(fields.Raw()),
        ),
    )

    nvim_error_repr: str

    def to_mux_error(self) -> MuxApiError:
        return MuxApiError.from_data(self)

    def to_reg_error(self) -> RegApiError:
        return RegApiError.from_data(self)


mux_errors.register_error_type(
    NvimErrorCode.NVIM_LUA_API_ERROR.value,
    "Neovim lua execution failed",
    NvimLuaApiError,
)

reg_errors.register_error_type(
    NvimErrorCode.NVIM_LUA_API_ERROR.value,
    "Neovim lua execution failed",
    NvimLuaApiError,
)


@dataclass
class NvimLuaInvalidResponse(DataClassJsonMixin):
    api_func: str
    invalid_response_repr: str

    def to_mux_error(self) -> MuxApiError:
        return MuxApiError.from_data(self)

    def to_reg_error(self) -> RegApiError:
        return RegApiError.from_data(self)


mux_errors.register_error_type(
    NvimErrorCode.NVIM_LUA_INVALID_RESPONSE.value,
    "Neovim lua API call returned an invalid response",
    NvimLuaInvalidResponse,
)

reg_errors.register_error_type(
    NvimErrorCode.NVIM_LUA_INVALID_RESPONSE.value,
    "Neovim lua API call returned an invalid response",
    NvimLuaInvalidResponse,
)


@dataclass
class OtherMuxServerError(DataClassJsonMixin):
    detailed_message: str


mux_errors.register_error_type(
    NvimErrorCode.NVIM_OTHER_MUX_SERVER_ERROR.value,
    "Other mux call failed",
    OtherMuxServerError,
)
