"""Reusable tkinter widgets for the Partiu GUI."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk
from typing import Any, Callable


def nested_value(row: dict[str, Any], *keys: str) -> str:
    """Safely extract a nested value from an API response row, returning ``str``."""
    value: Any = row
    for key in keys:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return "" if value is None else str(value)


@dataclass
class FieldSpec:
    """Describes a single field in a form dialog."""

    label: str
    key: str
    kind: str = "entry"  # entry | combobox | check | number
    required: bool = False
    options: list[tuple[Any, str]] = field(default_factory=list)  # (value, label)
    default: Any = None


class DataTable(ttk.Frame):
    """A labelled Treeview with a scrollbar and an optional empty state."""

    def __init__(self, parent, columns: list[tuple[str, str, int]], on_activate=None):
        """columns: list of (key, heading, width)."""
        super().__init__(parent)

        self._column_keys = [key for key, _, _ in columns]

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            container, columns=self._column_keys, show="headings", selectmode="browse"
        )
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w")

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        if on_activate is not None:
            self.tree.bind("<Double-1>", lambda _e: on_activate())

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            values = [self._fmt(row.get(key)) for key in self._column_keys]
            self.tree.insert("", "end", iid=str(row.get("pk", "")), values=values)

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None or value == "":
            return ""
        if isinstance(value, bool):
            return "yes" if value else "no"
        return str(value)

    def selected_pk(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        pk = selection[0]
        try:
            return int(pk)
        except ValueError:
            return None

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())


class SearchBar(ttk.Frame):
    """An entry + button pair used to filter a list view."""

    def __init__(self, parent, on_search: Callable[[str], None]):
        super().__init__(parent)
        self._on_search = on_search

        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.entry.bind("<Return>", lambda _e: self._on_search(self.var.get()))

        self.button = ttk.Button(self, text="Search", command=self._fire)
        self.button.pack(side="left")

        clear = ttk.Button(self, text="Clear", command=self.clear)
        clear.pack(side="left", padx=(4, 0))

    def _fire(self) -> None:
        self._on_search(self.var.get())

    def clear(self) -> None:
        self.var.set("")
        self._on_search("")


class FormDialog(tk.Toplevel):
    """A modal dialog built from a list of :class:`FieldSpec`.

    Call ``result()`` after the dialog closes to retrieve entered values.
    """

    def __init__(self, parent, title: str, fields: list[FieldSpec], initial: dict | None = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)

        self._fields = fields
        self._widgets: dict[str, ttk.Widget] = {}
        self._vars: dict[str, tk.Variable] = {}
        self._result: dict[str, Any] | None = None
        initial = initial or {}

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)

        for i, spec in enumerate(fields):
            ttk.Label(body, text=spec.label + ("" if not spec.required else " *")).grid(
                row=i, column=0, sticky="w", padx=(0, 8), pady=4
            )
            value = initial.get(spec.key, spec.default)

            if spec.kind == "check":
                var = tk.BooleanVar(value=bool(value))
                widget = ttk.Checkbutton(body, variable=var)
            elif spec.kind == "combobox":
                var = tk.StringVar()
                widget = ttk.Combobox(body, textvariable=var, state="readonly")
                widget["values"] = [label for _value, label in spec.options]
                if value is not None:
                    for opt_value, opt_label in spec.options:
                        if str(opt_value) == str(value):
                            var.set(opt_label)
                            break
            else:  # entry | number
                var = tk.StringVar(value="" if value is None else str(value))
                widget = ttk.Entry(body, textvariable=var)

            widget.grid(row=i, column=1, sticky="ew", pady=4)
            self._widgets[spec.key] = widget
            self._vars[spec.key] = var

        body.columnconfigure(1, weight=1)

        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", command=self._save).pack(side="right", padx=(0, 6))

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _save(self) -> None:
        result: dict[str, Any] = {}
        for spec in self._fields:
            var = self._vars[spec.key]

            if spec.required:
                if not str(var.get()).strip():
                    continue  # silently ignore; caller validates

            if spec.kind == "check":
                result[spec.key] = bool(var.get())
            elif spec.kind == "combobox":
                label = var.get()
                value = None
                for opt_value, opt_label in spec.options:
                    if opt_label == label:
                        value = opt_value
                        break
                result[spec.key] = value
            elif spec.kind == "number":
                raw = str(var.get()).strip()
                if raw == "":
                    result[spec.key] = None
                else:
                    try:
                        result[spec.key] = float(raw)
                    except ValueError:
                        result[spec.key] = raw
            else:
                result[spec.key] = str(var.get()).strip() or None

        self._result = result
        self.destroy()

    def result(self) -> dict[str, Any] | None:
        return self._result
