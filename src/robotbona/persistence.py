"""Minimal local persistence for public robot state and last map/track data."""

from __future__ import annotations

import json
from pathlib import Path

from .state import RobotState


class StatePersistence:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.state_path = self.data_dir / "latest_state.json"
        self.map_path = self.data_dir / "latest_map.txt"
        self.track_path = self.data_dir / "latest_track.txt"

    def load_into(self, state: RobotState) -> None:
        """Restore only non-sensitive, useful last-known state.

        Connection/session credentials are intentionally never restored.
        """
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            saved_state = payload.get("state")
            if isinstance(saved_state, dict):
                state.values.update(saved_state)
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass

        try:
            state.map_data = self.map_path.read_text(encoding="ascii")
        except (FileNotFoundError, OSError, UnicodeError):
            pass
        try:
            state.track_data = self.track_path.read_text(encoding="ascii")
        except (FileNotFoundError, OSError, UnicodeError):
            pass

        # A process restart never implies a live robot connection.
        state.connected = False

    def save(self, state: RobotState) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        public = state.public_snapshot()
        self._atomic_write(
            self.state_path,
            json.dumps(
                {
                    "state": public["state"],
                    "friendly": public["friendly"],
                    "raw": public["raw"],
                },
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            "utf-8",
        )
        if state.map_data is not None:
            self._atomic_write(self.map_path, state.map_data, "ascii")
        if state.track_data is not None:
            self._atomic_write(self.track_path, state.track_data, "ascii")

    @staticmethod
    def _atomic_write(path: Path, content: str, encoding: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding=encoding)
        temporary.replace(path)
