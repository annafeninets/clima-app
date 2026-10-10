"""HTTP adapter that translates wire requests into Clima API requests."""

from base64 import b64encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from urllib.parse import parse_qs, urlsplit

from clima.api import response_bytes
from clima.container import Application
from clima.errors import ValidationError
from clima.models.value_objects import Request, Response

logger = logging.getLogger("clima.http")
MAX_REQUEST_BYTES = 8 * 1024 * 1024


class ClimaHTTPServer(ThreadingHTTPServer):
    request_queue_size = 128


def create_handler(
    application: Application,
    corsOrigins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173"),
):
    class ClimaRequestHandler(BaseHTTPRequestHandler):
        server_version = "ClimaAPI/1.0"

        def do_GET(self):
            if urlsplit(self.path).path == "/health":
                self._health()
                return
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def do_PUT(self):
            self._dispatch()

        def do_DELETE(self):
            self._dispatch()

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _health(self):
            try:
                application.database.query("SELECT 1")
            except Exception:
                logger.exception("Health check failed: database is unavailable")
                self._write(Response.error("База данных недоступна", 503, "service_unavailable"))
                return
            self._write(Response.ok({"status": "ok"}))

        def _dispatch(self):
            try:
                response = application.api.dispatch(self._request())
            except ValidationError as error:
                response = Response.error(error.message, error.status_code, error.code)
            self._write(response)

        def _write(self, response: Response):
            payload, content_type = response_bytes(response)
            self.send_response(response.status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(payload)

        def _cors_headers(self):
            origin = self.headers.get("Origin")
            if isinstance(origin, str) and origin in corsOrigins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
                self.send_header("Access-Control-Max-Age", "600")

        def _request(self) -> Request:
            parsed = urlsplit(self.path)
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ValidationError("Некорректный Content-Length") from error
            if content_length < 0 or content_length > MAX_REQUEST_BYTES:
                raise ValidationError("Размер запроса превышает 8 МБ")
            raw = self.rfile.read(content_length) if content_length else b""
            content_type = self.headers.get("Content-Type", "")
            body = {}
            if raw and "application/json" in content_type:
                try:
                    body = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValidationError("Некорректный JSON") from error
                if not isinstance(body, dict):
                    raise ValidationError("JSON запроса должен быть объектом")
            elif raw and content_type.startswith("application/octet-stream"):
                body = {"photo": b64encode(raw).decode("ascii")}
            elif raw:
                raise ValidationError("Передавайте JSON или application/octet-stream")
            query = {
                key: values[-1]
                for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
            }
            authorization = self.headers.get("Authorization", "")
            token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
            headers = {key.lower(): value for key, value in self.headers.items()}
            headers["x-client-ip"] = self.client_address[0]
            return Request(
                action="", args=[], token=token, method=self.command, path=parsed.path,
                query=query, body=body, headers=headers,
            )

        def log_message(self, format, *args):
            logger.info("%s - %s", self.address_string(), format % args)

    return ClimaRequestHandler
