# Implementation Plan: Clean Architecture Migration

**Branch**: `001-clean-architecture-migration` | **Date**: 2026-10-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-clean-architecture-migration/spec.md`

## Summary

Restructure Partiu — an offline tkinter + SQLite component tracker — into the four
Clean Architecture layers defined by the project constitution: `domain/` (entities +
pure engineering calculations), `application/` (use cases + ports), `adapters/`
(SQLite repository, PDF/OCR extractors, spreadsheet importer, camera capture, config/
paths persistence), and `gui/` (presentation + composition root). The migration is
**incremental and layer-by-layer** (domain → application → adapters → gui), keeps the
app runnable at the end of each layer, is behavior-preserving, and delivers an
automated **regression + unit + import-discipline** test suite.

## Technical Context

**Language/Version**: Python 3.11–3.15 (`requires-python = ">=3.11,<3.16"`; developed on 3.14)

**Primary Dependencies**: tkinter (stdlib GUI), sqlite3 (stdlib storage), Pillow, pdfplumber, openpyxl, rapidocr + onnxruntime (OCR), opencv-python (camera); Nuitka (dev, packaging). No runtime server.

**Storage**: Single SQLite file (`partiu.db`) plus `attachments/` and `repairs/` directories under a per-user data directory.

**Testing**: NEEDS CLARIFICATION — test framework (pytest vs stdlib unittest) and import-discipline enforcement mechanism (dedicated import-linter vs custom architecture test).

**Target Platform**: macOS + Windows desktop, fully offline.

**Project Type**: Desktop GUI application (tkinter), offline-first.

**Performance Goals**: Existing interactive behavior unchanged; inner-layer (domain + use-case) test suite runs headless in under 30 seconds (SC-004).

**Constraints**: Offline-only; no data migration (existing SQLite schema preserved); behavior preservation across all features; dependency rule enforced automatically; runtime dependency set unchanged.

**Scale/Scope**: Single-user local app; ~25 source modules today; migration covers the whole codebase (including Reparos tool, camera, datasheet/OCR extraction).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Assessment |
|-----------|--------|------------|
| I. Dependency Rule (inward-only imports) | PASS | This migration exists to enforce it; enforced by automated gate (FR-007). |
| II. Entities (domain pure Python, no frameworks) | PASS | `domain/` will be extracted first with zero third-party imports (FR-002). |
| III. Use Cases depend on domain + ports only | PASS | `application/` depends only on `domain/` + `Protocol` ports (FR-003). |
| IV. Adapters translate outer formats at the boundary | PASS | `adapters/` owns SQL/PDF/spreadsheet/camera translation (FR-004). |
| V. Frameworks & drivers in outer ring | PASS | tkinter/sqlite3/pdfplumber/rapidocr/openpyxl/Nuitka stay at the edge (FR-005). |
| Architecture & Project Structure (4 packages + composition root) | PASS | Target layout documented below; `main.py` is the only assembler. |
| Development Workflow & Quality Gates | PASS | Unit-testable inner layers + automated import gate + adapter integration tests are in scope (FR-008/009/011). |
| Governance (migration plan accompanies change) | PASS | This plan is the required migration plan. |

**Gate result**: PASS — no violations. The migration aligns with the constitution; no justified deviations required.

**Post-design re-check (Phase 1)**: PASS — the design artifacts (`research.md`, `data-model.md`, `contracts/ports.md`, `quickstart.md`) keep the four-ring dependency direction, place all framework imports in `adapters/`/`gui/`, define ports as `Protocol`s the application depends on, and keep `main.py` as the sole composition root.

## Project Structure

### Documentation (this feature)

```text
specs/001-clean-architecture-migration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (port interfaces)
│   └── ports.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root) — target layout

```text
src/partiu/
├── domain/                       # Entities + pure engineering calculations (zero 3rd-party imports)
│   ├── part.py
│   ├── stock.py                  # stock item + location
│   ├── repair.py                 # repair project / photo / finding
│   └── engineering/
│       ├── eseries.py
│       ├── flyback.py
│       ├── transformer.py
│       ├── schematic.py
│       └── pinout.py
├── application/                  # Use cases + ports (depends only on domain)
│   ├── ports.py                  # Protocol interfaces for adapters
│   └── use_cases/
│       ├── parts.py
│       ├── stock.py
│       ├── locations.py
│       ├── repairs.py
│       ├── import_parts.py
│       └── extract_datasheet.py
├── adapters/                     # Concrete port implementations (framework imports allowed)
│   ├── sqlite_repository.py
│   ├── pdf_extractor.py
│   ├── ocr_extractor.py
│   ├── spreadsheet_importer.py
│   ├── camera.py                 # cv2 capture only (no tkinter)
│   └── persistence.py            # config + paths (UserSettings, data dir)
├── gui/                          # tkinter presentation (imported by nothing inner)
│   ├── app.py
│   ├── widgets.py
│   ├── views/
│   │   ├── base.py
│   │   ├── parts.py
│   │   ├── stock.py
│   │   ├── locations.py
│   │   └── detail.py
│   ├── tools/
│   │   ├── eseries.py
│   │   ├── flyback.py
│   │   ├── repairs.py
│   │   └── schematic.py
│   └── camera_dialog.py          # tkinter dialog (uses adapters.camera)
└── main.py                       # composition root — the ONLY place that wires adapters into use cases

tests/
├── architecture/                 # import-lint / dependency-rule gate
├── unit/                         # domain + application (fakes only, no display/DB/PDF)
└── integration/                  # adapters (e.g. sqlite repository on temp DB)
```

**Structure Decision**: Single-project layout (the app is one Python package). The
four rings map to the four packages under `src/partiu/` exactly as the constitution
prescribes; tests mirror the layers (`architecture`, `unit`, `integration`). Existing
files are **relocated** (with their logic split where a module currently mixes layers),
not duplicated.

## Complexity Tracking

No constitution violations — table intentionally empty.
