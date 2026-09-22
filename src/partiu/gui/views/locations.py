"""Stock locations list / create / edit view."""

from __future__ import annotations

from typing import Any

from ..widgets import FieldSpec
from .base import CrudView


class LocationsView(CrudView):
    title = "Stock Locations"
    columns = [
        ("name", "Name", 200),
        ("description", "Description", 260),
        ("pathstring", "Path", 260),
        ("items", "Items", 60),
        ("sublocations", "Sub-locations", 100),
    ]

    def form_fields(self) -> list[FieldSpec]:
        locations = self.db.list_stock_locations()
        parent_options = [(None, "(none)")] + [
            (loc["pk"], loc.get("name") or f"#{loc['pk']}") for loc in locations
        ]

        return [
            FieldSpec("Name", "name", kind="entry", required=True),
            FieldSpec("Description", "description", kind="entry"),
            FieldSpec("Parent", "parent", kind="combobox", options=parent_options),
        ]

    def fetch(self, search: str | None) -> list[dict[str, Any]]:
        return self.db.list_stock_locations(search=search)

    def create(self, data: dict[str, Any]) -> None:
        self.db.create_stock_location(data)

    def update(self, pk: int, data: dict[str, Any]) -> None:
        self.db.update_stock_location(pk, data)

    def delete_record(self, pk: int) -> None:
        self.db.delete_stock_location(pk)
