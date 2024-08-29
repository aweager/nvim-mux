from dataclasses import dataclass, field

from dataclasses_json import config
from jrpc.data import JsonTryLoadMixin
from marshmallow import fields
from mux.errors import LocationDoesNotExist, MuxApiError, MuxErrorCode


@dataclass
class VariableValues(JsonTryLoadMixin):
    values: dict[str, str] | tuple[str] = field(metadata=config(mm_field=fields.Raw()))


@dataclass
class LinkCounts(JsonTryLoadMixin):
    links: dict[str, dict[str, int]]


@dataclass
class Empty(JsonTryLoadMixin):
    pass


@dataclass
class LocationDne(JsonTryLoadMixin):
    scope: str
    id: int

    def to_mux_error(self) -> MuxApiError:
        return MuxApiError.from_data(LocationDoesNotExist(f"{self.scope}:{self.id}"))


ERROR_TYPES_BY_CODE = {MuxErrorCode.LOCATION_DOES_NOT_EXIST: LocationDne}
