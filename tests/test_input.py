import builtins
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.interpreter.interpreter import Interpreter


def run(source):
    program = Parser(Lexer(source, "input_test.blz").tokenize()).parse()
    interpreter = Interpreter(filename="input_test.blz")
    interpreter.interpret(program)
    return interpreter


class InputTests(unittest.TestCase):
    def test_prompt_and_whitespace_are_preserved(self):
        output = io.StringIO()
        with patch.object(builtins, "input", return_value="  Rohit  ") as read, redirect_stdout(output):
            interpreter = run('var name = Input("Name: ")')
        self.assertEqual(interpreter.global_scope["name"]["value"], "  Rohit  ")
        self.assertEqual(output.getvalue(), "Name: ")
        read.assert_called_once_with()

    def test_empty_prompt_and_empty_response(self):
        output = io.StringIO()
        with patch.object(builtins, "input", return_value=""), redirect_stdout(output):
            interpreter = run("var response = Input()")
        self.assertEqual(interpreter.global_scope["response"]["value"], "")
        self.assertEqual(output.getvalue(), "")

    def test_prompt_expression_and_function_use(self):
        source = '''
        var label = "Your name: "
        Function askName() { return Input(label + "") }
        var name = askName()
        '''
        output = io.StringIO()
        with patch.object(builtins, "input", return_value="Asha"), redirect_stdout(output):
            interpreter = run(source)
        self.assertEqual(interpreter.global_scope["name"]["value"], "Asha")
        self.assertEqual(output.getvalue(), "Your name: ")

    def test_terminal_errors_return_empty_string(self):
        with patch.object(builtins, "input", side_effect=EOFError), redirect_stdout(io.StringIO()):
            interpreter = run('var answer = Input("Continue? ")')
        self.assertEqual(interpreter.global_scope["answer"]["value"], "")


if __name__ == "__main__":
    unittest.main()
