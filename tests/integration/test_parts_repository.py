"""Integration tests for the SQLite part repository."""


def _part_data(**overrides):
    data = {
        "name": "TL062",
        "IPN": None,
        "category": "OpAmp",
        "description": None,
        "units": None,
        "manufacturer": None,
        "package": None,
        "package_size": None,
        "active": True,
    }
    data.update(overrides)
    return data


def test_parts_crud(tmp_db):
    pk = tmp_db.create_part(_part_data())["pk"]
    part = tmp_db.get_part(pk)
    assert part["name"] == "TL062"
    assert part["active"] is True
    assert any(r["pk"] == pk for r in tmp_db.list_parts(search="TL0"))


def test_import_dedupe(tmp_db):
    result = tmp_db.import_parts(
        [
            {"name": "A", "active": True},
            {"name": "A", "active": True},
            {"name": "", "active": True},
        ]
    )
    assert result == {"created": 1, "skipped": 1, "duplicates": 1}


def test_delete_removes_part(tmp_db):
    pk = tmp_db.create_part(_part_data())["pk"]
    tmp_db.delete_part(pk)
    assert tmp_db.get_part(pk) is None
