import json

from recognizers.json_compiler import compile_schema
from recognizers.json_etokens import scan_etokens
from recognizers.json_generator import generate_json
from recognizers.json_machine import validate_json, validate_json_compiled
from recognizers.json_machine_events import total_reward
from recognizers.json_scanner import Scanner
from recognizers.json_schema_importer import schema_from_json_schema


RAW_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["points"],
    "additionalProperties": False,
}

SOURCE = '{"points":[{"x":1.0,"y":1.0},{"y":2.5,"x":4.0}]}'
BAD_SOURCE = '{"points":[{"x":1.0}]}'


def main() -> None:
    schema = schema_from_json_schema(RAW_JSON_SCHEMA)
    compiled = compile_schema(schema)

    print_title("raw JSON Schema")
    print(json.dumps(RAW_JSON_SCHEMA, indent=2))

    print_title("IR")
    print(schema)

    print_title("compiled key table")
    for key_id, key in enumerate(compiled.key_table.keys):
        print(f"{key_id}: {key}")

    print_title("scanner tokens")
    for token in Scanner(SOURCE).scan():
        print(token)

    print_title("e-tokens with compiled key IDs")
    for etoken in scan_etokens(SOURCE, compiled.key_mapper):
        print(etoken)

    print_title("validate with string-key semantic machine")
    machine, events = validate_json(SOURCE, schema)
    print_validation(machine.valid, machine.reward, events)

    print_title("validate with compiled key-id/bitmask machine")
    machine, events = validate_json_compiled(SOURCE, compiled)
    print_validation(machine.valid, machine.reward, events)

    print_title("bad JSON against compiled machine")
    machine, events = validate_json_compiled(BAD_SOURCE, compiled)
    print_validation(machine.valid, machine.reward, events)

    print_title("generated valid JSON")
    generated = generate_json(schema, array_length=2, indent=2)
    print(generated)

    print_title("generated JSON validates")
    machine, events = validate_json_compiled(generated, compiled)
    print_validation(machine.valid, machine.reward, events)


def print_title(title: str) -> None:
    print()
    print(f"=== {title} ===")


def print_validation(valid: bool, final_reward: int, events) -> None:
    print(f"valid: {valid}")
    print(f"final reward: {final_reward}")
    print(f"event reward: {total_reward(events)}")
    for event in events:
        print(event)


if __name__ == "__main__":
    main()
