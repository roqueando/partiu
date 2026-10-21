"""Unit tests for domain entities and constants."""

from partiu.domain.part import Part
from partiu.domain.repair import (
    CATEGORIES,
    DEFAULT_FINDING_STATUS,
    FINDING_STATUSES,
    RepairFinding,
)
from partiu.domain.stock import STATUSES, StockItem, StockLocation


def test_part_defaults():
    part = Part(name="TL062")
    assert part.name == "TL062"
    assert part.active is True
    assert part.ipn is None


def test_stock_statuses_unchanged():
    assert STATUSES == [
        "OK",
        "Attention needed",
        "Damaged",
        "Destroyed",
        "Rejected",
        "Lost",
        "Quarantined",
        "Returned",
    ]
    assert StockItem(part_id=1).status == "OK"


def test_location_label_is_derived_not_stored():
    loc = StockLocation(name="1")
    assert not hasattr(loc, "label")


def test_finding_statuses_and_default():
    assert FINDING_STATUSES["Good"] == "Bom"
    assert FINDING_STATUSES["Bad"] == "Ruim"
    assert FINDING_STATUSES["Needs testing"] == "Precisa testar"
    assert DEFAULT_FINDING_STATUS == "Needs testing"
    finding = RepairFinding(project_id=1, photo_id=1, label="U1", x=0.5, y=0.5)
    assert finding.status == "Needs testing"


def test_categories_include_common_types():
    for expected in ("Trilha", "CI", "Componente", "Conector"):
        assert expected in CATEGORIES
