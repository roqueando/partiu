# Quickstart: Clean Architecture Migration — Validation Guide

**Feature**: 001-clean-architecture-migration | **Date**: 2026-10-20

How to verify the migration end-to-end. Commands run from the repository root.

## Prerequisites

- Python 3.11–3.15 and Poetry installed.
- Runtime dependencies: `poetry install`
- Development/test dependencies: `poetry install --with dev`

## Run the app (behavior preservation)

```bash
poetry run partiu
```

Expected: the app opens identically to before the migration. Confirm the core flows:

1. **Parts** — create/edit/delete a part; search; double-click → detail view (photo, datasheet, pins, parameters).
2. **Stock Items** — create/edit an item; assign a drawer.
3. **Stock Locations** — create a cabinet `A` and drawer `1`; search `GA[A1]` in Parts.
4. **Import** — Parts → Import… a CSV/XLSX; verify dedupe by name.
5. **Datasheet** — attach a PDF, open it, "Extract from datasheet".
6. **Tools** — Flyback DCM calculator and Valores comerciais open and compute.
7. **Reparos** — new project, capture/import a photo, place/edit/move markers, link a finding to a part, open its details, save/reopen.

## Run the automated test suite

```bash
poetry run pytest
```

Expected: all tests pass, including:

- `tests/unit/` — domain + use-case tests using fakes (no display, database, or PDF).
- `tests/integration/` — adapter tests (SQLite repository against a temporary database).
- `tests/architecture/` — the dependency-rule gate.

## Run just the architecture gate (import discipline)

```bash
poetry run pytest tests/architecture
```

Expected: passes when no inner layer imports an outer layer.

**Negative check**: temporarily add a wrong-direction import (e.g. `import partiu.gui`
inside `partiu/domain/part.py`), rerun the gate, and confirm it fails with a message
naming the file and the offending import. Remove the import and confirm it passes
again.

## Verify headless inner-layer speed (SC-004)

```bash
poetry run pytest tests/unit --durations=10
```

Expected: the domain + use-case suite completes in under 30 seconds with no display,
database file, or PDF involved.

## Verify backward compatibility (no data migration)

- Point the app at an existing `partiu.db` from before the migration.
- Open the app and confirm every record appears unchanged; no re-import is required.

## Verify packaging still works

```bash
# macOS (from README): Nuitka standalone app bundle + DMG
poetry run python -m nuitka --standalone --macos-create-app-bundle ...
```

Expected: the installable artifact is produced as before (package paths relocated,
same dependencies bundled).

## Acceptance summary

| Spec ref | How verified |
|----------|--------------|
| FR-001..005 (four layers) | `tests/architecture` gate + manual code review |
| FR-006 (no behavior change) | manual flows above + regression tests |
| FR-007 (auto import gate) | `pytest tests/architecture` negative check |
| FR-008/009 (testable inner + adapters) | `pytest tests/unit` + `tests/integration` |
| FR-010 (layer-by-layer, runnable) | app runs after each extraction step |
| SC-001..006 | test pass rate, headless duration, swap demo, build artifact |
