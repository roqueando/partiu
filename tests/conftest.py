"""Shared pytest fixtures for the Partiu test suite."""

from __future__ import annotations

import pytest

from fakes import (
    FakeDatasheetExtractor,
    FakePartRepository,
    FakePartsImporter,
)


@pytest.fixture
def fake_parts_repo() -> FakePartRepository:
    return FakePartRepository()


@pytest.fixture
def fake_importer() -> FakePartsImporter:
    return FakePartsImporter()


@pytest.fixture
def fake_extractor() -> FakeDatasheetExtractor:
    return FakeDatasheetExtractor()


@pytest.fixture
def tmp_db(tmp_path):
    """A real SQLite repository on a temporary database file."""
    from partiu.adapters.sqlite_repository import SqliteRepository

    db = SqliteRepository(tmp_path / "partiu.db")
    yield db
    db.close()
