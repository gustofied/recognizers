<p align="center">
  <img src="banner.png" width="600" />
  <br/>
  <sub><sup>screenshot from <a href="https://www.youtube.com/watch?v=tjX9Tg8l-w8">Languages and Formal Grammars</a> by Prof Ross</sup></sub>
</p>

# Recognizers

| Article                                                                                                             | Code                                             | Date       |
| ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ---------- |
| [Foundations: Language, Automata and Recognizers](https://www.adamsioud.com/exemplars/recognizers/foundations.html) | [foundations.py](src/recognizers/foundations.py) | 1 Mar 2026 |

---

The goal of this project is to take a JSON schema and automatically build an automaton that can validate documents against it.

The pipeline starts with `json_scanner.py`, which reads raw JSON and turns it into a stream of tokens. The next layer is `json_etokens.py`, which enriches those tokens into JSON e-tokens: object-key strings become `JKEY`, string values become `JSTR`, and numbers become `JNUM`. This gives the automaton a finite alphabet to work with while preserving the key/value distinction that matters for schemas.

Plain VPAs are a useful first mental model because JSON nesting is visible in the tokens: `{` and `[` push onto the stack, `}` and `]` pop, and primitives are internal symbols. But the VLDB paper "Streaming Validation of JSON Documents Against Schemas" points out the catch: object fields are unordered, so a plain VPA can blow up when it tries to encode all key permutations. The better target is a JSON automaton: a pushdown-style machine that also tracks the set of keys seen in the current object, usually as a bit vector on the stack.

The first prototype uses `json_ir.py` as a tiny internal schema language and `json_machine.py` as a semantic validator:

```python
from recognizers.json_ir import NumSchema, ObjSchema, StrSchema
from recognizers.json_machine import validate_json

schema = ObjSchema(
    properties={"name": StrSchema(), "age": NumSchema()},
    required={"name", "age"},
    additional=False,
)

machine, events = validate_json('{"name":"Adam","age":31}', schema)
print(machine.valid, machine.reward)
```

This first machine intentionally uses string keys. The next compiler layer will convert schema keys into integer IDs and bit masks, which is the version that starts looking like the paper's JSON automata.

Eventually, the automaton should be constructed directly from the schema, not written by hand.

Once you have that, three things follow. You can validate documents symbol by symbol as they stream in, without loading the whole thing first. You can generate valid documents from the schema, which gives you training data for free. And you can use the automaton as a reward signal: the model produces a tool call, the automaton checks if it matches the schema, and that yes or no is the reward. The same schema you already write to define a tool becomes the thing that trains the model on it.
