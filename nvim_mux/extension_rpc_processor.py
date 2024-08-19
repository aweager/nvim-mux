from dataclasses import dataclass
from typing import assert_never

from dataclasses_json import DataClassJsonMixin
from jrpc.errors import method_not_found, invalid_params
from jrpc.data import JsonRpcError, JsonRpcParams, JsonTryLoadMixin, ParsedJson
from mux.errors import MuxApiError
from result import Result, Ok, Err

from .extension_api import (
    NvimExtensionMethodName,
    PublishToParentParams,
    PublishToParentResult,
)
from .nvim_model import NvimMux


_methods: dict[str, type[JsonTryLoadMixin]] = {
    NvimExtensionMethodName.PUBLISH_TO_PARENT: PublishToParentParams,
}


@dataclass
class NvimExtensionRpcProcessor:
    model: NvimMux

    async def __call__(
        self, method: str, params: JsonRpcParams
    ) -> Result[ParsedJson, JsonRpcError]:
        if not method in _methods:
            return Err(method_not_found(method))

        params_type = _methods[method]
        match params_type.try_load(params):
            case Ok(loaded_params):
                result = await self._process_params(loaded_params)
                return result.map(DataClassJsonMixin.to_dict).map_err(
                    MuxApiError.to_json_rpc_error
                )
            case Err(schema_error):
                return Err(invalid_params(schema_error))

    async def _process_params(self, params) -> Result[DataClassJsonMixin, MuxApiError]:
        match params:
            case PublishToParentParams():
                return (await self.model.publish_to_parent(params.values)).map(
                    lambda _: PublishToParentResult()
                )

            case _:
                assert_never(params)
