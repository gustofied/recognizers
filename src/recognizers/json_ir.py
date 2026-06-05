from __future__ import annotations

from dataclasses import dataclass, field


class Schema:
    pass


@dataclass(frozen=True)
class AnySchema(Schema):
    pass


@dataclass(frozen=True)
class NullSchema(Schema):
    pass


@dataclass(frozen=True)
class BoolSchema(Schema):
    pass


@dataclass(frozen=True)
class NumSchema(Schema):
    pass


@dataclass(frozen=True)
class StrSchema(Schema):
    pass


@dataclass(frozen=True)
class ArrSchema(Schema):
    item: Schema


@dataclass(frozen=True)
class ObjSchema(Schema):
    properties: dict[str, Schema]
    required: set[str] = field(default_factory=set)
    additional: bool = True
