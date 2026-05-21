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

The pipeline has two steps. First a scanner reads raw JSON and turns it into a stream of tokens, mapping concrete values to abstract types: strings become `\S`, numbers become `\D`, integers become `\I`. This gives the automaton a finite alphabet to work with. Then a VPA (visibly pushdown automaton) reads that token stream and accepts or rejects it. The VPA is the right machine for JSON because the nesting structure is visible in the tokens: `{` and `[` always push onto the stack, `}` and `]` always pop, and everything else is an internal symbol that leaves the stack alone.

The automaton is constructed directly from the schema, not written by hand.

Once you have that, three things follow. You can validate documents symbol by symbol as they stream in, without loading the whole thing first. You can generate valid documents from the schema, which gives you training data for free. And you can use the automaton as a reward signal: the model produces a tool call, the automaton checks if it matches the schema, and that yes or no is the reward. The same schema you already write to define a tool becomes the thing that trains the model on it.
