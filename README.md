# Partiu

Offline component tracker — a **tkinter** desktop app backed by **SQLite** (no server).

Track:
- **Parts** (name, IPN, category, description, units, manufacturer, package, active, in-stock)
- **Stock Items** (part, quantity, location, serial, batch, status)
- **Stock Locations** (name, description, parent, path)
- **Component details** per part: photo, datasheet (PDF), pinout and electrical parameters

## Component detail view

Double-click a part (or select it and press **Details**) to open the detail window:

- **Photo** — add/change/remove a component image.
- **Datasheet** — attach a PDF and open it with the OS viewer.
- **Extract from datasheet** — parses the attached PDF and fills in manufacturer,
  package/size, the **pinout** table and the **electrical characteristics** table.
  Extracted values are editable.

PDF extraction is heuristic and header-driven: it recognises pin and electrical
characteristic tables by their column labels across common datasheet formats
(Texas Instruments, ST/onsemi, Infineon, …). It is best-effort — review the
extracted pins/parameters after importing. PDFs that are scanned images (no
text layer) and pin numbers that exist only inside a graphical pinout diagram
cannot be extracted.

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
  --output-folder-name=Partiu --output-filename=Partiu \
  --company-name="fabryk industries" --product-name="Partiu" \
  --file-version="0.1.0" --product-version="0.1.0" \
  --file-description="Offline component tracker" --copyright="2026 fabryk industries" \
  --enable-plugin=tk-inter --include-package=PIL --include-package=pdfplumber \
  --include-package=pdfminer --include-package=pypdfium2 --include-package=openpyxl \
  --include-package-data=pdfminer --include-package-data=pypdfium2 \
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
  --include-package-data=pdfminer --include-package-data=pypdfium2 \
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
