"""Persistence adapters: user settings (JSON) and filesystem paths.

All mutable data lives under a per-user directory so the packaged application
bundle can remain read-only. Resolved with the standard library only.

- macOS:   ``~/Library/Application Support/partiu``
- Windows: ``%APPDATA%\\partiu``
- Linux:   ``~/.local/share/partiu``
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .. import APP_NAME


def get_data_dir() -> Path:
    """Return (and create) the per-user data directory."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        base = Path.home() / ".local" / "share"

    data_dir = base / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_database_file(data_dir: Path | None = None) -> Path:
    """Return the path of the SQLite database file."""
    data_dir = data_dir or get_data_dir()
    return data_dir / "partiu.db"


class UserSettings:
    """Persist small UI preferences as JSON in the user data directory."""

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
