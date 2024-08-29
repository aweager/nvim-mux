from dataclasses import dataclass

from reg.api import RegLink, Regname
from reg.errors import RegApiError
from result import Err, Ok, Result

from nvim_mux.errors import NvimLuaApiError, NvimLuaInvalidResponse
from nvim_mux.nvim_api import Empty, LinkCounts, VariableValues
from nvim_mux.nvim_client import NvimClient


@dataclass
class RegClient:
    vim: NvimClient

    async def get_all_registers(
        self,
    ) -> Result[dict[str, str], NvimLuaApiError | NvimLuaInvalidResponse]:
        return (await self.vim.call_no_error("get_all_registers", VariableValues)).map(
            lambda result: result.values if isinstance(result.values, dict) else {}
        )

    async def clear_and_replace_registers(
        self, values: dict[Regname, str]
    ) -> Result[None, NvimLuaApiError | NvimLuaInvalidResponse]:
        values_str_keys = {k.value: v for k, v in values.items()}
        return (
            await self.vim.call_no_error(
                "clear_and_replace_registers",
                Empty,
                values_str_keys,
            )
        ).map(lambda _: None)

    async def set_multiple_registers(
        self, values: dict[Regname, str | None]
    ) -> Result[None, NvimLuaApiError | NvimLuaInvalidResponse]:
        values_str_keys = {k.value: v if v is not None else [] for k, v in values.items()}
        return (
            await self.vim.call_no_error(
                "set_multiple_registers",
                Empty,
                values_str_keys,
            )
        ).map(lambda _: None)

    async def add_link(
        self, link: RegLink
    ) -> Result[None, NvimLuaApiError | NvimLuaInvalidResponse]:
        return (
            await self.vim.call_no_error(
                "add_reg_link",
                Empty,
                link.instance,
                link.registry,
            )
        ).map(lambda _: None)

    async def remove_link(
        self, link: RegLink
    ) -> Result[None, NvimLuaApiError | NvimLuaInvalidResponse]:
        return (
            await self.vim.call_no_error(
                "remove_reg_link",
                Empty,
                link.instance,
                link.registry,
            )
        ).map(lambda _: None)

    async def list_links(self) -> Result[list[RegLink], NvimLuaApiError | NvimLuaInvalidResponse]:
        match await self.vim.call_no_error(
            "list_reg_links",
            LinkCounts,
        ):
            case Ok(result):
                pass
            case Err() as err:
                return err

        links: list[RegLink] = []
        for instance, registries in result.links.items():
            for registry in registries.keys():
                links.append(RegLink(instance, registry))
        return Ok(links)
