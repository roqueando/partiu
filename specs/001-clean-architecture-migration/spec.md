# Feature Specification: Clean Architecture Migration

**Feature Branch**: `001-clean-architecture-migration`

**Created**: 2026-10-20

**Status**: Draft

**Input**: User description: "Precisamos migrar o projeto para Clean Architecture."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End users see no behavior change (Priority: P1)

The people who use Partiu today — tracking parts, stock items, storage drawers,
extracting datasheets, importing spreadsheets, and running engineering tools
such as the flyback calculator or the Reparos repair workspace — continue to do
exactly the same things before, during, and after the restructuring. Nothing
about the product changes for them: the same screens, the same data, the same
files, the same shortcuts.

**Why this priority**: A structural migration only has value if it does not
break the working product. Preserving current behavior is the non-negotiable
foundation everything else builds on.

**Independent Test**: Run the complete set of existing user flows (create/edit a
part, search by drawer, import a CSV, extract a datasheet, capture a photo,
annotate a repair, open a linked part) against the restructured code and confirm
identical results and no data loss.

**Acceptance Scenarios**:

1. **Given** an existing local database with parts, stock and repairs, **When** the user opens the migrated app, **Then** all records appear exactly as before, with no data migration or re-import required.
2. **Given** any existing feature (list, create, edit, delete, import, extract, camera, tool), **When** the user performs the same action as before the migration, **Then** the result is identical to the previous version.
3. **Given** the migrated app, **When** the user opens a database created by the old version, **Then** it opens correctly and remains backward compatible.

---

### User Story 2 - Maintainers navigate a layered codebase (Priority: P1)

A developer opening the code can immediately locate business rules, workflows,
integrations, and presentation without tracing tangled dependencies. Business
objects and pure engineering calculations live in one clearly separated layer;
application workflows live in another; database, PDF, OCR, spreadsheet, and
settings integrations live in adapters; the graphical interface and the entry
point sit at the outer edge.

**Why this priority**: Readability and clear boundaries are the primary reason
for the migration; without them the effort delivers no benefit.

**Independent Test**: A developer unfamiliar with the project, given the layer
layout and the rule "dependencies point inward only", can locate where a given
business rule, workflow, or integration should live within minutes.

**Acceptance Scenarios**:

1. **Given** the restructured codebase, **When** a developer opens the business-rules layer, **Then** it contains entities and pure calculations with no references to screens, databases, PDFs, or OCR.
2. **Given** the restructured codebase, **When** a developer wants to change how data is stored, **Then** the change is confined to the adapter layer without touching business rules or workflows.
3. **Given** the restructured codebase, **When** a developer wants to understand a workflow (e.g. "import components"), **Then** it is expressed in one place in the workflow layer in terms of business concepts, not file formats.

---

### User Story 3 - Inner layers test fast, without external systems (Priority: P2)

Developers can verify business rules and workflows with automated tests that run
without a display, a database, or a PDF — using in-memory doubles — and that
complete in seconds.

**Why this priority**: Fast, isolated tests are the practical payoff of clean
separation; they make future changes safe and cheap.

**Independent Test**: Run the business-rule and workflow test suite in a headless
environment (no display, no database file, no PDF) and confirm it completes
within a few seconds and passes.

**Acceptance Scenarios**:

1. **Given** a business rule or calculation (e.g. E-series lookup, flyback design), **When** a developer runs its tests, **Then** no display, database, or document library is required and the test completes in under a few seconds.
2. **Given** a workflow (e.g. create a part, link a repair finding), **When** a developer runs its tests with a fake storage, **Then** the workflow behaves identically to the real storage path.

---

### User Story 4 - Frameworks and drivers are swappable (Priority: P2)

The specific choices of interface toolkit, database, PDF/OCR library, and
packager are details at the outer edge. Swapping any one of them must not force
changes to business rules or workflows.

**Why this priority**: This is the long-term durability guarantee that justifies
the migration's cost.

**Independent Test**: Demonstrate that the storage mechanism (or the presentation
technology) can be replaced without modifying the business-rules or workflow
layers — the change is absorbed entirely by adapters and composition.

**Acceptance Scenarios**:

1. **Given** a second storage implementation (e.g. an in-memory store for tests), **When** the app is wired to it instead of the file-based store, **Then** workflows and business rules are unchanged and function correctly.
2. **Given** the packaging/build step, **When** the app is built for the supported platforms, **Then** the installable artifact is produced as before.

---

### User Story 5 - Import discipline is enforced automatically (Priority: P2)

The dependency rule is checked by an automated gate: any import from an inner
layer into an outer layer fails the check, so violations cannot silently
accumulate.

**Why this priority**: A manual rule decays; an automated gate makes the
architecture self-preserving.

**Independent Test**: Introduce a deliberate wrong-direction import in a test
branch and confirm the automated check fails; remove it and confirm the check
passes.

**Acceptance Scenarios**:

1. **Given** a code change that adds an inward→outward import, **When** the check runs, **Then** it reports the violating import and fails.
2. **Given** a codebase with no violations, **When** the check runs, **Then** it passes and the change is accepted.

---

### Edge Cases

- What happens when a module currently mixes concerns (e.g. database access,
  schema, and data formatting in one file)? The migration must split it without
  changing outward behavior; each split is independently verifiable.
- What happens when a third-party-heavy module (PDF/OCR, camera, spreadsheet) is
  moved into an adapter? Its behavior must remain identical and the packaging
  must still bundle its libraries.
- What happens to databases created by the previous version? They must open
  unchanged — the storage format is not altered by the migration.
- What happens if a wrong-direction import is introduced mid-migration? The
  automated gate must catch it immediately so the error is fixed before more
  code builds on it.
- What happens during the transition, before every module is migrated? The app
  must remain runnable at every intermediate step.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The codebase MUST be organized into four separated layers: business rules (entities and pure calculations), application workflows (with their abstract ports), adapters (concrete integrations), and presentation/entry point.
- **FR-002**: The business-rules layer MUST contain no references to screens, databases, documents, or third-party libraries — it is pure business logic.
- **FR-003**: The workflow layer MUST express each user workflow (create/edit a part, import components, extract a datasheet, annotate a repair, run a calculation) as plain operations that depend only on business rules and abstract ports, never on concrete integrations.
- **FR-004**: The adapter layer MUST implement the workflow ports and translate outer formats (database rows, PDF pages, spreadsheet cells, screen models) into business objects at the boundary, without leaking those formats inward.
- **FR-005**: The presentation layer and the entry point MUST be the only place where concrete objects are assembled and wired together.
- **FR-006**: Every existing feature MUST continue to work identically after the migration (no behavior change, no data change, no data re-import).
- **FR-007**: The dependency rule MUST be enforced automatically, so any inward→outward import fails the check.
- **FR-008**: The business-rules and workflow layers MUST be unit-testable without a display, a database file, or a document.
- **FR-009**: The adapters MUST be integration-tested against their real dependency where feasible (e.g. the storage adapter against a temporary database).
- **FR-010**: The migration MUST be carried out incrementally, layer by layer — extract business rules first, then application workflows, then adapters, then presentation — keeping the app runnable at the end of each layer.
- **FR-011**: The migration MUST deliver an automated regression, unit, and import-discipline test suite as part of this work.

### Key Entities *(include if feature involves data)*

The migration makes explicit the entities that already exist implicitly in the
product. They move into the business-rules layer without changing their meaning:

- **Part**: a tracked component (name, part number, category, manufacturer, package, stock status).
- **Stock Item**: a physical quantity of a part in a location (quantity, serial, batch, status).
- **Stock Location**: a storage place (name, description, parent), including the drawer/cabinet hierarchy.
- **Repair Project / Finding**: a repair session and its annotated findings, each with a label, status, category, and an optional link to a Part.
- **Pin / Parameter / Attachment**: component details (pinout rows, electrical parameters, photo/datasheet files).
- **Engineering value objects**: pure results of the calculators (E-series values, flyback/transformer designs, schematic specifications, pinout geometry).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing user flows behave identically after the migration, verified by automated regression tests and a manual checklist.
- **SC-002**: The business-rules layer contains zero references to screens, databases, or document/third-party libraries, verified automatically.
- **SC-003**: Zero dependency-rule violations, verified automatically on every change.
- **SC-004**: The business-rules and workflow test suite runs headless and completes in under 30 seconds.
- **SC-005**: A storage or presentation mechanism can be swapped without modifying business-rules or workflow layers (demonstrated once).
- **SC-006**: Installable builds for the supported platforms are still produced from the migrated code.

## Assumptions

- The migration is behavior-preserving: the product's features, data, and user
  interface remain unchanged; only internal structure changes.
- The existing storage format (the local database and its files) is unchanged, so
  no data migration is required.
- The set of third-party libraries stays the same; the migration moves where they
  are used, not which ones are used.
- The target layer layout and naming already described in the project's
  governing principles (business rules / workflows / adapters / presentation)
  are authoritative for this feature.
- The migration covers the whole codebase, including the recent Reparos tool, the
  camera capture, and the document/OCR extraction paths.
- The migration proceeds layer by layer — business rules first, then workflows,
  then adapters, then presentation — and the application remains runnable after
  each layer is extracted.
- An automated regression, unit, and import-discipline test suite is delivered
  as part of this migration.
