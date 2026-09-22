# Partiu

Offline component tracker — a small **tkinter** desktop app backed by **pure SQLite** (no server, no external runtime dependencies).

Track three things:
- **Parts** (name, IPN, category, description, units, active, in-stock)
- **Stock Items** (part, quantity, location, serial, batch, status)
- **Stock Locations** (name, description, parent, path)

## Run (development)

```bash
poetry install
poetry run partiu
```

Data is stored in a per-user directory:
- macOS: `~/Library/Application Support/partiu/partiu.db`
- Windows: `%APPDATA%\partiu\partiu.db`
- Linux: `~/.local/share/partiu/partiu.db`

Use the **Export database…** button in the sidebar to copy the database elsewhere.

## Build a distributable package

```bash
poetry install
# macOS -> dist/Partiu.app
poetry run pyinstaller --noconfirm packaging/partiu.spec
# Windows -> dist/Partiu.exe (single file)
poetry run pyinstaller --noconfirm --onefile --windowed --name Partiu --paths src run.py
```

## Release artifacts

Creating a GitHub release triggers `.github/workflows/release.yml`, which builds and
attaches:

- `Partiu-macOS.zip` (Apple Silicon `.app`)
- `Partiu.exe` (Windows, single file)

> **macOS Gatekeeper:** the `.app` is not notarized. On first launch, right-click
> the app and choose **Open** (or run
> `xattr -dr com.apple.quarantine /Applications/Partiu.app`).
