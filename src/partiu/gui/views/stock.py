"""Stock items list / create / edit view."""

from __future__ import annotations

from typing import Any

from ..widgets import FieldSpec
from .base import CrudView

STOCK_STATUSES = [
    "OK",
    "Attention needed",
    "Damaged",
    "Destroyed",
    "Rejected",
    "Lost",
    "Quarantined",
    "Returned",
]


class StockView(CrudView):
    title = "Stock Items"
    columns = [
        ("part_name", "Part", 220),
        ("quantity", "Qty", 70),
        ("location_name", "Location", 160),
        ("serial", "Serial", 120),
        ("batch", "Batch", 100),
        ("status_text", "Status", 140),
    ]

    def form_fields(self) -> list[FieldSpec]:
        parts = self.db.list_parts()
        part_options = [(p["pk"], p.get("name") or f"#{p['pk']}") for p in parts]

        locations = self.db.list_stock_locations()
        location_options = [(None, "(none)")] + [
            (loc["pk"], loc.get("name") or f"#{loc['pk']}") for loc in locations
        ]

        return [
            FieldSpec("Part", "part", kind="combobox", required=True, options=part_options),
            FieldSpec("Quantity", "quantity", kind="number", required=True, default=1),
            FieldSpec("Location", "location", kind="combobox", options=location_options),
            FieldSpec("Serial", "serial", kind="entry"),
            FieldSpec("Batch", "batch", kind="entry"),
            FieldSpec("Status", "status", kind="combobox", options=[(s, s) for s in STOCK_STATUSES], default="OK"),
        ]

    def fetch(self, search: str | None) -> list[dict[str, Any]]:
        return self.db.list_stock_items(search=search)

    def create(self, data: dict[str, Any]) -> None:
        self.db.create_stock_item(data)

    def update(self, pk: int, data: dict[str, Any]) -> None:
        self.db.update_stock_item(pk, data)

    def delete_record(self, pk: int) -> None:
        self.db.delete_stock_item(pk)
