import unittest

from recognizers.json_compiler import (
    CompiledArrSchema,
    CompiledNumSchema,
    CompiledObjSchema,
    CompiledStrSchema,
    bit_for,
    compile_schema,
)
from recognizers.json_etokens import OTHER_KEY
from recognizers.json_ir import AnySchema, ArrSchema, NumSchema, ObjSchema, StrSchema
from recognizers.json_machine import validate_json_compiled
from recognizers.json_machine_events import EventType


class JsonCompilerTests(unittest.TestCase):
    def test_collects_schema_keys_in_deterministic_order(self):
        schema = ObjSchema(
            properties={
                "user": ObjSchema(
                    properties={"name": StrSchema(), "age": NumSchema()},
                    required={"name"},
                    additional=False,
                ),
                "tags": ArrSchema(
                    ObjSchema(
                        properties={"label": StrSchema()},
                        required={"label"},
                        additional=False,
                    )
                ),
            },
            required={"user"},
            additional=False,
        )

        compiled = compile_schema(schema)

        self.assertEqual(
            compiled.key_table.keys,
            ("user", "name", "age", "tags", "label"),
        )

    def test_compiles_object_properties_and_required_mask(self):
        compiled = compile_schema(self.point_schema())
        root = compiled.root

        self.assertIsInstance(root, CompiledObjSchema)
        self.assertEqual(
            root.required_mask,
            bit_for(compiled.key_table.id_for("x"))
            | bit_for(compiled.key_table.id_for("y")),
        )
        self.assertIsInstance(
            root.properties[compiled.key_table.id_for("x")],
            CompiledNumSchema,
        )
        self.assertIsInstance(
            root.properties[compiled.key_table.id_for("y")],
            CompiledNumSchema,
        )

    def test_compiles_nested_array_schema(self):
        compiled = compile_schema(ArrSchema(StrSchema()))

        self.assertIsInstance(compiled.root, CompiledArrSchema)
        self.assertIsInstance(compiled.root.item, CompiledStrSchema)

    def test_rejects_required_key_without_property_schema(self):
        schema = ObjSchema(
            properties={"name": StrSchema()},
            required={"name", "age"},
            additional=False,
        )

        with self.assertRaises(ValueError):
            compile_schema(schema)

    def test_maps_known_keys_to_ids_and_unknown_to_other(self):
        compiled = compile_schema(self.point_schema())

        self.assertEqual(compiled.key_mapper("x"), compiled.key_table.id_for("x"))
        self.assertEqual(compiled.key_mapper("y"), compiled.key_table.id_for("y"))
        self.assertIs(compiled.key_mapper("z"), OTHER_KEY)

    def test_validates_compiled_schema_with_integer_key_ids(self):
        compiled = compile_schema(self.person_schema())
        machine, events = validate_json_compiled(
            '{"age":31,"name":"Adam"}',
            compiled,
        )

        key_events = [
            event.value for event in events if event.event_type == EventType.KEY_SEEN
        ]

        self.assertTrue(machine.valid)
        self.assertEqual(
            key_events,
            [
                compiled.key_table.id_for("age"),
                compiled.key_table.id_for("name"),
            ],
        )

    def test_rejects_missing_required_key_with_compiled_mask(self):
        compiled = compile_schema(self.person_schema())
        machine, events = validate_json_compiled('{"name":"Adam"}', compiled)

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("age", events[-1].message)

    def test_rejects_unknown_key_when_compiled_additional_is_false(self):
        compiled = compile_schema(self.person_schema())
        machine, events = validate_json_compiled(
            '{"name":"Adam","age":31,"admin":true}',
            compiled,
        )

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Unknown key not allowed", events[-1].message)

    def test_allows_unknown_key_when_compiled_additional_is_true(self):
        schema = ObjSchema(
            properties={"name": StrSchema()},
            required={"name"},
            additional=True,
        )
        compiled = compile_schema(schema)

        machine, _ = validate_json_compiled('{"name":"Adam","admin":true}', compiled)

        self.assertTrue(machine.valid)

    def test_compiled_any_schema_accepts_integer_key_ids(self):
        schema = ObjSchema(
            properties={"payload": AnySchema()},
            required={"payload"},
            additional=False,
        )
        compiled = compile_schema(schema)

        machine, _ = validate_json_compiled(
            '{"payload":{"payload":1}}',
            compiled,
        )

        self.assertTrue(machine.valid)

    def test_rejects_duplicate_known_key_with_compiled_seen_mask(self):
        compiled = compile_schema(self.person_schema())
        machine, events = validate_json_compiled(
            '{"name":"Adam","name":"Eve","age":31}',
            compiled,
        )

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Duplicate object key", events[-1].message)

    def point_schema(self) -> ObjSchema:
        return ObjSchema(
            properties={"x": NumSchema(), "y": NumSchema()},
            required={"x", "y"},
            additional=False,
        )

    def person_schema(self) -> ObjSchema:
        return ObjSchema(
            properties={"name": StrSchema(), "age": NumSchema()},
            required={"name", "age"},
            additional=False,
        )


if __name__ == "__main__":
    unittest.main()
