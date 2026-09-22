"""Application entry point: open the local database and launch the GUI."""

from __future__ import annotations

from .db import Database
from .paths import get_data_dir, get_database_file


def main() -> int:
    """Run the Partiu application."""
    data_dir = get_data_dir()
    db = Database(get_database_file(data_dir))

    try:
        from .gui.app import PartiuApp

        app = PartiuApp(db=db, data_dir=data_dir)
        app.mainloop()
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
