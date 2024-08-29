from dataclasses import dataclass

from jrpc.data import JsonTryLoadMixin
from jrpc.service import JsonTryConverter, MethodDescriptor
from mux.errors import ERROR_CONVERTER as MUX_ERROR_CONVERTER
from reg.api import Regname, values_field
from reg.errors import ERROR_CONVERTER as REG_ERROR_CONVERTER

from nvim_mux.nvim_api import LinkCounts


@dataclass
class PublishToParentParams(JsonTryLoadMixin):
    values: dict[str, str]


@dataclass
class PublishToParentResult(JsonTryLoadMixin):
    pass


@dataclass
class SyncRegistersDownParams(JsonTryLoadMixin):
    pass


@dataclass
class SyncRegistersDownResult(JsonTryLoadMixin):
    pass


@dataclass
class PublishRegistersParams(JsonTryLoadMixin):
    key: Regname


@dataclass
class PublishRegistersResult(JsonTryLoadMixin):
    pass


class NvimExtensionMethod:
    PUBLISH_TO_PARENT = MethodDescriptor(
        name="nvim.publish-to-parent",
        params_converter=JsonTryConverter(PublishToParentParams),
        result_converter=JsonTryConverter(PublishToParentResult),
        error_converter=MUX_ERROR_CONVERTER,
    )
    SYNC_REGISTERS_DOWN = MethodDescriptor(
        name="nvim.sync-registers-down",
        params_converter=JsonTryConverter(SyncRegistersDownParams),
        result_converter=JsonTryConverter(SyncRegistersDownResult),
        error_converter=REG_ERROR_CONVERTER,
    )
    PUBLISH_REGISTERS = MethodDescriptor(
        name="nvim.publish-registers",
        params_converter=JsonTryConverter(PublishRegistersParams),
        result_converter=JsonTryConverter(PublishRegistersResult),
        error_converter=REG_ERROR_CONVERTER,
    )
