from __future__ import annotations

from dataclasses import dataclass, field

from recognizers.json_etokens import EToken, ETokenType, OTHER_KEY, scan_etokens
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
from recognizers.json_machine_events import Event, EventType


@dataclass
class ArrayFrame:
    schema: ArrSchema | AnySchema


@dataclass
class ObjectFrame:
    schema: ObjSchema | AnySchema
    seen_keys: set[str] = field(default_factory=set)
    current_key: str | None = None


Frame = ArrayFrame | ObjectFrame


class JsonSchemaMachine:
    def __init__(self, schema: Schema):
        self.root_schema = schema
        self.value_expected: Schema | None = schema
        self.stack: list[Frame] = []
        self.complete = False
        self.valid = False
        self.failed = False

    @property
    def reward(self) -> int:
        return 1 if self.valid else 0

    def accept(self, etoken: EToken) -> list[Event]:
        if self.failed:
            return []
        if self.complete:
            return self.fail("Unexpected token after complete JSON value", etoken)

        match etoken.token_type:
            case ETokenType.LEFT_BRACE:
                return self.open_object()
            case ETokenType.LEFT_BRACKET:
                return self.open_array()
            case ETokenType.RIGHT_BRACE:
                return self.close_object()
            case ETokenType.RIGHT_BRACKET:
                return self.close_array()
            case ETokenType.JKEY:
                return self.accept_key(etoken.value)
            case (
                ETokenType.JSTR
                | ETokenType.JNUM
                | ETokenType.TRUE
                | ETokenType.FALSE
                | ETokenType.NULL
            ):
                return self.accept_primitive(etoken)
            case ETokenType.COLON | ETokenType.COMMA:
                return []

    def open_object(self) -> list[Event]:
        schema = self.expected_value_schema()
        if isinstance(schema, AnySchema):
            self.stack.append(ObjectFrame(schema))
        elif isinstance(schema, ObjSchema):
            self.stack.append(ObjectFrame(schema))
        else:
            return self.fail(f"Expected {schema_name(schema)}, got object")

        self.value_expected = None
        return []

    def close_object(self) -> list[Event]:
        frame = self.pop_frame(ObjectFrame, "object")
        if frame is None:
            return []

        events: list[Event] = []
        if isinstance(frame.schema, ObjSchema):
            missing = frame.schema.required - frame.seen_keys
            if missing:
                return self.fail(f"Missing required keys: {sorted(missing)}")

        events.append(Event(EventType.OBJECT_COMPLETE, "Object complete"))
        events.extend(self.complete_value())
        return events

    def open_array(self) -> list[Event]:
        schema = self.expected_value_schema()
        if isinstance(schema, AnySchema):
            self.stack.append(ArrayFrame(schema))
        elif isinstance(schema, ArrSchema):
            self.stack.append(ArrayFrame(schema))
        else:
            return self.fail(f"Expected {schema_name(schema)}, got array")

        self.value_expected = None
        return []

    def close_array(self) -> list[Event]:
        frame = self.pop_frame(ArrayFrame, "array")
        if frame is None:
            return []

        return self.complete_value()

    def accept_key(self, key: object) -> list[Event]:
        frame = self.top_frame()
        if not isinstance(frame, ObjectFrame):
            return self.fail("Object key outside object", key)

        if key is not OTHER_KEY:
            if not isinstance(key, str):
                return self.fail("Expected string key before schema compilation", key)
            if key in frame.seen_keys:
                return self.fail(f"Duplicate object key: {key!r}", key)
            frame.seen_keys.add(key)

        if (
            isinstance(frame.schema, ObjSchema)
            and not frame.schema.additional
            and (not isinstance(key, str) or key not in frame.schema.properties)
        ):
            return self.fail(f"Unknown key not allowed: {key!r}", key)

        value_schema = self.schema_for_key(frame, key)

        frame.current_key = key if isinstance(key, str) else None
        self.value_expected = value_schema
        return [Event(EventType.KEY_SEEN, f"Key seen: {key!r}", key)]

    def accept_primitive(self, etoken: EToken) -> list[Event]:
        schema = self.expected_value_schema()
        if not self.matches_primitive(schema, etoken):
            return self.fail(
                f"Expected {schema_name(schema)}, got {etoken.token_type.value}",
                etoken.value,
            )

        return self.complete_value(etoken.value)

    def schema_for_key(self, frame: ObjectFrame, key: object) -> Schema:
        if isinstance(frame.schema, AnySchema):
            return AnySchema()

        if isinstance(key, str) and key in frame.schema.properties:
            return frame.schema.properties[key]

        if frame.schema.additional:
            return AnySchema()

        return AnySchema()

    def expected_value_schema(self) -> Schema:
        if self.value_expected is not None:
            return self.value_expected

        frame = self.top_frame()
        if isinstance(frame, ArrayFrame):
            return frame.schema.item if isinstance(frame.schema, ArrSchema) else AnySchema()

        return AnySchema()

    def matches_primitive(self, schema: Schema, etoken: EToken) -> bool:
        if isinstance(schema, AnySchema):
            return True
        if isinstance(schema, StrSchema):
            return etoken.token_type == ETokenType.JSTR
        if isinstance(schema, NumSchema):
            return etoken.token_type == ETokenType.JNUM
        if isinstance(schema, BoolSchema):
            return etoken.token_type in {ETokenType.TRUE, ETokenType.FALSE}
        if isinstance(schema, NullSchema):
            return etoken.token_type == ETokenType.NULL
        return False

    def complete_value(self, value: object = None) -> list[Event]:
        events: list[Event] = []
        parent = self.top_frame()

        if parent is None:
            self.complete = True
            self.valid = True
            self.value_expected = None
            return [Event(EventType.VALID_COMPLETE, "JSON value satisfies schema", value)]

        if isinstance(parent, ArrayFrame):
            self.value_expected = None
            return [Event(EventType.ARRAY_ELEMENT_COMPLETE, "Array element complete", value)]

        key = parent.current_key
        parent.current_key = None
        self.value_expected = None
        events.append(Event(EventType.FIELD_COMPLETE, f"Field complete: {key!r}", key))
        return events

    def top_frame(self) -> Frame | None:
        return self.stack[-1] if self.stack else None

    def pop_frame(self, frame_type: type, expected: str) -> Frame | None:
        frame = self.top_frame()
        if not isinstance(frame, frame_type):
            self.fail(f"Unexpected closing {expected}")
            return None
        return self.stack.pop()

    def fail(self, message: str, value: object = None) -> list[Event]:
        self.failed = True
        self.valid = False
        return [Event(EventType.ERROR, message, value)]


def validate_json(source: str, schema: Schema) -> tuple[JsonSchemaMachine, list[Event]]:
    machine = JsonSchemaMachine(schema)
    events: list[Event] = []

    for etoken in scan_etokens(source):
        events.extend(machine.accept(etoken))
        if machine.failed:
            break

    if not machine.complete and not machine.failed:
        events.extend(machine.fail("Incomplete JSON value"))

    return machine, events


def schema_name(schema: Schema) -> str:
    return type(schema).__name__.removesuffix("Schema")
