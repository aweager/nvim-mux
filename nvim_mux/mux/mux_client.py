import logging
from dataclasses import dataclass
from enum import StrEnum

from mux.api import LocationInfoResult
from mux.errors import MuxApiError
from result import Err, Ok, Result

from nvim_mux.errors import InvalidNvimLocation
from nvim_mux.nvim_api import Empty, VariableValues
from nvim_mux.nvim_client import NvimClient

_LOGGER = logging.getLogger("mux-client")


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


@dataclass
class MuxClient:
    vim: NvimClient

    async def get_all_vars(
        self, ref: Reference, namespace: str
    ) -> Result[dict[str, str], MuxApiError]:
        match await self.vim.call_api(
            "get_all_vars",
            VariableValues,
            ref.scope.value,
            ref.target_id,
            namespace,
        ):
            case Ok(result):
                if isinstance(result.values, dict):
                    return Ok(result.values)
                return Ok(dict())
            case Err(e):
                return Err(e.to_mux_error())

    async def resolve_all_vars(
        self,
        ref: Reference,
        namespace: str,
    ) -> Result[dict[str, str], MuxApiError]:
        match await self.vim.call_api(
            "resolve_all_vars",
            VariableValues,
            ref.scope.value,
            ref.target_id,
            namespace,
        ):
            case Ok(result):
                if isinstance(result.values, dict):
                    return Ok(result.values)
                return Ok(dict())
            case Err(e):
                return Err(e.to_mux_error())

    async def clear_and_replace_vars(
        self, ref: Reference, namespace: str, values: dict[str, str]
    ) -> Result[None, MuxApiError]:
        match await self.vim.call_api(
            "clear_and_replace_vars",
            Empty,
            ref.scope.value,
            ref.target_id,
            namespace,
            values,
        ):
            case Ok():
                return Ok(None)
            case Err(e):
                return Err(e.to_mux_error())

    async def set_multiple_vars(
        self,
        ref: Reference,
        namespace: str,
        values: dict[str, str | None],
    ) -> Result[None, MuxApiError]:
        match await self.vim.call_api(
            "set_multiple_vars",
            Empty,
            ref.scope.value,
            ref.target_id,
            namespace,
            values,
        ):
            case Ok():
                return Ok(None)
            case Err(e):
                return Err(e.to_mux_error())

    async def get_location_info(self, ref: Reference) -> Result[LocationInfoResult, MuxApiError]:
        return (
            await self.vim.call_api(
                "get_location_info", LocationInfoResult, ref.scope.value, ref.target_id
            )
        ).map_err(lambda e: e.to_mux_error())
