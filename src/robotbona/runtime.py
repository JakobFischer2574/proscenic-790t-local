"""Standalone/container runtime that starts all three local service surfaces."""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .api_server import LocalAPIServer
from .http_server import HTTPServiceConfig, RobotBonaHTTPServer
from .persistence import StatePersistence
from .service import RobotService
from .state import RobotState
from .tcp_server import RobotConnection, serve_tcp

LOGGER = logging.getLogger("robotbona")
DEFAULT_LOCAL_TOKEN = "LOCAL790T00000000000000000000000"


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    app_key: str
    device_id: str
    local_token: str = DEFAULT_LOCAL_TOKEN
    robot_http_host: str = "0.0.0.0"
    robot_http_port: int = 18080
    robot_tcp_host: str = "0.0.0.0"
    robot_tcp_port: int = 20008
    api_host: str = "0.0.0.0"
    api_port: int = 8090
    data_dir: Path = Path("/data")
    persist_interval: float = 5.0

    @classmethod
    def from_environment(cls) -> "RuntimeConfig":
        options = _load_options(
            Path(os.getenv("ROBOTBONA_OPTIONS_FILE", "/data/options.json"))
        )

        def get(env_name: str, option_name: str, default: Any = None) -> Any:
            if env_name in os.environ:
                return os.environ[env_name]
            return options.get(option_name, default)

        config = cls(
            app_key=str(get("ROBOTBONA_APP_KEY", "app_key", "")).strip(),
            device_id=str(get("ROBOTBONA_DEVICE_ID", "device_id", "")).strip(),
            local_token=str(
                get("ROBOTBONA_LOCAL_TOKEN", "local_token", DEFAULT_LOCAL_TOKEN)
            ).strip(),
            robot_http_host=str(get("ROBOTBONA_HTTP_HOST", "robot_http_host", "0.0.0.0")),
            robot_http_port=int(get("ROBOTBONA_HTTP_PORT", "robot_http_port", 18080)),
            robot_tcp_host=str(get("ROBOTBONA_TCP_HOST", "robot_tcp_host", "0.0.0.0")),
            robot_tcp_port=int(get("ROBOTBONA_TCP_PORT", "robot_tcp_port", 20008)),
            api_host=str(get("ROBOTBONA_API_HOST", "api_host", "0.0.0.0")),
            api_port=int(get("ROBOTBONA_API_PORT", "api_port", 8090)),
            data_dir=Path(str(get("ROBOTBONA_DATA_DIR", "data_dir", "/data"))),
            persist_interval=float(
                get("ROBOTBONA_PERSIST_INTERVAL", "persist_interval", 5.0)
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.app_key:
            raise ValueError("ROBOTBONA_APP_KEY / app_key is required")
        if not self.device_id:
            raise ValueError("ROBOTBONA_DEVICE_ID / device_id is required")
        if len(self.local_token) != 32:
            raise ValueError("local token must be exactly 32 characters on the tested firmware")
        for name, port in (
            ("robot_http_port", self.robot_http_port),
            ("robot_tcp_port", self.robot_tcp_port),
            ("api_port", self.api_port),
        ):
            if not 1 <= port <= 65535:
                raise ValueError(f"{name} must be between 1 and 65535")
        if self.persist_interval <= 0:
            raise ValueError("persist_interval must be positive")


class RobotRuntime:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.state = RobotState()
        self.connection = RobotConnection(self.state, log=LOGGER.info)
        self.service = RobotService(self.state, self.connection)
        self.persistence = StatePersistence(config.data_dir)
        self.persistence.load_into(self.state)
        self.stop_event = threading.Event()
        self.http_server = RobotBonaHTTPServer(
            (config.robot_http_host, config.robot_http_port),
            HTTPServiceConfig(config.app_key, config.device_id, config.local_token),
        )
        self.api_server = LocalAPIServer(
            (config.api_host, config.api_port), self.service
        )
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        LOGGER.info(
            "starting robot HTTP=%s:%s TCP=%s:%s API=%s:%s",
            self.config.robot_http_host,
            self.config.robot_http_port,
            self.config.robot_tcp_host,
            self.config.robot_tcp_port,
            self.config.api_host,
            self.config.api_port,
        )
        self._threads = [
            threading.Thread(
                target=self.http_server.serve_forever,
                name="robot-http",
                daemon=True,
            ),
            threading.Thread(
                target=serve_tcp,
                args=(
                    self.config.robot_tcp_host,
                    self.config.robot_tcp_port,
                    self.connection,
                ),
                name="robot-tcp",
                daemon=True,
            ),
            threading.Thread(
                target=self.api_server.serve_forever,
                name="local-api",
                daemon=True,
            ),
            threading.Thread(
                target=self._persistence_loop,
                name="persistence",
                daemon=True,
            ),
        ]
        for thread in self._threads:
            thread.start()

    def run_forever(self) -> None:
        self.start()
        self._install_signal_handlers()
        try:
            self.stop_event.wait()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self.stop_event.is_set():
            # Still execute idempotent server shutdown below.
            pass
        self.stop_event.set()
        try:
            self.persistence.save(self.state)
        except OSError:
            LOGGER.exception("failed to persist final robot state")
        self.http_server.shutdown()
        self.api_server.shutdown()
        self.http_server.server_close()
        self.api_server.server_close()

    def _persistence_loop(self) -> None:
        while not self.stop_event.wait(self.config.persist_interval):
            try:
                self.persistence.save(self.state)
            except OSError:
                LOGGER.exception("failed to persist robot state")

    def _install_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return

        def stop(_signum: int, _frame: object) -> None:
            self.stop_event.set()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)


def _load_options(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    logging.basicConfig(
        level=os.getenv("ROBOTBONA_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        config = RuntimeConfig.from_environment()
    except (ValueError, TypeError) as exc:
        raise SystemExit(f"configuration error: {exc}") from exc
    RobotRuntime(config).run_forever()
