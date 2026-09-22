"""User settings persistence.

Small UI-level preferences (window geometry, last view, etc.) are kept as JSON
in the user data directory.
"""

from __future__ import annotations

import json
from pathlib import Path

from .paths import get_data_dir


class UserSettings:
    """Persist small UI preferences as JSON."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or get_data_dir()
        self.path = self.data_dir / "settings.json"
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()
