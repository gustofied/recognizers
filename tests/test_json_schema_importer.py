import unittest

from recognizers.json_compiler import compile_schema
from recognizers.json_ir import (
    AnySchema,
    ArrSchema,
    BoolSchema,
    NullSchema,
    NumSchema,
    ObjSchema,
    StrSchema,
)
from recognizers.json_machine import validate_json_compiled
from recognizers.json_schema_importer import schema_from_json_schema


class JsonSchemaImporterTests(unittest.TestCase):
    def test_imports_object_schema(self):
        schema = schema_from_json_schema(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"},
                },
                "required": ["name", "age"],
                "additionalProperties": False,
            }
        )

        self.assertEqual(
            schema,
            ObjSchema(
                properties={"name": StrSchema(), "age": NumSchema()},
                required={"name", "age"},
                additional=False,
            ),
        )

    def test_imports_array_schema(self):
        schema = schema_from_json_schema(
            {"type": "array", "items": {"type": "boolean"}}
        )

        self.assertEqual(schema, ArrSchema(BoolSchema()))

    def test_imports_primitives_and_empty_schema(self):
        examples = [
            ({"type": "string"}, StrSchema()),
            ({"type": "number"}, NumSchema()),
            ({"type": "integer"}, NumSchema()),
            ({"type": "boolean"}, BoolSchema()),
            ({"type": "null"}, NullSchema()),
            ({}, AnySchema()),
        ]

        for raw_schema, expected in examples:
            with self.subTest(raw_schema=raw_schema):
                self.assertEqual(schema_from_json_schema(raw_schema), expected)

    def test_infers_object_from_properties(self):
        schema = schema_from_json_schema(
            {
                "properties": {"x": {"type": "number"}},
                "required": ["x"],
                "additionalProperties": False,
            }
        )

        self.assertEqual(
            schema,
            ObjSchema(
                properties={"x": NumSchema()},
                required={"x"},
                additional=False,
            ),
        )

    def test_imported_schema_validates_through_compiler(self):
        schema = schema_from_json_schema(
            {
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            }
        )
        compiled = compile_schema(schema)

        machine, _ = validate_json_compiled('{"y":1.5,"x":1.0}', compiled)

        self.assertTrue(machine.valid)

    def test_rejects_unsupported_union_type(self):
        with self.assertRaises(ValueError):
            schema_from_json_schema({"type": ["string", "null"]})

    def test_rejects_invalid_required_list(self):
        with self.assertRaises(ValueError):
            schema_from_json_schema(
                {
                    "type": "object",
                    "properties": {"x": {"type": "number"}},
                    "required": "x",
                }
            )


if __name__ == "__main__":
    unittest.main()
