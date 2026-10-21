# Plan: Reparos tool (equipment repair / board annotation)

## Context

Partiu is an offline tkinter + SQLite component tracker. It has a **Tools** menu
(`src/partiu/gui/tools/__init__.py`, `Tool(id, label, launch)`, launched via
`launch(master, db, search_inventory)`).

We are adding a **Reparos** tool for equipment/PCB repair workflows:

- A **tabbed** dialog (3 tabs).
- **Tab 1 — Análise e reconhecimento**: capture photos from a camera (default or
  microscope), or import an image file, and **annotate** it by placing point markers
  (numbered pin + label) on the image to identify traces, CIs, components, etc.
- **Tab 2 — Tabela de rótulos**: a table of every label across the project's photos,
  with a **status** (Bom / Ruim / Precisa testar), a **category**, and the ability to
  **link** a finding to an inventory part (search + pick), plus a one-click **Abrir
  detalhes** that opens that part's `PartDetailView`.
- **Tab 3 — placeholder** (to be designed later).
- Projects are **savable** and persist across sessions.

## Decisions (confirmed)

1. **Persistence**: SQLite — new tables `repair_project`, `repair_photo`,
   `repair_annotation` in the existing `partiu.db` (added to `SCHEMA`; tables are
   created with `CREATE TABLE IF NOT EXISTS` on open, so no migration needed).
2. **Annotation shape**: point marker (numbered pin + label) only, for now.
3. **Camera**: reuse the modal `CameraCaptureDialog` (already supports selecting the
   default or microscope camera). Also support **import image from file**.
4. **Project management**: toolbar at top of the dialog — **Novo / Abrir (list) /
   Salvar** (+ Excluir), with a project name field.
5. **Statuses**: three initial values — **Good** ("Bom"), **Bad** ("Ruim"),
   **Needs testing** ("Precisa testar").
6. **Category**: fixed list + free-text entry (editable combobox) —
   Trilha, CI, Componente, Conector, Transistor, Capacitor, Resistor, Outro.
7. **Inventory link**: one part per finding, chosen via a search dialog;
   "Abrir detalhes" opens `PartDetailView` in a new window.

## Data model (new tables in `db.py` `SCHEMA`)

```sql
CREATE TABLE IF NOT EXISTS repair_project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    equipment TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS repair_photo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES repair_project(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS repair_annotation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES repair_project(id) ON DELETE CASCADE,
    photo_id INTEGER NOT NULL REFERENCES repair_photo(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    category TEXT,
    x REAL NOT NULL,   -- normalized 0..1 relative to full-res image
    y REAL NOT NULL,   -- normalized 0..1
    status TEXT NOT NULL DEFAULT 'Needs testing',
    part_id INTEGER REFERENCES part(id) ON DELETE SET NULL,
    notes TEXT
);
```

- Photos are copied to `data_dir/repairs/<project_id>/<uuid>.<ext>` (a new
  `repairs_dir` on `Database`, mirroring the `attachments_dir` pattern).
- `list_repair_annotations` LEFT JOINs `part` to also return `part_name` / `part_ipn`
  for display and for "Abrir detalhes".

## Approach

### DB layer — `src/partiu/db.py`

Add `self.repairs_dir = self.path.parent / "repairs"` (created in `__init__`), the
three tables to `SCHEMA`, and CRUD methods:

- `list_repair_projects()`, `get_repair_project(pk)`, `create_repair_project(data)`,
  `update_repair_project(pk, data)`, `delete_repair_project(pk)` (also removes the
  project's photo directory).
- `add_repair_photo(project_id, source_path)` → copy file, insert row, return `{pk}`;
  `list_repair_photos(project_id)`; `repair_photo_path(pk)`; `delete_repair_photo(pk)`.
- `list_repair_annotations(project_id)` (LEFT JOIN `part` for name/IPN);
  `replace_repair_annotations(project_id, rows)` (delete + bulk insert, atomic).

### GUI — new `src/partiu/gui/tools/repairs.py`

`RepairsDialog(tk.Toplevel)` with:

- **Toolbar**: project `ttk.Combobox` (list of projects → select to open), buttons
  **Novo** (FormDialog: name required, equipment, notes), **Salvar**, **Excluir**.
  `equipment` / `notes` shown as editable entries. A `dirty` flag tracks unsaved
  meta/annotation changes; on close, prompt to save.
- **Notebook** with 3 tabs.

**Tab 1 — Análise e reconhecimento**
- Photo list (combobox/Listbox of the project's photos) + buttons: **Tirar foto…**
  (opens `CameraCaptureDialog`, copies temp JPG via `add_repair_photo`),
  **Importar imagem…** (`filedialog`, same path), **Remover foto**.
- Annotation canvas (`tk.Canvas`): draws the scaled photo (PIL `ImageTk.PhotoImage`,
  scale-to-fit like `detail.py`), then renders markers from normalized `(x, y)`.
  - Click empty area → `FormDialog` (label required, category editable combobox) →
    append marker with normalized coords.
  - Click a marker → select (highlight). **Editar** / **Remover** buttons.
  - Drag a marker to move it (recompute normalized coords on release).
  - Markers stored in an in-memory `self._annotations` list (per project); the canvas
    shows only the current photo's annotations, filtered by `photo_id`.

**Tab 2 — Tabela de rótulos**
- `DataTable` over `self._annotations` (all photos): columns Photo, Label, Category,
  Status, Linked part, Notes.
- Buttons: **Editar** (FormDialog: label, category comboedit, status combobox, notes),
  **Vincular ao inventário…** (opens `PartPickerDialog`), **Abrir detalhes**
  (`open_part(part_id)`), **Desvincular**, **Remover**.
- `PartPickerDialog(tk.Toplevel)` — `SearchBar` + `DataTable` over
  `db.list_parts(search)` (name/IPN/category/description) + Selecionar/Cancelar;
  returns the chosen part `pk`.

**Tab 3 — placeholder**: a frame with "Em breve" text.

`launch(master, db, search_inventory, open_part)` builds the dialog; `db` is used for
projects/photos/annotations and part search; `open_part` opens linked part details.

### Tool plumbing

- `src/partiu/gui/tools/__init__.py`: register
  `Tool(id="repairs", label="Reparos…", launch=repairs_launch)`.
- `src/partiu/gui/app.py`: add `_open_part(pk)` (instantiates `PartDetailView(self,
  self.db, pk)`) and pass it to tools: `tool.launch(self, self.db,
  self._search_inventory, self._open_part)`.
- `src/partiu/gui/tools/flyback.py` and `eseries.py`: extend their `launch` signatures
  with an optional, ignored `open_part=None` so the new 4-arg call doesn't break them.
- `src/partiu/gui/widgets.py`: add `kind="comboedit"` to `FormDialog` (editable
  `ttk.Combobox`, `state="normal"`) for the category field.

## Files to modify

| File | Purpose |
|------|---------|
| `src/partiu/db.py` | Repair tables in `SCHEMA`, `repairs_dir`, CRUD methods |
| `src/partiu/gui/tools/repairs.py` | NEW — `RepairsDialog` (3 tabs), annotation canvas, `PartPickerDialog`, status/category constants |
| `src/partiu/gui/tools/__init__.py` | Register the Reparos tool |
| `src/partiu/gui/app.py` | Add `_open_part(pk)`; pass `open_part` to tools |
| `src/partiu/gui/tools/flyback.py` | Accept optional `open_part` arg |
| `src/partiu/gui/tools/eseries.py` | Accept optional `open_part` arg |
| `src/partiu/gui/widgets.py` | `comboedit` field kind in `FormDialog` |
| `README.md` | Document the Reparos tool |

## Reuse

- `src/partiu/gui/camera.py::CameraCaptureDialog` — photo capture (default + microscope).
- `src/partiu/gui/views/detail.py::PartDetailView` — open linked part details.
- `src/partiu/gui/widgets.py::DataTable / FormDialog / FieldSpec / SearchBar`.
- `src/partiu/db.py::list_parts(search)` — part search for the picker.
- File-copy + `stored_name` uuid pattern from `Database.set_attachment` — repair photos.
- Image scale-to-fit / `ImageTk.PhotoImage` pattern from `detail.py::_load_photo`.

## Steps

- [x] `db.py`: add `repairs_dir`, 3 tables to `SCHEMA`, and the repair CRUD methods
      (projects / photos / annotations), with `list_repair_annotations` joining `part`.
- [x] `widgets.py`: add `kind="comboedit"` (editable combobox) to `FormDialog`.
- [x] Create `src/partiu/gui/tools/repairs.py`:
      - constants (status keys → PT labels, category list);
      - `PartPickerDialog` (search + select part);
      - `RepairsDialog` toolbar (Novo/Abrir/Salvar/Excluir);
      - Tab 1 annotation canvas (photo list, capture/import/remove, add/edit/move/
        remove markers);
      - Tab 2 findings table (edit status/category, link to inventory, open details);
      - Tab 3 placeholder.
- [x] `tools/__init__.py`: register the Reparos tool.
- [x] `app.py`: add `_open_part` and pass it (4th arg) in `open_tool`.
- [x] `flyback.py` / `eseries.py`: add optional `open_part=None` to `launch`.
- [x] `README.md`: document the Reparos tool under "Tools menu".

## Verification

- `poetry run partiu` → Tools → "Reparos…".
- **Novo** project, give a name; **Tirar foto…** (default camera) and **Importar
  imagem…** — both add a photo to Tab 1.
- Click the canvas to place markers; edit/rename one, drag to move it, remove one.
- **Salvar**, close, reopen the tool and **Abrir** the project — photos + markers
  restored at the same positions.
- Tab 2 shows every label; set statuses (Bom/Ruim/Precisa testar); **Vincular ao
  inventário…** picks a part; **Abrir detalhes** opens that part's detail window.
- Confirm Tab 3 shows the placeholder.
- Regression: Flyback DCM and Valores comerciais tools still open (4-arg launch).
- Confirm the existing database opens cleanly (new tables created, no data loss).
