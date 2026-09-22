"""Main tkinter application window."""

from __future__ import annotations

import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import APP_NAME, __version__
from ..paths import get_database_file
from .views.locations import LocationsView
from .views.parts import PartsView
from .views.stock import StockView


class PartiuApp(tk.Tk):
    """The Partiu main window: sidebar navigation + content area."""

    def __init__(self, db, data_dir: Path):
        super().__init__()
        self.db = db
        self.data_dir = data_dir

        self.title(f"{APP_NAME} - Component Tracker")
        self.geometry("980x620")
        self.minsize(760, 480)

        self._views: dict[str, ttk.Frame] = {}
        self._build_ui()
        self.show_view("parts")

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        sidebar = ttk.Frame(container, width=180, padding=8)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text=APP_NAME.title(), font=("", 16, "bold")).pack(
            anchor="w", pady=(0, 8)
        )
        ttk.Label(sidebar, text=f"v{__version__}", foreground="#777").pack(
            anchor="w", pady=(0, 12)
        )

        self._nav_buttons: dict[str, ttk.Button] = {}
        for key, label in [
            ("parts", "Parts"),
            ("stock", "Stock Items"),
            ("locations", "Stock Locations"),
        ]:
            btn = ttk.Button(
                sidebar, text=label, command=lambda k=key: self.show_view(k)
            )
            btn.pack(fill="x", pady=2)
            self._nav_buttons[key] = btn

        ttk.Separator(sidebar).pack(fill="x", pady=12)
        ttk.Button(sidebar, text="Export database…", command=self.export_database).pack(
            fill="x", pady=2
        )

        self.content = ttk.Frame(container)
        self.content.pack(side="left", fill="both", expand=True)

        self.status = ttk.Label(self, text="Ready", anchor="w", relief="sunken")
        self.status.pack(side="bottom", fill="x")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------------------------------------------------------- views

    def show_view(self, key: str) -> None:
        for name, btn in self._nav_buttons.items():
            state = ["pressed"] if name == key else ["!pressed"]
            btn.state(state)

        view = self._views.get(key)
        if view is None:
            if key == "parts":
                view = PartsView(self.content, self.db, on_status=self._set_status)
            elif key == "stock":
                view = StockView(self.content, self.db, on_status=self._set_status)
            elif key == "locations":
                view = LocationsView(self.content, self.db, on_status=self._set_status)
            else:
                return
            self._views[key] = view

        for child in self.content.winfo_children():
            child.pack_forget()
        view.pack(fill="both", expand=True)

    def _set_status(self, message: str) -> None:
        self.status.configure(text=message)

    # -------------------------------------------------------------- actions

    def export_database(self) -> None:
        db_path = get_database_file(self.data_dir)
        if not db_path.exists():
            messagebox.showerror("Export", "Database file not found.")
            return

        destination = filedialog.asksaveasfilename(
            title="Export database",
            defaultextension=".db",
            initialfile="partiu.db",
            filetypes=[("SQLite database", "*.db *.sqlite3"), ("All files", "*.*")],
        )
        if not destination:
            return

        try:
            shutil.copy2(db_path, destination)
        except OSError as exc:
            messagebox.showerror("Export", f"Export failed:\n{exc}")
            return

        messagebox.showinfo("Export", f"Database exported to:\n{destination}")

    def on_close(self) -> None:
        self.destroy()
