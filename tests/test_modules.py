import unittest
from pathlib import Path

from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.interpreter.interpreter import Interpreter
from blazelang.errors.error_handler import ImportError as BlazeImportError, ParserError


def run(path):
    source = Path(path).read_text(encoding="utf-8")
    program = Parser(Lexer(source, str(path)).tokenize()).parse()
    interpreter = Interpreter(filename=str(path))
    interpreter.interpret(program)
    return interpreter


class ModuleTests(unittest.TestCase):
    @property
    def fixtures(self):
        return Path(__file__).parent / "module_fixtures"

    def test_named_alias_namespace_and_default_imports(self):
        root = self.fixtures / "features"
        interpreter = run(root / "main.blz")
        self.assertAlmostEqual(interpreter.global_scope['total']['value'], 10.141592653589793)
        self.assertEqual(interpreter.global_scope['user']['value'].properties['name'], 'Rohit')

    def test_module_cache_and_relative_parent_path(self):
        root = self.fixtures / "relative"
        interpreter = run(root / "main.blz")
        self.assertEqual(interpreter.global_scope['A']['value'], 7)
        self.assertEqual(interpreter.global_scope['value']['value'], 7)
        self.assertEqual(len(interpreter.module_registry), 2)

    def test_import_and_export_validation(self):
        root = self.fixtures / "validation"
        with self.assertRaisesRegex(BlazeImportError, "was not exported"):
            run(root / "main.blz")
        with self.assertRaisesRegex(BlazeImportError, "Circular Import Error"):
            run(root / "circular_main.blz")
        with self.assertRaisesRegex(ParserError, "Duplicate export 'x'"):
            Parser(Lexer('Export var x = 1 Export var x = 2').tokenize()).parse()
        with self.assertRaisesRegex(ParserError, "Only one default export"):
            Parser(Lexer('Export Default var x = 1 Export Default var y = 2').tokenize()).parse()


if __name__ == '__main__':
    unittest.main()
