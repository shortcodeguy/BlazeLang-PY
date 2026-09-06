import io
import unittest
from contextlib import redirect_stdout

from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError
from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.stdlib.process import ProcessLibrary, create_process_module


class ProcessTests(unittest.TestCase):
    def test_process_run_string(self):
        lib = ProcessLibrary()
        res = lib.run("cmd /c echo BlazeLangProcess")
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("BlazeLangProcess", res["stdout"])

    def test_process_run_cmd_args(self):
        lib = ProcessLibrary()
        res = lib.run("cmd", ["/c", "echo", "SeparateArgs"])
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("SeparateArgs", res["stdout"])

    def test_process_start_wait_pid(self):
        lib = ProcessLibrary()
        handle = lib.start("cmd", ["/c", "echo", "AsyncStart"])
        pid = lib.pid(handle)
        self.assertIsInstance(pid, int)
        exit_code = lib.wait(handle, timeout=5)
        self.assertEqual(exit_code, 0)
        self.assertFalse(lib.is_running(handle))
        self.assertEqual(lib.exit_code(handle), 0)

    def test_process_kill(self):
        lib = ProcessLibrary()
        handle = lib.start("ping", ["127.0.0.1", "-n", "10"])
        self.assertTrue(lib.is_running(handle))
        self.assertTrue(lib.kill(handle))
        self.assertFalse(lib.is_running(handle))

    def test_process_errors(self):
        lib = ProcessLibrary()
        with self.assertRaises(BlazeRuntimeError):
            lib.run("invalid_nonexistent_command_12345")
        with self.assertRaises(BlazeRuntimeError):
            lib.start("invalid_nonexistent_command_12345")
        with self.assertRaises(BlazeRuntimeError):
            lib.wait("invalid_handle")

    def test_interpreter_process_import(self):
        source = '''
Import Process from "process"
var res = Process.Run("cmd /c echo HelloFromBlaze")
Show(res.stdout)
var proc = Process.Start("cmd", ["/c", "echo", "BlazeStart"])
var exit_code = Process.Wait(proc)
Show("Exit: " + exit_code)
'''
        interpreter = Interpreter(filename="test_process.blz")
        with redirect_stdout(io.StringIO()) as output:
            interpreter.interpret(Parser(Lexer(source, "test_process.blz").tokenize()).parse())
        out = output.getvalue()
        self.assertIn("HelloFromBlaze", out)
        self.assertIn("Exit: 0", out)
