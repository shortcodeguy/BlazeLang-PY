import json
import tempfile
import unittest
from pathlib import Path

from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.package import CACHE, PackageError, cache_package, create_package, materialize_installed_module, read_package
from blazelang.parser.parser import Parser


def run(source):
    program = Parser(Lexer(source, "<test>").tokenize()).parse()
    interpreter = Interpreter(filename="<test>")
    interpreter.interpret(program)
    return interpreter


class RuntimeOptimizationTests(unittest.TestCase):
    def test_lazy_range_and_numeric_accumulation(self):
        interpreter = run("var total = 0 for i in range(1, 100001) { total += i }")
        self.assertEqual(interpreter.global_scope["total"]["value"], 5_000_050_000)
        self.assertIsInstance(interpreter.builtin_range(3), range)

    def test_constant_folding_preserves_result(self):
        interpreter = run("var answer = (2 + 3) * 4")
        self.assertEqual(interpreter.global_scope["answer"]["value"], 20)


class PackageTests(unittest.TestCase):
    def test_binary_package_round_trip_and_import(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "sample"
            project.mkdir()
            (project / "main.blz").write_text("Export Default var answer = 42", encoding="utf-8")
            (project / "utils.blz").write_text("Export var greeting = 'hello'", encoding="utf-8")
            (project / "package.json").write_text(json.dumps({"name": "sample-test-package", "version": "1.0.0", "main": "main.blz", "dependencies": {}}), encoding="utf-8")
            archive = create_package(project / "main.blz")
            self.assertFalse(archive.read_bytes().startswith(b"{"))
            document = read_package(archive)
            self.assertEqual(document["metadata"]["name"], "sample-test-package")
            cache_package(archive)
            main = materialize_installed_module("sample-test-package")
            self.assertIsNotNone(main)
            interpreter = Interpreter(filename=str(project / "consumer.blz"))
            exports = interpreter._load_module("sample-test-package")
            self.assertEqual(exports["default"], 42)

    def test_tampered_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "sample"; project.mkdir()
            (project / "main.blz").write_text("var x = 1", encoding="utf-8")
            (project / "package.json").write_text(json.dumps({"name": "tamper-test-package", "main": "main.blz"}), encoding="utf-8")
            archive = create_package(project / "main.blz")
            raw = bytearray(archive.read_bytes()); raw[-1] ^= 1; archive.write_bytes(raw)
            with self.assertRaises(PackageError): read_package(archive)
