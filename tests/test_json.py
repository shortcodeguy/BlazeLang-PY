import unittest

from blazelang.errors.error_handler import JSONError
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.interpreter.interpreter import Interpreter
from blazelang.stdlib.json import JsonLibrary


class JsonTests(unittest.TestCase):
    def test_parse_stringify_pretty_and_validate(self):
        library = JsonLibrary()
        value = library.parse('{"name":"Rohit","age":13}')
        self.assertEqual(value["name"], "Rohit")
        self.assertEqual(library.stringify(value), '{"name":"Rohit","age":13}')
        self.assertIn('\n    "name": "Rohit"', library.pretty(value))
        self.assertTrue(library.validate('{"ok":true}'))
        self.assertFalse(library.validate('{invalid json}'))

    def test_parse_error_has_stable_code_and_json_location(self):
        with self.assertRaises(JSONError) as raised:
            JsonLibrary().parse('{invalid json}')
        self.assertEqual(raised.exception.code, "BLZ6001")
        self.assertEqual(raised.exception.json_line, 1)

    def test_default_and_namespace_imports(self):
        source = '''
        Import Json from "json"
        Import * as Data from "json"
        var object = Json.Parse("{\\"ok\\":true}")
        var text = Data.Stringify(object)
        '''
        program = Parser(Lexer(source, "json_test.blz").tokenize()).parse()
        interpreter = Interpreter(filename="json_test.blz")
        interpreter.interpret(program)
        self.assertTrue(interpreter.global_scope["object"]["value"]["ok"])
        self.assertEqual(interpreter.global_scope["text"]["value"], '{"ok":true}')


if __name__ == "__main__":
    unittest.main()
