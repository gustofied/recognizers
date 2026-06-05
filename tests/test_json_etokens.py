import unittest

from recognizers.json_etokens import (
    EToken,
    ETokenType,
    OTHER_KEY,
    etokens_from_tokens,
    make_key_mapper,
    scan_etokens,
)
from recognizers.json_scanner import Token, TokenType


class JsonEventTests(unittest.TestCase):
    def token_values(self, source: str) -> list[tuple[ETokenType, object]]:
        return [(token.token_type, token.value) for token in scan_etokens(source)]

    def test_marks_object_strings_as_keys(self):
        self.assertEqual(
            self.token_values('{"name": "Adam"}'),
            [
                (ETokenType.LEFT_BRACE, "{"),
                (ETokenType.JKEY, "name"),
                (ETokenType.COLON, ":"),
                (ETokenType.JSTR, "Adam"),
                (ETokenType.RIGHT_BRACE, "}"),
            ],
        )

    def test_marks_array_values_without_keys(self):
        self.assertEqual(
            self.token_values('["a", 1, true, false, null]'),
            [
                (ETokenType.LEFT_BRACKET, "["),
                (ETokenType.JSTR, "a"),
                (ETokenType.COMMA, ","),
                (ETokenType.JNUM, 1),
                (ETokenType.COMMA, ","),
                (ETokenType.TRUE, True),
                (ETokenType.COMMA, ","),
                (ETokenType.FALSE, False),
                (ETokenType.COMMA, ","),
                (ETokenType.NULL, None),
                (ETokenType.RIGHT_BRACKET, "]"),
            ],
        )

    def test_accepts_top_level_primitives_and_empty_containers(self):
        self.assertEqual(self.token_values("null"), [(ETokenType.NULL, None)])
        self.assertEqual(
            self.token_values("[]"),
            [(ETokenType.LEFT_BRACKET, "["), (ETokenType.RIGHT_BRACKET, "]")],
        )
        self.assertEqual(
            self.token_values("{}"),
            [(ETokenType.LEFT_BRACE, "{"), (ETokenType.RIGHT_BRACE, "}")],
        )

    def test_maps_known_keys_to_ids_and_unknown_to_other(self):
        key_mapper = make_key_mapper(["x", "y"])
        tokens = scan_etokens('{"x": 1, "z": 2, "y": 3}', key_mapper)

        self.assertEqual(tokens[1], EToken(ETokenType.JKEY, 0))
        self.assertIs(tokens[5].value, OTHER_KEY)
        self.assertEqual(tokens[9], EToken(ETokenType.JKEY, 1))

    def test_maps_keys_independent_of_object_order(self):
        key_mapper = make_key_mapper(["name", "age"])

        self.assertEqual(
            self.token_values_with_mapper('{"name":"Adam","age":31}', key_mapper),
            [
                (ETokenType.LEFT_BRACE, "{"),
                (ETokenType.JKEY, 0),
                (ETokenType.COLON, ":"),
                (ETokenType.JSTR, "Adam"),
                (ETokenType.COMMA, ","),
                (ETokenType.JKEY, 1),
                (ETokenType.COLON, ":"),
                (ETokenType.JNUM, 31),
                (ETokenType.RIGHT_BRACE, "}"),
            ],
        )
        self.assertEqual(
            self.token_values_with_mapper('{"age":31,"name":"Adam"}', key_mapper),
            [
                (ETokenType.LEFT_BRACE, "{"),
                (ETokenType.JKEY, 1),
                (ETokenType.COLON, ":"),
                (ETokenType.JNUM, 31),
                (ETokenType.COMMA, ","),
                (ETokenType.JKEY, 0),
                (ETokenType.COLON, ":"),
                (ETokenType.JSTR, "Adam"),
                (ETokenType.RIGHT_BRACE, "}"),
            ],
        )

    def test_maps_unknown_key_to_other(self):
        key_mapper = make_key_mapper(["name", "age"])
        tokens = scan_etokens('{"unknown": true}', key_mapper)

        self.assertIs(tokens[1].value, OTHER_KEY)
        self.assertEqual(tokens[3], EToken(ETokenType.TRUE, True))

    def test_accepts_nested_empty_array_value(self):
        key_mapper = make_key_mapper(["x"])

        self.assertEqual(
            self.token_values_with_mapper('{"x":[]}', key_mapper),
            [
                (ETokenType.LEFT_BRACE, "{"),
                (ETokenType.JKEY, 0),
                (ETokenType.COLON, ":"),
                (ETokenType.LEFT_BRACKET, "["),
                (ETokenType.RIGHT_BRACKET, "]"),
                (ETokenType.RIGHT_BRACE, "}"),
            ],
        )

    def test_rejects_malformed_json_shapes(self):
        invalid = [
            "",
            '{"x":}',
            "[1,]",
            '{"x": 1,}',
            '{"x" 1}',
            '{"x": 1} {"y": 2}',
            '{["x"]: 1}',
            "[}",
            "{]",
            "[1}",
            '{"x":1]',
            '{"x":[}]}',
        ]

        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    scan_etokens(source)

    def test_rejects_unfinished_token_stream_without_eof(self):
        with self.assertRaises(ValueError):
            etokens_from_tokens([Token(TokenType.LEFT_BRACE, "{")])

    def token_values_with_mapper(
        self,
        source: str,
        key_mapper,
    ) -> list[tuple[ETokenType, object]]:
        return [
            (token.token_type, token.value)
            for token in scan_etokens(source, key_mapper)
        ]


if __name__ == "__main__":
    unittest.main()
