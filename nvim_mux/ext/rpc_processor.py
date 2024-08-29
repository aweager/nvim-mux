import asyncio
import logging
from dataclasses import dataclass

from jrpc.client import ClientFactory, JsonRpcClient, JsonRpcOneoffClient
from jrpc.service import JsonRpcProcessor, MethodSet, TypedMethodHandler
from mux.api import ClearAndReplaceParams, MuxMethod
from mux.errors import MuxApiError
from reg.api import GetAllParams, GetAllResult, RegMethod
from reg.errors import RegApiError
from reg.syncer import RegSyncer
from result import Err, Ok, Result

from nvim_mux.errors import OtherMuxServerError
from nvim_mux.nvim_client import NvimClient
from nvim_mux.reg.reg_client import RegClient

from .api import (
    NvimExtensionMethod,
    PublishRegistersParams,
    PublishRegistersResult,
    PublishToParentParams,
    PublishToParentResult,
    SyncRegistersDownParams,
    SyncRegistersDownResult,
)

_LOGGER = logging.getLogger("ext-impl")


@dataclass
class NvimExtensionApiImpl:
    vim: NvimClient
    this_instance: str
    parent_mux_client: JsonRpcClient | None
    parent_mux_location: str | None
    parent_reg_instance: str | None
    parent_reg_registry: str | None
    client_factory: ClientFactory

    def __post_init__(self) -> None:
        self.registers = RegClient(self.vim)
        self.reg_syncer = RegSyncer(self.client_factory, self.this_instance)

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

    async def sync_registers_down(
        self, _: SyncRegistersDownParams
    ) -> Result[SyncRegistersDownResult, RegApiError]:
        if not self.parent_reg_instance or not self.parent_reg_registry:
            return Ok(SyncRegistersDownResult())

        _LOGGER.info(f"Syncing down from {self.parent_reg_instance} : {self.parent_reg_registry}")

        match await JsonRpcOneoffClient(self.parent_reg_instance, self.client_factory).request(
            descriptor=RegMethod.GET_ALL,
            params=GetAllParams(self.parent_reg_registry),
        ):
            case Ok(GetAllResult(values)):
                pass
            case Err(e):
                _LOGGER.error(f"Failed to get parent registers: {e}")
                return Ok(SyncRegistersDownResult())

        match await self.registers.clear_and_replace_registers(values):
            case Ok():
                return Ok(SyncRegistersDownResult())
            case Err(e):
                _LOGGER.error(f"Failed to write parent's registers: {e}")
                return Err(e.to_reg_error())

    async def publish_registers(
        self, params: PublishRegistersParams
    ) -> Result[PublishRegistersResult, RegApiError]:
        async with asyncio.TaskGroup() as tg:
            links_task = tg.create_task(self.registers.list_links())
            values_task = tg.create_task(self.registers.get_all_registers())

        match links_task.result():
            case Ok(links):
                pass
            case Err(e):
                return Err(e.to_reg_error())
        match values_task.result():
            case Ok(values):
                pass
            case Err(e):
                return Err(e.to_reg_error())

        await self.reg_syncer.forward_sync_multiple(
            registry="0",
            visited_registries=[],
            values={params.key: values[params.key] if params.key in values else None},
            links=links,
        )

        return Ok(PublishRegistersResult())


def ext_rpc_processor(ext_impl: NvimExtensionApiImpl) -> JsonRpcProcessor:
    handlers: list[TypedMethodHandler] = [
        TypedMethodHandler(NvimExtensionMethod.PUBLISH_TO_PARENT, ext_impl.publish_to_parent),
        TypedMethodHandler(NvimExtensionMethod.SYNC_REGISTERS_DOWN, ext_impl.sync_registers_down),
        TypedMethodHandler(NvimExtensionMethod.PUBLISH_REGISTERS, ext_impl.publish_registers),
    ]
    return MethodSet({m.descriptor.name: m for m in handlers})
