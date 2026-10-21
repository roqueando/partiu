<!--
Sync Impact Report (temporary — remove before committing)
- Version change: unversioned placeholder → 1.0.0
- Modified principles: all five placeholder principles replaced with Clean
  Architecture principles (initial adoption; no renames)
- Added sections: "Architecture & Project Structure"; "Development Workflow
  & Quality Gates"
- Removed sections: none
- Follow-up TODOs: none
-->

# Partiu Constitution

## Core Principles

### I. Dependency Rule (NON-NEGOTIABLE)
Source-code dependencies MUST point inward only. Inner layers MUST NOT import,
reference, or otherwise know about outer layers. Any import from an inner layer
into a more outward layer (e.g. `domain` importing `gui`, or `application`
importing `adapters`) is a violation.
Rationale: the dependency rule is the load-bearing wall of Clean Architecture —
it is what makes each layer independently testable, replaceable, and readable.

### II. Entities (Domain Layer)
The domain layer owns the business objects and rules of the inventory domain:
parts, stock items, stock locations, repair findings, and the pure engineering
calculations (E-series, flyback, transformer, schematic, pinout). It MUST be
pure Python with no framework imports (no tkinter, sqlite3, pdfplumber,
rapidocr, onnxruntime, openpyxl).
Rationale: a framework-free core survives UI and storage changes and is unit
testable in milliseconds.

### III. Use Cases (Application Layer)
Application-specific workflows — create/edit a part, import components, extract
a datasheet, annotate a repair — MUST be expressed as plain functions or
classes that depend only on entities and abstract ports (interfaces), never on
concrete adapters or frameworks. Each use case MUST state its input and output
in domain terms.
Rationale: use cases are the application's behavior; keeping them free of I/O
details makes them deterministic and testable with fakes.

### IV. Interface Adapters
Adapters implement the ports that use cases define: the SQLite repository, the
PDF/OCR extractors, the CSV/XLSX import readers, and the presenters that format
data for the GUI. Adapters MUST translate outer formats (SQL rows, PDF pages,
spreadsheet cells, tkinter models) into domain objects at the boundary and MUST
NOT leak those formats inward.
Rationale: isolating format conversion in one layer is what makes storage and
presentation swaps cheap and low-risk.

### V. Frameworks & Drivers (Outer Ring)
tkinter, sqlite3, pdfplumber, rapidocr/onnxruntime, openpyxl, and Nuitka live
in the outermost ring. They are details. Swapping any of them (a different GUI
toolkit or a different database) MUST NOT require changes to the domain or
use-case layers.
Rationale: frameworks change fastest and impose the most coupling; keeping them
at the edge contains that churn.

## Architecture & Project Structure

The four rings map to concrete packages under `src/partiu/`:

- `domain/` — entities and pure business rules (part, stock item, location,
  engineering calculators). MUST have zero third-party imports.
- `application/` — use cases and the ports they depend on. Imports only
  `domain/` and abstract interfaces.
- `adapters/` — implementations of ports: SQLite repository, PDF/OCR extractors,
  CSV/XLSX import readers, config/paths persistence. Imports `domain/` and
  `application/`; MAY import framework libraries.
- `gui/` — tkinter presentation (views, widgets, dialogs) and the composition
  root (`main.py`) that wires adapters into use cases. Imports everything;
  imported by nothing inner.

The composition root (`main.py`) is the only place allowed to assemble concrete
objects. Use cases MUST receive their dependencies via constructor or parameter
injection rather than instantiating adapters themselves.

The current codebase predates this layout. Restructuring it into these layers is
a separate migration effort and MUST follow the dependency rule above.

## Development Workflow & Quality Gates

- Every change MUST preserve the dependency rule; reviewers MUST reject inward
  imports of outer layers.
- Domain and use-case code MUST be unit-testable without a display, a database,
  or a PDF. Tests for inner layers MUST use fakes/in-memory doubles only.
- Import discipline MUST be enforced automatically (an import-lint or
  architecture test) once the layer packages exist; until then, a manual
  checklist MUST accompany each change.
- Adapters MUST be integration-tested against their real dependency where
  feasible (e.g. the SQLite repository against a temporary database).

## Governance

- This constitution supersedes other development practices. Where a practice
  conflicts, the constitution wins and the practice MUST be amended or removed.
- Amendments MUST be proposed, documented, and reviewed before taking effect. A
  migration plan MUST accompany any change that affects existing code.
- Versioning follows SemVer: MAJOR for principle removals or redefinitions,
  MINOR for new principles or sections, PATCH for clarifications and wording.
- Compliance MUST be verified on every change (code review plus import checks).
  Deviations MUST be justified in writing and carry an explicit expiry date.

**Version**: 1.0.0 | **Ratified**: 2026-10-20 | **Last Amended**: 2026-10-20
