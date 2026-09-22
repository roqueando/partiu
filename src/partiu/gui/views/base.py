"""Generic CRUD list view used as the base for Parts / Stock / Locations."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from ..widgets import DataTable, FieldSpec, FormDialog, SearchBar


class CrudView(ttk.Frame):
    """A searchable table with New / Edit / Delete / Refresh controls.

    Subclasses provide:

    - ``title``: heading shown above the table.
    - ``columns``: list of ``(key, heading, width)`` tuples.
    - ``form_fields()``: list of :class:`FieldSpec` for the create/edit form.
    - ``fetch(search)``, ``create(data)``, ``update(pk, data)``, ``delete(pk)``.
    """

    title: str = "Items"
    columns: list[tuple[str, str, int]] = []

    def __init__(self, parent, db, on_status: Callable[[str], None] | None = None):
        super().__init__(parent)
        self.db = db
        self.on_status = on_status or (lambda _msg: None)
        self._search = ""
        self._rows: list[dict[str, Any]] = []

        self._build_ui()
        self.load()

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        header = ttk.Label(self, text=self.title, font=("", 14, "bold"))
        header.pack(anchor="w", padx=8, pady=(8, 4))

        self.search_bar = SearchBar(self, on_search=self._on_search)
        self.search_bar.pack(fill="x", padx=8, pady=(0, 4))

        self.table = DataTable(self, columns=self.columns, on_activate=self.edit)
        self.table.pack(fill="both", expand=True, padx=8, pady=4)

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(actions, text="New", command=self.new).pack(side="left")
        ttk.Button(actions, text="Edit", command=self.edit).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Delete", command=self.delete).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Refresh", command=self.load).pack(side="right")

    # ---------------------------------------------------------------- actions

    def _on_search(self, text: str) -> None:
        self._search = text
        self.load()

    def load(self) -> None:
        try:
            self._rows = self.fetch(self._search or None)
            self.table.set_rows(self._rows)
            self.on_status(f"{len(self._rows)} item(s)")
        except Exception as exc:
            messagebox.showerror(self.title, f"Failed to load data:\n{exc}")

    def new(self) -> None:
        dialog = FormDialog(self, title=f"New {self.title_singular}", fields=self.form_fields())
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        try:
            self.create(data)
            self.load()
        except Exception as exc:
            messagebox.showerror(self.title, f"Failed to create:\n{exc}")

    def edit(self) -> None:
        pk = self.table.selected_pk()
        if pk is None:
            messagebox.showinfo(self.title, "Select an item to edit.")
            return

        current = self._find_row(pk)
        if current is None:
            return

        dialog = FormDialog(
            self,
            title=f"Edit {self.title_singular}",
            fields=self.form_fields(),
            initial=current,
        )
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        try:
            self.update(pk, data)
            self.load()
        except Exception as exc:
            messagebox.showerror(self.title, f"Failed to update:\n{exc}")

    def delete(self) -> None:
        pk = self.table.selected_pk()
        if pk is None:
            messagebox.showinfo(self.title, "Select an item to delete.")
            return
        if not messagebox.askyesno(self.title, f"Delete item #{pk}?"):
            return
        try:
            self.delete_record(pk)
            self.load()
        except Exception as exc:
            messagebox.showerror(self.title, f"Failed to delete:\n{exc}")

    def _find_row(self, pk: int) -> dict[str, Any] | None:
        for row in self._rows:
            if row.get("pk") == pk:
                return row
        return None

    # ------------------------------------------------------ subclass hooks

    @property
    def title_singular(self) -> str:
        return self.title.rstrip("s")

    def form_fields(self) -> list[FieldSpec]:
        raise NotImplementedError

    def fetch(self, search: str | None) -> list[dict[str, Any]]:
        raise NotImplementedError

    def create(self, data: dict[str, Any]) -> None:
        raise NotImplementedError

    def update(self, pk: int, data: dict[str, Any]) -> None:
        raise NotImplementedError

    def delete_record(self, pk: int) -> None:
        raise NotImplementedError
