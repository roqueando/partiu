"""Integration tests for the SQLite stock repository."""


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


def test_stock_item_roundtrip(tmp_db):
    part = tmp_db.create_part(_part_data())["pk"]
    item = tmp_db.create_stock_item(
        {"part": part, "quantity": 3, "location": None, "serial": "S1", "batch": "B1", "status": "OK"}
    )["pk"]
    rows = tmp_db.list_stock_items()
    assert len(rows) == 1
    assert rows[0]["pk"] == item
    assert rows[0]["part"] == part
    assert rows[0]["quantity"] == 3
    assert rows[0]["part_name"] == "TL062"


def test_location_label_derivation(tmp_db):
    cabinet = tmp_db.create_stock_location(
        {"name": "A", "description": None, "parent": None}
    )["pk"]
    drawer = tmp_db.create_stock_location(
        {"name": "1", "description": None, "parent": cabinet}
    )["pk"]
    locs = {l["pk"]: l for l in tmp_db.list_stock_locations()}
    assert locs[drawer]["label"] == "A1"
