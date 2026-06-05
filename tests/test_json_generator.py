import json
import unittest

from recognizers.json_compiler import compile_schema
from recognizers.json_generator import generate_json, generate_value
from recognizers.json_ir import (
    AnySchema,
    ArrSchema,
    BoolSchema,
    NullSchema,
    NumSchema,
    ObjSchema,
    StrSchema,
)
from recognizers.json_machine import validate_json, validate_json_compiled
from recognizers.json_schema_importer import schema_from_json_schema


class JsonGeneratorTests(unittest.TestCase):
    def test_generates_primitive_values(self):
        examples = [
            (AnySchema(), None),
            (NullSchema(), None),
            (BoolSchema(), True),
            (NumSchema(), 0),
            (StrSchema(), "string"),
        ]

        for schema, expected in examples:
            with self.subTest(schema=schema):
                self.assertEqual(generate_value(schema), expected)

    def test_generates_object_with_required_and_optional_fields(self):
        schema = ObjSchema(
            properties={"name": StrSchema(), "age": NumSchema(), "admin": BoolSchema()},
            required={"name", "age"},
            additional=False,
        )

        self.assertEqual(
            json.loads(generate_json(schema)),
            {"name": "string", "age": 0, "admin": True},
        )

    def test_can_generate_required_fields_only(self):
        schema = ObjSchema(
            properties={"name": StrSchema(), "nickname": StrSchema()},
            required={"name"},
            additional=False,
        )

        self.assertEqual(
            json.loads(generate_json(schema, include_optional=False)),
            {"name": "string"},
        )

    def test_generates_array_with_requested_length(self):
        source = generate_json(ArrSchema(NumSchema()), array_length=3)

        self.assertEqual(json.loads(source), [0, 0, 0])

    def test_generated_json_validates_against_schema(self):
        schema = ObjSchema(
            properties={
                "points": ArrSchema(
                    ObjSchema(
                        properties={"x": NumSchema(), "y": NumSchema()},
                        required={"x", "y"},
                        additional=False,
                    )
                )
            },
            required={"points"},
            additional=False,
        )
        source = generate_json(schema, array_length=2)

        machine, _ = validate_json(source, schema)

        self.assertTrue(machine.valid)

    def test_generated_json_validates_against_compiled_schema(self):
        schema = ObjSchema(
            properties={"name": StrSchema(), "age": NumSchema()},
            required={"name", "age"},
            additional=False,
        )
        source = generate_json(schema)
        compiled = compile_schema(schema)

        machine, _ = validate_json_compiled(source, compiled)

        self.assertTrue(machine.valid)

    def test_generates_from_imported_json_schema(self):
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
        source = generate_json(schema)

        machine, _ = validate_json_compiled(source, compile_schema(schema))

        self.assertTrue(machine.valid)


if __name__ == "__main__":
    unittest.main()
