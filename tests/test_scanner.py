import unittest

from recognizers.scanner import Scanner, TokenType


class ScannerTests(unittest.TestCase):
    def token_values(self, source: str) -> list[tuple[TokenType, object]]:
        return [(token.token_type, token.value) for token in Scanner(source).scan()]

    def test_scans_object(self):
        self.assertEqual(
            self.token_values('{"name": "Adam"}'),
            [
                (TokenType.LEFT_BRACE, "{"),
                (TokenType.STRING, "name"),
                (TokenType.COLON, ":"),
                (TokenType.STRING, "Adam"),
                (TokenType.RIGHT_BRACE, "}"),
                (TokenType.EOF, None),
            ],
        )

    def test_scans_array_literals(self):
        self.assertEqual(
            self.token_values('["a", 1, true, false, null]'),
            [
                (TokenType.LEFT_BRACKET, "["),
                (TokenType.STRING, "a"),
                (TokenType.COMMA, ","),
                (TokenType.NUMBER, 1),
                (TokenType.COMMA, ","),
                (TokenType.BOOLEAN, True),
                (TokenType.COMMA, ","),
                (TokenType.BOOLEAN, False),
                (TokenType.COMMA, ","),
                (TokenType.NULL, None),
                (TokenType.RIGHT_BRACKET, "]"),
                (TokenType.EOF, None),
            ],
        )

    def test_decodes_string_escapes(self):
        tokens = Scanner(r'{"quote": "hello \"Adam\""}').scan()
        self.assertEqual(tokens[3].value, 'hello "Adam"')

    def test_scans_exponent_number(self):
        tokens = Scanner('{"n": -3.5e-2}').scan()
        self.assertEqual(tokens[3].value, -0.035)

    def test_rejects_invalid_literals(self):
        invalid = ['{"n": 012}', '{"x": "unterminated}', '{"x": tru}']
        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    Scanner(source).scan()

if __name__ == "__main__":
    unittest.main()
