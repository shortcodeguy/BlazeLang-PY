import unittest

from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError
from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.stdlib.date import DateLibrary
from blazelang.stdlib.math import MathLibrary
from blazelang.stdlib.path import PathLibrary
from blazelang.stdlib.random import RandomLibrary


class StandardLibraryTests(unittest.TestCase):
    def test_math_random_date_and_path_values(self):
        math = MathLibrary()
        self.assertEqual(math.sqrt(81), 9)
        self.assertEqual(math.clamp(12, 0, 10), 10)
        self.assertEqual(math.round(2.345, 2), 2.35)
        with self.assertRaises(BlazeRuntimeError):
            math.sqrt(-1)

        random = RandomLibrary()
        self.assertTrue(1 <= random.int(1, 1) <= 1)
        self.assertEqual(len(random.string(8)), 8)
        values = [1, 2, 3]
        shuffled = random.shuffle(values)
        self.assertEqual(sorted(shuffled), values)
        self.assertEqual(values, [1, 2, 3])

        date = DateLibrary()
        self.assertRegex(date.today(), r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(date.format("dd/MM/yyyy"), r"^\d{2}/\d{2}/\d{4}$")
        path = PathLibrary()
        self.assertEqual(path.extension(path.join("src", "main.blz")), "blz")
        self.assertEqual(path.file_name(path.join("src", "main.blz")), "main.blz")

    def test_all_reserved_modules_bind_as_pascal_case_namespaces(self):
        source = '''
        Import Math from "math"
        Import Random from "random"
        Import Date from "date"
        Import Time from "time"
        Import Path from "path"
        Import System from "system"
        Import Env from "env"
        var result = Math.Max(2, 4)
        var extension = Path.Extension("demo.blz")
        var version = System.Version()
        '''
        program = Parser(Lexer(source, "stdlib_test.blz").tokenize()).parse()
        interpreter = Interpreter(filename="stdlib_test.blz")
        interpreter.interpret(program)
        self.assertEqual(interpreter.global_scope["result"]["value"], 4)
        self.assertEqual(interpreter.global_scope["extension"]["value"], "blz")
        self.assertEqual(interpreter.global_scope["version"]["value"], "1.6")


if __name__ == "__main__":
    unittest.main()
