import asyncio
import logging
from dataclasses import dataclass

from jrpc.client_cache import ClientManager
from jrpc.service import JsonRpcProcessor, MethodSet, TypedMethodHandler
from mux.api import ClearAndReplaceParams, MuxMethod
from mux.errors import MuxApiError
from reg.api import GetAllParams, GetAllResult, RegMethod
from reg.errors import RegApiError
from reg.syncer import RegSyncer
from result import Err, Ok, Result

from nvim_mux.errors import OtherMuxServerError
from nvim_mux.mux.mux_client import MuxClient, Reference, Scope
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
    parent_mux_instance: str | None
    parent_mux_location: str | None
    parent_reg_instance: str | None
    parent_reg_registry: str | None
    mux_clients: ClientManager
    reg_clients: ClientManager

    def __post_init__(self) -> None:
        self.vars = MuxClient(self.vim)
        self.registers = RegClient(self.vim)
        self.reg_syncer = RegSyncer(self.reg_clients, self.this_instance)

    async def publish_to_parent(
        self, _: PublishToParentParams
    ) -> Result[PublishToParentResult, MuxApiError]:
        if self.parent_mux_instance is None or self.parent_mux_location is None:
            return Ok(PublishToParentResult())

        ref = Reference(
            scope=Scope.SESSION,
            target_id=0,
            raw_value="s:0",
        )

        match await self.vars.resolve_all_vars(ref, "INFO"):
            case Ok(values):
                pass
            case Err() as err:
                return err

        _LOGGER.info(f"Syncing {values} to parent mux")

        async with self.mux_clients.client(self.parent_mux_instance) as client:
            match (
                await client.request(
                    MuxMethod.CLEAR_AND_REPLACE,
                    ClearAndReplaceParams(
                        location=self.parent_mux_location,
                        namespace="INFO",
                        values=values,
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

        async with self.reg_clients.client(self.parent_reg_instance) as client:
            match await client.request(
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
