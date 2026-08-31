import io
import unittest
from contextlib import redirect_stdout

from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError
from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.stdlib.cli import CLIApplication


class CLITests(unittest.TestCase):
    def test_commands_options_flags_aliases_and_positionals(self):
        received = []
        cli = CLIApplication(None, "tool", "Test application", ["add", "10", "20", "--name=Rohit", "-v"])
        cli.Command("add", "Add values", lambda args: received.append(args)).Alias("sum").Argument("a").Argument("b").Option("name", "n", "Name", True).Flag("verbose", "v")
        self.assertEqual(cli.Run(), 0)
        self.assertEqual(received[0]["a"], 10)
        self.assertEqual(received[0]["b"], 20)
        self.assertEqual(received[0]["name"], "Rohit")
        self.assertTrue(received[0]["verbose"])

    def test_help_version_and_validation(self):
        cli = CLIApplication(None, "tool", "Test application", ["--help"])
        cli.Command("hello", "Say hello", lambda args: None)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.Run(), 0)
        self.assertIn("Usage: tool <command>", output.getvalue())

        version = CLIApplication(None, "tool", "Test application", ["--version"])
        with redirect_stdout(io.StringIO()) as output:
            version.Run()
        self.assertIn("tool 1.0.0", output.getvalue())

        invalid = CLIApplication(None, "tool", "Test application", ["hello"])
        invalid.Command("hello", "Say hello", lambda args: None).Argument("name")
        with self.assertRaises(BlazeRuntimeError): invalid.Run()

    def test_subcommands_dispatch(self):
        received = []
        cli = CLIApplication(None, "tool", "Test application", ["user", "add", "Asha"])
        cli.Command("user", "Manage users", lambda args: None).Command("add", "Add a user", lambda args: received.append(args)).Argument("name")
        cli.Run()
        self.assertEqual(received[0]["name"], "Asha")

    def test_interpreter_receives_script_arguments_and_runs_example_style_handler(self):
        source = '''
import CLI from "cli"
var cli = CLI.Create("tool", "Test")
cli.Command("hello", "Say hello", function(args) { Show("Hello, " + args.name) }).Option("name", "n", "Name", true)
cli.Run()
'''
        interpreter = Interpreter(filename="cli.blz", cli_args=["hello", "--name", "Rohit"])
        with redirect_stdout(io.StringIO()) as output:
            interpreter.interpret(Parser(Lexer(source, "cli.blz").tokenize()).parse())
        self.assertEqual(output.getvalue().strip(), "Hello, Rohit")

    def test_context_helpers_are_available(self):
        source = 'import CLI from "cli"\nvar args = CLI.Arguments()\nvar cwd = CLI.CurrentDirectory()\nvar script = CLI.ScriptPath()\nvar executable = CLI.ExecutablePath()'
        interpreter = Interpreter(filename="context.blz", cli_args=["run", "--fast"])
        interpreter.interpret(Parser(Lexer(source, "context.blz").tokenize()).parse())
        self.assertEqual(interpreter.global_scope["args"]["value"], ["run", "--fast"])
        self.assertEqual(interpreter.global_scope["script"]["value"], interpreter.filename)
        self.assertTrue(interpreter.global_scope["cwd"]["value"])
        self.assertTrue(interpreter.global_scope["executable"]["value"])
