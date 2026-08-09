import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.interpreter.interpreter import Interpreter
from blazelang.stdlib.http import HttpClient


class FakeResponse:
    status = 200
    reason = "OK"

    def __init__(self, body=b'{"message":"hello"}'):
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = "application/json; charset=utf-8"

    def read(self):
        return self.body

    def geturl(self):
        return "https://api.example.test/items?page=1"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class HttpTests(unittest.TestCase):
    def test_get_encodes_query_and_decodes_json(self):
        with patch("blazelang.stdlib.http.urlopen", return_value=FakeResponse()) as open_url:
            response = HttpClient().get("https://api.example.test/items", {"query": {"page": 1}})
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.example.test/items?page=1")
        self.assertEqual(response["status"], 200)
        self.assertTrue(response["ok"])
        self.assertEqual(response["body"], {"message": "hello"})

    def test_post_serializes_object_as_json(self):
        with patch("blazelang.stdlib.http.urlopen", return_value=FakeResponse()) as open_url:
            response = HttpClient().post("https://api.example.test/items", {"name": "Blaze"})
        request = open_url.call_args.args[0]
        self.assertEqual(request.data, b'{"name": "Blaze"}')
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(response["method"], "POST")

    def test_network_errors_are_response_objects(self):
        with patch("blazelang.stdlib.http.urlopen", side_effect=URLError("offline")):
            response = HttpClient().get("https://api.example.test/items")
        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], 0)
        self.assertIn("offline", response["statusText"])
        self.assertIn("offline", response["error"])

    def test_download_creates_missing_destination_directories(self):
        base_dir = Path(__file__).parent / "file_runtime"
        destination_dir = base_dir / "http_download"
        if destination_dir.exists():
            import shutil
            shutil.rmtree(destination_dir)
        with patch("blazelang.stdlib.http.urlopen", return_value=FakeResponse(b"image-bytes")):
            response = HttpClient(base_dir).download("https://example.test/logo.jpg", "http_download/logo.jpg")
        self.assertTrue(response["ok"])
        self.assertIsNone(response["error"])
        self.assertEqual((destination_dir / "logo.jpg").read_bytes(), b"image-bytes")
        import shutil
        shutil.rmtree(destination_dir)

    def test_language_default_and_namespace_imports(self):
        source = '''
        Import Http from "http"
        Import * as Network from "http"
        var first = Http.Get("https://api.example.test/one")
        var second = Network.Head("https://api.example.test/two")
        '''
        with patch("blazelang.stdlib.http.urlopen", return_value=FakeResponse()):
            program = Parser(Lexer(source, "http_test.blz").tokenize()).parse()
            interpreter = Interpreter(filename="http_test.blz")
            interpreter.interpret(program)
        self.assertEqual(interpreter.global_scope["first"]["value"]["method"], "GET")
        self.assertEqual(interpreter.global_scope["second"]["value"]["method"], "HEAD")


if __name__ == "__main__":
    unittest.main()
