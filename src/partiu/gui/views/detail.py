"""Detail view for a single part: photo, datasheet, pins and parameters."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from PIL import Image, ImageTk

from ... import pdf_extract
from ..widgets import DataTable, FieldSpec, FormDialog

_PIN_COLUMNS = [
    ("pin_number", "Pin", 60),
    ("name", "Name", 120),
    ("type", "Type", 60),
    ("description", "Description", 260),
]

_PARAM_COLUMNS = [
    ("symbol", "Sym", 90),
    ("name", "Name", 180),
    ("test_conditions", "Conditions", 220),
    ("min", "Min", 55),
    ("typ", "Typ", 55),
    ("max", "Max", 55),
    ("unit", "Unit", 55),
]

_PIN_FIELDS = [
    FieldSpec("Pin number", "pin_number", kind="entry"),
    FieldSpec("Name", "name", kind="entry", required=True),
    FieldSpec("Type", "type", kind="entry"),
    FieldSpec("Description", "description", kind="entry"),
]

_PARAM_FIELDS = [
    FieldSpec("Category", "category", kind="entry", default="Electrical"),
    FieldSpec("Symbol", "symbol", kind="entry"),
    FieldSpec("Name", "name", kind="entry", required=True),
    FieldSpec("Test conditions", "test_conditions", kind="entry"),
    FieldSpec("Min", "min", kind="entry"),
    FieldSpec("Typ", "typ", kind="entry"),
    FieldSpec("Max", "max", kind="entry"),
    FieldSpec("Unit", "unit", kind="entry"),
]

_INFO_FIELDS = [
    ("manufacturer", "Manufacturer"),
    ("package", "Package"),
    ("package_size", "Package size"),
    ("units", "Units"),
    ("description", "Description"),
]


class PartDetailView(tk.Toplevel):
    """A modal window showing the full details of one part."""

    def __init__(self, master, db, part_pk: int):
        super().__init__(master)
        self.db = db
        self.part_pk = part_pk

        self.title("Component details")
        self.geometry("960x680")
        self.minsize(820, 560)
        self.transient(master)

        self._photo_ref = None
        self._info_vars: dict[str, tk.StringVar] = {}
        self._datasheet_label: ttk.Label | None = None

        self._build_ui()
        self.reload()

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="both", expand=True)

        # ---- header row: photo + info ----
        header = ttk.Frame(top)
        header.pack(fill="x")

        self.photo_label = ttk.Label(
            header, text="(no photo)", anchor="center", relief="solid", width=32
        )
        self.photo_label.pack(side="left", padx=(0, 12), ipady=8)

        photo_buttons = ttk.Frame(header)
        photo_buttons.pack(side="left", fill="y")
        ttk.Button(photo_buttons, text="Add / change photo", command=self.add_photo).pack(
            fill="x", pady=2
        )
        ttk.Button(photo_buttons, text="Remove photo", command=self.remove_photo).pack(
            fill="x", pady=2
        )

        info = ttk.Frame(header)
        info.pack(side="left", fill="both", expand=True, padx=(16, 0))

        self.name_var = tk.StringVar()
        self.ipn_var = tk.StringVar()
        self.category_var = tk.StringVar()

        ttk.Label(info, textvariable=self.name_var, font=("", 15, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(info, textvariable=self.ipn_var, foreground="#666").grid(
            row=1, column=0, columnspan=2, sticky="w"
        )

        for i, (key, label) in enumerate(_INFO_FIELDS):
            var = tk.StringVar()
            self._info_vars[key] = var
            ttk.Label(info, text=label).grid(
                row=i + 2, column=0, sticky="w", padx=(0, 8), pady=2
            )
            ttk.Entry(info, textvariable=var).grid(
                row=i + 2, column=1, sticky="ew", pady=2
            )

        ttk.Label(info, text="Category").grid(
            row=7, column=0, sticky="w", padx=(0, 8), pady=2
        )
        ttk.Entry(info, textvariable=self.category_var).grid(
            row=7, column=1, sticky="ew", pady=2
        )

        info.columnconfigure(1, weight=1)
        ttk.Button(info, text="Save info", command=self.save_info).grid(
            row=8, column=1, sticky="e", pady=(6, 0)
        )

        # ---- datasheet row ----
        ds = ttk.Frame(top)
        ds.pack(fill="x", pady=(10, 0))
        self._datasheet_label = ttk.Label(ds, text="Datasheet: none", foreground="#666")
        self._datasheet_label.pack(side="left")
        ttk.Button(ds, text="Attach datasheet…", command=self.attach_datasheet).pack(
            side="right"
        )
        ttk.Button(ds, text="Open datasheet", command=self.open_datasheet).pack(
            side="right", padx=(0, 6)
        )
        ttk.Button(ds, text="Extract from datasheet", command=self.extract_datasheet).pack(
            side="right", padx=(0, 6)
        )

        # ---- notebook: pins / parameters ----
        self.notebook = ttk.Notebook(top)
        self.notebook.pack(fill="both", expand=True, pady=(10, 0))

        self.pins_tab = self._make_table_tab(
            self.notebook,
            "Pins",
            _PIN_COLUMNS,
            _PIN_FIELDS,
            self.db.list_pins,
            self.db.add_pin,
            self.db.update_pin,
            self.db.delete_pin,
        )
        self.params_tab = self._make_table_tab(
            self.notebook,
            "Parameters",
            _PARAM_COLUMNS,
            _PARAM_FIELDS,
            self.db.list_parameters,
            self.db.add_parameter,
            self.db.update_parameter,
            self.db.delete_parameter,
        )
        self.notebook.add(self.pins_tab, text="Pins")
        self.notebook.add(self.params_tab, text="Parameters")

    def _make_table_tab(
        self, parent, title, columns, fields, list_fn, add_fn, update_fn, delete_fn
    ) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=8)
        table = DataTable(frame, columns=columns, on_activate=lambda: self._edit_row(table, fields, list_fn, update_fn))
        table.pack(fill="both", expand=True)
        frame._table = table  # type: ignore[attr-defined]

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Add", command=lambda: self._add_row(table, fields, list_fn, add_fn)).pack(
            side="left"
        )
        ttk.Button(actions, text="Edit", command=lambda: self._edit_row(table, fields, list_fn, update_fn)).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(actions, text="Delete", command=lambda: self._delete_row(table, list_fn, delete_fn)).pack(
            side="left", padx=(6, 0)
        )
        return frame

    # ------------------------------------------------------------------ load

    def reload(self) -> None:
        part = self.db.get_part(self.part_pk)
        if part is None:
            self.destroy()
            return

        self.name_var.set(part.get("name") or "")
        self.ipn_var.set(part.get("IPN") or "")
        self.category_var.set(part.get("category") or "")
        for key in self._info_vars:
            self._info_vars[key].set(part.get(key) or "")

        self._load_photo()
        self._refresh_tables()
        self._refresh_datasheet_label()

    def _refresh_tables(self) -> None:
        self.pins_tab._table.set_rows(self.db.list_pins(self.part_pk))
        self.params_tab._table.set_rows(self.db.list_parameters(self.part_pk))

    # ----------------------------------------------------------------- photo

    def _load_photo(self) -> None:
        self._photo_ref = None
        self.photo_label.configure(image="", text="(no photo)")
        att = self.db.get_attachment(self.part_pk, "photo")
        if not att:
            return
        path = self.db.attachment_path(att["pk"])
        if not path:
            return
        try:
            image = Image.open(path)
            image.thumbnail((240, 240))
            self._photo_ref = ImageTk.PhotoImage(image)
            self.photo_label.configure(image=self._photo_ref, text="")
        except Exception:  # noqa: BLE001 - non-image / unreadable
            self.photo_label.configure(text="(unreadable photo)")

    def add_photo(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a photo",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.db.set_attachment(self.part_pk, "photo", Path(path))
        self._load_photo()

    def remove_photo(self) -> None:
        att = self.db.get_attachment(self.part_pk, "photo")
        if att:
            self.db.delete_attachment(att["pk"])
        self._load_photo()

    # ------------------------------------------------------------- datasheet

    def _refresh_datasheet_label(self) -> None:
        att = self.db.get_attachment(self.part_pk, "datasheet")
        if att:
            self._datasheet_label.configure(
                text=f"Datasheet: {att['filename']}", foreground="#000"
            )
        else:
            self._datasheet_label.configure(
                text="Datasheet: none", foreground="#666"
            )

    def attach_datasheet(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a datasheet",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        self.db.set_attachment(self.part_pk, "datasheet", Path(path))
        self._refresh_datasheet_label()

    def open_datasheet(self) -> None:
        att = self.db.get_attachment(self.part_pk, "datasheet")
        if not att:
            messagebox.showinfo("Datasheet", "No datasheet attached.")
            return
        path = self.db.attachment_path(att["pk"])
        if not path:
            messagebox.showerror("Datasheet", "Datasheet file is missing.")
            return
        _open_with_system(path)

    def extract_datasheet(self) -> None:
        att = self.db.get_attachment(self.part_pk, "datasheet")
        if not att:
            messagebox.showinfo("Datasheet", "Attach a datasheet first.")
            return
        path = self.db.attachment_path(att["pk"])
        if not path:
            messagebox.showerror("Datasheet", "Datasheet file is missing.")
            return

        if not messagebox.askyesno(
            "Extract from datasheet",
            "This will replace the current pins and parameters with the"
            " extracted data. Continue?",
        ):
            return

        try:
            data = pdf_extract.extract(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Extraction failed", str(exc))
            return

        if data.get("manufacturer"):
            self._info_vars["manufacturer"].set(data["manufacturer"])
        if data.get("package"):
            self._info_vars["package"].set(data["package"])
        if data.get("package_size"):
            self._info_vars["package_size"].set(data["package_size"])

        self.db.replace_pins(self.part_pk, data.get("pins", []))
        self.db.replace_parameters(self.part_pk, data.get("parameters", []))
        self._refresh_tables()

        messagebox.showinfo(
            "Extraction complete",
            f"Extracted {len(data.get('pins', []))} pins and"
            f" {len(data.get('parameters', []))} parameters.",
        )

    # ------------------------------------------------------------------ info

    def save_info(self) -> None:
        data = {
            "name": self.name_var.get(),
            "IPN": self.ipn_var.get(),
            "category": self.category_var.get(),
            "active": True,
        }
        for key, var in self._info_vars.items():
            data[key] = var.get()
        try:
            self.db.update_part(self.part_pk, data)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save", f"Failed to save:\n{exc}")
            return
        messagebox.showinfo("Save", "Saved.")

    # --------------------------------------------------------- table editing

    def _add_row(self, table, fields, list_fn, add_fn) -> None:
        dialog = FormDialog(self, title="Add", fields=fields)
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        add_fn(self.part_pk, data)
        self._refresh_tables()

    def _edit_row(self, table, fields, list_fn, update_fn) -> None:
        pk = table.selected_pk()
        if pk is None:
            messagebox.showinfo("Edit", "Select a row to edit.")
            return
        current = next((r for r in list_fn(self.part_pk) if r["pk"] == pk), None)
        if current is None:
            return
        dialog = FormDialog(self, title="Edit", fields=fields, initial=current)
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        update_fn(pk, data)
        self._refresh_tables()

    def _delete_row(self, table, list_fn, delete_fn) -> None:
        pk = table.selected_pk()
        if pk is None:
            messagebox.showinfo("Delete", "Select a row to delete.")
            return
        if not messagebox.askyesno("Delete", "Delete this row?"):
            return
        delete_fn(pk)
        self._refresh_tables()


def _open_with_system(path: Path) -> None:
    """Open a file with the OS default application."""
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
