# Plan: InvenTree Tkinter GUI Application

## Context

We need to build a packaged Python desktop application that provides a **tkinter GUI** for interacting with **InvenTree** inventory management. InvenTree is a Django server application with a REST API. Because the app must run **offline on a local PC**, we will **bundle the InvenTree Django server itself** (using SQLite) and run it in the background, with the tkinter GUI acting as a client that talks to the local API via the official [`inventree`](https://pypi.org/project/inventree/) Python library.

The current repo (`partiu`) is a minimal Poetry-based Python project (Python ≥3.14, no dependencies yet).

## InvenTree Python Library Summary

- **Install**: `pip install inventree`
- **Auth**: `InvenTreeAPI(host, username=..., password=...)` or token-based; env vars supported (`INVENTREE_API_HOST`, `INVENTREE_API_USERNAME`, `INVENTREE_API_PASSWORD`, `INVENTREE_API_TOKEN`)
- **Key modules / classes**:
  - `inventree.api.InvenTreeAPI`
  - `inventree.part.Part`, `inventree.part.PartCategory`
  - `inventree.stock.StockItem`, `inventree.stock.StockLocation`
  - `inventree.company.Company`
  - `inventree.build.Build`
  - `inventree.purchase_order.PurchaseOrder`
  - `inventree.sales_order.SalesOrder`
- **Operations**: `list()`, `create()`, `save()`, `delete()`, `bulkDelete()`, `reload()`

## Clarified Requirements

1. **MVP Scope**: Parts, Stock Items, Stock Locations (browse, search, create, edit).
2. **Platforms**: macOS and Windows.
3. **Deployment**: Runs locally on a single PC, fully offline.
4. **Offline mode**: Full offline support — no remote server required.

## Architecture

Because InvenTree is a Django server application, an offline desktop app requires bundling the server itself:

```
+-------------------------------------------+
|          Packaged Desktop App             |
|  +-------------------------------------+  |
|  |   Tkinter GUI (user-facing)         |  |
|  |   - Uses `inventree` Python library |  |
|  |   - Calls http://127.0.0.1:<port>   |  |
|  +-------------------------------------+  |
|  +-------------------------------------+  |
|  |   Embedded InvenTree Server         |  |
|  |   - Django + SQLite database        |  |
|  |   - Lightweight WSGI server         |  |
|  |   - Static files + migrations       |  |
|  +-------------------------------------+  |
+-------------------------------------------+
```

**Key design decisions:**
- **SQLite**: File-based database, no external DB server needed. Suitable for single-user local use.
- **WSGI server**: `waitress` (pure-Python, cross-platform) or Django's `runserver` (simpler, sufficient for single-user local). Run in a background subprocess/thread.
- **User data directory**: Database, config, logs, and media files live in the user's home dir via `platformdirs` (not inside the read-only app bundle).
- **Launcher**: On startup, the app checks if migrations have run, runs them if needed, starts the WSGI server, then opens the tkinter GUI.

## Proposed Approach

### Phase 1 — Local InvenTree Server Setup
1. Add `inventree` (the PyPI package) and the InvenTree Django source (`inventree/InvenTree` from GitHub) as dependencies.
2. Create a custom Django settings module (`src/partiu/inventree_settings.py`) that:
   - Uses SQLite pointing to `platformdirs.user_data_dir("partiu")`
   - Disables unnecessary production features (email, external auth, etc.)
   - Configures static files and media paths in user data dir
3. Create a server launcher (`src/partiu/server.py`) that:
   - Sets `DJANGO_SETTINGS_MODULE`
   - Runs `migrate` on first launch
   - Runs `collectstatic` if needed
   - Starts `waitress` or Django dev server on `127.0.0.1` + random free port
4. Verify the server starts and the API responds locally.

### Phase 2 — Tkinter GUI
1. Create `src/partiu/gui/app.py` — main tkinter application.
2. Add a **login / connection** screen (local server needs auth; default superuser can be auto-created).
3. Add a **navigation sidebar** (Parts, Stock Items, Stock Locations).
4. Implement **list views** with `ttk.Treeview`, search/filter entries, and pagination.
5. Implement **detail / create / edit forms** as modal dialogs or dedicated frames.
6. Wrap all `inventree` library calls in `src/partiu/inventree_client.py` for error handling and offline detection.

### Phase 3 — Integration & Configuration
1. Create `src/partiu/launcher.py` that orchestrates server startup → GUI launch.
2. Add config persistence (`platformdirs` + JSON) for window size, last view, etc.
3. Add graceful shutdown: when the GUI closes, terminate the WSGI server subprocess.

### Phase 4 — Packaging
1. Add `pyinstaller` as a dev dependency.
2. Create PyInstaller spec files for macOS and Windows.
3. Handle PyInstaller-specific paths for templates, static files, and migrations.
4. Build and test on both platforms.

## Files to Modify / Create

| File | Purpose |
|------|---------|
| `pyproject.toml` | Add `inventree`, Django, waitress, platformdirs, pyinstaller dependencies |
| `src/partiu/__init__.py` | Package init |
| `src/partiu/main.py` | Application entry point |
| `src/partiu/launcher.py` | Orchestrates server startup → GUI launch |
| `src/partiu/server.py` | Django/WSGI server management (migrations, start, stop) |
| `src/partiu/inventree_settings.py` | Custom Django settings for local SQLite mode |
| `src/partiu/config.py` | User settings persistence (paths, credentials, UI state) |
| `src/partiu/inventree_client.py` | Thin wrapper around `inventree` library with error handling |
| `src/partiu/gui/app.py` | Main tkinter application / window manager |
| `src/partiu/gui/views/parts.py` | Parts list + detail views |
| `src/partiu/gui/views/stock.py` | Stock items list + detail views |
| `src/partiu/gui/views/locations.py` | Stock locations list + detail views |
| `src/partiu/gui/widgets.py` | Reusable tkinter widgets (search bar, data table, forms) |
| `build/macos.spec` | PyInstaller spec for macOS `.app` bundle |
| `build/windows.spec` | PyInstaller spec for Windows `.exe` |

## Verification

- **Phase 1**: Run `python -m partiu.server` and verify the InvenTree API responds at `http://127.0.0.1:8000/api/`.
- **Phase 2**: Run `python -m partiu` and verify tkinter GUI can list/create/edit Parts, Stock Items, and Stock Locations via the local API.
- **Phase 3**: Close the GUI and verify the server subprocess terminates cleanly.
- **Phase 4**: Build with PyInstaller on macOS and Windows; verify the resulting app launches without Python installed, runs migrations on first start, and performs CRUD operations successfully.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| InvenTree has many dependencies; PyInstaller may miss some | Use `--hidden-import` and a `.spec` file with explicit collects; test thoroughly |
| Django static files / templates not found in PyInstaller bundle | Use `sys._MEIPASS` checks; include data files in `.spec` |
| SQLite performance on large datasets | Acceptable for single-user local MVP; document limitation |
| macOS code signing / notarization | Out of scope for MVP; build unsigned `.app`; document gatekeeper bypass |
| InvenTree minimum Python is 3.12; project is 3.14 | Compatible; no issue |

## Decisions (Confirmed)

| Decision | Choice |
|----------|--------|
| InvenTree version | Pin to latest stable release (e.g., `0.17.x`) |
| First-run admin | Auto-create a default superuser silently on first launch |
| WSGI server | `waitress` (pure-Python, cross-platform, robust) |
| Backup / export | Support exporting the local SQLite database from the GUI |
