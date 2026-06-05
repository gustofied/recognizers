from __future__ import annotations

import json
from typing import Any

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


def generate_value(
    schema: Schema,
    *,
    array_length: int = 1,
    include_optional: bool = True,
) -> Any:
    if isinstance(schema, AnySchema | NullSchema):
        return None
    if isinstance(schema, BoolSchema):
        return True
    if isinstance(schema, NumSchema):
        return 0
    if isinstance(schema, StrSchema):
        return "string"
    if isinstance(schema, ArrSchema):
        return [
            generate_value(
                schema.item,
                array_length=array_length,
                include_optional=include_optional,
            )
            for _ in range(array_length)
        ]
    if isinstance(schema, ObjSchema):
        keys = (
            schema.properties
            if include_optional
            else {
                key: value
                for key, value in schema.properties.items()
                if key in schema.required
            }
        )
        return {
            key: generate_value(
                value_schema,
                array_length=array_length,
                include_optional=include_optional,
            )
            for key, value_schema in keys.items()
        }

    raise TypeError(f"Unsupported schema: {schema!r}")


def generate_json(
    schema: Schema,
    *,
    array_length: int = 1,
    include_optional: bool = True,
    indent: int | None = None,
) -> str:
    value = generate_value(
        schema,
        array_length=array_length,
        include_optional=include_optional,
    )
    return json.dumps(value, indent=indent, separators=None if indent else (",", ":"))
