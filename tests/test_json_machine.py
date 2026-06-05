import unittest

from recognizers.json_ir import ArrSchema, BoolSchema, NumSchema, ObjSchema, StrSchema
from recognizers.json_machine import validate_json
from recognizers.json_machine_events import EventType


class JsonMachineTests(unittest.TestCase):
    def person_schema(self) -> ObjSchema:
        return ObjSchema(
            properties={
                "name": StrSchema(),
                "age": NumSchema(),
            },
            required={"name", "age"},
            additional=False,
        )

    def test_validates_object_independent_of_key_order(self):
        for source in ['{"name":"Adam","age":31}', '{"age":31,"name":"Adam"}']:
            with self.subTest(source=source):
                machine, events = validate_json(source, self.person_schema())

                self.assertTrue(machine.valid)
                self.assertEqual(machine.reward, 1)
                self.assertIn(EventType.VALID_COMPLETE, self.event_types(events))

    def test_rejects_missing_required_key(self):
        machine, events = validate_json('{"name":"Adam"}', self.person_schema())

        self.assertFalse(machine.valid)
        self.assertEqual(machine.reward, 0)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Missing required keys", events[-1].message)

    def test_rejects_wrong_primitive_type(self):
        machine, events = validate_json('{"name":31,"age":31}', self.person_schema())

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Expected Str", events[-1].message)

    def test_rejects_unknown_key_when_additional_is_false(self):
        machine, events = validate_json(
            '{"name":"Adam","age":31,"admin":true}',
            self.person_schema(),
        )

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Unknown key not allowed", events[-1].message)

    def test_rejects_duplicate_object_key(self):
        machine, events = validate_json(
            '{"name":"Adam","name":"Eve","age":31}',
            self.person_schema(),
        )

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Duplicate object key", events[-1].message)

    def test_allows_unknown_key_when_additional_is_true(self):
        schema = ObjSchema(
            properties={"name": StrSchema()},
            required={"name"},
            additional=True,
        )

        machine, _ = validate_json('{"name":"Adam","admin":true}', schema)

        self.assertTrue(machine.valid)

    def test_validates_array_of_point_objects(self):
        point = ObjSchema(
            properties={"x": NumSchema(), "y": NumSchema()},
            required={"x", "y"},
            additional=False,
        )
        schema = ArrSchema(point)

        machine, events = validate_json(
            '[{"x":1.0,"y":1.0},{"y":2.0,"x":5.0}]',
            schema,
        )

        self.assertTrue(machine.valid)
        self.assertEqual(machine.reward, 1)
        self.assertEqual(events[-1].event_type, EventType.VALID_COMPLETE)

    def test_rejects_bad_array_element(self):
        point = ObjSchema(
            properties={"x": NumSchema(), "y": NumSchema()},
            required={"x", "y"},
            additional=False,
        )

        machine, events = validate_json('[{"x":1.0}]', ArrSchema(point))

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Missing required keys", events[-1].message)

    def test_validates_bool_schema(self):
        machine, _ = validate_json("true", BoolSchema())

        self.assertTrue(machine.valid)

    def event_types(self, events):
        return [event.event_type for event in events]


if __name__ == "__main__":
    unittest.main()
