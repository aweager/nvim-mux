import logging
from dataclasses import dataclass

from jrpc.client_cache import ClientManager
from reg.api import (
    AddLinkParams,
    AddLinkResult,
    ClearAndReplaceParams,
    ClearAndReplaceResult,
    GetAllParams,
    GetAllResult,
    GetMultipleParams,
    GetMultipleResult,
    RegistryInfoParams,
    RegistryInfoResult,
    Regname,
    RemoveLinkParams,
    RemoveLinkResult,
    SetMultipleParams,
    SetMultipleResult,
    SyncAllParams,
    SyncAllResult,
    SyncMultipleParams,
    SyncMultipleResult,
    parse_regname,
)
from reg.errors import RegApiError, RejectedUnlinkedSync
from reg.service import RegApi
from reg.syncer import RegSyncer
from result import Err, Ok, Result
from typing_extensions import TypeVar, override

from nvim_mux.nvim_client import NvimClient
from nvim_mux.reg.reg_client import RegClient

_LOGGER = logging.getLogger("reg-impl")

TValue = TypeVar("TValue")


def regname_key_coerce(values: dict[str, TValue]) -> dict[Regname, TValue]:
    coerced: dict[Regname, TValue] = {}
    for key, value in values.items():
        match parse_regname(key):
            case Ok(regname):
                coerced[regname] = value
            case Err(msg):
                _LOGGER.error(f"Regname in lua result was invalid: {msg}")
    return coerced


@dataclass
class NvimRegApiImpl(RegApi):
    vim: NvimClient
    clients: ClientManager
    this_instance: str

    def __post_init__(self) -> None:
        self.registers = RegClient(self.vim)
        self.syncer = RegSyncer(self.clients, self.this_instance)

    @override
    async def get_registry_info(
        self, params: RegistryInfoParams
    ) -> Result[RegistryInfoResult, RegApiError]:
        if params.registry == "0":
            return Ok(RegistryInfoResult(exists=True))
        return Ok(RegistryInfoResult(exists=False))

    @override
    async def get_multiple(
        self, params: GetMultipleParams
    ) -> Result[GetMultipleResult, RegApiError]:
        match (
            (await self.registers.get_all_registers())
            .map(regname_key_coerce)
            .map_err(lambda e: e.to_reg_error())
        ):
            case Ok(all_values):
                pass
            case Err() as err:
                return err

        values: dict[Regname, str | None] = {}
        for key in params.keys:
            if key in all_values:
                values[key] = all_values[key]
            else:
                values[key] = None
        return Ok(GetMultipleResult(values))

    @override
    async def get_all(self, params: GetAllParams) -> Result[GetAllResult, RegApiError]:
        return (
            (await self.registers.get_all_registers())
            .map(regname_key_coerce)
            .map(lambda values: GetAllResult(values))
            .map_err(lambda e: e.to_reg_error())
        )

    @override
    async def set_multiple(
        self, params: SetMultipleParams
    ) -> Result[SetMultipleResult, RegApiError]:
        match (
            (await self.registers.set_multiple_registers(params.values)).map_err(
                lambda e: e.to_reg_error()
            )
        ):
            case Ok():
                pass
            case Err() as err:
                return err

        await (await self.registers.list_links()).map_async(
            lambda links: self.syncer.forward_sync_multiple(
                registry=params.registry,
                visited_registries=[],
                links=links,
                values=params.values,
            )
        )

        return Ok(SetMultipleResult())

    @override
    async def clear_and_replace(
        self, params: ClearAndReplaceParams
    ) -> Result[ClearAndReplaceResult, RegApiError]:
        match await self.registers.clear_and_replace_registers(params.values):
            case Ok():
                pass
            case Err(e):
                return Err(e.to_reg_error())

        await (await self.registers.list_links()).map_async(
            lambda links: self.syncer.forward_sync_all(
                registry=params.registry,
                visited_registries=[],
                links=links,
                values=params.values,
            )
        )

        return Ok(ClearAndReplaceResult())

    @override
    async def add_link(self, params: AddLinkParams) -> Result[AddLinkResult, RegApiError]:
        return (
            (await self.registers.add_link(params.link))
            .map(lambda _: AddLinkResult())
            .map_err(lambda e: e.to_reg_error())
        )

    @override
    async def remove_link(self, params: RemoveLinkParams) -> Result[RemoveLinkResult, RegApiError]:
        return (
            (await self.registers.remove_link(params.link))
            .map(lambda _: RemoveLinkResult())
            .map_err(lambda e: e.to_reg_error())
        )

    @override
    async def sync_multiple(
        self, params: SyncMultipleParams
    ) -> Result[SyncMultipleResult, RegApiError]:
        match await self.registers.list_links():
            case Ok(links):
                pass
            case Err(e):
                return Err(e.to_reg_error())

        if params.source_link not in links:
            return Err(RegApiError.from_data(RejectedUnlinkedSync()))

        match await self.registers.set_multiple_registers(params.values):
            case Ok():
                pass
            case Err(e):
                return Err(e.to_reg_error())

        return Ok(
            await self.syncer.forward_sync_multiple(
                registry=params.registry,
                visited_registries=params.visited_registries,
                links=links,
                values=params.values,
            )
        )

    @override
    async def sync_all(self, params: SyncAllParams) -> Result[SyncAllResult, RegApiError]:
        match await self.registers.list_links():
            case Ok(links):
                pass
            case Err(e):
                return Err(e.to_reg_error())

        if params.source_link not in links:
            return Err(RegApiError.from_data(RejectedUnlinkedSync()))

        match await self.registers.clear_and_replace_registers(params.values):
            case Ok():
                pass
            case Err(e):
                return Err(e.to_reg_error())

        return Ok(
            await self.syncer.forward_sync_all(
                registry=params.registry,
                visited_registries=params.visited_registries,
                links=links,
                values=params.values,
            )
        )
