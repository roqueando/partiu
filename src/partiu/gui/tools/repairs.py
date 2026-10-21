"""Reparos tool: annotate repair photos and link findings to inventory."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from PIL import Image, ImageTk

from ..camera_dialog import CameraCaptureDialog
from ..widgets import DataTable, FieldSpec, FormDialog, SearchBar
from ...domain.repair import (
    CATEGORIES,
    DEFAULT_FINDING_STATUS,
    FINDING_STATUS_OPTIONS as STATUS_OPTIONS,
    FINDING_STATUSES as STATUS_LABELS,
)

#: Annotation canvas size (the photo is scaled to fit inside it).
_CANVAS_WIDTH = 760
_CANVAS_HEIGHT = 480

#: Marker radius on the canvas, in pixels.
_MARKER_RADIUS = 8

#: Photo list columns for the part picker.
_PART_COLUMNS = [
    ("name", "Name", 200),
    ("IPN", "IPN", 120),
    ("category", "Category", 120),
    ("description", "Description", 200),
]


class PartPickerDialog(tk.Toplevel):
    """Modal search dialog returning the selected inventory part ``pk``."""

    def __init__(self, master, db) -> None:
        super().__init__(master)
        self.db = db
        self.title("Vincular ao inventário")
        self.geometry("680x480")
        self.transient(master)
        self._pk: int | None = None

        self._build_ui()
        self._on_search("")
        self.grab_set()

    def _build_ui(self) -> None:
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        self.search = SearchBar(body, on_search=self._on_search)
        self.search.pack(fill="x")

        self.table = DataTable(
            body, columns=_PART_COLUMNS, on_activate=self._choose
        )
        self.table.pack(fill="both", expand=True, pady=(6, 0))

        buttons = ttk.Frame(self, padding=10)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Selecionar", command=self._choose).pack(
            side="right", padx=(0, 6)
        )

    def _on_search(self, text: str) -> None:
        self.table.set_rows(self.db.list_parts(search=text or None))

    def _choose(self) -> None:
        pk = self.table.selected_pk()
        if pk is None:
            messagebox.showinfo(self.title, "Selecione um componente.")
            return
        self._pk = pk
        self.destroy()

    def result(self) -> int | None:
        return self._pk


class RepairsDialog(tk.Toplevel):
    """Tabbed repair-project workspace: annotate photos, table of findings."""

    def __init__(
        self,
        master,
        db,
        search_inventory: Callable[[str], None] | None = None,
        open_part: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.db = db
        self._search_inventory = search_inventory or (lambda _term: None)
        self._open_part = open_part or self._open_part_unavailable

        self.title("Reparos")
        self.geometry("1080x720")
        self.minsize(900, 600)
        self.transient(master)

        self.project_id: int | None = None
        self._projects: list[dict[str, Any]] = []
        self._photos: list[dict[str, Any]] = []
        self._annotations: list[dict[str, Any]] = []
        self._current_photo_id: int | None = None
        self._selected_idx: int | None = None
        self._dirty = False
        self._loading = False

        # Canvas state.
        self._photo_ref: ImageTk.PhotoImage | None = None
        self._photo_image: Image.Image | None = None
        self._scale = 1.0
        self._offset = (0, 0)
        self._markers: list[dict[str, Any]] = []
        self._marker_items: list[int] = []

        self._build_ui()
        self._reload_projects()
        self._render_photo()
        self._refresh_findings_table()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        self._build_toolbar()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self._build_tab1(self.notebook)
        self._build_tab2(self.notebook)
        self._build_tab3(self.notebook)

        footer = ttk.Label(self, textvariable=self._status_var(), anchor="w")
        footer.pack(fill="x", padx=8, pady=(0, 4))

    def _status_var(self) -> tk.StringVar:
        if not hasattr(self, "_status_text"):
            self._status_text = tk.StringVar(value="Nenhum projeto aberto.")
        return self._status_text

    def _set_status(self, message: str) -> None:
        self._status_var().set(message)

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")

        row = ttk.Frame(toolbar)
        row.pack(fill="x")
        ttk.Label(row, text="Abrir:").pack(side="left")
        self.project_box = ttk.Combobox(row, state="readonly", width=28)
        self.project_box.pack(side="left", padx=(6, 0))
        self.project_box.bind("<<ComboboxSelected>>", self._on_project_selected)
        ttk.Button(row, text="Novo…", command=self._new_project).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(row, text="Salvar", command=self._save).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(row, text="Excluir", command=self._delete_project).pack(
            side="left", padx=(6, 0)
        )

        meta = ttk.Frame(toolbar)
        meta.pack(fill="x", pady=(6, 0))
        ttk.Label(meta, text="Nome:").pack(side="left")
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(meta, textvariable=self.name_var, width=28)
        self.name_entry.pack(side="left", padx=(6, 0))
        ttk.Label(meta, text="Equipamento:").pack(side="left", padx=(12, 0))
        self.equipment_var = tk.StringVar()
        ttk.Entry(meta, textvariable=self.equipment_var, width=22).pack(
            side="left", padx=(6, 0)
        )
        ttk.Label(meta, text="Notas:").pack(side="left", padx=(12, 0))
        self.notes_var = tk.StringVar()
        ttk.Entry(meta, textvariable=self.notes_var, width=22).pack(
            side="left", padx=(6, 0)
        )

        for var in (self.name_var, self.equipment_var, self.notes_var):
            var.trace_add("write", self._on_meta_change)

    def _on_meta_change(self, *_args) -> None:
        if not self._loading:
            self._dirty = True

    # ---------------------------------------------------------------- tab 1

    def _build_tab1(self, notebook) -> None:
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text="Análise e reconhecimento")

        # ---- photo controls ----
        controls = ttk.Frame(tab)
        controls.pack(fill="x")
        ttk.Label(controls, text="Foto:").pack(side="left")
        self.photo_box = ttk.Combobox(controls, state="readonly", width=34)
        self.photo_box.pack(side="left", padx=(6, 0))
        self.photo_box.bind("<<ComboboxSelected>>", self._on_photo_selected)
        ttk.Button(controls, text="Tirar foto…", command=self._take_photo).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(controls, text="Importar imagem…", command=self._import_photo).pack(
            side="left", padx=(6, 0)
        )
        self.remove_photo_button = ttk.Button(
            controls, text="Remover foto", command=self._remove_photo
        )
        self.remove_photo_button.pack(side="left", padx=(6, 0))

        # ---- annotation canvas ----
        self.canvas = tk.Canvas(
            tab,
            width=_CANVAS_WIDTH,
            height=_CANVAS_HEIGHT,
            highlightthickness=1,
            relief="solid",
            background="#2b2b2b",
        )
        self.canvas.pack(fill="both", expand=True, pady=(8, 0))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)

        # ---- marker actions ----
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(8, 0))
        self.edit_marker_button = ttk.Button(
            actions, text="Editar rótulo", command=self._edit_marker, state="disabled"
        )
        self.edit_marker_button.pack(side="left")
        self.remove_marker_button = ttk.Button(
            actions, text="Remover rótulo", command=self._remove_marker, state="disabled"
        )
        self.remove_marker_button.pack(side="left", padx=(6, 0))
        ttk.Label(
            actions,
            text="Clique na imagem para adicionar um rótulo; arraste um marcador para movê-lo.",
            foreground="#777",
        ).pack(side="right")

    # ---------------------------------------------------------------- tab 2

    def _build_tab2(self, notebook) -> None:
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text="Tabela de rótulos")

        self.findings_table = DataTable(
            tab,
            columns=[
                ("photo", "Foto", 180),
                ("label", "Rótulo", 200),
                ("category", "Categoria", 120),
                ("status", "Status", 120),
                ("part", "Parte vinculada", 180),
                ("notes", "Notas", 200),
            ],
            on_activate=self._open_finding,
        )
        self.findings_table.pack(fill="both", expand=True)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Editar", command=self._edit_finding).pack(side="left")
        ttk.Button(
            actions, text="Vincular ao inventário…", command=self._link_finding
        ).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Abrir detalhes", command=self._open_finding).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(actions, text="Desvincular", command=self._unlink_finding).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(actions, text="Remover", command=self._remove_finding).pack(
            side="left", padx=(6, 0)
        )

    # ---------------------------------------------------------------- tab 3

    def _build_tab3(self, notebook) -> None:
        tab = ttk.Frame(notebook, padding=20)
        notebook.add(tab, text="…")
        ttk.Label(
            tab,
            text="Em breve",
            font=("", 16),
            foreground="#777",
        ).pack(expand=True)

    # -------------------------------------------------------------- projects

    def _reload_projects(self) -> None:
        self._projects = self.db.list_repair_projects()
        self.project_box["values"] = [p["name"] for p in self._projects]
        self._sync_project_box()

    def _sync_project_box(self) -> None:
        if self.project_id is None:
            self.project_box.set("")
            return
        for i, p in enumerate(self._projects):
            if p["pk"] == self.project_id:
                self.project_box.current(i)
                return
        self.project_box.set("")

    def _on_project_selected(self, _event=None) -> None:
        label = self.project_box.get()
        for p in self._projects:
            if p["name"] == label and p["pk"] != self.project_id:
                if not self._maybe_save():
                    self._sync_project_box()
                    return
                self._load_project(p["pk"])
                return

    def _new_project(self) -> None:
        dialog = FormDialog(
            self,
            title="Novo projeto de reparo",
            fields=[
                FieldSpec("Nome", "name", kind="entry", required=True),
                FieldSpec("Equipamento", "equipment", kind="entry"),
                FieldSpec("Notas", "notes", kind="entry"),
            ],
        )
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        if not (data.get("name") or "").strip():
            messagebox.showerror("Novo projeto", "Informe um nome para o projeto.")
            return
        if not self._maybe_save():
            return
        try:
            result = self.db.create_repair_project(data)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Novo projeto", f"Falha ao criar:\n{exc}")
            return
        self._reload_projects()
        self._load_project(result["pk"])

    def _load_project(self, pk: int) -> None:
        self._loading = True
        self.project_id = pk
        proj = self.db.get_repair_project(pk)
        self.name_var.set((proj or {}).get("name") or "")
        self.equipment_var.set((proj or {}).get("equipment") or "")
        self.notes_var.set((proj or {}).get("notes") or "")
        self._photos = self.db.list_repair_photos(pk)
        self._annotations = self.db.list_repair_annotations(pk)
        self._selected_idx = None
        self._dirty = False
        self._loading = False

        self._refresh_photo_box(select_pk=self._current_photo_id)
        self._refresh_findings_table()
        self._set_status(f"Projeto: {self.name_var.get()}")

    def _save(self) -> bool:
        if self.project_id is None:
            messagebox.showinfo("Salvar", "Crie ou abra um projeto primeiro.")
            return False
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Salvar", "Informe um nome para o projeto.")
            return False
        try:
            self.db.update_repair_project(
                self.project_id,
                {
                    "name": name,
                    "equipment": self.equipment_var.get().strip() or None,
                    "notes": self.notes_var.get().strip() or None,
                },
            )
            self.db.replace_repair_annotations(self.project_id, self._annotations)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Salvar", f"Falha ao salvar:\n{exc}")
            return False

        self._reload_projects()
        self._load_project(self.project_id)
        self._dirty = False
        self._set_status(f"Salvo: {name}")
        return True

    def _delete_project(self) -> None:
        if self.project_id is None:
            messagebox.showinfo("Excluir", "Nenhum projeto aberto.")
            return
        name = self.name_var.get() or self.project_box.get()
        if not messagebox.askyesno("Excluir", f"Excluir o projeto '{name}'?"):
            return
        try:
            self.db.delete_repair_project(self.project_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Excluir", f"Falha ao excluir:\n{exc}")
            return
        self.project_id = None
        self._photos = []
        self._annotations = []
        self._current_photo_id = None
        self._selected_idx = None
        self._dirty = False
        self._reload_projects()
        self._refresh_photo_box()
        self._refresh_findings_table()
        self._set_status("Projeto excluído.")

    def _maybe_save(self) -> bool:
        """Ask to save unsaved changes; return False only to cancel the action."""
        if not self._dirty:
            return True
        choice = messagebox.askyesnocancel(
            "Reparos", "Salvar as alterações do projeto atual?"
        )
        if choice is None:
            return False
        if choice:
            return self._save()
        return True

    def _on_close(self) -> None:
        if not self._maybe_save():
            return
        self.destroy()

    def _open_part_unavailable(self, _pk: int) -> None:
        messagebox.showinfo("Reparos", "Detalhes do componente indisponíveis.")

    # ---------------------------------------------------------------- photos

    def _ensure_project(self) -> bool:
        if self.project_id is None:
            messagebox.showinfo("Reparos", "Crie ou abra um projeto primeiro.")
            return False
        return True

    def _refresh_photo_box(self, select_pk: int | None = None) -> None:
        self.photo_box["values"] = [
            f"{ph['position'] + 1}. {ph['filename']}" for ph in self._photos
        ]
        if not self._photos:
            self.photo_box.set("")
            self._current_photo_id = None
            self.remove_photo_button.configure(state="disabled")
            self._render_photo()
            return

        if select_pk is not None:
            idx = next(
                (i for i, ph in enumerate(self._photos) if ph["pk"] == select_pk),
                0,
            )
        else:
            idx = 0
        self.photo_box.current(idx)
        self._current_photo_id = self._photos[idx]["pk"]
        self.remove_photo_button.configure(state="normal")
        self._render_photo()

    def _on_photo_selected(self, _event=None) -> None:
        idx = self.photo_box.current()
        if 0 <= idx < len(self._photos):
            self._current_photo_id = self._photos[idx]["pk"]
            self._selected_idx = None
            self._render_photo()

    def _take_photo(self) -> None:
        if not self._ensure_project():
            return
        dialog = CameraCaptureDialog(self)
        self.wait_window(dialog)
        path = dialog.captured_path
        if path is None:
            return
        try:
            self.db.add_repair_photo(self.project_id, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Reparos", f"Falha ao salvar a foto:\n{exc}")
            return
        finally:
            path.unlink(missing_ok=True)
        self._photos = self.db.list_repair_photos(self.project_id)
        new_pk = self._photos[-1]["pk"] if self._photos else None
        self._refresh_photo_box(select_pk=new_pk)

    def _import_photo(self) -> None:
        if not self._ensure_project():
            return
        path = filedialog.askopenfilename(
            title="Importar imagem",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            self.db.add_repair_photo(self.project_id, Path(path))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Reparos", f"Falha ao importar a imagem:\n{exc}")
            return
        self._photos = self.db.list_repair_photos(self.project_id)
        new_pk = self._photos[-1]["pk"] if self._photos else None
        self._refresh_photo_box(select_pk=new_pk)

    def _remove_photo(self) -> None:
        if self._current_photo_id is None:
            return
        if not messagebox.askyesno("Remover foto", "Remover a foto atual?"):
            return
        self.db.delete_repair_photo(self._current_photo_id)
        self._annotations = [
            a for a in self._annotations if a.get("photo_id") != self._current_photo_id
        ]
        self._photos = self.db.list_repair_photos(self.project_id)
        self._current_photo_id = None
        self._selected_idx = None
        self._dirty = True
        self._refresh_photo_box()
        self._refresh_findings_table()

    # ---------------------------------------------------------- photo canvas

    def _render_photo(self) -> None:
        self.canvas.delete("all")
        self._photo_ref = None
        self._photo_image = None
        self._scale = 1.0
        self._offset = (0, 0)
        self._markers = []
        self._marker_items = []

        if self._current_photo_id is None:
            self.canvas.create_text(
                _CANVAS_WIDTH // 2,
                _CANVAS_HEIGHT // 2,
                text="Nenhuma foto",
                fill="#bbb",
                font=("", 14),
            )
            self._update_tab1_buttons()
            return

        path = self.db.repair_photo_path(self._current_photo_id)
        if not path:
            self.canvas.create_text(
                _CANVAS_WIDTH // 2,
                _CANVAS_HEIGHT // 2,
                text="(imagem não encontrada)",
                fill="#bbb",
            )
            self._update_tab1_buttons()
            return

        try:
            image = Image.open(path)
            image.load()
            full = image.convert("RGB")
        except Exception:  # noqa: BLE001 - unreadable image
            self.canvas.create_text(
                _CANVAS_WIDTH // 2,
                _CANVAS_HEIGHT // 2,
                text="(imagem ilegível)",
                fill="#bbb",
            )
            self._update_tab1_buttons()
            return

        iw, ih = full.size
        scale = min(_CANVAS_WIDTH / iw, _CANVAS_HEIGHT / ih)
        dw, dh = int(iw * scale), int(ih * scale)
        self._scale = scale
        self._offset = ((_CANVAS_WIDTH - dw) // 2, (_CANVAS_HEIGHT - dh) // 2)

        thumb = full.resize((dw, dh), Image.Resampling.LANCZOS)
        self._photo_image = full
        self._photo_ref = ImageTk.PhotoImage(thumb)
        self.canvas.create_image(
            _CANVAS_WIDTH // 2, _CANVAS_HEIGHT // 2, image=self._photo_ref
        )

        self._rebuild_markers()
        self._update_tab1_buttons()

    def _norm_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        iw, ih = self._photo_image.size
        return (
            self._offset[0] + x * iw * self._scale,
            self._offset[1] + y * ih * self._scale,
        )

    def _canvas_to_norm(self, cx: float, cy: float) -> tuple[float, float]:
        iw, ih = self._photo_image.size
        x = (cx - self._offset[0]) / (iw * self._scale)
        y = (cy - self._offset[1]) / (ih * self._scale)
        return (min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0))

    def _rebuild_markers(self) -> None:
        for item in self._marker_items:
            self.canvas.delete(item)
        self._marker_items = []
        self._markers = []
        if self._photo_image is None or self._current_photo_id is None:
            return

        idxs = [
            i
            for i, a in enumerate(self._annotations)
            if a.get("photo_id") == self._current_photo_id
        ]
        for n, idx in enumerate(idxs, start=1):
            ann = self._annotations[idx]
            cx, cy = self._norm_to_canvas(ann["x"], ann["y"])
            self._draw_marker(idx, n, cx, cy)

    def _draw_marker(self, idx: int, n: int, cx: float, cy: float) -> None:
        selected = self._selected_idx == idx
        r = _MARKER_RADIUS
        fill = "#d4452f" if selected else "#0a7d2f"
        self._marker_items.append(
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r, fill=fill, outline="#fff", width=2
            )
        )
        self._marker_items.append(
            self.canvas.create_text(
                cx, cy, text=str(n), fill="#fff", font=("", 9, "bold")
            )
        )
        label = self._annotations[idx].get("label") or ""
        self._marker_items.append(
            self.canvas.create_text(
                cx, cy - r - 8, text=label, anchor="s", fill="#fff", font=("", 9)
            )
        )
        self._markers.append({"idx": idx, "cx": cx, "cy": cy, "n": n})

    def _hit_marker(self, x: float, y: float) -> int | None:
        for m in self._markers:
            if (
                abs(x - m["cx"]) <= _MARKER_RADIUS + 5
                and abs(y - m["cy"]) <= _MARKER_RADIUS + 5
            ):
                return m["idx"]
        return None

    def _on_canvas_click(self, event: tk.Event) -> None:
        if self._photo_image is None:
            return
        hit = self._hit_marker(event.x, event.y)
        if hit is not None:
            self._selected_idx = hit
            self._rebuild_markers()
            self._update_tab1_buttons()
            return
        self._add_annotation(event.x, event.y)

    def _on_canvas_drag(self, event: tk.Event) -> None:
        if self._selected_idx is None or self._photo_image is None:
            return
        x, y = self._canvas_to_norm(event.x, event.y)
        self._annotations[self._selected_idx]["x"] = x
        self._annotations[self._selected_idx]["y"] = y
        self._dirty = True
        self._rebuild_markers()

    def _update_tab1_buttons(self) -> None:
        state = "normal" if self._selected_idx is not None else "disabled"
        self.edit_marker_button.configure(state=state)
        self.remove_marker_button.configure(state=state)

    # ------------------------------------------------------------ annotations

    def _add_annotation(self, cx: float, cy: float) -> None:
        dialog = FormDialog(
            self,
            title="Novo rótulo",
            fields=[
                FieldSpec("Rótulo", "label", kind="entry", required=True),
                FieldSpec(
                    "Categoria",
                    "category",
                    kind="comboedit",
                    options=[(c, c) for c in CATEGORIES],
                ),
            ],
        )
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        label = (data.get("label") or "").strip()
        if not label:
            messagebox.showerror("Novo rótulo", "O rótulo é obrigatório.")
            return
        x, y = self._canvas_to_norm(cx, cy)
        self._annotations.append(
            {
                "pk": None,
                "photo_id": self._current_photo_id,
                "label": label,
                "category": data.get("category"),
                "x": x,
                "y": y,
                "status": DEFAULT_FINDING_STATUS,
                "part_id": None,
                "notes": None,
                "part_name": None,
                "part_ipn": None,
            }
        )
        self._selected_idx = len(self._annotations) - 1
        self._dirty = True
        self._rebuild_markers()
        self._refresh_findings_table()
        self._update_tab1_buttons()

    def _edit_marker(self) -> None:
        idx = self._selected_idx
        if idx is None:
            messagebox.showinfo("Editar", "Selecione um rótulo na imagem.")
            return
        ann = self._annotations[idx]
        dialog = FormDialog(
            self,
            title="Editar rótulo",
            fields=[
                FieldSpec("Rótulo", "label", kind="entry", required=True),
                FieldSpec(
                    "Categoria",
                    "category",
                    kind="comboedit",
                    options=[(c, c) for c in CATEGORIES],
                ),
            ],
            initial=ann,
        )
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        ann["label"] = (data.get("label") or "").strip()
        ann["category"] = data.get("category")
        self._dirty = True
        self._rebuild_markers()
        self._refresh_findings_table()

    def _remove_marker(self) -> None:
        idx = self._selected_idx
        if idx is None:
            messagebox.showinfo("Remover", "Selecione um rótulo na imagem.")
            return
        if not messagebox.askyesno("Remover rótulo", "Remover este rótulo?"):
            return
        del self._annotations[idx]
        self._selected_idx = None
        self._dirty = True
        self._rebuild_markers()
        self._refresh_findings_table()
        self._update_tab1_buttons()

    # --------------------------------------------------------------- findings

    def _photo_label(self, photo_id: int | None) -> str:
        for ph in self._photos:
            if ph["pk"] == photo_id:
                return f"{ph['position'] + 1}. {ph['filename']}"
        return ""

    def _refresh_findings_table(self) -> None:
        rows = []
        for idx, a in enumerate(self._annotations):
            status = a.get("status") or DEFAULT_FINDING_STATUS
            rows.append(
                {
                    "pk": idx,
                    "photo": self._photo_label(a.get("photo_id")),
                    "label": a.get("label") or "",
                    "category": a.get("category") or "",
                    "status": STATUS_LABELS.get(status, status),
                    "part": a.get("part_name") or "",
                    "notes": a.get("notes") or "",
                }
            )
        self.findings_table.set_rows(rows)

    def _selected_finding(self) -> int | None:
        pk = self.findings_table.selected_pk()
        if pk is None or pk < 0 or pk >= len(self._annotations):
            return None
        return pk

    def _edit_finding(self) -> None:
        idx = self._selected_finding()
        if idx is None:
            messagebox.showinfo("Editar", "Selecione um rótulo na tabela.")
            return
        ann = self._annotations[idx]
        dialog = FormDialog(
            self,
            title="Editar rótulo",
            fields=[
                FieldSpec("Rótulo", "label", kind="entry", required=True),
                FieldSpec(
                    "Categoria",
                    "category",
                    kind="comboedit",
                    options=[(c, c) for c in CATEGORIES],
                ),
                FieldSpec(
                    "Status", "status", kind="combobox", options=STATUS_OPTIONS
                ),
                FieldSpec("Notas", "notes", kind="entry"),
            ],
            initial=ann,
        )
        self.wait_window(dialog)
        data = dialog.result()
        if data is None:
            return
        ann["label"] = (data.get("label") or "").strip()
        ann["category"] = data.get("category")
        ann["status"] = data.get("status") or DEFAULT_FINDING_STATUS
        ann["notes"] = data.get("notes")
        self._dirty = True
        self._rebuild_markers()
        self._refresh_findings_table()

    def _link_finding(self) -> None:
        idx = self._selected_finding()
        if idx is None:
            messagebox.showinfo("Vincular", "Selecione um rótulo na tabela.")
            return
        picker = PartPickerDialog(self, self.db)
        self.wait_window(picker)
        part_pk = picker.result()
        if part_pk is None:
            return
        part = self.db.get_part(part_pk)
        ann = self._annotations[idx]
        ann["part_id"] = part_pk
        ann["part_name"] = (part or {}).get("name") or ""
        ann["part_ipn"] = (part or {}).get("IPN") or ""
        self._dirty = True
        self._refresh_findings_table()

    def _open_finding(self) -> None:
        idx = self._selected_finding()
        if idx is None:
            messagebox.showinfo("Abrir", "Selecione um rótulo na tabela.")
            return
        ann = self._annotations[idx]
        if not ann.get("part_id"):
            messagebox.showinfo("Abrir", "Este rótulo não está vinculado ao inventário.")
            return
        self._open_part(ann["part_id"])

    def _unlink_finding(self) -> None:
        idx = self._selected_finding()
        if idx is None:
            messagebox.showinfo("Desvincular", "Selecione um rótulo na tabela.")
            return
        ann = self._annotations[idx]
        ann["part_id"] = None
        ann["part_name"] = None
        ann["part_ipn"] = None
        self._dirty = True
        self._refresh_findings_table()

    def _remove_finding(self) -> None:
        idx = self._selected_finding()
        if idx is None:
            messagebox.showinfo("Remover", "Selecione um rótulo na tabela.")
            return
        if not messagebox.askyesno("Remover rótulo", "Remover este rótulo?"):
            return
        del self._annotations[idx]
        self._selected_idx = None
        self._dirty = True
        self._rebuild_markers()
        self._refresh_findings_table()


def launch(
    master,
    db,
    search_inventory: Callable[[str], None] | None = None,
    open_part: Callable[[int], None] | None = None,
) -> None:
    """Open the Reparos workspace."""
    RepairsDialog(
        master,
        db,
        search_inventory=search_inventory,
        open_part=open_part,
    )
