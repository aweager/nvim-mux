from dataclasses import dataclass


@dataclass
class ParentMux:
    instance: str
    location: str


@dataclass
class ParentReg:
    instance: str
    registry: str


@dataclass
class ParentInfo:
    parent_mux: ParentMux | None
    parent_reg: ParentReg | None
