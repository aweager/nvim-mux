from dataclasses import dataclass

from mux.api import LocationInfoResult
from mux.errors import MuxApiError
from mux.model import Location, Mux, VariableNamespace
from result import Err, Ok, Result
from typing_extensions import override

from .nvim_client import NvimClient, Reference, Scope, parse_reference


@dataclass
class NvimNamespace(VariableNamespace):
    parent_mux_info: VariableNamespace | None
    client: NvimClient
    ref: Reference
    name: str

    @override
    async def get_multiple(self, keys: list[str]) -> Result[dict[str, str | None], MuxApiError]:
        result = await self.client.get_all_vars(self.ref, self.name)

        match result:
            case Ok(all_values):
                pass
            case Err():
                return result

        values: dict[str, str | None] = {}
        for key in keys:
            if key in all_values:
                values[key] = all_values[key]
            else:
                values[key] = None

        return Ok(values)

    @override
    async def get_all(self) -> Result[dict[str, str], MuxApiError]:
        return await self.client.get_all_vars(self.ref, self.name)

    @override
    async def resolve_multiple(self, keys: list[str]) -> Result[dict[str, str | None], MuxApiError]:
        result = await self.client.resolve_all_vars(self.ref, self.name)

        match result:
            case Ok(all_values):
                pass
            case Err():
                return result

        values: dict[str, str | None] = {}
        for key in keys:
            if key in all_values:
                values[key] = all_values[key]
            else:
                values[key] = None

        return Ok(values)

    @override
    async def resolve_all(self) -> Result[dict[str, str], MuxApiError]:
        return await self.client.resolve_all_vars(self.ref, self.name)

    async def _publish(self) -> None:
        if self.parent_mux_info is None:
            return

        session_info_result = await self.client.resolve_all_vars(
            Reference("s:0", 0, Scope.SESSION), "INFO"
        )
        match session_info_result:
            case Ok(session_info):
                pass
            case Err():
                return

        await self.parent_mux_info.clear_and_replace(session_info)

    @override
    async def set_multiple(self, values: dict[str, str | None]) -> Result[None, MuxApiError]:
        final_result = await self.client.set_multiple_vars(self.ref, self.name, values)

        if self.name == "INFO":
            await self._publish()

        return final_result

    @override
    async def clear_and_replace(self, values: dict[str, str]) -> Result[None, MuxApiError]:
        final_result = await self.client.clear_and_replace_vars(self.ref, self.name, values)

        if self.name == "INFO":
            await self._publish()

        return final_result


@dataclass
class NvimLocation(Location):
    parent_mux_info: VariableNamespace | None
    client: NvimClient
    ref: Reference

    @override
    async def get_info(self) -> Result[LocationInfoResult, MuxApiError]:
        return await self.client.get_location_info(self.ref)

    @override
    def namespace(self, name: str) -> NvimNamespace:
        return NvimNamespace(self.parent_mux_info, self.client, self.ref, name)


@dataclass
class NvimMux(Mux):
    parent_mux_info: VariableNamespace | None
    client: NvimClient

    @override
    def location(self, reference: str) -> Result[NvimLocation, MuxApiError]:
        match parse_reference(reference):
            case Ok(ref):
                return Ok(NvimLocation(self.parent_mux_info, self.client, ref))
            case Err() as err:
                return err

    async def publish_to_parent(self, values: dict[str, str]) -> Result[None, MuxApiError]:
        if not self.parent_mux_info:
            return Ok(None)

        return await self.parent_mux_info.clear_and_replace(values)
