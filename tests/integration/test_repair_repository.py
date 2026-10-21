"""Integration tests for the SQLite repair repository."""


def test_repair_roundtrip(tmp_db, tmp_path):
    proj = tmp_db.create_repair_project(
        {"name": "Placa X", "equipment": None, "notes": None}
    )["pk"]

    src = tmp_path / "photo.jpg"
    src.write_bytes(b"\xff\xd8\xff\xd9 fake jpeg")
    photo = tmp_db.add_repair_photo(proj, src)["pk"]

    tmp_db.replace_repair_annotations(
        proj,
        [
            {
                "photo_id": photo,
                "label": "U1",
                "category": "CI",
                "x": 0.5,
                "y": 0.5,
                "status": "Good",
                "part_id": None,
                "notes": None,
            }
        ],
    )
    anns = tmp_db.list_repair_annotations(proj)
    assert len(anns) == 1
    assert anns[0]["label"] == "U1"
    assert anns[0]["status"] == "Good"
    assert anns[0]["part_name"] is None


def test_repair_delete_cleans_directory(tmp_db, tmp_path):
    proj = tmp_db.create_repair_project({"name": "P", "equipment": None, "notes": None})["pk"]
    src = tmp_path / "photo.jpg"
    src.write_bytes(b"\xff\xd8\xff\xd9")
    tmp_db.add_repair_photo(proj, src)
    assert (tmp_db.repairs_dir / str(proj)).exists()
    tmp_db.delete_repair_project(proj)
    assert not (tmp_db.repairs_dir / str(proj)).exists()
