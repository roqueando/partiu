"""Stock items list / create / edit view."""

from __future__ import annotations

from tkinter import messagebox, ttk
from typing import Any

from ..widgets import FieldSpec, FormDialog
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
        ("location_label", "Location", 160),
        ("serial", "Serial", 120),
        ("batch", "Batch", 100),
        ("status_text", "Status", 140),
    ]

    selectmode = "extended"

    def _location_options(self) -> list[tuple[Any, str]]:
        locations = self.db.list_stock_locations()
        drawers = [loc for loc in locations if loc.get("parent_id") is not None]
        return [(None, "(none)")] + [
            (loc["pk"], loc.get("label") or loc.get("name") or f"#{loc['pk']}")
            for loc in drawers
        ]

    def form_fields(self) -> list[FieldSpec]:
        parts = self.db.list_parts()
        part_options = [(p["pk"], p.get("name") or f"#{p['pk']}") for p in parts]

        return [
            FieldSpec("Part", "part", kind="combobox", required=True, options=part_options),
            FieldSpec("Quantity", "quantity", kind="number", required=True, default=1),
            FieldSpec("Location", "location", kind="combobox", options=self._location_options()),
            FieldSpec("Serial", "serial", kind="entry"),
            FieldSpec("Batch", "batch", kind="entry"),
            FieldSpec("Status", "status", kind="combobox", options=[(s, s) for s in STOCK_STATUSES], default="OK"),
        ]

    def _build_extra_actions(self, actions) -> None:
        ttk.Button(actions, text="Pull all parts…", command=self.pull_all_parts).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(actions, text="Set location…", command=self.assign_location).pack(
            side="left", padx=(6, 0)
        )

    def pull_all_parts(self) -> None:
        if not messagebox.askyesno(
            self.title,
            "Create a stock item (quantity 1) for every part that does not"
            " have one yet?",
        ):
            return
        try:
            created = self.db.create_stock_items_for_all_parts()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.title, f"Failed to pull parts:\n{exc}")
            return
        self.load()
        messagebox.showinfo(
            self.title,
            f"Added {created} stock item(s)."
            + ("" if created else " All parts already have stock items."),
        )

    def assign_location(self) -> None:
        pks = self.table.selected_pks()
        if not pks:
            messagebox.showinfo(self.title, "Select one or more items to assign.")
            return
        dialog = FormDialog(
            self,
            title="Set location",
            fields=[
                FieldSpec("Location", "location", kind="combobox",
                          options=self._location_options())
            ],
        )
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        try:
            self.db.set_stock_items_location(pks, data.get("location"))
            self.load()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.title, f"Failed to set location:\n{exc}")

    def fetch(self, search: str | None) -> list[dict[str, Any]]:
        return self.db.list_stock_items(search=search)

    def create(self, data: dict[str, Any]) -> None:
        self.db.create_stock_item(data)

    def update(self, pk: int, data: dict[str, Any]) -> None:
        self.db.update_stock_item(pk, data)

    def delete_record(self, pk: int) -> None:
        self.db.delete_stock_item(pk)
