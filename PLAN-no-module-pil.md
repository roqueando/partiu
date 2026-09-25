# Plan: Migrate packaging from PyInstaller to Nuitka (fix "no module named PIL" on Windows)

## Context

The Windows release (`Partiu.exe`, built by `.github/workflows/release.yml`) crashes at
runtime with `no module named PIL`. The direct cause is that the workflow never installs
the app's runtime deps (`pdfplumber`, `pillow`); it only runs
`python -m pip install --upgrade pip pyinstaller`.

**Decision (confirmed with user):** migrate packaging from **PyInstaller** to **Nuitka**.
Nuitka compiles the Python code and follows imports at compile time, and with explicit
`--include-package` flags it bundles `PIL`, `pdfplumber`, `pdfminer`, and their data files
into the standalone/onefile output.

> Note: Nuitka also requires the dependencies to be **installed** at build time (it follows
> imports, exactly like PyInstaller). So the workflow must still `pip install .` (which
> installs `partiu` + `pdfplumber` + `pillow`) before compiling. This is what actually
> guarantees the modules are present.

## Approach

Replace the PyInstaller build steps in `release.yml` with Nuitka `--standalone` /
`--onefile` builds, and swap the dev dependency. Keep `run.py` as the single entry point.

### Runtime dependency coverage

The app uses these non-stdlib packages (verified in `poetry.lock` / `pyproject.toml`):

| Package | Used for | Nuitka handling |
|---|---|---|
| `pillow` (`PIL`) | photo display (`Image`, `ImageTk`) | `--include-package=PIL` (pulls in all format plugins + `ImageTk`) |
| `pdfplumber` | PDF table/text extraction | `--include-package=pdfplumber` |
| `pdfminer.six` (`pdfminer`) | pdfplumber backend | `--include-package=pdfminer` + `--include-package-data=pdfminer` (bundles `cmap/*.pickle.gz` used at runtime) |
| `pypdfium2` | pdfplumber image rendering (unused by current extraction path, but a pdfplumber dep) | `--include-package=pypdfium2` (+ `--include-package-data=pypdfium2` as belt-and-suspenders) |
| `tkinter` | entire GUI | `--enable-plugin=tk-inter` (bundles Tcl/Tk) |

### Platform builds

**Windows** (`windows-latest`, VS 2022 preinstalled):
- Set up MSVC env via `ilammy/msvc-dev-cmd@v1` (robust `cl.exe` on PATH; avoids the
  known `--msvc=latest` detection flakiness).
- `python -m nuitka --standalone --onefile --enable-plugin=tk-inter`
  `--include-package=PIL --include-package=pdfplumber --include-package=pdfminer`
  `--include-package=pypdfium2 --include-package-data=pdfminer --include-package-data=pypdfium2`
  `--windows-console-mode=disable --output-filename=Partiu.exe`
  `--assume-yes-for-downloads run.py`
  → single `Partiu.exe` (matches current artifact).

**macOS** (`macos-14`, clang preinstalled):
- `python -m nuitka --standalone --macos-create-app-bundle --macos-app-name=Partiu`
  `--enable-plugin=tk-inter --include-package=PIL --include-package=pdfplumber`
  `--include-package=pdfminer --include-package=pypdfium2`
  `--include-package-data=pdfminer --include-package-data=pypdfium2`
  `--assume-yes-for-downloads run.py`
  → `Partiu.app`, then `codesign --force --deep --sign -` and `ditto` zip (keep current
  Gatekeeper workaround).

## Files to modify

| File | Change |
|------|--------|
| `.github/workflows/release.yml` | Install deps + Nuitka (`pip install . nuitka`), add MSVC setup step (Windows), replace both PyInstaller build steps with the Nuitka commands above, keep the artifact upload step. |
| `pyproject.toml` | Replace `pyinstaller = ">=6.11.0"` with `nuitka = ">=2.0.0"` in `[tool.poetry.group.dev.dependencies]`. |
| `README.md` | Update "Build a distributable package" and "Release artifacts" sections to the Nuitka commands. |
| `packaging/partiu.spec` | **DELETE** (PyInstaller-specific; Nuitka does not use `.spec`). Remove `packaging/` if it becomes empty. |
| `run.py` | *(optional)* update the `"PyInstaller entry point"` docstring to `"Packaged-app entry point"`. |

## Reuse

- `run.py` — single entry point (`from partiu.main import main`) used by both packagers.
- `src/partiu/**` — unchanged; Nuitka follows `import partiu.main` from the installed
  package after `pip install .`.
- Existing macOS codesign + `ditto` zip step in the workflow — kept as-is.

## Steps

- [ ] 1. `pyproject.toml`: swap `pyinstaller` → `nuitka` in the dev group.
- [ ] 2. `release.yml`: change the install step to `python -m pip install --upgrade pip . nuitka`.
- [ ] 3. `release.yml`: add `uses: ilammy/msvc-dev-cmd@v1` before the Windows build step.
- [ ] 4. `release.yml`: replace the Windows PyInstaller step with the Nuitka onefile command above.
- [ ] 5. `release.yml`: replace the macOS PyInstaller step with the Nuitka app-bundle command
        + existing codesign/ditto.
- [ ] 6. Delete `packaging/partiu.spec` (and empty `packaging/` dir).
- [ ] 7. Update `README.md` build + release sections.
- [ ] 8. *(optional)* update the `run.py` docstring.

## Verification

- **Local macOS build (fastest to iterate):**
  `poetry install` then run the macOS Nuitka command; confirm `Partiu.app` launches,
  open a part detail view (exercises `PIL.Image`/`ImageTk`), and "Extract from datasheet"
  on `tl062.pdf` (exercises `pdfplumber`/`pdfminer` + cmap data files). No `ModuleNotFoundError`.
- **CI Windows:** trigger a release; download `Partiu.exe` on a Windows machine, run it, and
  repeat the PIL + pdfplumber smoke test. It must no longer raise `no module named PIL`.
- **CI macOS artifact:** download `Partiu-macOS.zip`, launch the `.app`, repeat the same test.
- **Build logs:** confirm the Nuitka output lists the included packages (`PIL`, `pdfplumber`,
  `pdfminer`, `pypdfium2`) and no "missing module" warnings for them.

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Nuitka builds are slow (compiles pdfplumber/pdfminer/PIL) | Release-only job; acceptable. Use `fail-fast: false` matrix as today. |
| Windows onefile + compiled code may trip AV heuristics | Keep `--onefile`; if flagged, fall back to `--standalone` (folder) and zip it. |
| MSVC detection on `windows-latest` | Use `ilammy/msvc-dev-cmd@v1` (proven pattern) rather than relying on `--msvc=latest`. |
| Missing pdfminer cmap data at runtime | `--include-package-data=pdfminer` bundles `cmap/*.pickle.gz`. |
| pypdfium2 native DLL not bundled | `--include-package=pypdfium2` + `--include-package-data=pypdfium2`; confirm via smoke test (it's not on the extraction code path). |
| First Nuitka run may try to download tools (non-interactive CI) | `--assume-yes-for-downloads`. |
