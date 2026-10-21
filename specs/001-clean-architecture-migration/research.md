# Research: Clean Architecture Migration

**Feature**: 001-clean-architecture-migration | **Date**: 2026-10-20

Phase 0 output. Resolves every NEEDS CLARIFICATION in `plan.md` Technical Context and
records the design decisions that Phase 1 builds on.

## R1 — Test framework

- **Decision**: `pytest` as a development dependency.
- **Rationale**: Industry-standard, zero-config discovery of `tests/`, native fixtures
  for building in-memory fakes, and it runs the same way locally and in CI. The
  project already maintains a Poetry `dev` group (Nuitka), so adding `pytest` there
  keeps runtime dependencies untouched — consistent with the constitution's
  "framework-free core" rule (test tooling is not part of the runtime).
- **Alternatives considered**: stdlib `unittest` (no new dependency, but weaker
  ergonomics and harder to express the architecture gate as a concise test);
  `tox`/`nox` (overkill for a single offline app).

## R2 — Import-discipline enforcement

- **Decision**: A custom architecture test (a small `pytest` module under
  `tests/architecture/`) that walks the package and asserts the inward-only import
  rule, using Python's `ast` to read top-level imports plus `importlib` metadata.
- **Rationale**: Zero new dependencies, exact fit to the four-layer contract, and it
  fails on any inward→outward import with a precise message (file, layer, offending
  import). Because it is plain pytest, it runs in the same command as the rest of the
  suite (`poetry run pytest`), satisfying FR-007.
- **Alternatives considered**: `import-linter` (purpose-built and configurable, but
  adds a dependency and a separate config/CI step); a `pyproject.toml`-based lint rule
  (not natively supported without a tool).

## R3 — Port mechanism (application ↔ adapters boundary)

- **Decision**: Ports are `typing.Protocol` classes declared in
  `application/ports.py`.
- **Rationale**: Python ≥3.11 supports structural subtyping, so adapters implement a
  port without importing an abstract base; this keeps the application layer free of
  any concrete type and lets fakes be plain classes in tests. `Protocol` is the
  idiomatic Python form of an "interface" for a use case to depend on.
- **Alternatives considered**: `abc.ABC` (nominal, more ceremony and explicit
  inheritance from application into adapters); passing bare callables (too coarse for
  repository-shaped ports with many methods).

## R4 — Use-case style

- **Decision**: Use cases are plain functions (or small dataclass-free classes when
  state is needed) in `application/use_cases/`, each declaring its inputs and outputs
  in domain terms and receiving ports via parameter injection (repository, store,
  extractor, importer).
- **Rationale**: Matches the constitution ("plain functions or classes … never
  concrete adapters"; "dependencies via constructor or parameter injection"). Keeps
  each workflow deterministic and testable with fakes.
- **Alternatives considered**: Service classes with constructor injection (equally
  valid, chosen per use case when shared state or several ports are involved);
  global service locator (rejected — hides dependencies and couples to composition).

## R5 — Module → layer mapping

Current module → target layer (relocate, split where a file mixes layers):

| Current module | Target | Notes |
|----------------|--------|-------|
| `tools/eseries.py`, `tools/flyback.py`, `tools/transformer.py`, `tools/schematic.py`, `tools/pinout.py` | `domain/engineering/` | Already pure; move as-is. |
| `db.py` (entities/SQL) | split → `domain/` (entities) + `adapters/sqlite_repository.py` (SQL) + `application/use_cases/` (workflows) | The largest split: schema stays in the adapter; domain objects become explicit. |
| `pdf_extract.py` | `adapters/pdf_extractor.py` | Header-driven table extraction; returns domain `ExtractedDatasheet`. |
| `ocr_extract.py` | `adapters/ocr_extractor.py` | OCR fallback; same output contract as PDF extractor. |
| `importer.py` | `adapters/spreadsheet_importer.py` | CSV/XLSX → rows; template writer stays here. |
| `config.py`, `paths.py` | `adapters/persistence.py` | Settings store + data-dir resolution. |
| `gui/camera.py` | split → `adapters/camera.py` (cv2 capture) + `gui/camera_dialog.py` (tkinter) | Separates the driver from the dialog. |
| `gui/app.py`, `gui/views/*`, `gui/widgets.py`, `gui/tools/*` | `gui/` (unchanged location) | Views stop calling the DB directly; they call use cases injected from the composition root. |
| `main.py` | composition root | Wires real adapters → use cases → GUI. |

## R6 — Incremental extraction order

- **Decision**: Extract in constitution order, each step ending runnable:
  1. **domain/** — entities + engineering calculators (pure, no deps).
  2. **application/** — ports + use cases (depend on domain; tested with fakes).
  3. **adapters/** — move SQL/PDF/OCR/spreadsheet/camera/config implementations and
     make them implement the ports.
  4. **gui/** — rewire views/tools through use cases; move composition to `main.py`.
- **Rationale**: Satisfies FR-010 (layer-by-layer, app runnable after each layer) and
  mirrors the dependency rule, so each layer is fully testable before the next depends
  on it.
- **Alternatives considered**: Feature-by-feature vertical slices (each slice crosses
  all four layers; more moving parts at once but delivers value sooner — rejected
  because the spec chose layer-by-layer); big-bang (rejected by the user in Q1).

## R7 — Runtime dependency and data stability

- **Decision**: No runtime dependencies are added or removed; the SQLite schema and
  file layout (`partiu.db`, `attachments/`, `repairs/`) are unchanged.
- **Rationale**: Satisfies FR-006 (no behavior/data change) and the assumption that
  old databases open unchanged; keeps Nuitka packaging untouched apart from the
  relocated package paths.
- **Alternatives considered**: Normalizing the schema during migration (rejected —
  would break backward compatibility and expand scope).
