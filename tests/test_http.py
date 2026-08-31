import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from blazelang.stdlib.http import HttpClient


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/json"):
            data = json.dumps({"ok": True, "path": self.path}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)


class HttpClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_json_requests_and_query_parameters(self):
        client = HttpClient()
        response = client.get(self.base_url + "/json", {"query": {"page": 2}})
        self.assertTrue(response["ok"])
        self.assertEqual(response["body"]["path"], "/json?page=2")
        posted = client.post(self.base_url + "/post", {"title": "BlazeLang"})
        self.assertEqual(posted["status"], 201)
        self.assertEqual(posted["body"], {"title": "BlazeLang"})

    def test_invalid_options_return_a_normal_error_response(self):
        client = HttpClient()
        for options in ("bad", {"headers": "bad"}, {"timeout": None}):
            response = client.get(self.base_url + "/json", options)
            self.assertFalse(response["ok"])
            self.assertEqual(response["status"], 0)
            self.assertIsInstance(response["error"], str)
        upload = client.upload(self.base_url + "/post", "missing.bin", "bad")
        self.assertFalse(upload["ok"])
        self.assertEqual(upload["status"], 0)
