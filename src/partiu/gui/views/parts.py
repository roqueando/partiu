"""Parts list / create / edit view."""

from __future__ import annotations

from typing import Any

from ..widgets import FieldSpec
from .base import CrudView


class PartsView(CrudView):
    title = "Parts"
    columns = [
        ("name", "Name", 220),
        ("IPN", "IPN", 140),
        ("category", "Category", 160),
        ("description", "Description", 240),
        ("active", "Active", 60),
        ("in_stock", "In Stock", 70),
    ]

    def form_fields(self) -> list[FieldSpec]:
        return [
            FieldSpec("Name", "name", kind="entry", required=True),
            FieldSpec("IPN", "IPN", kind="entry"),
            FieldSpec("Category", "category", kind="entry"),
            FieldSpec("Description", "description", kind="entry"),
            FieldSpec("Units", "units", kind="entry"),
            FieldSpec("Active", "active", kind="check", default=True),
        ]

    def fetch(self, search: str | None) -> list[dict[str, Any]]:
        return self.db.list_parts(search=search)

    def create(self, data: dict[str, Any]) -> None:
        self.db.create_part(data)

    def update(self, pk: int, data: dict[str, Any]) -> None:
        self.db.update_part(pk, data)

    def delete_record(self, pk: int) -> None:
        self.db.delete_part(pk)
