# Partiu

Offline component tracker — a **tkinter** desktop app backed by **SQLite** (no server).

Track:
- **Parts** (name, IPN, category, description, units, manufacturer, package, active, in-stock)
- **Stock Items** (part, quantity, location, serial, batch, status)
- **Stock Locations** (name, description, parent, path)
- **Component details** per part: photo, datasheet (PDF), pinout and electrical parameters

## Component detail view

Double-click a part (or select it and press **Details**) to open the detail window:

- **Photo** — add/change/remove a component image, or **take a photo** with a
  camera: a live-preview window lets you pick which camera to use and capture a
  frame for that component.
- **Datasheet** — attach a PDF and open it with the OS viewer.
- **Extract from datasheet** — parses the attached PDF and fills in manufacturer,
  package/size, the **pinout** table and the **electrical characteristics** table.
  Extracted values are editable.

PDF extraction is heuristic and header-driven: it recognises pin and electrical
characteristic tables by their column labels across common datasheet formats
(Texas Instruments, ST/onsemi, Infineon, …). It is best-effort — review the
extracted pins/parameters after importing.

When a PDF has **no text layer** (a scan), the app falls back to a **local OCR
model** (`rapidocr` + `onnxruntime`, PP-OCR ONNX, runs fully offline): pages are
rendered with `pypdfium2` and the same header-driven extractors run over the
recognised text. Pin numbers drawn inside a **graphical pinout diagram** (DIP /
SOIC / logic-diagram style) are recovered by a geometric parser that pairs each
number with its adjacent pin name — for both text-layer and OCR'd diagrams. The
OCR fallback runs in the background and can take a minute or more for a long
scanned datasheet.

## Import components

In the **Parts** view, click **Import…** and choose a `.csv` or `.xlsx` file.
Click **Template…** to download a ready-to-fill CSV template. The first row
must be a header row; columns are matched by name (case-insensitive,
underscores/punctuation ignored). Recognized headers:

| Field | Accepted headers |
|-------|------------------|
| name (required) | `name`, `part name`, `part_name`, `component`, `component name` |
| IPN | `ipn`, `internal part number`, `part number`, `pn`, `mpn` |
| category | `category`, `type`, `group` |
| description | `description`, `desc`, `notes` |
| units | `units`, `unit`, `uom` |
| manufacturer | `manufacturer`, `mfr`, `vendor`, `brand`, `make` |
| package | `package`, `case`, `footprint` |
| package size | `package size`, `package_size`, `case size` |
| active | `active`, `enabled` (`0`/`no`/`false` = inactive; blank = active) |

Rows with an empty `name` are skipped, and rows whose `name` already exists in
the database (case-insensitive) are skipped as duplicates. The import is
atomic: if anything fails, no rows are inserted.

## Storage drawers (gavetas)

Organize physical storage as a two-level hierarchy of **Stock Locations**:

1. Create a **Gaveteiro** (cabinet) as a top-level location with a short letter
   name, e.g. `A`.
2. Create each **Gaveta** (drawer) under it with a number name, e.g. `1`.

The drawer's **label** is the concatenation of both, e.g. `A1`. Assign stock
items to a drawer in **Stock Items**, then search a part name in **Parts** —
the **Locations** column shows which drawers hold it and how many, e.g.
`A1 ×3, B2 ×2`.

To list every part stored in a drawer or cabinet, type a `GA[...]` token in the
**Parts** search box:

- `GA[A1]` — all parts in drawer `A1`.
- `GA[A]` — all parts in cabinet `A` (i.e. every drawer under it).

You can combine it with free text, e.g. `GA[A1] resistor` narrows to parts
matching `resistor` in that drawer.

## Tools menu

A **Tools** menu (menu bar) hosts engineering tools that connect to the
inventory. Each tool is registered in `src/partiu/gui/tools/__init__.py`
(`TOOLS`); the menu is built from that registry, so adding a tool is a single
registration.

### Flyback DCM calculator

Design a discontinuous-mode flyback converter from its operating parameters
(`Vin`, `Vin_max`, `Vout`, `Iout`, ripple, efficiency, duty cycle, switching
frequency). It computes the turns ratio (rounded up, as in the reference
project), the recalculated duty cycle, primary/secondary inductances and
currents, MOSFET and diode ratings, and the output capacitor — following the
equations in `M2A1_FC_Ini_II__ANEXO_1__Projeto.pdf` / `M2A1_calc_flyback.m`.

The dialog has three tabs:

1. **Flyback DCM** — the converter calculator above.
2. **Transformador HF** — high-frequency transformer design based on
   `M2A2_calc_transf.m`: core area product (`Ae·Aw`) and margin, air gap
   (total/side), primary/secondary turns (raw and rounded up), wire sizing
   (required area, parallel conductors, max conductor diameter for skin
   depth) and a window-area feasibility check (`Exec ≤ 1`). Every
   **Calculate** re-reads the tab 1 fields first (converter → transformer →
   assembly), and a **Dados do conversor** frame echoes the values being
   consumed (`Vin`, `f`, `n`, recalc `D`, `IL1_rms`, `IL1_max`, `IL2_rms`,
   `Pin`).

   Below the calculations, two reference tables extracted from
   `M2A2_FC_Ini_II__ANEXO_1__Projeto.pdf` are shown in their own tabs:

   - **Tabela 1 — Núcleos EE** (9 cores with `Ae`, `Aw`, `Ae·Aw`)
   - **Tabela 2 — Fios AWG** (AWG 10…41: diameters, areas, `Imax`)

   Clicking (or pressing Enter on) a row **applies it to the inputs** — a
   core fills `Ae`, `Aw` and `Ae·Aw`, a wire fills the wire area — and the
   fields stay editable, so a custom value simply clears the highlight.
   Rows are tagged after each **Calculate**: **green** is the row matching
   the applied inputs, **blue** is the recommendation (the *smallest* core
   whose `Ae·Aw` covers the requirement and the *thickest* wire inside the
   skin-effect limit `15/√f`), with both spelled out in the status line.

3. **Montagem HF** — winding/assembly guide derived from tab 2
   (`transformer.winding_guide`), using the **very same wire and counts** as
   the design, so `Awire1`/`Awire2`, `N1cond`, `N2cond`, `UA1`/`UA2` and
   `Exec` match the Transformador HF tab exactly. It shows the minimum wire
   area (`IL_rms/Jmax`), the parallel conductors, the per-conductor
   currents, the occupied areas and the checks (window, `Ae·Aw`, skin
   depth, wire `Imax`) — the Tabela 1/Tabela 2 limits are advisory and
   never change the counts. The tab also echoes the converter feed and
   renders a **step-by-step winding list** (turns, parallel strands, air
   gap, window occupancy) with warnings when the applied core is too small,
   the wire breaks the skin limit, its `Imax` would ask for more strands or
   the window does not fit.

Every result group has a **Find in inventory** button that opens the Parts
view pre-filtered with a suggested term (e.g. `MOSFET`, `diode`, `capacitor`,
`transformer`), so you can locate stocked components for the design.

### Commercial values (E-Series)

Given any value, find the nearest **commercial E-Series value** (IEC 60063) for
a resistor, inductor or capacitor. Enter the value with an optional SI prefix
(`4.7k`, `100n`, `10µ`), pick the component type (Ω / H / F), and choose the
tolerance (20% … 0.1%) — the E-Series is derived automatically (E6/E12/E24/E48/
E96/E192), or you can select the series directly. The tool shows the nearest
value plus the next-lower and next-higher values with their % deviation, and a
**Find in inventory** button opens the Parts view pre-filtered by component
category (`resistor`, `inductor`, `capacitor`).

## Run (development)

```bash
poetry install
poetry run partiu
```

Data is stored in a per-user directory:
- macOS: `~/Library/Application Support/partiu/partiu.db`
- Windows: `%APPDATA%\partiu\partiu.db`
- Linux: `~/.local/share/partiu/partiu.db`

Attachments (photos, datasheets) live in `attachments/` next to the database.

Use **Export database…** in the sidebar to copy the database elsewhere.

## Dependencies

Runtime: `pdfplumber` (PDF table extraction), `pillow` (photo display) and
`openpyxl` (Excel import). Everything else is the Python standard library
(`tkinter`, `sqlite3`, `csv`).

## Build a distributable package

```bash
poetry install
python scripts/make_icons.py all   # gera partiu.ico + partiu.icns

# macOS -> Partiu.app, depois Partiu.dmg
poetry run python -m nuitka --standalone --macos-create-app-bundle \
  --macos-app-name=Partiu --macos-app-version="0.1.0" \
  --macos-signed-app-name=com.fabrykindustries.partiu --macos-app-icon=partiu.icns \
  --macos-app-protected-resource="NSCameraUsageDescription:Camera access for capturing component photos." \
  --output-folder-name=Partiu --output-filename=Partiu \
  --company-name="fabryk industries" --product-name="Partiu" \
  --file-version="0.1.0" --product-version="0.1.0" \
  --file-description="Offline component tracker" --copyright="2026 fabryk industries" \
  --enable-plugin=tk-inter --include-package=PIL --include-package=pdfplumber \
  --include-package=pdfminer --include-package=pypdfium2 --include-package=openpyxl \
  --include-package=onnxruntime --include-package=rapidocr --include-package=cv2 \
  --include-package-data=pdfminer --include-package-data=pypdfium2 \
  --include-package-data=rapidocr \
  --assume-yes-for-downloads run.py
mkdir -p dmg_stage && cp -R "Partiu.app" dmg_stage/ && ln -s /Applications dmg_stage/Applications
hdiutil create -volname "Partiu" -srcfolder dmg_stage -ov -format UDZO "Partiu.dmg"

# Windows -> Partiu-Setup.exe (instalador NSIS; requer MSVC — rode no VS Developer Command Prompt)
poetry run python -m nuitka --standalone --windows-create-installer \
  --windows-installer-output=Partiu-Setup.exe --windows-installer-shortcuts=desktop,start-menu \
  --windows-installer-mode=user --windows-icon-from-ico=partiu.ico --windows-console-mode=disable \
  --company-name="fabryk industries" --product-name="Partiu" \
  --file-version="0.1.0" --product-version="0.1.0" \
  --file-description="Offline component tracker" --copyright="2026 fabryk industries" \
  --enable-plugin=tk-inter --include-package=PIL --include-package=pdfplumber \
  --include-package=pdfminer --include-package=pypdfium2 --include-package=openpyxl \
  --include-package=onnxruntime --include-package=rapidocr --include-package=cv2 \
  --include-package-data=pdfminer --include-package-data=pypdfium2 \
  --include-package-data=rapidocr \
  --output-filename=Partiu.exe --assume-yes-for-downloads run.py
```

## Release artifacts

Creating a GitHub release triggers `.github/workflows/release.yml`, which builds and
attaches:

- `Partiu.dmg` (macOS, Apple Silicon)
- `Partiu-Setup.exe` (Windows NSIS installer)

To test a build **without creating a release**, run the workflow manually
(Actions → Build Release → Run workflow). The built files are then uploaded as
runnable/downloadable artifacts instead of being attached to a release.

> **Not signed yet:** the artifacts are built with full metadata but **without
> code signing** (no certificate configured). Windows Defender may still warn,
> and macOS Gatekeeper shows an "unidentified developer" prompt until
> certificates are added — see **Code signing** below.

## Code signing

The workflow has signing steps ready, gated on secrets so they run only once
certificates are added:

- **Windows**: add secrets `WINDOWS_SIGNING_CERT` (base64 of the `.pfx`) and
  `WINDOWS_SIGNING_PASSWORD`. The step signs `Partiu-Setup.exe` with `signtool`.
- **macOS**: add a Developer ID certificate plus secrets `APPLE_ID`,
  `APPLE_TEAM_ID` and `APPLE_APP_SPECIFIC_PASSWORD` to sign and notarize the
  DMG.

Until then, builds are unsigned; a code-signing certificate (OV/EV for Windows,
Developer ID for macOS) is what removes the Defender / Gatekeeper warnings.

### Windows installer: "Error opening file for writing"

This error during install usually means the installer could not overwrite a
file because it is locked (a running copy of the app, or antivirus scanning)
or because it lacks permission. The build already installs **per-user**
(`--windows-installer-mode=user`, no admin/UAC needed). If it still happens:
close any running Partiu instance and retry — the underlying trigger is
typically the unsigned binary being scanned aggressively by antivirus, which
code signing resolves.
