from dataclasses import dataclass
from enum import StrEnum

from jrpc.data import JsonTryLoadMixin


class NvimExtensionMethodName(StrEnum):
    PUBLISH_TO_PARENT = "nvim.publish-to-parent"


@dataclass
class PublishToParentParams(JsonTryLoadMixin):
    values: dict[str, str]


@dataclass
class PublishToParentResult(JsonTryLoadMixin):
    pass
