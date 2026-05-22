# inspo , and mosaci  by https://ivanleo.com/blog/why-constrained-decoding and his series Structured Outputs From Scratch

from pydantic import BaseModel
from typing import List, Optional, Literal, Union, Any
import json
import hashlib

class User(BaseModel):
    name: str
    age: int

adam = User(name="Adam", age=20)

adam_schema = User.model_json_schema()



class Address(BaseModel):
    city: str
    country: str

class User(BaseModel):
    name: str
    age: int
    address: Address

schema = User.model_json_schema()

# print(schema)
print(json.dumps(schema, indent=2))

# Primitives for JSON validation
STRING_PATTERN = r'"([^"\\]|\\.)*"'
INTEGER_PATTERN = r"-?(0|[1-9][0-9]*)"
NUMBER_PATTERN = r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?"
BOOLEAN_PATTERN = r"(true|false)"
NULL_PATTERN = r"null"
WS = r"[ \t\n\r]*" # Whitespace

import re

# Assemble the pieces to match the User structure
full_pattern = (
    f"\\{{{WS}"   # Match the opening brace and whitespace
    f'"name"{WS}:{WS}{STRING_PATTERN}{WS},{WS}'  # "name" key-value pair, plus a comma
    f'"age"{WS}:{WS}{INTEGER_PATTERN}{WS}'      # "age" key-value pair
    f"\\}}"  # Match the closing brace
)

# Now, let's test it. We use `re.fullmatch` to ensure the *entire* string conforms.
valid_json = '{"name": "Ivan", "age": 29}'
invalid_json = '{"name": "Ivan"}' # Missing "age" field

print(f"Matching valid JSON:   {bool(re.fullmatch(full_pattern, valid_json))}")
print(f"Matching invalid JSON: {bool(re.fullmatch(full_pattern, invalid_json))}")


# (Primitive patterns from above are assumed to be defined here)

def pydantic_to_regex(pydantic_model: type[BaseModel]) -> str:
    """
    Takes a Pydantic model and returns a regex pattern that validates a
    JSON string representation of it.
    """
    json_schema = pydantic_model.model_json_schema()
    # Pydantic places schemas for nested models in `$defs`. We pass this
    # lookup dictionary through our recursive calls.
    defs = json_schema.get("$defs", {})
    return _schema_to_regex(json_schema, defs)

def _schema_to_regex(schema: dict, defs: dict) -> str:
    # Handle $ref for nested models by replacing the reference with its definition.
    if "$ref" in schema:
        definition_key = schema["$ref"].split("/")[-1]
        return _schema_to_regex(defs[definition_key], defs)

    # Handle Union types (anyOf) with a regex OR.
    if "anyOf" in schema:
        options = [_schema_to_regex(s, defs) for s in schema["anyOf"]]
        return f"({'|'.join(options)})"

    # Handle Literal types (enum).
    if "enum" in schema:
        literals = []
        for v in schema["enum"]:
            if isinstance(v, str):
                literals.append('"' + re.escape(v) + '"')
            elif isinstance(v, (int, float, bool)) or v is None:
                literals.append(re.escape(str(v).lower()))
        return f"({'|'.join(literals)})"

    prop_type = schema.get("type")

    # --- Base Cases: Primitive Types ---
    if prop_type == "string": return STRING_PATTERN
    if prop_type == "integer": return INTEGER_PATTERN
    if prop_type == "number": return NUMBER_PATTERN
    if prop_type == "boolean": return BOOLEAN_PATTERN
    if prop_type == "null": return NULL_PATTERN

    # --- Recursive Cases: Complex Types ---
    if prop_type == "array":
        items_regex = _schema_to_regex(schema["items"], defs)
        # An array is either empty `[]` or has one or more comma-separated items.
        empty = rf"\[{WS}\]"
        non_empty = rf"\[{WS}{items_regex}(?:{WS},{WS}{items_regex})*{WS}\]"
        return f"(?:{empty}|{non_empty})"

    if prop_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Convert each property schema into a reusable key-value regex fragment.
        prop_patterns = {
            key: f'"{re.escape(key)}"{WS}:{WS}{_schema_to_regex(prop_schema, defs)}'
            for key, prop_schema in properties.items()
        }

        # Positive lookaheads enforce required fields regardless of field order.
        required_lookaheads = "".join(
            rf"(?=.*{prop_patterns[key]})" for key in required if key in prop_patterns
        )

        if not prop_patterns:
            return rf"\{{{WS}\}}"

        pair = f"(?:{'|'.join(prop_patterns.values())})"
        body = rf"{pair}(?:{WS},{WS}{pair})*"
        return rf"\{{{WS}{required_lookaheads}{body}{WS}\}}"

    raise NotImplementedError(f"Schema type '{prop_type}' not supported.")


class User(BaseModel):
    name: str
    age: int

class Data(BaseModel):
    users: list[User]

# Generate the pattern automatically!
pattern = pydantic_to_regex(Data)


# --- Test Cases ---
should_match = '{"users": [{"name": "Ivan", "age": 29}, {"name": "Jane", "age": 34}]}'
should_not_match = '{"users": [{"name": "Ivan"}]}' # Missing age
wrong_type = '{"users": [{"name": "Ivan", "age": "twenty"}]}' # Wrong type

print(pattern)

print(f"Match valid:         {bool(re.fullmatch(pattern, should_match))}")
print(f"No match incomplete: {bool(re.fullmatch(pattern, should_not_match))}")
print(f"No match wrong type: {bool(re.fullmatch(pattern, wrong_type))}")



patterns = [
    r"a+",
    r"aa*",
    r"a(a)*",
]

tests = ["aaa", "a"]

for s in tests:
    print(f"\nTesting: {s!r}")
    for p in patterns:
        ok = re.fullmatch(p, s) is not None
        print(f"  {p:<8} -> {ok}")


_SCHEMA_REGEX_CACHE: dict[str, str] = {}

def _hash_schema(schema: dict[str, Any]) -> str:
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def from_json_schema(schema: dict) -> str:
    schema_hash = _hash_schema(schema)
    regex = _SCHEMA_REGEX_CACHE.get(schema_hash)
    if regex is None:
        regex = schema_to_regex(schema)
        _SCHEMA_REGEX_CACHE[schema_hash] = regex
    return regex