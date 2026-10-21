"""Stock item and stock location entities."""

from __future__ import annotations

from dataclasses import dataclass

#: Status vocabulary used by the stock form and list (unchanged).
STATUSES = [
    "OK",
    "Attention needed",
    "Damaged",
    "Destroyed",
    "Rejected",
    "Lost",
    "Quarantined",
    "Returned",
]


@dataclass
class StockLocation:
    """A physical storage place (drawer/cabinet hierarchy).

    ``label`` is derived (concatenation of ancestor names root→leaf, e.g. ``A1``)
    and is not a stored field.
    """

    name: str
    description: str | None = None
    parent_id: int | None = None


@dataclass
class StockItem:
    """A physical quantity of a part at a location."""

    part_id: int
    quantity: float = 0.0
    location_id: int | None = None
    serial: str | None = None
    batch: str | None = None
    status: str = "OK"
