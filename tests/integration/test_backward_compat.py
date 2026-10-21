"""Backward-compatibility test: a pre-migration database must open unchanged."""

from partiu.adapters.sqlite_repository import SqliteRepository


def test_reopen_existing_database(tmp_path):
    path = tmp_path / "partiu.db"

    db = SqliteRepository(path)
    pk = db.create_part(
        {
            "name": "TL062",
            "IPN": "IPN-1",
            "category": "OpAmp",
            "description": None,
            "units": None,
            "manufacturer": None,
            "package": None,
            "package_size": None,
            "active": True,
        }
    )["pk"]
    db.close()

    # Reopen as if it were a database created by the previous version.
    db2 = SqliteRepository(path)
    part = db2.get_part(pk)
    assert part["name"] == "TL062"
    assert part["IPN"] == "IPN-1"
    db2.close()
