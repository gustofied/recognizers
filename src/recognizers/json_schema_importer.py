from __future__ import annotations

from collections.abc import Mapping
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


def schema_from_json_schema(schema: Mapping[str, Any]) -> Schema:
    schema_type = schema.get("type")

    if schema_type is None:
        if "properties" in schema:
            return object_from_json_schema(schema)
        if "items" in schema:
            return ArrSchema(schema_from_json_schema(as_mapping(schema["items"])))
        return AnySchema()

    if isinstance(schema_type, list):
        raise ValueError("Union JSON Schema types are not supported yet")

    match schema_type:
        case "object":
            return object_from_json_schema(schema)
        case "array":
            return ArrSchema(
                schema_from_json_schema(as_mapping(schema.get("items", {})))
            )
        case "string":
            return StrSchema()
        case "number" | "integer":
            return NumSchema()
        case "boolean":
            return BoolSchema()
        case "null":
            return NullSchema()
        case _:
            raise ValueError(f"Unsupported JSON Schema type: {schema_type!r}")


def object_from_json_schema(schema: Mapping[str, Any]) -> ObjSchema:
    raw_properties = schema.get("properties", {})
    if not isinstance(raw_properties, Mapping):
        raise ValueError("JSON Schema object properties must be an object")

    properties = {
        str(key): schema_from_json_schema(as_mapping(value))
        for key, value in raw_properties.items()
    }

    raw_required = schema.get("required", [])
    if not isinstance(raw_required, list) or not all(
        isinstance(key, str) for key in raw_required
    ):
        raise ValueError("JSON Schema required must be a list of strings")

    additional = schema.get("additionalProperties", True)
    if not isinstance(additional, bool):
        additional = True

    return ObjSchema(
        properties=properties,
        required=set(raw_required),
        additional=additional,
    )


def as_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Expected JSON Schema object")
    return value
