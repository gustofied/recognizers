"""JSON text scanner."""

from types import NoneType
from enum import StrEnum, auto
import json

type JsonValue = JsonObject | JsonArray | str | int | float | bool | NoneType
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]

class TokenType(StrEnum): 
    STRING = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    NULL = auto()

    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    COMMA = auto()
    COLON = auto()
    EOF = auto()

class Token:
    def __init__(self, token_type: TokenType, value: object):
        self.token_type = token_type
        self.value = value

    def __repr__(self):
        return f"Token({self.token_type}, {self.value!r})"

class Scanner:
    tokens: list[Token]

    def __init__(self, source: str):
        self.source = source
        self.start = 0
        self.tokens = []
        self.current = 0
        self.line = 1

    def scan(self) -> list[Token]:
        while not self.is_at_end():
            self.start = self.current
            self.scan_token()

        self.tokens.append(Token(TokenType.EOF, None))
        return self.tokens

    def is_at_end(self):
        return self.current >= len(self.source)

    def scan_token(self):
        c = self.advance()
        match c:
            case "{":
                self.tokens.append(Token(TokenType.LEFT_BRACE, c))
            case "}":
                self.tokens.append(Token(TokenType.RIGHT_BRACE, c))
            case "[":
                self.tokens.append(Token(TokenType.LEFT_BRACKET, c))
            case "]":
                self.tokens.append(Token(TokenType.RIGHT_BRACKET, c))
            case ",":
                self.tokens.append(Token(TokenType.COMMA, c))
            case ":":
                self.tokens.append(Token(TokenType.COLON, c))
            case "\n":
                self.line += 1
            case " " | "\t" | "\r":
                pass
            case '"':
                self.add_string()
            case "-":
                if self.is_digit(self.peek()):
                    self.add_number()
                else:
                    raise ValueError("- must be followed by a number")
            case _:
                if self.is_digit(c):
                    self.add_number()
                elif c.isalpha():
                    self.add_keyword()
                else:
                    raise ValueError("Unexpected token", c, self.line)

    def advance(self) -> str:
        c = self.source[self.current]
        self.current += 1
        return c

    def add_string(self):
        while not self.is_at_end():
            c = self.advance()
            if c == '"':
                literal = self.source[self.start : self.current]
                try:
                    value = json.loads(literal)
                except json.JSONDecodeError as error:
                    raise ValueError("Invalid string", self.line, literal) from error
                self.tokens.append(Token(TokenType.STRING, value))
                return
            if c == "\\":
                if self.is_at_end():
                    break
                self.advance()
            elif ord(c) < 0x20:
                raise ValueError("Control character in string", self.line)

        raise ValueError("Unterminated string", self.line)

    def add_number(self):
        if self.source[self.start] == "-":
            first_digit = self.peek()
            self.advance()
        else:
            first_digit = self.source[self.start]

        if first_digit == "0":
            if self.is_digit(self.peek()):
                raise ValueError("Leading zero in number", self.line)
        else:
            while self.is_digit(self.peek()):
                self.advance()

        if self.peek() == ".":
            if not self.is_digit(self.peek_next()):
                raise ValueError("Expected digit after . (trying to parse float)")

            self.advance()

            while self.is_digit(self.peek()):
                self.advance()

        if self.peek() in ("e", "E"):
            self.advance()
            if self.peek() in ("+", "-"):
                self.advance()
            if not self.is_digit(self.peek()):
                raise ValueError("Expected digit in number exponent", self.line)
            while self.is_digit(self.peek()):
                self.advance()

        literal = self.source[self.start : self.current]
        value = float(literal) if any(c in literal for c in ".eE") else int(literal)
        self.tokens.append(Token(TokenType.NUMBER, value))

    def add_keyword(self):
        while self.peek().isalpha():
            self.advance()

        keyword = self.source[self.start : self.current]
        match keyword:
            case "true":
                token = Token(TokenType.BOOLEAN, True)
            case "false":
                token = Token(TokenType.BOOLEAN, False)
            case "null":
                token = Token(TokenType.NULL, None)
            case _:
                raise ValueError("Unexpected token", self.line, keyword)
        
        self.tokens.append(token)

    def peek(self) -> str:
        if self.is_at_end():
            return ""

        return self.source[self.current]

    def peek_next(self) -> str:
        if self.current + 1 >= len(self.source):
            return ""

        return self.source[self.current + 1]

    def is_digit(self, c: str) -> bool:
        return "0" <= c <= "9" if c else False


if __name__ == "__main__":
    lexed = Scanner('{"name": "Adam"}').scan()
    print(lexed)
# def parse(input: str) -> JsonValue:
#     pass
