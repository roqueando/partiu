"""Swap demonstration: the same use case against in-memory and SQLite adapters."""

from pathlib import Path

from fakes import FakePartsImporter
from partiu.application.use_cases.import_parts import import_parts_from_file


def test_swap_demo_same_results(tmp_db, fake_parts_repo):
    rows = [
        {"name": "X", "active": True},
        {"name": "X", "active": True},  # duplicate
        {"name": "Y", "active": True},
    ]
    importer = FakePartsImporter(rows=rows)

    in_memory = import_parts_from_file(fake_parts_repo, importer, Path("unused.csv"))
    sqlite = import_parts_from_file(tmp_db, importer, Path("unused.csv"))

    assert in_memory["created"] == sqlite["created"] == 2
    assert in_memory["duplicates"] == sqlite["duplicates"] == 1
    assert in_memory["skipped"] == sqlite["skipped"] == 0
