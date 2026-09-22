"""Filesystem paths for user data.

All mutable data lives under a per-user directory so the packaged application
bundle can remain read-only.  Resolved with the standard library only (no
external dependencies):

- macOS:   ``~/Library/Application Support/partiu``
- Windows: ``%APPDATA%\\partiu``
- Linux:   ``~/.local/share/partiu``
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


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
