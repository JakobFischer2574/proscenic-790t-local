"""Stable local JSON API for Home Assistant and other local clients."""

from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from .service import RobotService


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status: int
    body: dict[str, Any]


def _ok(**body: Any) -> ApiResponse:
    return ApiResponse(200, {"ok": True, **body})


def _error(status: int, message: str) -> ApiResponse:
    return ApiResponse(status, {"ok": False, "error": message})


def dispatch_api(service: RobotService, method: str, raw_path: str) -> ApiResponse:
    """Route one API request without depending on the HTTP transport.

    Keeping routing testable separately also ensures the HTTP layer never
    reimplements RobotBona packet construction.
    """
    path = urlsplit(raw_path).path.rstrip("/") or "/"
    method = method.upper()

    try:
        if method == "GET" and path == "/api/status":
            return _ok(status=service.status())
        if method == "GET" and path == "/api/health":
            return _ok(connected=service.state.connected)
        if method == "GET" and path == "/api/map":
            return _ok(map=service.map_snapshot())

        if method == "POST":
            simple_commands = {
                "/api/start": "start",
                "/api/stop": "stop",
                "/api/home": "home",
                "/api/map": "map",
                "/api/voice/on": "voice_on",
                "/api/voice/off": "voice_off",
            }
            if path in simple_commands:
                sequence = service.command(simple_commands[path])
                return _ok(sequence=sequence)

            if path.startswith("/api/mode/"):
                mode = path.removeprefix("/api/mode/")
                if not mode or "/" in mode:
                    return _error(404, "unknown endpoint")
                sequence = service.set_mode(mode)
                return _ok(sequence=sequence, mode=mode, evidence="confirmed")

            if path.startswith("/api/fan/"):
                fan = path.removeprefix("/api/fan/")
                if not fan or "/" in fan:
                    return _error(404, "unknown endpoint")
                sequence, evidence = service.set_fan(fan)
                return _ok(sequence=sequence, fan=fan, evidence=evidence)

        return _error(404, "unknown endpoint")
    except ValueError as exc:
        return _error(400, str(exc))
    except RuntimeError as exc:
        # Most commonly: robot is not connected/logged in yet.
        return _error(409, str(exc))


class LocalAPIServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], service: RobotService):
        self.service = service
        super().__init__(server_address, LocalAPIHandler)


class LocalAPIHandler(BaseHTTPRequestHandler):
    server_version = "Proscenic790TLocalAPI/0.1"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        # Initial command API is path-only; consume any supplied body so clients
        # can safely reuse HTTP connections without leaving unread bytes.
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length:
            self.rfile.read(length)
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        server = self.server
        assert isinstance(server, LocalAPIServer)
        response = dispatch_api(server.service, method, self.path)
        payload = json.dumps(response.body, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        # Applications/containers can add structured logging around the service.
        return


def serve_api(host: str, port: int, service: RobotService) -> None:
    with LocalAPIServer((host, port), service) as server:
        server.serve_forever()
