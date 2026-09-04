"""Robot-facing TCP session handling for port 20008-style RobotBona traffic."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable

from .commands import CommandBuilder, ControlContext
from .protocol import (
    CONTROL_RESPONSE_MAGIC,
    HEADER_SIZE,
    build_keepalive_ack,
    build_login_ack,
    build_normal_ack,
    parse_header,
)
from .state import RobotState

LogFn = Callable[[str], None]


def recv_exact(sock: socket.socket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("connection closed")
        data.extend(chunk)
    return bytes(data)


class RobotConnection:
    """Shared live connection used by the server and the local API."""

    def __init__(self, state: RobotState, *, log: LogFn | None = None) -> None:
        self.state = state
        self.log = log or (lambda _message: None)
        self._lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._peer: tuple[str, int] | None = None
        self.commands = CommandBuilder()

    def attach(self, sock: socket.socket, peer: tuple[str, int]) -> None:
        with self._lock:
            self._socket = sock
            self._peer = peer
            self.state.connected = True

    def detach(self, sock: socket.socket) -> None:
        with self._lock:
            if self._socket is sock:
                self._socket = None
                self._peer = None
                self.state.connected = False

    def send_control(self, transit_cmd: str | int, *, extra_value: dict[str, object] | None = None) -> int:
        with self._lock:
            sock = self._socket
            if sock is None:
                raise RuntimeError("no active robot connection")
            session = self.state.session
            if not session.control_ready():
                raise RuntimeError("robot login not complete")
            context = ControlContext(
                auth_code=session.auth_code or "",
                device_ip=session.device_ip or "",
                device_port=session.device_port,
            )
            sequence, packet = self.commands.build(context, transit_cmd, extra_value=extra_value)
            sock.sendall(packet)
            return sequence


def handle_tcp_client(
    sock: socket.socket,
    peer: tuple[str, int],
    connection: RobotConnection,
) -> None:
    sock.settimeout(90)
    try:
        while True:
            header_bytes = recv_exact(sock, HEADER_SIZE)
            header = parse_header(header_bytes)
            payload = recv_exact(sock, header.total_length - HEADER_SIZE) if header.total_length > HEADER_SIZE else b""

            obj = None
            if payload:
                text = payload.decode("utf-8", errors="replace").rstrip("\x00\r\n")
                try:
                    obj = json.loads(text)
                except json.JSONDecodeError:
                    connection.log("received non-JSON RobotBona payload")
                else:
                    if isinstance(obj, dict):
                        connection.state.update_from_message(obj)

            value = obj.get("value") if isinstance(obj, dict) else None
            if isinstance(value, dict) and "token" in value:
                sock.sendall(build_login_ack(header.sequence))
                connection.attach(sock, peer)
            elif header.magic == CONTROL_RESPONSE_MAGIC:
                connection.log(f"control response seq={header.sequence}")
            elif header.total_length == HEADER_SIZE:
                sock.sendall(build_keepalive_ack(header.sequence))
            else:
                sock.sendall(build_normal_ack(header.sequence))
    except (ConnectionError, ConnectionResetError, BrokenPipeError, socket.timeout):
        pass
    finally:
        connection.detach(sock)
        try:
            sock.close()
        except OSError:
            pass


def serve_tcp(host: str, port: int, connection: RobotConnection) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(5)
        while True:
            sock, peer = server.accept()
            threading.Thread(
                target=handle_tcp_client,
                args=(sock, peer, connection),
                daemon=True,
            ).start()
