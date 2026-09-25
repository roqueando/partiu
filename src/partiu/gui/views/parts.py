"""Parts list / create / edit view."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from ... import importer
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
        ttk.Button(actions, text="Import…", command=self.import_components).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(actions, text="Template…", command=self.download_template).pack(
            side="left", padx=(6, 0)
        )
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

    def import_components(self) -> None:
        path = filedialog.askopenfilename(
            title="Import components",
            filetypes=[
                ("Spreadsheets", "*.csv *.xlsx *.xlsm"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx *.xlsm"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            result = importer.import_parts_from_file(self.db, Path(path))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.title, f"Import failed:\n{exc}")
            return
        self.load()
        messagebox.showinfo(
            self.title,
            f"Imported {result['created']} component(s).\n"
            f"{result['duplicates']} duplicate(s) skipped.\n"
            f"{result['skipped']} row(s) without a name skipped.",
        )

    def download_template(self) -> None:
        destination = filedialog.asksaveasfilename(
            title="Save component template",
            defaultextension=".csv",
            initialfile="components_template.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not destination:
            return
        try:
            importer.write_template(Path(destination))
        except OSError as exc:
            messagebox.showerror(self.title, f"Could not save template:\n{exc}")
            return
        messagebox.showinfo(self.title, f"Template saved to:\n{destination}")

    def fetch(self, search: str | None) -> list[dict[str, Any]]:
        return self.db.list_parts(search=search)

    def create(self, data: dict[str, Any]) -> None:
        self.db.create_part(data)

    def update(self, pk: int, data: dict[str, Any]) -> None:
        self.db.update_part(pk, data)

    def delete_record(self, pk: int) -> None:
        self.db.delete_part(pk)
