import unittest

from recognizers.json_ir import ArrSchema, NumSchema, ObjSchema, StrSchema
from recognizers.json_machine import validate_json
from recognizers.json_machine_events import EventType


class JsonPaperExampleTests(unittest.TestCase):
    def test_accepts_array_of_2d_point_objects(self):
        schema = ArrSchema(self.point_schema())

        machine, events = validate_json(
            '[{"x":1.0,"y":1.0}, {"x":2.0,"y":1.0}, {"x":5.0,"y":1.5}]',
            schema,
        )

        self.assertTrue(machine.valid)
        self.assertEqual(machine.reward, 1)
        self.assertEqual(events[-1].event_type, EventType.VALID_COMPLETE)

    def test_accepts_2d_point_object_keys_in_any_order(self):
        schema = self.point_schema()

        for source in ['{"x":1.0,"y":1.0}', '{"y":1.0,"x":1.0}']:
            with self.subTest(source=source):
                machine, _ = validate_json(source, schema)

                self.assertTrue(machine.valid)

    def test_rejects_2d_point_missing_required_key(self):
        machine, events = validate_json('{"x":1.0}', self.point_schema())

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Missing required keys", events[-1].message)

    def test_rejects_2d_point_extra_key_when_additional_is_false(self):
        machine, events = validate_json('{"x":1.0,"y":1.0,"z":0}', self.point_schema())

        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)
        self.assertIn("Unknown key not allowed", events[-1].message)

    def test_accepts_columnar_2d_points_schema(self):
        schema = ObjSchema(
            properties={
                "x": ArrSchema(NumSchema()),
                "y": ArrSchema(NumSchema()),
            },
            required={"x", "y"},
            additional=False,
        )

        machine, _ = validate_json('{"y":[1.0,1.5],"x":[1.0,5.0]}', schema)

        self.assertTrue(machine.valid)

    def test_accepts_array_of_strings_inside_object(self):
        schema = ObjSchema(
            properties={"inner": ArrSchema(StrSchema())},
            required={"inner"},
            additional=False,
        )

        machine, _ = validate_json('{"inner":["a","b","c"]}', schema)

        self.assertTrue(machine.valid)

    def test_rejects_malformed_json_as_machine_error(self):
        machine, events = validate_json('{"x":1.0,}', self.point_schema())

        self.assertTrue(machine.failed)
        self.assertFalse(machine.valid)
        self.assertEqual(events[-1].event_type, EventType.ERROR)

    def point_schema(self) -> ObjSchema:
        return ObjSchema(
            properties={"x": NumSchema(), "y": NumSchema()},
            required={"x", "y"},
            additional=False,
        )


if __name__ == "__main__":
    unittest.main()
