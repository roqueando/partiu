"""Parts list / create / edit view."""

from __future__ import annotations

from tkinter import messagebox, ttk
from typing import Any

from ..widgets import FieldSpec
from .base import CrudView
from .detail import PartDetailView


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

    def _build_extra_actions(self, actions) -> None:
        ttk.Button(actions, text="Details", command=self.show_details).pack(
            side="left", padx=(6, 0)
        )

    def open(self) -> None:
        self.show_details()

    def show_details(self) -> None:
        pk = self.table.selected_pk()
        if pk is None:
            messagebox.showinfo(self.title, "Select a part to view details.")
            return
        PartDetailView(self, self.db, pk)

    def fetch(self, search: str | None) -> list[dict[str, Any]]:
        return self.db.list_parts(search=search)

    def create(self, data: dict[str, Any]) -> None:
        self.db.create_part(data)

    def update(self, pk: int, data: dict[str, Any]) -> None:
        self.db.update_part(pk, data)

    def delete_record(self, pk: int) -> None:
        self.db.delete_part(pk)
