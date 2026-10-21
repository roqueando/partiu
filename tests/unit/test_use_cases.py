"""Unit tests for the application use cases (with fakes)."""

from pathlib import Path

from fakes import FakeDatasheetExtractor
from partiu.application.use_cases.extract_datasheet import extract_datasheet
from partiu.application.use_cases.import_parts import import_parts_from_file


def test_import_parts_use_case(fake_parts_repo, fake_importer):
    fake_importer.rows = [
        {"name": "TL062", "category": "OpAmp", "active": True},
        {"name": "TL062", "category": "dup", "active": True},  # duplicate
        {"name": "", "category": "skipped"},  # no name
    ]
    result = import_parts_from_file(fake_parts_repo, fake_importer, Path("unused.csv"))
    assert result["created"] == 1
    assert result["duplicates"] == 1
    assert result["skipped"] == 1
    assert result["total"] == 3
    assert [p["name"] for p in fake_parts_repo.list_parts()] == ["TL062"]


def test_extract_datasheet_use_case_no_ocr_needed():
    primary = FakeDatasheetExtractor(
        result={
            "manufacturer": "Texas Instruments",
            "package": "SOIC-8",
            "package_size": "",
            "pins": [{"pin_number": "1", "name": "VCC"}],
            "parameters": [{"name": "Icc", "typ": "2"}],
        }
    )
    ocr = FakeDatasheetExtractor()
    data = extract_datasheet(primary, ocr, Path("d.pdf"), part_name="TL062")
    assert data["manufacturer"] == "Texas Instruments"
    assert ocr.calls == []  # OCR fallback not triggered


def test_extract_datasheet_use_case_ocr_fallback():
    primary = FakeDatasheetExtractor()
    ocr = FakeDatasheetExtractor(
        result={
            "manufacturer": "STM",
            "package": "SOIC-8",
            "package_size": "",
            "pins": [{"pin_number": "1", "name": "VCC"}],
            "parameters": [{"name": "Icc", "typ": "2"}],
        }
    )
    data = extract_datasheet(primary, ocr, Path("d.pdf"))
    assert data["manufacturer"] == "STM"
    assert data["pins"] == [{"pin_number": "1", "name": "VCC"}]
