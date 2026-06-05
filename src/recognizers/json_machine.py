from __future__ import annotations

from dataclasses import dataclass, field

from recognizers.json_compiler import (
    CompiledAnySchema,
    CompiledArrSchema,
    CompiledBoolSchema,
    CompiledJsonSchema,
    CompiledNullSchema,
    CompiledNumSchema,
    CompiledObjSchema,
    CompiledSchema,
    CompiledStrSchema,
    bit_for,
)
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
    schema: ArrSchema | AnySchema | CompiledArrSchema | CompiledAnySchema


@dataclass
class ObjectFrame:
    schema: ObjSchema | AnySchema | CompiledObjSchema | CompiledAnySchema
    seen_keys: set[str] = field(default_factory=set)
    completed_keys: set[str] = field(default_factory=set)
    seen_mask: int = 0
    completed_mask: int = 0
    current_key: str | int | None = None


Frame = ArrayFrame | ObjectFrame


class JsonSchemaMachine:
    def __init__(
        self,
        schema: Schema | CompiledSchema,
        key_names: tuple[str, ...] = (),
    ):
        self.root_schema = schema
        self.value_expected: Schema | CompiledSchema | None = schema
        self.key_names = key_names
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
        if isinstance(schema, AnySchema | CompiledAnySchema):
            self.stack.append(ObjectFrame(schema))
        elif isinstance(schema, ObjSchema | CompiledObjSchema):
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
            missing = frame.schema.required - frame.completed_keys
            if missing:
                return self.fail(f"Missing required keys: {sorted(missing)}")
        elif isinstance(frame.schema, CompiledObjSchema):
            missing_mask = frame.schema.required_mask & ~frame.completed_mask
            if missing_mask:
                return self.fail(
                    f"Missing required keys: {self.names_for_mask(missing_mask)}"
                )

        events.append(Event(EventType.OBJECT_COMPLETE, "Object complete"))
        events.extend(self.complete_value())
        return events

    def open_array(self) -> list[Event]:
        schema = self.expected_value_schema()
        if isinstance(schema, AnySchema | CompiledAnySchema):
            self.stack.append(ArrayFrame(schema))
        elif isinstance(schema, ArrSchema | CompiledArrSchema):
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

        if isinstance(frame.schema, CompiledAnySchema | CompiledObjSchema):
            return self.accept_compiled_key(frame, key)

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

    def accept_compiled_key(self, frame: ObjectFrame, key: object) -> list[Event]:
        if isinstance(key, int):
            key_bit = bit_for(key)
            if frame.seen_mask & key_bit:
                return self.fail(f"Duplicate object key: {self.key_name(key)!r}", key)
            frame.seen_mask |= key_bit
        elif key is not OTHER_KEY:
            return self.fail("Expected compiled key id", key)

        if (
            isinstance(frame.schema, CompiledObjSchema)
            and not frame.schema.additional
            and (not isinstance(key, int) or key not in frame.schema.properties)
        ):
            return self.fail(f"Unknown key not allowed: {self.key_name(key)!r}", key)

        frame.current_key = key if isinstance(key, int) else None
        self.value_expected = self.schema_for_key(frame, key)
        return [Event(EventType.KEY_SEEN, f"Key seen: {self.key_name(key)!r}", key)]

    def accept_primitive(self, etoken: EToken) -> list[Event]:
        schema = self.expected_value_schema()
        if not self.matches_primitive(schema, etoken):
            return self.fail(
                f"Expected {schema_name(schema)}, got {etoken.token_type.value}",
                etoken.value,
            )

        return self.complete_value(etoken.value)

    def schema_for_key(self, frame: ObjectFrame, key: object) -> Schema | CompiledSchema:
        if isinstance(frame.schema, AnySchema):
            return AnySchema()
        if isinstance(frame.schema, CompiledAnySchema):
            return CompiledAnySchema()

        if isinstance(key, str) and key in frame.schema.properties:
            return frame.schema.properties[key]
        if (
            isinstance(frame.schema, CompiledObjSchema)
            and isinstance(key, int)
            and key in frame.schema.properties
        ):
            return frame.schema.properties[key]

        if frame.schema.additional:
            if isinstance(frame.schema, CompiledObjSchema):
                return CompiledAnySchema()
            return AnySchema()

        return AnySchema()

    def expected_value_schema(self) -> Schema | CompiledSchema:
        if self.value_expected is not None:
            return self.value_expected

        frame = self.top_frame()
        if isinstance(frame, ArrayFrame):
            if isinstance(frame.schema, ArrSchema | CompiledArrSchema):
                return frame.schema.item
            if isinstance(frame.schema, CompiledAnySchema):
                return CompiledAnySchema()
            return AnySchema()

        return AnySchema()

    def matches_primitive(self, schema: Schema | CompiledSchema, etoken: EToken) -> bool:
        if isinstance(schema, AnySchema | CompiledAnySchema):
            return True
        if isinstance(schema, StrSchema | CompiledStrSchema):
            return etoken.token_type == ETokenType.JSTR
        if isinstance(schema, NumSchema | CompiledNumSchema):
            return etoken.token_type == ETokenType.JNUM
        if isinstance(schema, BoolSchema | CompiledBoolSchema):
            return etoken.token_type in {ETokenType.TRUE, ETokenType.FALSE}
        if isinstance(schema, NullSchema | CompiledNullSchema):
            return etoken.token_type == ETokenType.NULL
        return False

    def complete_value(self, value: object = None) -> list[Event]:
        events: list[Event] = []
        parent = self.top_frame()

        if parent is None:
            self.complete = True
            self.valid = True
            self.value_expected = None
            return [
                Event(
                    EventType.VALID_COMPLETE,
                    "JSON value satisfies schema",
                    value,
                    reward=1.0,
                )
            ]

        if isinstance(parent, ArrayFrame):
            self.value_expected = None
            return [Event(EventType.ARRAY_ELEMENT_COMPLETE, "Array element complete", value)]

        key = parent.current_key
        reward = self.field_reward(parent, key)
        if isinstance(parent.schema, CompiledObjSchema) and isinstance(key, int):
            parent.completed_mask |= bit_for(key)
        elif key is not None:
            parent.completed_keys.add(key)
        parent.current_key = None
        self.value_expected = None
        key_display = self.key_name(key)
        events.append(
            Event(
                EventType.FIELD_COMPLETE,
                f"Field complete: {key_display!r}",
                key,
                reward=reward,
            )
        )
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
        return [Event(EventType.ERROR, message, value, reward=-1.0)]

    def field_reward(self, frame: ObjectFrame, key: str | int | None) -> float:
        if key is None:
            return 0.0
        if isinstance(frame.schema, ObjSchema):
            return 1.0 if isinstance(key, str) and key in frame.schema.required else 0.0
        if isinstance(frame.schema, CompiledObjSchema):
            return (
                1.0
                if isinstance(key, int) and frame.schema.required_mask & bit_for(key)
                else 0.0
            )
        return 0.0

    def key_name(self, key: object) -> object:
        if isinstance(key, int) and key < len(self.key_names):
            return self.key_names[key]
        return key

    def names_for_mask(self, mask: int) -> list[str]:
        return [name for key_id, name in enumerate(self.key_names) if mask & bit_for(key_id)]


def validate_json(source: str, schema: Schema) -> tuple[JsonSchemaMachine, list[Event]]:
    machine = JsonSchemaMachine(schema)
    events: list[Event] = []

    # First prototype intentionally uses string keys. json_compiler.py will switch
    # this path to integer key IDs and bit masks later.
    try:
        for etoken in scan_etokens(source, key_mapper=lambda key: key):
            events.extend(machine.accept(etoken))
            if machine.failed:
                break
    except ValueError as error:
        events.extend(machine.fail(str(error)))
        return machine, events

    if not machine.complete and not machine.failed:
        events.extend(machine.fail("Incomplete JSON value"))

    return machine, events


def validate_json_compiled(
    source: str,
    compiled: CompiledJsonSchema,
) -> tuple[JsonSchemaMachine, list[Event]]:
    machine = JsonSchemaMachine(compiled.root, key_names=compiled.key_table.keys)
    events: list[Event] = []

    try:
        for etoken in scan_etokens(source, key_mapper=compiled.key_mapper):
            events.extend(machine.accept(etoken))
            if machine.failed:
                break
    except ValueError as error:
        events.extend(machine.fail(str(error)))
        return machine, events

    if not machine.complete and not machine.failed:
        events.extend(machine.fail("Incomplete JSON value"))

    return machine, events


def schema_name(schema: Schema) -> str:
    return type(schema).__name__.removeprefix("Compiled").removesuffix("Schema")
