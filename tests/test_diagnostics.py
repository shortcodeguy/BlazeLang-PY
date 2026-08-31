import unittest

from blazelang.errors.error_handler import (
    ArgumentError,
    ErrorFormatter,
    FileNotFoundErrorBlaze,
    ImportError as BlazeImportError,
    LexerError,
    NativeModuleError,
    ParserError,
    PropertyError,
    RuntimeError as BlazeRuntimeError,
)
from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.package import PackageError
from blazelang.parser.parser import Parser


class DiagnosticTests(unittest.TestCase):
    SOURCE = "var answer = 42\nShow(answer.channels)\nShow(missingName)\n"

    def assert_diagnostic(self, error, expected_code, expected_type):
        error.attach_context(2, 13, "sample.blz", ["main()", "render()"]) 
        result = ErrorFormatter.format_diagnostic(error, self.SOURCE, color=False)
        self.assertIn(f"BlazeLang [{expected_code}] {expected_type}", result)
        self.assertIn("Location", result)
        self.assertIn("Hint", result)
        self.assertIn("Call Stack\n  at main()\n  at render()", result)
        return result

    def test_lexer_and_parser_diagnostics_have_locations(self):
        with self.assertRaises(LexerError) as lexer_error:
            Lexer("var x = $", "lex.blz").tokenize()
        self.assertEqual((lexer_error.exception.line, lexer_error.exception.column), (1, 9))
        rendered = self.assert_diagnostic(lexer_error.exception, "BLZ1001", "LexerError")
        self.assertIn("File   : lex.blz\nLine   : 1\nColumn : 9", rendered)

        with self.assertRaises(ParserError) as parser_error:
            Parser(Lexer("var = 1", "parse.blz").tokenize()).parse()
        self.assertEqual(parser_error.exception.filename, "parse.blz")
        rendered = self.assert_diagnostic(parser_error.exception, "BLZ1002", "ParserError")
        self.assertIn("File   : parse.blz", rendered)

    def test_runtime_property_argument_import_package_and_file_diagnostics(self):
        self.assertIn("Did you mean", self.assert_diagnostic(
            PropertyError("chanels", "BlazeImage", known_properties=["channels"]), "BLZ2011", "PropertyError"))
        self.assert_diagnostic(BlazeRuntimeError("Something failed"), "BLZ2001", "RuntimeError")
        self.assert_diagnostic(ArgumentError("Render", 2, 1), "BLZ2007", "ArgumentError")
        self.assert_diagnostic(BlazeImportError("Module file not found: imgae"), "BLZ3001", "ImportError")
        self.assert_diagnostic(PackageError("Invalid package.json"), "BLZ3002", "PackageError")
        self.assert_diagnostic(FileNotFoundErrorBlaze("missing.txt"), "BLZ5002", "FileNotFoundErrorBlaze")

    def test_native_failure_is_safe_and_preserves_cause(self):
        source = 'Explode()'
        interpreter = Interpreter(filename="native.blz")
        interpreter.global_scope["Explode"] = {"value": lambda: 1 / 0, "constant": True}
        with self.assertRaises(NativeModuleError) as caught:
            interpreter.interpret(Parser(Lexer(source, "native.blz").tokenize()).parse())
        error = caught.exception
        self.assertIsInstance(error.cause, Exception)
        rendered = ErrorFormatter.format_diagnostic(error, source, color=False)
        self.assertIn("Caused By", rendered)
        self.assertIn("NativeModuleError", rendered)

    def test_runtime_property_suggestion_is_discovered_for_native_objects(self):
        source = 'Import Image from "image"\nvar image = Image.Create(2, 2)\nShow(image.wdth)'
        interpreter = Interpreter(filename="property.blz")
        with self.assertRaises(PropertyError) as caught:
            interpreter.interpret(Parser(Lexer(source, "property.blz").tokenize()).parse())
        self.assertIn("Did you mean:\n  width", caught.exception.hint)
