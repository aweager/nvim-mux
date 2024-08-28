from dataclasses import dataclass

from jrpc.data import JsonTryLoadMixin
from jrpc.service import JsonTryConverter, MethodDescriptor
from mux.errors import ERROR_CONVERTER


@dataclass
class PublishToParentParams(JsonTryLoadMixin):
    values: dict[str, str]


@dataclass
class PublishToParentResult(JsonTryLoadMixin):
    pass


class NvimExtensionMethod:
    PUBLISH_TO_PARENT = MethodDescriptor(
        name="nvim.publish-to-parent",
        params_converter=JsonTryConverter(PublishToParentParams),
        result_converter=JsonTryConverter(PublishToParentResult),
        error_converter=ERROR_CONVERTER,
    )
