from dataclasses import dataclass

from jrpc.client import JsonRpcClient
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

from nvim_mux.errors import OtherMuxServerError
from nvim_mux.extension_api import PublishToParentParams, PublishToParentResult

from .nvim_client import NvimClient, Reference, Scope, parse_reference


@dataclass
class NvimMuxApiImpl(MuxApi):
    parent_mux_client: JsonRpcClient | None
    parent_mux_location: str | None
    vim: NvimClient

    @override
    async def get_multiple(
        self, params: GetMultipleParams
    ) -> Result[GetMultipleResult, MuxApiError]:
        result = await parse_reference(params.location).and_then_async(
            lambda ref: self.vim.get_all_vars(ref, params.namespace)
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
                lambda ref: self.vim.get_all_vars(ref, params.namespace)
            )
        ).map(GetAllResult)

    @override
    async def resolve_multiple(
        self, params: ResolveMultipleParams
    ) -> Result[ResolveMultipleResult, MuxApiError]:
        result = await parse_reference(params.location).and_then_async(
            lambda ref: self.vim.resolve_all_vars(ref, params.namespace)
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
                lambda ref: self.vim.resolve_all_vars(ref, params.namespace)
            )
        ).map(ResolveAllResult)

    async def _publish(self) -> None:
        if self.parent_mux_client is None or self.parent_mux_location is None:
            return

        session_info_result = await self.vim.resolve_all_vars(
            Reference("s:0", 0, Scope.SESSION), "INFO"
        )
        match session_info_result:
            case Ok(session_info):
                pass
            case Err():
                return

        await self.parent_mux_client.request(
            MuxMethod.CLEAR_AND_REPLACE,
            ClearAndReplaceParams(
                location=self.parent_mux_location, namespace="INFO", values=session_info
            ),
        )

    @override
    async def set_multiple(
        self, params: SetMultipleParams
    ) -> Result[SetMultipleResult, MuxApiError]:
        match await parse_reference(params.location).and_then_async(
            lambda ref: self.vim.set_multiple_vars(ref, params.namespace, params.values)
        ):
            case Ok():
                if params.namespace == "INFO":
                    await self._publish()
                return Ok(SetMultipleResult())
            case Err() as err:
                return err

    @override
    async def clear_and_replace(
        self, params: ClearAndReplaceParams
    ) -> Result[ClearAndReplaceResult, MuxApiError]:
        match await parse_reference(params.location).and_then_async(
            lambda ref: self.vim.clear_and_replace_vars(ref, params.namespace, params.values)
        ):
            case Ok():
                if params.namespace == "INFO":
                    await self._publish()
                return Ok(ClearAndReplaceResult())
            case Err() as err:
                return err

    @override
    async def get_location_info(
        self, params: LocationInfoParams
    ) -> Result[LocationInfoResult, MuxApiError]:
        return await parse_reference(params.ref).and_then_async(
            lambda ref: self.vim.get_location_info(ref)
        )

    async def publish_to_parent(
        self, params: PublishToParentParams
    ) -> Result[PublishToParentResult, MuxApiError]:
        if self.parent_mux_client is None or self.parent_mux_location is None:
            return Ok(PublishToParentResult())

        match (
            await self.parent_mux_client.request(
                MuxMethod.CLEAR_AND_REPLACE,
                ClearAndReplaceParams(
                    location=self.parent_mux_location,
                    namespace="INFO",
                    values=params.values,
                ),
            )
        ):
            case Ok():
                return Ok(PublishToParentResult())
            case Err(e):
                match e:
                    case MuxApiError():
                        return Err(e)
                    case _:
                        return Err(MuxApiError.from_data(OtherMuxServerError(repr(e))))
