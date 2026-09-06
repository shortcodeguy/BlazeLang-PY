import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang import package
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
    def test_installed_package_lookup_reuses_index_and_manifest_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "sample"; project.mkdir()
            (project / "main.blz").write_text("Export var answer = 42", encoding="utf-8")
            (project / "package.json").write_text(json.dumps({
                "name": "cached-package", "version": "1.0.0", "main": "main.blz"
            }), encoding="utf-8")
            with patch("blazelang.package.CACHE", Path(temp) / "cache"):
                cache_package(create_package(project / "main.blz"))
                self.assertIsNotNone(package.load_installed_package("cached-package"))
                self.assertIsNotNone(package.load_installed_package("cached-package"))
                self.assertIsNotNone(package.materialize_installed_module("cached-package"))
    def test_package_default_api_supports_nested_members_and_chained_calls(self):
        """A packaged default export is a normal BlazeLang object graph."""
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "hello-package"
            project.mkdir()
            (project / "main.blz").write_text("""
Class PackageUser {
    Constructor(name) { this.name = name }
    Function welcome() { return "Class welcome " + this.name }
}
Struct PackageProfile { name }
var greet = {
    name: "Hello Package",
    version: "1.0.0",
    developer: function() { return "Hello Developer!" },
    user: function() { return "Hello User!" },
    config: { api: { version: "v1" } },
    utils: { format: function() { return "formatted" } },
    User: function(name) { return { welcome: function() { return "Welcome " + name + "!" } } },
    UserType: PackageUser,
    Profile: PackageProfile
}
export default greet
""", encoding="utf-8")
            (project / "package.json").write_text(json.dumps({
                "name": "hello-package", "version": "1.0.0",
                "description": "API package", "main": "main.blz", "dependencies": {}
            }), encoding="utf-8")
            archive = create_package(project / "main.blz")
            with patch("blazelang.package.CACHE", Path(temp) / "cache"):
                cache_package(archive)
                consumer = Interpreter(filename=str(project / "consumer.blz"))
                consumer.interpret(Parser(Lexer("""
import greet from "hello-package"
var a = greet.developer()
var b = greet.user()
var c = greet.name
var d = greet.config.api.version
var e = greet.utils.format()
var f = greet.User("Rohit").welcome()
var g = greet.UserType("Nina").welcome()
var h = greet.Profile(name: "Asha").name
""", str(project / "consumer.blz")).tokenize()).parse())
            self.assertEqual(consumer.global_scope["a"]["value"], "Hello Developer!")
            self.assertEqual(consumer.global_scope["b"]["value"], "Hello User!")
            self.assertEqual(consumer.global_scope["c"]["value"], "Hello Package")
            self.assertEqual(consumer.global_scope["d"]["value"], "v1")
            self.assertEqual(consumer.global_scope["e"]["value"], "formatted")
            self.assertEqual(consumer.global_scope["f"]["value"], "Welcome Rohit!")
            self.assertEqual(consumer.global_scope["g"]["value"], "Class welcome Nina")
            self.assertEqual(consumer.global_scope["h"]["value"], "Asha")

    def test_package_keeps_optional_source_paths_and_named_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "api"; project.mkdir()
            (project / "main.blz").write_text("Export var version = \"1.0\"", encoding="utf-8")
            nested = project / "anything"; nested.mkdir()
            (nested / "utils.blz").write_text("Export var helper = 1", encoding="utf-8")
            (project / "package.json").write_text(json.dumps({
                "name": "paths-package", "version": "1.0.0", "main": "main.blz",
                "dependencies": {"other": "owner/other"}
            }), encoding="utf-8")
            archive = create_package(project / "main.blz")
            document = read_package(archive)
            self.assertEqual(document["metadata"]["dependencies"], {"other": "owner/other"})
            self.assertIn("anything/utils.blz", document["modules"])
            self.assertFalse((project / "modules").exists())
            with patch("blazelang.package.CACHE", Path(temp) / "cache"):
                cache_package(archive)
                consumer = Interpreter(filename=str(project / "consumer.blz"))
                consumer.interpret(Parser(Lexer(
                    'import { version as apiVersion } from "paths-package"\n'
                    'import "paths-package" as api', str(project / "consumer.blz")
                ).tokenize()).parse())
            self.assertEqual(consumer.global_scope["apiVersion"]["value"], "1.0")
            self.assertEqual(consumer.global_scope["api"]["value"]["version"], "1.0")

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
