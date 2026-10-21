---
description: "Task list for Clean Architecture Migration"
---

# Tasks: Clean Architecture Migration

**Input**: Design documents from `specs/001-clean-architecture-migration/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Included — the feature specification (FR-011) explicitly requires an automated regression, unit, and import-discipline test suite.

**Organization**: Tasks are grouped by user story (US1–US5 from `spec.md`). The structural migration (US2) is further ordered by layer (domain → application → adapters → gui) per `research.md` R6.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths included in descriptions

## Path Conventions

Single project: `src/partiu/` and `tests/` at repository root. Target layout from `plan.md`:
`domain/`, `application/`, `adapters/`, `gui/`, `main.py` (composition root).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization for testing

- [X] T001 Add `pytest` to the Poetry dev group in `pyproject.toml` (`[tool.poetry.group.dev.dependencies]`, alongside `nuitka`)
- [X] T002 [P] Add `[tool.pytest.ini_options]` in `pyproject.toml` with `testpaths = ["tests"]` and `addopts = "-q"`
- [X] T003 [P] Create the test tree directories `tests/architecture/`, `tests/unit/`, `tests/integration/` (empty dirs; pytest discovers them without `__init__.py`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The boundary contracts, test fakes, and the dependency-rule gate that everything else depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create `src/partiu/application/__init__.py` and `src/partiu/application/ports.py` declaring the 8 `typing.Protocol` interfaces from `contracts/ports.md`: `PartRepository`, `StockRepository`, `RepairRepository`, `AttachmentStore`, `DatasheetExtractor`, `PartsImporter`, `SettingsStore`, `CameraCapturer`
- [X] T005 [P] Create `tests/conftest.py` with in-memory fakes for each port (`FakePartRepository`, `FakeStockRepository`, `FakeRepairRepository`, `FakeAttachmentStore`, `FakeSettingsStore`) and a `tmp_db` fixture that builds a `Database` on a temporary file
- [X] T006 [P] Create the architecture gate `tests/architecture/test_dependency_rule.py` that walks `src/partiu/` and asserts the inward-only import rule from `plan.md`: `domain/` imports nothing outside stdlib/`typing`; `application/` imports only `domain/` + `typing`; `adapters/` imports only `domain/` + `application/`; `gui/` may import all. Gate must report the file, layer, and offending import on failure

**Checkpoint**: Contracts, fakes, and gate ready — layer extraction can begin

---

## Phase 3: User Story 1 - End users see no behavior change (Priority: P1) 🎯 MVP

**Goal**: Pin the current system's behavior in automated tests before any restructuring, so every later refactor is proven non-breaking

**Independent Test**: `poetry run pytest tests/unit tests/integration` passes against the un-migrated codebase and continues to pass (with only import-path updates) after each layer is extracted

### Tests for User Story 1

- [X] T007 [P] [US1] Unit tests for the pure engineering calculators against known outputs in `tests/unit/test_eseries.py`, `tests/unit/test_flyback.py`, `tests/unit/test_transformer.py` (import from `partiu.tools.*`; assert the documented results)
- [X] T008 [P] [US1] Integration tests for the SQLite repository on a temp DB in `tests/integration/test_parts_repository.py`, `tests/integration/test_stock_repository.py`, `tests/integration/test_repair_repository.py` (CRUD, import dedupe by name, cascade delete, attachment/photo file copy)
- [X] T009 [P] [US1] Backward-compatibility test in `tests/integration/test_backward_compat.py` that opens a pre-migration `partiu.db` fixture and asserts existing records read unchanged (no data migration)

### Implementation for User Story 1

- [X] T010 [US1] Run the suite and record the baseline durations in `specs/001-clean-architecture-migration/quickstart.md` (`pytest --durations=10`); note any flow not yet covered so it is added before Phase 4 begins

**Checkpoint**: Current behavior is pinned; any future failure indicates a regression

---

## Phase 4: User Story 2 - Maintainers navigate a layered codebase (Priority: P1)

**Goal**: Relocate/split the codebase into `domain/`, `application/`, `adapters/`, `gui/`, with the composition root in `main.py`, per `plan.md` target layout

**Independent Test**: The app runs after each layer below; a developer can locate any business rule, workflow, or integration by the layer map in `plan.md`

### Layer 1 — Domain (entities + pure calculators)

- [X] T011 [US2] Create `src/partiu/domain/__init__.py` and `src/partiu/domain/part.py` with the `Part` entity — `name` (required), `ipn`, `category`, `description`, `units`, `manufacturer`, `package`, `package_size`, `active` (default true), derived `in_stock`
- [X] T012 [P] [US2] Create `src/partiu/domain/stock.py` with `StockItem` (status vocabulary verbatim: `OK`, `Attention needed`, `Damaged`, `Destroyed`, `Rejected`, `Lost`, `Quarantined`, `Returned`) and `StockLocation` (`label` is derived, concatenation of ancestor names root→leaf, e.g. `A1`)
- [X] T013 [P] [US2] Create `src/partiu/domain/repair.py` with `RepairProject`, `RepairPhoto`, `RepairFinding` — finding `label` required, `x`/`y` normalized 0..1, status vocabulary verbatim: `Good`, `Bad`, `Needs testing`
- [X] T014 [P] [US2] Create `src/partiu/domain/engineering/` by relocating `src/partiu/tools/eseries.py`, `flyback.py`, `transformer.py`, `schematic.py`, `pinout.py` → `domain/engineering/` (pure, zero third-party imports)
- [X] T015 [US2] Update the `tests/unit/test_*.py` from T007 to import from `partiu.domain.engineering.*`; keep assertions identical and confirm they pass

### Layer 2 — Application (use cases over ports)

- [X] T016 [US2] Create `src/partiu/application/use_cases/__init__.py` and `use_cases/parts.py` (create/edit/delete/list/import parts; depends only on `domain` + ports)
- [X] T017 [P] [US2] Implement `application/use_cases/stock.py` and `application/use_cases/locations.py` (stock item/location workflows incl. bulk location assign)
- [X] T018 [P] [US2] Implement `application/use_cases/repairs.py` (project/photo/finding workflows incl. link/unlink finding to a part)
- [X] T019 [P] [US2] Implement `application/use_cases/import_parts.py` and `application/use_cases/extract_datasheet.py` (orchestrating the `PartsImporter` / `DatasheetExtractor` ports)
- [X] T020 [US2] Add use-case unit tests in `tests/unit/test_use_cases.py` using the fakes from `tests/conftest.py`

### Layer 3 — Adapters (concrete port implementations)

- [X] T021 [US2] Create `src/partiu/adapters/sqlite_repository.py` by relocating/splitting `src/partiu/db.py` (schema unchanged, same tables) into one class implementing `PartRepository`, `StockRepository`, `RepairRepository`, `AttachmentStore`
- [X] T022 [P] [US2] Create `src/partiu/adapters/pdf_extractor.py` and `src/partiu/adapters/ocr_extractor.py` implementing `DatasheetExtractor` (relocate `pdf_extract.py` / `ocr_extract.py`)
- [X] T023 [P] [US2] Create `src/partiu/adapters/spreadsheet_importer.py` implementing `PartsImporter` (relocate `importer.py`, incl. template writer)
- [X] T024 [P] [US2] Create `src/partiu/adapters/persistence.py` implementing `SettingsStore` and data-dir/paths resolution (relocate `config.py` / `paths.py`)
- [X] T025 [P] [US2] Create `src/partiu/adapters/camera.py` implementing `CameraCapturer` (cv2 capture only, no tkinter) — split from `gui/camera.py`
- [X] T026 [US2] Update the `tests/integration/test_*_repository.py` from T008 to import from `partiu.adapters.sqlite_repository`; keep assertions and confirm they pass

### Layer 4 — GUI + composition root

- [X] T027 [US2] Rewire `src/partiu/gui/views/` (`base.py`, `parts.py`, `stock.py`, `locations.py`, `detail.py`) to call injected use cases instead of `self.db` directly
- [X] T028 [P] [US2] Rewire `src/partiu/gui/tools/` (`eseries.py`, `flyback.py`, `repairs.py`, `schematic.py`) to use cases; rename `gui/camera.py` → `gui/camera_dialog.py` using `adapters/camera.py`
- [X] T029 [US2] Rewrite `src/partiu/main.py` as the composition root (build adapters, inject into use cases, hand to the GUI); delete the now-relocated top-level modules `src/partiu/db.py`, `importer.py`, `pdf_extract.py`, `ocr_extract.py`, `config.py`, `paths.py`, `tools/`
- [X] T030 [US2] Run `poetry run partiu` and the full suite; confirm every flow from `quickstart.md` still works

**Checkpoint**: The four layers exist and the app runs; US2 is complete

---

## Phase 5: User Story 3 - Inner layers test fast, without external systems (Priority: P2)

**Goal**: Domain and use-case code is fully unit-tested with fakes, runs headless, and completes in under 30 seconds

**Independent Test**: `poetry run pytest tests/unit --durations=10` passes in a headless environment (no display, no database file, no PDF) in under 30 seconds

### Tests for User Story 3

- [X] T031 [P] [US3] Add domain entity unit tests in `tests/unit/test_domain.py` (validation: required `name`/`label`, status enums, derived `label`/`in_stock`, `x`/`y` clamped to 0..1)
- [X] T032 [P] [US3] Expand `tests/unit/test_use_cases.py` to cover each use case's happy path and error path with fakes only
- [X] T033 [US3] Confirm no `tests/unit` test imports tkinter, sqlite3, pdfplumber, rapidocr, onnxruntime, opencv, or openpyxl; fix any that do

**Checkpoint**: Inner layers are provably fast and isolated (SC-004)

---

## Phase 6: User Story 4 - Frameworks and drivers are swappable (Priority: P2)

**Goal**: Demonstrate a storage swap absorbed entirely by adapters, with no change to domain or use cases

**Independent Test**: A test wires use cases to the in-memory fakes and to the SQLite adapter and asserts identical results for the same operations

### Implementation for User Story 4

- [X] T034 [US4] Add `tests/integration/test_swap_demo.py` running the same use-case scenario against the in-memory fakes (from `tests/conftest.py`) and the SQLite adapter, asserting identical outcomes
- [X] T035 [US4] Document the swap demonstration and its result in `specs/001-clean-architecture-migration/quickstart.md` (SC-005)

**Checkpoint**: Swappability is demonstrated, not just claimed

---

## Phase 7: User Story 5 - Import discipline is enforced automatically (Priority: P2)

**Goal**: The dependency-rule gate passes with zero violations and runs on every change

**Independent Test**: Introducing a wrong-direction import (e.g. `import partiu.gui` in `domain/part.py`) makes `pytest tests/architecture` fail naming the file and import; removing it makes the gate pass

### Implementation for User Story 5

- [X] T036 [US5] Run `pytest tests/architecture` against the migrated tree and fix all remaining inward→outward imports until zero violations
- [X] T037 [US5] Add a CI workflow `.github/workflows/test.yml` running `poetry run pytest` (gate + unit + integration) on push/PR

**Checkpoint**: The architecture is self-preserving (FR-007)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, packaging, and end-to-end validation

- [X] T038 [P] Update `README.md` with the new layer layout (`domain/`, `application/`, `adapters/`, `gui/`) and how to run the test suite
- [X] T039 [P] Update the Nuitka build commands/docs in `README.md` for the relocated package paths (runtime deps unchanged)
- [X] T040 Run the full `quickstart.md` validation end-to-end (app flows, `pytest`, gate negative check, headless timing, backward-compat, packaging smoke)

**Checkpoint**: Migration complete and verified

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — pins behavior before refactoring
- **US2 (Phase 4)**: Depends on US1 (safety net in place) — the four layers in strict order: domain → application → adapters → gui
- **US3 (Phase 5)**: Depends on US2 domain + application layers existing
- **US4 (Phase 6)**: Depends on US2 adapters + US3 fakes
- **US5 (Phase 7)**: Depends on US2 full tree existing (gate was authored in Foundational, enforced here)
- **Polish (Phase 8)**: Depends on all preceding phases

### User Story Dependencies

- **US1 (P1)**: after Foundational; no story dependencies
- **US2 (P1)**: after US1; internal layer ordering (domain → application → adapters → gui)
- **US3 (P2)**: after US2 layers 1–2
- **US4 (P2)**: after US2 layer 3 + US3
- **US5 (P2)**: after US2 (all layers); gate authored in Foundational

### Within Each User Story

- Tests written and failing first (where they capture behavior), then implementation
- Domain entities before use cases; ports before adapters; adapters before GUI wiring
- Each layer ends runnable (app still starts)

### Parallel Opportunities

- T002/T003, T005/T006, T007/T008/T009, T012/T013/T014, T017/T018/T019, T022/T023/T024/T025, T031/T032, T038/T039 — all marked [P]
- Within US2, different adapters (T022–T025) can be extracted in parallel once ports exist

---

## Parallel Example: US2 Adapters layer

```bash
# After application/ports.py (T004) and use cases (T016–T019) exist, extract in parallel:
Task: "Create src/partiu/adapters/pdf_extractor.py and src/partiu/adapters/ocr_extractor.py ..."
Task: "Create src/partiu/adapters/spreadsheet_importer.py ..."
Task: "Create src/partiu/adapters/persistence.py ..."
Task: "Create src/partiu/adapters/camera.py ..."
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup → Phase 2 Foundational (contracts + fakes + gate)
2. Phase 3 US1: regression + backward-compat tests capturing current behavior
3. **STOP and VALIDATE**: `poetry run pytest` green against the un-migrated codebase

### Incremental Delivery

1. Setup + Foundational → contracts, fakes, and gate ready
2. US1 → behavior pinned (MVP safety net)
3. US2 → migrate layer-by-layer, app runnable after each layer (domain → application → adapters → gui)
4. US3 → prove inner layers are fast and headless
5. US4 → prove frameworks swappable
6. US5 → enforce the dependency rule in CI
7. Polish → docs, packaging, end-to-end validation

### Parallel Team Strategy

- One developer owns the gate + fakes (Foundational) while another drafts US1 regression tests
- During US2, after `domain/` lands, `application/` and `adapters/` work can be split across developers (ports are stable)
- US3/US4/US5 can be picked up by different developers once their US2 layers land

---

## Notes

- [P] tasks touch different files with no dependencies
- [Story] label maps each task to a user story for traceability
- US2 tasks are ordered by layer — do not parallelize across layers within US2
- Commit after each task or logical group
- Stop at any checkpoint to validate the app still runs
- Keep the SQLite schema and file layout (`partiu.db`, `attachments/`, `repairs/`) unchanged throughout
