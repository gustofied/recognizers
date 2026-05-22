# inspo: https://ivanleo.com/blog/why-constrained-decoding
#        https://ivanleo.com/blog/building-our-first-fsm
#        https://ivanleo.com/blog/compiling-ir-to-nfa-and-dfa
# Structured Outputs From Scratch — Ivan Leo

from __future__ import annotations
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel


# ════════════════════════════════════════════════════════════════════
#  Article 1 — Schema to Regex
# ════════════════════════════════════════════════════════════════════

STRING_PATTERN  = r'"([^"\\]|\\.)*"'
INTEGER_PATTERN = r"-?(0|[1-9][0-9]*)"
NUMBER_PATTERN  = r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?"
BOOLEAN_PATTERN = r"(true|false)"
NULL_PATTERN    = r"null"
WS              = r"[ \t\n\r]*"


def _schema_to_regex(schema: dict, defs: dict) -> str:
    if "$ref" in schema:
        return _schema_to_regex(defs[schema["$ref"].split("/")[-1]], defs)

    if "anyOf" in schema:
        return f"({'|'.join(_schema_to_regex(s, defs) for s in schema['anyOf'])})"

    if "enum" in schema:
        literals = []
        for v in schema["enum"]:
            if isinstance(v, str):
                literals.append('"' + re.escape(v) + '"')
            else:
                literals.append(re.escape(str(v).lower()))
        return f"({'|'.join(literals)})"

    prop_type = schema.get("type")

    if prop_type == "string":  return STRING_PATTERN
    if prop_type == "integer": return INTEGER_PATTERN
    if prop_type == "number":  return NUMBER_PATTERN
    if prop_type == "boolean": return BOOLEAN_PATTERN
    if prop_type == "null":    return NULL_PATTERN

    if prop_type == "array":
        items     = _schema_to_regex(schema["items"], defs)
        empty     = rf"\[{WS}\]"
        non_empty = rf"\[{WS}{items}(?:{WS},{WS}{items})*{WS}\]"
        return f"(?:{empty}|{non_empty})"

    if prop_type == "object":
        properties = schema.get("properties", {})
        required   = schema.get("required", [])

        prop_patterns = {
            key: f'"{re.escape(key)}"{WS}:{WS}{_schema_to_regex(prop, defs)}'
            for key, prop in properties.items()
        }

        if not prop_patterns:
            return rf"\{{{WS}\}}"

        lookaheads = "".join(
            rf"(?=.*{prop_patterns[k]})" for k in required if k in prop_patterns
        )
        pair = f"(?:{'|'.join(prop_patterns.values())})"
        body = rf"{pair}(?:{WS},{WS}{pair})*"
        return rf"\{{{WS}{lookaheads}{body}{WS}\}}"

    raise NotImplementedError(f"Schema type '{prop_type}' not supported.")


def pydantic_to_regex(model: type[BaseModel]) -> str:
    schema = model.model_json_schema()
    return _schema_to_regex(schema, schema.get("$defs", {}))


_SCHEMA_REGEX_CACHE: dict[str, str] = {}

def from_json_schema(schema: dict[str, Any]) -> str:
    key = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    if key not in _SCHEMA_REGEX_CACHE:
        _SCHEMA_REGEX_CACHE[key] = _schema_to_regex(schema, schema.get("$defs", {}))
    return _SCHEMA_REGEX_CACHE[key]


def matches(model: type[BaseModel], json_string: str) -> bool:
    return bool(re.fullmatch(pydantic_to_regex(model), json_string))


# ════════════════════════════════════════════════════════════════════
#  Article 2 — Regex to IR
# ════════════════════════════════════════════════════════════════════

CharClassKind = Literal[
    "DIGIT", "NOT_DIGIT",
    "WHITESPACE", "NOT_WHITESPACE",
    "WORD", "NOT_WORD",
    "ANY", "BRACKET",
]

@dataclass(frozen=True, slots=True)
class Lit:
    text: str

@dataclass(frozen=True, slots=True)
class CharClass:
    kind: CharClassKind
    pattern: str | None = None
    negated: bool = False

    def __post_init__(self):
        if self.kind == "BRACKET":
            if self.pattern is None:
                raise ValueError("pattern required for BRACKET")
            return
        if self.pattern is not None:
            raise ValueError("pattern only valid for BRACKET")
        if self.negated:
            raise ValueError("negated only valid for BRACKET")

@dataclass(frozen=True, slots=True)
class Seq:
    parts: tuple

@dataclass(frozen=True, slots=True)
class Alt:
    options: tuple

@dataclass(frozen=True, slots=True)
class Repeat:
    node: object
    min_times: int
    max_times: int | None

@dataclass(frozen=True, slots=True)
class Optional:
    node: object

@dataclass(frozen=True, slots=True)
class BraceQuantifier:
    min_times: int
    max_times: int | None
    next_index: int

Node = Lit | CharClass | Seq | Alt | Repeat | Optional


def _extract_group(pattern: str, group_start: int) -> tuple[str, int]:
    if group_start < 0 or group_start >= len(pattern) or pattern[group_start] != "(":
        raise ValueError("group_start must point at '('")
    depth = 1
    i = group_start + 1
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "(":   depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return pattern[group_start + 1 : i], i
        i += 1
    raise ValueError("Unclosed group in pattern")


def split_top_level_alternation(pattern: str) -> list[str]:
    parts: list[str] = []
    start = 0
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "(":
            _, end = _extract_group(pattern, i)
            i = end + 1
            continue
        if ch == ")":
            raise ValueError("Unbalanced ')' in pattern")
        if ch == "|":
            parts.append(pattern[start:i])
            start = i + 1
        i += 1
    if n > 0 and pattern[-1] == "\\":
        raise ValueError("Dangling escape at end of pattern")
    parts.append(pattern[start:])
    return parts


def _decode_escaped_literal(esc: str) -> str:
    return {"n": "\n", "t": "\t", "r": "\r", "f": "\f", "v": "\v"}.get(esc, esc)


def _resolve_char_class_body(body: str) -> str:
    i = 0
    while i < len(body):
        if body[i] == "\\" and i + 1 >= len(body):
            raise ValueError("Dangling escape inside character class")
        i += 2 if body[i] == "\\" else 1
    return body


def _extract_char_class(pattern: str, index: int) -> tuple[CharClass, int]:
    n = len(pattern)
    i = index + 1
    negated = False
    if i < n and pattern[i] == "^":
        negated = True
        i += 1
    start = i
    while i < n:
        if pattern[i] == "\\":
            i += 2
            continue
        if pattern[i] == "]":
            body = pattern[start:i]
            _resolve_char_class_body(body)
            return CharClass("BRACKET", pattern=body, negated=negated), i + 1
        i += 1
    raise ValueError("Unclosed character class")


def _parse_escape_atom_at(pattern: str, index: int) -> tuple[Node, int]:
    if index + 1 >= len(pattern):
        raise ValueError("Dangling escape at end of pattern")
    esc = pattern[index + 1]
    kinds = {
        "d": "DIGIT",      "D": "NOT_DIGIT",
        "s": "WHITESPACE", "S": "NOT_WHITESPACE",
        "w": "WORD",       "W": "NOT_WORD",
    }
    if esc in kinds:
        return CharClass(kinds[esc]), index + 2
    return Lit(_decode_escaped_literal(esc)), index + 2


def parse_atom_at(pattern: str, index: int) -> tuple[Node, int]:
    if index < 0 or index >= len(pattern):
        raise ValueError("index out of bounds")
    ch = pattern[index]
    if ch == ".":  return CharClass("ANY"), index + 1
    if ch == "\\": return _parse_escape_atom_at(pattern, index)
    if ch == "[":  return _extract_char_class(pattern, index)
    if ch == "(":
        inner, end = _extract_group(pattern, index)
        return regex_to_ir(inner), end + 1
    if ch == ")":
        raise ValueError("Unexpected ')' while parsing atom")
    return Lit(ch), index + 1


def _parse_brace_quantifier(pattern: str, index: int) -> BraceQuantifier:
    if index + 1 >= len(pattern):
        raise ValueError("Unclosed brace quantifier")
    close = pattern.find("}", index + 1)
    if close == -1:
        raise ValueError("Unclosed brace quantifier")
    inner = pattern[index + 1 : close]
    m = re.fullmatch(r"(\d+)(?:,(\d*))?", inner)
    if m is None:
        raise ValueError("Invalid brace quantifier format")
    min_times = int(m.group(1))
    g2 = m.group(2)
    if g2 is None:  return BraceQuantifier(min_times, min_times, close + 1)
    if g2 == "":    return BraceQuantifier(min_times, None, close + 1)
    max_times = int(g2)
    if max_times < min_times:
        raise ValueError("max bound must be >= min bound")
    return BraceQuantifier(min_times, max_times, close + 1)


def _apply_quantifier_at(node: Node, pattern: str, index: int) -> tuple[Node, int]:
    if index >= len(pattern):
        return node, index
    ch = pattern[index]
    if ch == "?": return Optional(node), index + 1
    if ch == "*": return Repeat(node, min_times=0, max_times=None), index + 1
    if ch == "+": return Repeat(node, min_times=1, max_times=None), index + 1
    if ch == "{":
        q = _parse_brace_quantifier(pattern, index)
        return Repeat(node, min_times=q.min_times, max_times=q.max_times), q.next_index
    return node, index


def _normalize_term(atoms: list[Node]) -> Node:
    if not atoms:
        return Lit("")
    merged: list[Node] = []
    lit_buf: list[str] = []

    def flush():
        if lit_buf:
            merged.append(Lit("".join(lit_buf)))
            lit_buf.clear()

    for node in atoms:
        if isinstance(node, Lit):
            lit_buf.append(node.text)
        else:
            flush()
            merged.append(node)
    flush()

    return merged[0] if len(merged) == 1 else Seq(tuple(merged))


def parse_term(pattern: str) -> Node:
    if pattern == "":
        return Lit("")
    atoms: list[Node] = []
    i = 0
    n = len(pattern)
    while i < n:
        node, i = parse_atom_at(pattern, i)
        node, i = _apply_quantifier_at(node, pattern, i)
        atoms.append(node)
    return _normalize_term(atoms)


def regex_to_ir(pattern: str) -> Node:
    parts = split_top_level_alternation(pattern)
    if len(parts) == 1:
        return parse_term(parts[0])
    return Alt(tuple(parse_term(p) for p in parts))


# ════════════════════════════════════════════════════════════════════
#  Article 3 — IR to NFA
# ════════════════════════════════════════════════════════════════════

StateId      = int
StateSet     = set[int]
TransitionMap = dict[int, list[tuple[object, int]]]
EpsilonMap   = dict[int, set[int]]


@dataclass(frozen=True, slots=True)
class Sym:
    value: str  # single character NFA symbol

# Symbol reuses CharClass from Article 2 for character class transitions


def _matches_symbol(symbol: object, char: str) -> bool:
    if isinstance(symbol, Sym):
        return symbol.value == char
    if isinstance(symbol, CharClass):
        if symbol.kind == "ANY":         return True
        if symbol.kind == "DIGIT":       return char.isdigit()
        if symbol.kind == "NOT_DIGIT":   return not char.isdigit()
        if symbol.kind == "WHITESPACE":  return char.isspace()
        if symbol.kind == "NOT_WHITESPACE": return not char.isspace()
        if symbol.kind == "WORD":        return char.isalnum() or char == "_"
        if symbol.kind == "NOT_WORD":    return not (char.isalnum() or char == "_")
        if symbol.kind == "BRACKET":
            expr = f"[^{symbol.pattern}]" if symbol.negated else f"[{symbol.pattern}]"
            return re.fullmatch(expr, char) is not None
    raise NotImplementedError(f"Unsupported symbol: {symbol}")


@dataclass(frozen=True, slots=True)
class Fragment:
    start: int
    end: int


@dataclass(slots=True)
class NFA:
    start_state: StateId
    final_states: StateSet
    transitions: TransitionMap
    epsilon: EpsilonMap
    _next_state: StateId

    def _new_state(self) -> StateId:
        s = self._next_state
        self._next_state += 1
        return s

    def add_transition(self, src: StateId, symbol: object, dst: StateId) -> None:
        self.transitions.setdefault(src, []).append((symbol, dst))

    def add_epsilon(self, src: StateId, dst: StateId) -> None:
        self.epsilon.setdefault(src, set()).add(dst)

    def epsilon_closure(self, states: StateSet) -> StateSet:
        closure = set(states)
        stack = list(states)
        while stack:
            src = stack.pop()
            for dst in self.epsilon.get(src, set()):
                if dst not in closure:
                    closure.add(dst)
                    stack.append(dst)
        return closure

    def step(self, states: StateSet, char: str) -> StateSet:
        if len(char) != 1:
            raise ValueError("step expects a single character")
        reached: StateSet = set()
        for src in self.epsilon_closure(states):
            for symbol, dst in self.transitions.get(src, []):
                if _matches_symbol(symbol, char):
                    reached.add(dst)
        return self.epsilon_closure(reached)

    def accepts(self, text: str) -> bool:
        states = self.epsilon_closure({self.start_state})
        for ch in text:
            states = self.step(states, ch)
            if not states:
                return False
        return bool(states)

    def _compile_node(self, ir: Node) -> Fragment:
        if isinstance(ir, Lit):          return self._compile_lit(ir)
        if isinstance(ir, Alt):          return self._compile_alt(ir)
        if isinstance(ir, Seq):          return self._compile_seq(ir)
        if isinstance(ir, CharClass):    return self._compile_char_class(ir)
        if isinstance(ir, Optional):     return self._compile_optional(ir)
        if isinstance(ir, Repeat):       return self._compile_repeat(ir)
        raise NotImplementedError(f"Unsupported IR node: {type(ir)}")

    def _compile_lit(self, lit: Lit) -> Fragment:
        if lit.text == "":
            start = end = self._new_state()
            return Fragment(start, end)
        prev = self._new_state()
        start = prev
        for ch in lit.text:
            nxt = self._new_state()
            self.add_transition(prev, Sym(ch), nxt)
            prev = nxt
        return Fragment(start, prev)

    def _compile_alt(self, alt: Alt) -> Fragment:
        start = self._new_state()
        frags = []
        for option in alt.options:
            frag = self._compile_node(option)
            frags.append(frag)
            self.add_epsilon(start, frag.start)
        end = self._new_state()
        for frag in frags:
            self.add_epsilon(frag.end, end)
        return Fragment(start, end)

    def _compile_seq(self, seq: Seq) -> Fragment:
        if not seq.parts:
            raise ValueError("Seq must have at least one part")
        parts = list(seq.parts)
        first = self._compile_node(parts[0])
        prev = first
        for node in parts[1:]:
            cur = self._compile_node(node)
            self.add_epsilon(prev.end, cur.start)
            prev = cur
        return Fragment(first.start, prev.end)

    def _compile_char_class(self, cc: CharClass) -> Fragment:
        start = self._new_state()
        end   = self._new_state()
        self.add_transition(start, cc, end)
        return Fragment(start, end)

    def _compile_optional(self, opt: Optional) -> Fragment:
        start = self._new_state()
        end   = self._new_state()
        frag  = self._compile_node(opt.node)
        self.add_epsilon(start, end)
        self.add_epsilon(start, frag.start)
        self.add_epsilon(frag.end, end)
        return Fragment(start, end)

    def _compile_repeat(self, repeat: Repeat) -> Fragment:
        start  = self._new_state()
        cursor = start

        for _ in range(repeat.min_times):
            frag = self._compile_node(repeat.node)
            self.add_epsilon(cursor, frag.start)
            cursor = frag.end

        end = self._new_state()

        if repeat.max_times is None:
            self.add_epsilon(cursor, end)
            loop = self._compile_node(repeat.node)
            self.add_epsilon(cursor, loop.start)
            self.add_epsilon(loop.end, cursor)
        else:
            for _ in range(repeat.max_times - repeat.min_times):
                self.add_epsilon(cursor, end)
                frag = self._compile_node(repeat.node)
                self.add_epsilon(cursor, frag.start)
                cursor = frag.end
            self.add_epsilon(cursor, end)

        return Fragment(start, end)


def ir_to_nfa(node: Node) -> NFA:
    nfa = NFA(
        start_state=0,
        final_states=set(),
        transitions={},
        epsilon={},
        _next_state=0,
    )
    frag = nfa._compile_node(node)
    nfa.start_state  = frag.start
    nfa.final_states = {frag.end}
    return nfa
