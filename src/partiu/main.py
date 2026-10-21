"""Composition root — the only place that wires concrete adapters to the GUI."""

from __future__ import annotations

from .adapters.persistence import get_data_dir, get_database_file
from .adapters.sqlite_repository import SqliteRepository


def main() -> int:
    """Run the Partiu application."""
    data_dir = get_data_dir()
    repository = SqliteRepository(get_database_file(data_dir))

    try:
        from .gui.app import PartiuApp

        app = PartiuApp(db=repository, data_dir=data_dir)
        app.mainloop()
    finally:
        repository.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
