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

PDF extraction is heuristic (tuned to the Texas Instruments datasheet format,
e.g. `tl062.pdf`), so review the extracted pins/parameters after importing.

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

Runtime: `pdfplumber` (PDF table extraction) and `pillow` (photo display).
Everything else is the Python standard library (`tkinter`, `sqlite3`).

## Build a distributable package

```bash
poetry install
# macOS -> Partiu.app
poetry run python -m nuitka --standalone --macos-create-app-bundle --macos-app-name=Partiu \
  --enable-plugin=tk-inter --include-package=PIL --include-package=pdfplumber \
  --include-package=pdfminer --include-package=pypdfium2 \
  --include-package-data=pdfminer --include-package-data=pypdfium2 \
  --assume-yes-for-downloads run.py
# Windows -> Partiu.exe (single file; needs MSVC — run from a VS Developer Command Prompt)
poetry run python -m nuitka --standalone --onefile --enable-plugin=tk-inter \
  --include-package=PIL --include-package=pdfplumber --include-package=pdfminer \
  --include-package=pypdfium2 --include-package-data=pdfminer \
  --include-package-data=pypdfium2 --windows-console-mode=disable \
  --output-filename=Partiu.exe --assume-yes-for-downloads run.py
```

## Release artifacts

Creating a GitHub release triggers `.github/workflows/release.yml`, which builds and
attaches:

- `Partiu-macOS.zip` (Apple Silicon `.app`)
- `Partiu.exe` (Windows, single file)

> **macOS Gatekeeper:** the `.app` is not notarized. On first launch, right-click
> the app and choose **Open** (or run
> `xattr -dr com.apple.quarantine /Applications/Partiu.app`).
