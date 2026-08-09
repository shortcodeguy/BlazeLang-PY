import unittest
from pathlib import Path

from blazelang.errors.error_handler import FileSystemError
from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.stdlib.file import FileLibrary


class FileLibraryTests(unittest.TestCase):
    def setUp(self):
        self.runtime_root = Path(__file__).parent / "file_runtime"
        self.files = FileLibrary(self.runtime_root)
        for name in ("lifecycle", "imports"):
            if self.files.exists_directory(name):
                self.files.delete_directory(name, True)

    def tearDown(self):
        for name in ("lifecycle", "imports"):
            if self.files.exists_directory(name):
                self.files.delete_directory(name, True)

    def test_full_file_and_directory_lifecycle(self):
        files = self.files
        self.assertTrue(files.create_directory("lifecycle/data"))
        self.assertTrue(files.write("lifecycle/data/note.txt", "Hello"))
        self.assertTrue(files.append("lifecycle/data/note.txt", " BlazeLang"))
        self.assertEqual(files.read("lifecycle/data/note.txt"), "Hello BlazeLang")
        self.assertTrue(files.exists("lifecycle/data/note.txt"))
        self.assertEqual(files.size("lifecycle/data/note.txt"), 15)
        self.assertEqual(files.extension("lifecycle/data/note.txt"), "txt")
        self.assertTrue(files.copy("lifecycle/data/note.txt", "lifecycle/data/copy.txt"))
        self.assertTrue(files.move("lifecycle/data/copy.txt", "lifecycle/data/moved.txt"))
        self.assertTrue(files.rename("lifecycle/data/moved.txt", "lifecycle/data/renamed.txt"))
        self.assertEqual(files.list_files("lifecycle/data"), ["note.txt", "renamed.txt"])
        self.assertEqual(files.list_directories("lifecycle"), ["data"])
        self.assertTrue(files.delete("lifecycle/data/renamed.txt"))
        self.assertTrue(files.delete("lifecycle/data/note.txt"))
        self.assertTrue(files.delete_directory("lifecycle/data"))

    def test_errors_have_the_file_code_and_recovery_hint(self):
        with self.assertRaises(FileSystemError) as raised:
            self.files.read("missing.txt")
        self.assertEqual(raised.exception.code, "BLZ5001")
        self.assertIn("Reason", raised.exception.message)
        self.assertIn("Check that the file", raised.exception.hint)

    def test_relative_paths_are_anchored_to_source_and_import_forms_work(self):
        source_path = self.runtime_root / "imports" / "program.blz"
        self.files.create_directory("imports")
        source = '''
        Import File from "file"
        Import * as Files from "file"
        File.Write("one.txt", "1")
        Files.Append("one.txt", "2")
        var text = File.Read("one.txt")
        '''
        program = Parser(Lexer(source, str(source_path)).tokenize()).parse()
        interpreter = Interpreter(filename=str(source_path))
        interpreter.interpret(program)
        self.assertEqual((self.runtime_root / "imports" / "one.txt").read_text(encoding="utf-8"), "12")
        self.assertEqual(interpreter.global_scope["text"]["value"], "12")


if __name__ == "__main__":
    unittest.main()
