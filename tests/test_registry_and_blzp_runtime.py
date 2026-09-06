import hashlib
import json
import os
import shutil
import tempfile
import unittest
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from blazelang import package
from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.package import (
    CACHE,
    PackageError,
    cache_package,
    create_package,
    install_package,
    load_installed_package,
    read_package,
)
from blazelang.parser.parser import Parser


class RegistryHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        # Silence HTTP server logs during unit tests
        pass


class RegistryAndBLZPRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.cache_dir = self.temp_path / "cache"
        self.registry_dir = self.temp_path / "registry"
        self.packages_dir = self.registry_dir / "packages"
        self.releases_dir = self.registry_dir / "releases"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.releases_dir.mkdir(parents=True, exist_ok=True)

        self.cache_patch = patch("blazelang.package.CACHE", self.cache_dir)
        self.cache_patch.start()
        package._INDEX_CACHE_PATH = None
        package._INDEX_CACHE = None

        # Build a test package (blz-utils 1.0.0)
        self.pkg_project = self.temp_path / "blz-utils-src"
        self.pkg_project.mkdir()
        (self.pkg_project / "package.json").write_text(
            json.dumps({
                "name": "blz-utils",
                "version": "1.0.0",
                "description": "Utilities for BlazeLang",
                "main": "main.blz"
            }),
            encoding="utf-8"
        )
        (self.pkg_project / "main.blz").write_text(
            "Import { StringUtil } from \"./utils/string\"\n"
            "Export Function Add(a, b) { return a + b }\n"
            "Export Function Greet(name) { return StringUtil(name) }\n",
            encoding="utf-8"
        )
        (self.pkg_project / "utils").mkdir()
        (self.pkg_project / "utils" / "string.blz").write_text(
            "Export Function StringUtil(s) { return \"Hello \" + s }\n",
            encoding="utf-8"
        )

        self.blzp_file = create_package(self.pkg_project / "main.blz")
        self.blzp_bytes = self.blzp_file.read_bytes()
        self.blzp_sha256 = hashlib.sha256(self.blzp_bytes).hexdigest()

        # Copy archive to releases dir for HTTP serving
        self.rel_blzp = self.releases_dir / "blz-utils-1.0.0.blzp"
        self.rel_blzp.write_bytes(self.blzp_bytes)

        # Set up mock HTTP server for registry test cases
        self.server = HTTPServer(("127.0.0.1", 0), lambda *a, **k: RegistryHTTPHandler(*a, directory=str(self.registry_dir), **k))
        self.port = self.server.server_port
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        self.registry_url = f"http://127.0.0.1:{self.port}"
        self.env_patch = patch.dict("os.environ", {"BLZ_REGISTRY_URL": self.registry_url})
        self.env_patch.start()

        # Write index.json and blz-utils.json to mock registry
        (self.registry_dir / "index.json").write_text(
            json.dumps({
                "registryVersion": 1,
                "packages": {
                    "blz-utils": {"latest": "1.0.0"}
                }
            }),
            encoding="utf-8"
        )

        (self.packages_dir / "blz-utils.json").write_text(
            json.dumps({
                "name": "blz-utils",
                "publisher": "shortcodeguy",
                "description": "Utilities for BlazeLang",
                "latest": "1.0.0",
                "versions": {
                    "1.0.0": {
                        "download": f"{self.registry_url}/releases/blz-utils-1.0.0.blzp",
                        "sha256": self.blzp_sha256
                    }
                }
            }),
            encoding="utf-8"
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.env_patch.stop()
        self.cache_patch.stop()
        package._INDEX_CACHE_PATH = None
        package._INDEX_CACHE = None
        self.temp_dir.cleanup()

    # --- 1. Registry Index Parsing ---
    def test_1_index_json_parsing(self):
        url = f"{self.registry_url}/index.json"
        import urllib.request
        data = json.loads(urllib.request.urlopen(url).read().decode("utf-8"))
        self.assertEqual(data["registryVersion"], 1)
        self.assertIn("blz-utils", data["packages"])

    # --- 2. Package Metadata Parsing ---
    def test_2_package_metadata_parsing(self):
        url = f"{self.registry_url}/packages/blz-utils.json"
        import urllib.request
        data = json.loads(urllib.request.urlopen(url).read().decode("utf-8"))
        self.assertEqual(data["name"], "blz-utils")
        self.assertIn("1.0.0", data["versions"])

    # --- 3. Package Resolution ---
    def test_3_package_resolution(self):
        meta = install_package("blz-utils")
        self.assertEqual(meta["name"], "blz-utils")
        self.assertEqual(meta["version"], "1.0.0")

    # --- 4. Latest Version Resolution ---
    def test_4_latest_version_resolution(self):
        meta = install_package("blz-utils")
        self.assertEqual(meta["version"], "1.0.0")

    # --- 5. Exact Version Resolution ---
    def test_5_exact_version_resolution(self):
        meta = install_package("blz-utils@1.0.0")
        self.assertEqual(meta["version"], "1.0.0")

    # --- 6. Unknown Package ---
    def test_6_unknown_package(self):
        with self.assertRaises(PackageError) as ctx:
            install_package("non-existent-pkg")
        self.assertIn("not found in registry", str(ctx.exception))

    # --- 7. Unknown Version ---
    def test_7_unknown_version(self):
        with self.assertRaises(PackageError) as ctx:
            install_package("blz-utils@9.9.9")
        self.assertIn("Version '9.9.9'", str(ctx.exception))

    # --- 8. Invalid Registry JSON ---
    def test_8_invalid_registry_json(self):
        (self.packages_dir / "invalid-pkg.json").write_text("NOT_JSON", encoding="utf-8")
        with self.assertRaises(PackageError) as ctx:
            install_package("invalid-pkg")
        self.assertIn("Invalid registry JSON", str(ctx.exception))

    # --- 9. Registry Unavailable ---
    def test_9_registry_unavailable(self):
        with patch.dict("os.environ", {"BLZ_REGISTRY_URL": "http://127.0.0.1:59999"}):
            with self.assertRaises(PackageError) as ctx:
                install_package("blz-utils")
            self.assertIn("Failed to connect", str(ctx.exception))

    # --- 10. HTTP Error ---
    def test_10_http_error(self):
        with self.assertRaises(PackageError):
            install_package("missing-pkg-404")

    # --- 11. Download Failure ---
    def test_11_download_failure(self):
        (self.packages_dir / "bad-dl.json").write_text(
            json.dumps({
                "name": "bad-dl",
                "latest": "1.0.0",
                "versions": {
                    "1.0.0": {"download": f"{self.registry_url}/releases/nonexistent.blzp"}
                }
            }),
            encoding="utf-8"
        )
        with self.assertRaises(PackageError) as ctx:
            install_package("bad-dl")
        self.assertIn("Failed to download", str(ctx.exception))

    # --- 12. Correct SHA-256 ---
    def test_12_correct_sha256(self):
        meta = install_package("blz-utils")
        self.assertEqual(meta["name"], "blz-utils")

    # --- 13. Incorrect SHA-256 ---
    def test_13_incorrect_sha256(self):
        (self.packages_dir / "bad-hash.json").write_text(
            json.dumps({
                "name": "bad-hash",
                "latest": "1.0.0",
                "versions": {
                    "1.0.0": {
                        "download": f"{self.registry_url}/releases/blz-utils-1.0.0.blzp",
                        "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
                    }
                }
            }),
            encoding="utf-8"
        )
        with self.assertRaises(PackageError) as ctx:
            install_package("bad-hash")
        self.assertIn("checksum mismatch", str(ctx.exception))

    # --- 14. Missing Checksum Behavior ---
    def test_14_missing_checksum_behavior(self):
        (self.packages_dir / "no-hash.json").write_text(
            json.dumps({
                "name": "no-hash",
                "latest": "1.0.0",
                "versions": {
                    "1.0.0": {
                        "download": f"{self.registry_url}/releases/blz-utils-1.0.0.blzp"
                    }
                }
            }),
            encoding="utf-8"
        )
        meta = install_package("no-hash")
        self.assertEqual(meta["name"], "blz-utils")

    # --- 15. Registry Package Installation ---
    def test_15_registry_package_installation(self):
        meta = install_package("blz-utils")
        self.assertIsNotNone(load_installed_package("blz-utils"))

    # --- 16. Already-Installed Package Skip ---
    def test_16_already_installed_package(self):
        install_package("blz-utils")
        # Second call should skip without downloading
        meta = install_package("blz-utils")
        self.assertEqual(meta["name"], "blz-utils")

    # --- 17. Local .blzp Installation ---
    def test_17_local_blzp_installation(self):
        meta = install_package(str(self.blzp_file))
        self.assertEqual(meta["name"], "blz-utils")

    # --- 18. Invalid .blzp ---
    def test_18_invalid_blzp(self):
        bad_file = self.temp_path / "bad.blzp"
        bad_file.write_bytes(b"INVALID_HEADER")
        with self.assertRaises(PackageError):
            install_package(str(bad_file))

    # --- 19. Corrupted .blzp ---
    def test_19_corrupted_blzp(self):
        corrupt_file = self.temp_path / "corrupt.blzp"
        data = bytearray(self.blzp_bytes)
        data[-5] ^= 0xFF
        corrupt_file.write_bytes(data)
        with self.assertRaises(PackageError):
            install_package(str(corrupt_file))

    # --- 20. Interpreter Reads .blzp Directly ---
    def test_20_interpreter_reads_blzp_directly(self):
        install_package(str(self.blzp_file))
        doc = load_installed_package("blz-utils")
        self.assertIsNotNone(doc)
        self.assertIn("modules", doc)
        self.assertIn("main.blz", doc["modules"])

    # --- 21. .blzp Executes Successfully ---
    def test_21_blzp_executes_successfully(self):
        install_package(str(self.blzp_file))
        consumer = Interpreter(filename=str(self.temp_path / "app.blz"))
        ast = Parser(Lexer(
            'Import { Add } from "blz-utils"\nvar res = Add(10, 20)\n',
            str(self.temp_path / "app.blz")
        ).tokenize()).parse()
        consumer.interpret(ast)
        self.assertEqual(consumer.global_scope["res"]["value"], 30)

    # --- 22. Package Imports Work ---
    def test_22_package_imports_work(self):
        install_package(str(self.blzp_file))
        consumer = Interpreter(filename=str(self.temp_path / "app.blz"))
        ast = Parser(Lexer(
            'Import { Greet } from "blz-utils"\nvar greeting = Greet("Blaze")\n',
            str(self.temp_path / "app.blz")
        ).tokenize()).parse()
        consumer.interpret(ast)
        self.assertEqual(consumer.global_scope["greeting"]["value"], "Hello Blaze")

    # --- 23 & 24. No .blz Files Generated / Source Reconstructed ---
    def test_23_and_24_no_blz_files_generated_on_disk(self):
        install_package(str(self.blzp_file))

        # Check installed cache directory contents
        blz_files = list(self.cache_dir.rglob("*.blz"))
        self.assertEqual(len(blz_files), 0, f"Found extracted .blz files on disk: {blz_files}")

        # Run package import to ensure no .blz files generated during execution
        consumer = Interpreter(filename=str(self.temp_path / "app.blz"))
        ast = Parser(Lexer(
            'Import { Add, Greet } from "blz-utils"\nvar a = Add(5, 5)\nvar b = Greet("Test")\n',
            str(self.temp_path / "app.blz")
        ).tokenize()).parse()
        consumer.interpret(ast)

        blz_files_after_exec = list(self.cache_dir.rglob("*.blz"))
        self.assertEqual(len(blz_files_after_exec), 0, f"Found .blz files generated after execution: {blz_files_after_exec}")

    # --- 25. Temporary Files Cleaned ---
    def test_25_temporary_files_cleaned(self):
        before_temps = set(os.listdir(tempfile.gettempdir()))
        install_package("blz-utils")
        after_temps = set(os.listdir(tempfile.gettempdir()))
        # Check no .blzp temp residual files remain
        new_temps = [f for f in (after_temps - before_temps) if f.endswith(".blzp")]
        self.assertEqual(new_temps, [])

    # --- 26. Registry-Installed .blzp Works After Restart ---
    def test_26_registry_installed_blzp_works_after_restart(self):
        install_package("blz-utils")

        # Simulate CLI restart by resetting memory caches
        package._INDEX_CACHE_PATH = None
        package._INDEX_CACHE = None

        new_interpreter = Interpreter(filename=str(self.temp_path / "app2.blz"))
        ast = Parser(Lexer(
            'Import { Add } from "blz-utils"\nvar x = Add(100, 200)\n',
            str(self.temp_path / "app2.blz")
        ).tokenize()).parse()
        new_interpreter.interpret(ast)
        self.assertEqual(new_interpreter.global_scope["x"]["value"], 300)


if __name__ == "__main__":
    unittest.main()
