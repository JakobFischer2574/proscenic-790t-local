"""Robot-facing HTTP service used by the ESP8266 for local token bootstrap."""

from __future__ import annotations

import json
import socketserver
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class HTTPServiceConfig:
    app_key: str
    device_id: str
    local_token: str


def chunked_response(body: bytes, *, now: datetime | None = None) -> bytes:
    current = now or datetime.now(timezone.utc)
    date_value = current.strftime("%a, %d %b %Y %H:%M:%S GMT")
    head = (
        b"HTTP/1.1 200 \r\n"
        b"Server: nginx\r\n"
        + f"Date: {date_value}\r\n".encode("ascii")
        + b"Content-Type: application/json;charset=UTF-8\r\n"
        + b"Transfer-Encoding: chunked\r\n"
        + b"Connection: close\r\n\r\n"
    )
    return head + f"{len(body):x}\r\n".encode("ascii") + body + b"\r\n0\r\n\r\n"


def token_response_body(config: HTTPServiceConfig) -> bytes:
    # Compact JSON and string result match the captured cloud response shape.
    return json.dumps(
        {
            "msg": "ok",
            "result": "0",
            "data": {
                "appKey": config.app_key,
                "deviceNo": config.device_id,
                "token": config.local_token,
            },
            "version": "1.0.0",
        },
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


class RobotBonaHTTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], config: HTTPServiceConfig):
        self.config = config
        super().__init__(server_address, RobotBonaHTTPHandler)


class RobotBonaHTTPHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(5)
        data = bytearray()
        while b"\r\n\r\n" not in data:
            part = self.request.recv(4096)
            if not part:
                return
            data.extend(part)

        header_end = data.index(b"\r\n\r\n") + 4
        header = bytes(data[:header_end])
        request_line = header.split(b"\r\n", 1)[0]
        content_length = 0
        for line in header.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                try:
                    content_length = int(line.split(b":", 1)[1].strip())
                except ValueError:
                    content_length = 0
        while len(data) - header_end < content_length:
            part = self.request.recv(content_length - (len(data) - header_end))
            if not part:
                break
            data.extend(part)

        server = self.server
        assert isinstance(server, RobotBonaHTTPServer)
        if b"/baole-web/common/getToken.do" in request_line:
            body = token_response_body(server.config)
        else:
            body = b'{"msg":"ok","result":"0","version":"1.0.0"}'
        self.request.sendall(chunked_response(body))
