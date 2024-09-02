import logging
from dataclasses import dataclass

from jrpc.client_cache import ClientManager
from mux.api import (
    ClearAndReplaceParams,
    ClearAndReplaceResult,
    GetAllParams,
    GetAllResult,
    GetMultipleParams,
    GetMultipleResult,
    LocationInfoParams,
    LocationInfoResult,
    MuxMethod,
    ResolveAllParams,
    ResolveAllResult,
    ResolveMultipleParams,
    ResolveMultipleResult,
    SetMultipleParams,
    SetMultipleResult,
)
from mux.errors import MuxApiError
from mux.service import MuxApi
from result import Err, Ok, Result
from typing_extensions import override

from nvim_mux.mux.mux_client import MuxClient, Reference, Scope, parse_reference
from nvim_mux.nvim_client import NvimClient

_LOGGER = logging.getLogger("nvim-mux-impl")


@dataclass
class NvimMuxApiImpl(MuxApi):
    clients: ClientManager
    parent_mux_instance: str | None
    parent_mux_location: str | None
    vim: NvimClient

    def __post_init__(self) -> None:
        self.vim_mux = MuxClient(self.vim)

    @override
    async def get_multiple(
        self, params: GetMultipleParams
    ) -> Result[GetMultipleResult, MuxApiError]:
        result = await parse_reference(params.location).and_then_async(
            lambda ref: self.vim_mux.get_all_vars(ref, params.namespace)
        )

        match result:
            case Ok(all_values):
                pass
            case Err():
                return result

        values: dict[str, str | None] = {}
        for key in params.keys:
            if key in all_values:
                values[key] = all_values[key]
            else:
                values[key] = None

        return Ok(GetMultipleResult(values))

    @override
    async def get_all(self, params: GetAllParams) -> Result[GetAllResult, MuxApiError]:
        return (
            await parse_reference(params.location).and_then_async(
                lambda ref: self.vim_mux.get_all_vars(ref, params.namespace)
            )
        ).map(GetAllResult)

    @override
    async def resolve_multiple(
        self, params: ResolveMultipleParams
    ) -> Result[ResolveMultipleResult, MuxApiError]:
        result = await parse_reference(params.location).and_then_async(
            lambda ref: self.vim_mux.resolve_all_vars(ref, params.namespace)
        )

        match result:
            case Ok(all_values):
                pass
            case Err():
                return result

        values: dict[str, str | None] = {}
        for key in params.keys:
            if key in all_values:
                values[key] = all_values[key]
            else:
                values[key] = None

        return Ok(ResolveMultipleResult(values))

    @override
    async def resolve_all(self, params: ResolveAllParams) -> Result[ResolveAllResult, MuxApiError]:
        return (
            await parse_reference(params.location).and_then_async(
                lambda ref: self.vim_mux.resolve_all_vars(ref, params.namespace)
            )
        ).map(ResolveAllResult)

    async def publish(self) -> None:
        if self.parent_mux_instance is None or self.parent_mux_location is None:
            return

        async with self.clients.client(self.parent_mux_instance) as client:
            session_info_result = await self.vim_mux.resolve_all_vars(
                Reference("s:0", 0, Scope.SESSION), "INFO"
            )
            match session_info_result:
                case Ok(session_info):
                    pass
                case Err():
                    return

            match await client.request(
                MuxMethod.CLEAR_AND_REPLACE,
                ClearAndReplaceParams(
                    location=self.parent_mux_location, namespace="INFO", values=session_info
                ),
            ):
                case Err(e):
                    _LOGGER.warning(f"Failed to publish to parent mux: {e}")

    @override
    async def set_multiple(
        self, params: SetMultipleParams
    ) -> Result[SetMultipleResult, MuxApiError]:
        match await parse_reference(params.location).and_then_async(
            lambda ref: self.vim_mux.set_multiple_vars(ref, params.namespace, params.values)
        ):
            case Ok():
                if params.namespace == "INFO":
                    await self.publish()
                return Ok(SetMultipleResult())
            case Err() as err:
                return err

    @override
    async def clear_and_replace(
        self, params: ClearAndReplaceParams
    ) -> Result[ClearAndReplaceResult, MuxApiError]:
        match await parse_reference(params.location).and_then_async(
            lambda ref: self.vim_mux.clear_and_replace_vars(ref, params.namespace, params.values)
        ):
            case Ok():
                if params.namespace == "INFO":
                    await self.publish()
                return Ok(ClearAndReplaceResult())
            case Err() as err:
                return err

    @override
    async def get_location_info(
        self, params: LocationInfoParams
    ) -> Result[LocationInfoResult, MuxApiError]:
        return await parse_reference(params.ref).and_then_async(
            lambda ref: self.vim_mux.get_location_info(ref)
        )
