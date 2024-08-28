from dataclasses import dataclass

from jrpc.data import JsonTryLoadMixin


@dataclass
class VariableValuesResult(JsonTryLoadMixin):
    values: dict[str, str] | tuple[str]


@dataclass
class NothingResult(JsonTryLoadMixin):
    pass
