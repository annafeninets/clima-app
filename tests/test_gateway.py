"""HTTP-граница и жизненный цикл процесса: health, CORS, лимиты, корректная остановка."""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
from threading import Thread
from time import monotonic, sleep
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request as HttpRequest, urlopen

from clima.boundaries.http_gateway import ClimaHTTPServer, create_handler
from clima.container import Application
from support import TEST_DATABASE_URL, drop_schema, new_schema_name, requires_database


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@requires_database
class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.schema = new_schema_name()
        self.app = Application(TEST_DATABASE_URL, root / "uploads", databaseSchema=self.schema)
        self.server = ClimaHTTPServer(
            ("127.0.0.1", 0), create_handler(self.app, ("http://allowed.example",))
        )
        self.thread = Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.app.close()
        drop_schema(self.schema)
        self.directory.cleanup()

    def test_health_reports_ok(self):
        with urlopen(f"{self.base}/health", timeout=3) as response:
            payload = json.load(response)
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["data"], {"status": "ok"})

    def test_health_reports_unavailable_database(self):
        self.app.database._pool.close()  # имитируем недоступную базу
        with self.assertRaises(HTTPError) as caught:
            urlopen(f"{self.base}/health", timeout=3)
        self.assertEqual(caught.exception.code, 503)
        self.assertFalse(json.load(caught.exception)["success"])

    def test_unknown_route_returns_json_404(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(f"{self.base}/no/such/route", timeout=3)
        self.assertEqual(caught.exception.code, 404)
        self.assertFalse(json.load(caught.exception)["success"])

    def test_cors_only_for_allowed_origins(self):
        def origin_header(origin: str):
            request = HttpRequest(f"{self.base}/health", headers={"Origin": origin})
            with urlopen(request, timeout=3) as response:
                return response.headers.get("Access-Control-Allow-Origin")

        self.assertEqual(origin_header("http://allowed.example"), "http://allowed.example")
        self.assertIsNone(origin_header("http://evil.example"))

    def test_oversized_request_is_rejected(self):
        request = HttpRequest(
            f"{self.base}/auth/login", data=b"{}", method="POST",
            headers={"Content-Type": "application/json", "Content-Length": str(9 * 1024 * 1024)},
        )
        with self.assertRaises((HTTPError, URLError, ConnectionError)):
            urlopen(request, timeout=3)

    def test_non_json_body_is_rejected(self):
        request = HttpRequest(
            f"{self.base}/auth/login", data=b"login=a", method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 422)

    def test_scheduler_endpoint_requires_token(self):
        request = HttpRequest(f"{self.base}/internal/scheduler/morning", data=b"", method="POST")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 403)


@requires_database
class ProcessLifecycleTests(unittest.TestCase):
    def test_sigterm_stops_server_gracefully(self):
        if sys.platform == "win32":
            self.skipTest("SIGTERM semantics differ on Windows")
        port = free_port()
        schema = new_schema_name()
        self.addCleanup(drop_schema, schema)
        with tempfile.TemporaryDirectory() as directory:
            env = {
                **os.environ,
                "CLIMA_HOST": "127.0.0.1",
                "CLIMA_PORT": str(port),
                "CLIMA_DATABASE_URL": TEST_DATABASE_URL,
                "CLIMA_DB_SCHEMA": schema,
                "CLIMA_REDIS_URL": "",
                "CLIMA_UPLOADS_PATH": str(Path(directory) / "uploads"),
            }
            process = subprocess.Popen(
                [sys.executable, "-m", "clima"], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            try:
                deadline = monotonic() + 20
                while True:
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
                            break
                    except (URLError, ConnectionError):
                        if process.poll() is not None or monotonic() > deadline:
                            self.fail("сервер не запустился")
                        sleep(0.2)
                process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=10), 0)
                self.assertIn("остановлен", process.stderr.read())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stderr.close()


if __name__ == "__main__":
    unittest.main()
