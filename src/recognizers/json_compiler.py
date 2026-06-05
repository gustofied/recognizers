from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from recognizers.json_etokens import OTHER_KEY
from recognizers.json_ir import (
    AnySchema,
    ArrSchema,
    BoolSchema,
    NullSchema,
    NumSchema,
    ObjSchema,
    Schema,
    StrSchema,
)


class CompiledSchema:
    pass


@dataclass(frozen=True)
class CompiledAnySchema(CompiledSchema):
    pass


@dataclass(frozen=True)
class CompiledNullSchema(CompiledSchema):
    pass


@dataclass(frozen=True)
class CompiledBoolSchema(CompiledSchema):
    pass


@dataclass(frozen=True)
class CompiledNumSchema(CompiledSchema):
    pass


@dataclass(frozen=True)
class CompiledStrSchema(CompiledSchema):
    pass


@dataclass(frozen=True)
class CompiledArrSchema(CompiledSchema):
    item: CompiledSchema


@dataclass(frozen=True)
class CompiledObjSchema(CompiledSchema):
    properties: dict[int, CompiledSchema]
    required_mask: int
    additional: bool = True


@dataclass(frozen=True)
class KeyTable:
    keys: tuple[str, ...]
    ids: dict[str, int]

    def id_for(self, key: str) -> int:
        return self.ids[key]

    def key_mapper(self, key: str) -> object:
        return self.ids.get(key, OTHER_KEY)

    def mask_for(self, keys: set[str]) -> int:
        mask = 0
        for key in keys:
            mask |= bit_for(self.id_for(key))
        return mask

    def names_for_mask(self, mask: int) -> list[str]:
        return [key for key_id, key in enumerate(self.keys) if mask & bit_for(key_id)]


@dataclass(frozen=True)
class CompiledJsonSchema:
    root: CompiledSchema
    key_table: KeyTable

    @property
    def key_mapper(self) -> Callable[[str], object]:
        return self.key_table.key_mapper


def compile_schema(schema: Schema) -> CompiledJsonSchema:
    keys: list[str] = []
    collect_keys(schema, keys)
    key_table = KeyTable(
        keys=tuple(keys),
        ids={key: key_id for key_id, key in enumerate(keys)},
    )
    return CompiledJsonSchema(
        root=compile_node(schema, key_table),
        key_table=key_table,
    )


def collect_keys(schema: Schema, keys: list[str]) -> None:
    if isinstance(schema, ObjSchema):
        unknown_required = schema.required - set(schema.properties)
        if unknown_required:
            raise ValueError(f"Required keys missing schemas: {sorted(unknown_required)}")

        for key, value_schema in schema.properties.items():
            if key not in keys:
                keys.append(key)
            collect_keys(value_schema, keys)
    elif isinstance(schema, ArrSchema):
        collect_keys(schema.item, keys)


def compile_node(schema: Schema, key_table: KeyTable) -> CompiledSchema:
    if isinstance(schema, AnySchema):
        return CompiledAnySchema()
    if isinstance(schema, NullSchema):
        return CompiledNullSchema()
    if isinstance(schema, BoolSchema):
        return CompiledBoolSchema()
    if isinstance(schema, NumSchema):
        return CompiledNumSchema()
    if isinstance(schema, StrSchema):
        return CompiledStrSchema()
    if isinstance(schema, ArrSchema):
        return CompiledArrSchema(compile_node(schema.item, key_table))
    if isinstance(schema, ObjSchema):
        properties = {
            key_table.id_for(key): compile_node(value_schema, key_table)
            for key, value_schema in schema.properties.items()
        }
        return CompiledObjSchema(
            properties=properties,
            required_mask=key_table.mask_for(schema.required),
            additional=schema.additional,
        )

    raise TypeError(f"Unsupported schema: {schema!r}")


def bit_for(key_id: int) -> int:
    return 1 << key_id
