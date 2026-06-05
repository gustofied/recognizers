from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum, auto

from recognizers.json_scanner import Scanner, Token, TokenType


class ETokenType(StrEnum):
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    COMMA = auto()
    COLON = auto()
    JKEY = auto()
    JSTR = auto()
    JNUM = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()


@dataclass(frozen=True)
class EToken:
    token_type: ETokenType
    value: object = None


class OtherKey:
    def __repr__(self) -> str:
        return "OTHER_KEY"


OTHER_KEY = OtherKey()


class Mode(StrEnum):
    START = auto()
    KEY = auto()
    COLON = auto()
    COMMA_ARRAY = auto()
    COMMA_OBJECT = auto()
    FINISHED = auto()


@dataclass
class Frame:
    kind: str
    count: int = 0


def make_key_mapper(known_keys: Iterable[str]) -> Callable[[str], object]:
    key_ids = {key: index for index, key in enumerate(known_keys)}
    return lambda key: key_ids.get(key, OTHER_KEY)


class ETokenStream:
    def __init__(self, key_mapper: Callable[[str], object] | None = None):
        self.key_mapper = key_mapper or (lambda key: key)
        self.mode = Mode.START
        self.stack: list[Frame] = []

    def read(self, token: Token) -> EToken | None:
        if token.token_type == TokenType.EOF:
            self.finish()
            return None

        match self.mode:
            case Mode.START:
                return self.read_start(token)
            case Mode.KEY:
                return self.read_key(token)
            case Mode.COLON:
                return self.read_colon(token)
            case Mode.COMMA_ARRAY:
                return self.read_comma_array(token)
            case Mode.COMMA_OBJECT:
                return self.read_comma_object(token)
            case Mode.FINISHED:
                raise ValueError("Unexpected token after complete JSON value", token)

    def read_start(self, token: Token) -> EToken:
        match token.token_type:
            case TokenType.LEFT_BRACKET:
                self.stack.append(Frame("array"))
                self.mode = Mode.START
                return EToken(ETokenType.LEFT_BRACKET, token.value)
            case TokenType.LEFT_BRACE:
                self.stack.append(Frame("object"))
                self.mode = Mode.KEY
                return EToken(ETokenType.LEFT_BRACE, token.value)
            case TokenType.RIGHT_BRACKET:
                frame = self.top_frame()
                if frame is None or frame.kind != "array" or frame.count != 0:
                    raise ValueError("Unexpected closing bracket")
                self.stack.pop()
                self.value_completion()
                return EToken(ETokenType.RIGHT_BRACKET, token.value)
            case TokenType.STRING:
                self.value_completion()
                return EToken(ETokenType.JSTR, token.value)
            case TokenType.NUMBER:
                self.value_completion()
                return EToken(ETokenType.JNUM, token.value)
            case TokenType.BOOLEAN:
                self.value_completion()
                token_type = ETokenType.TRUE if token.value else ETokenType.FALSE
                return EToken(token_type, token.value)
            case TokenType.NULL:
                self.value_completion()
                return EToken(ETokenType.NULL, token.value)
            case _:
                raise ValueError("Expected JSON value", token)

    def read_key(self, token: Token) -> EToken:
        match token.token_type:
            case TokenType.RIGHT_BRACE:
                frame = self.top_frame()
                if frame is None or frame.kind != "object" or frame.count != 0:
                    raise ValueError("Unexpected closing brace")
                self.stack.pop()
                self.value_completion()
                return EToken(ETokenType.RIGHT_BRACE, token.value)
            case TokenType.STRING:
                self.mode = Mode.COLON
                return EToken(ETokenType.JKEY, self.key_mapper(str(token.value)))
            case _:
                raise ValueError("Expected object key", token)

    def read_colon(self, token: Token) -> EToken:
        if token.token_type != TokenType.COLON:
            raise ValueError("Expected colon after object key", token)
        self.mode = Mode.START
        return EToken(ETokenType.COLON, token.value)

    def read_comma_array(self, token: Token) -> EToken:
        match token.token_type:
            case TokenType.RIGHT_BRACKET:
                frame = self.top_frame()
                if frame is None or frame.kind != "array":
                    raise ValueError("Unexpected closing bracket")
                self.stack.pop()
                self.value_completion()
                return EToken(ETokenType.RIGHT_BRACKET, token.value)
            case TokenType.COMMA:
                self.mode = Mode.START
                return EToken(ETokenType.COMMA, token.value)
            case _:
                raise ValueError("Expected comma or closing bracket", token)

    def read_comma_object(self, token: Token) -> EToken:
        match token.token_type:
            case TokenType.RIGHT_BRACE:
                frame = self.top_frame()
                if frame is None or frame.kind != "object":
                    raise ValueError("Unexpected closing brace")
                self.stack.pop()
                self.value_completion()
                return EToken(ETokenType.RIGHT_BRACE, token.value)
            case TokenType.COMMA:
                self.mode = Mode.KEY
                return EToken(ETokenType.COMMA, token.value)
            case _:
                raise ValueError("Expected comma or closing brace", token)

    def value_completion(self) -> None:
        frame = self.top_frame()
        if frame is None:
            self.mode = Mode.FINISHED
            return

        frame.count += 1
        self.mode = Mode.COMMA_ARRAY if frame.kind == "array" else Mode.COMMA_OBJECT

    def finish(self) -> None:
        if self.mode != Mode.FINISHED or self.stack:
            raise ValueError("Incomplete JSON value")

    def top_frame(self) -> Frame | None:
        return self.stack[-1] if self.stack else None


def etokens_from_tokens(
    tokens: Iterable[Token],
    key_mapper: Callable[[str], object] | None = None,
) -> list[EToken]:
    stream = ETokenStream(key_mapper)
    etokens: list[EToken] = []
    saw_eof = False

    for token in tokens:
        saw_eof = saw_eof or token.token_type == TokenType.EOF
        etoken = stream.read(token)
        if etoken is not None:
            etokens.append(etoken)

    if not saw_eof:
        stream.finish()

    return etokens


def scan_etokens(
    source: str,
    key_mapper: Callable[[str], object] | None = None,
) -> list[EToken]:
    return etokens_from_tokens(Scanner(source).scan(), key_mapper)
