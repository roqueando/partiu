# Data Model: Clean Architecture Migration

**Feature**: 001-clean-architecture-migration | **Date**: 2026-10-20

The migration makes the existing data model explicit in the `domain/` layer without
changing it. Entities below mirror the current storage schema and business rules;
field lists are the domain view (not the physical SQL).

## Entities

### Part
A tracked component.

- `name` (text, required, unique case-insensitive for import dedupe)
- `ipn` (text, optional) — internal part number
- `category` (text, optional)
- `description` (text, optional)
- `units` (text, optional)
- `manufacturer` (text, optional)
- `package` (text, optional)
- `package_size` (text, optional)
- `active` (boolean, default true)
- `in_stock` (derived: sum of its stock items' quantities)

Relationships: has many Stock Items, Pins, Parameters, Attachments; referenced by Repair Findings.

### Stock Location
A physical storage place (drawer/cabinet hierarchy).

- `name` (text, required)
- `description` (text, optional)
- `parent` (self-reference to another location, optional)
- `label` (derived: concatenation of ancestor names root→leaf, e.g. `A1`)
- `pathstring` (derived: `A / 1`)

Relationships: parent/children self-relationship; holds Stock Items.

### Stock Item
A physical quantity of a part at a location.

- `part` (reference to Part, required)
- `quantity` (number, default 0)
- `location` (reference to Stock Location, optional)
- `serial` (text, optional)
- `batch` (text, optional)
- `status` (enum, default `OK`)

Status vocabulary (existing, unchanged): `OK`, `Attention needed`, `Damaged`,
`Destroyed`, `Rejected`, `Lost`, `Quarantined`, `Returned`.

### Part Pin
A pin of a component's pinout.

- `part` (reference, required)
- `pin_number` (text, optional)
- `name` (text, required)
- `type` (text, optional)
- `description` (text, optional)

### Part Parameter
An electrical (or other) parameter of a component.

- `part` (reference, required)
- `category` (text, default `Electrical`)
- `symbol` / `name` / `test_conditions` (text, optional)
- `min` / `typ` / `max` (text, optional)
- `unit` (text, optional)

### Part Attachment
A file attached to a part (photo or datasheet PDF).

- `part` (reference, required)
- `kind` (text: `photo` | `datasheet`)
- `filename` (original name)
- `stored_name` (on-disk name under `attachments/<part_id>/`)

### Repair Project
A repair session.

- `name` (text, required)
- `equipment` (text, optional)
- `notes` (text, optional)
- `created_at`, `updated_at` (timestamps)

Relationships: has many Photos and Findings.

### Repair Photo
An image captured/imported for a repair project.

- `project` (reference, required)
- `filename` (original name)
- `stored_name` (on-disk name under `repairs/<project_id>/`)
- `position` (integer ordering within the project)

### Repair Finding (annotation)
A labeled point on a repair photo; links optionally to an inventory part.

- `project` (reference, required)
- `photo` (reference, required)
- `label` (text, required)
- `category` (text, optional; suggested: Trilha, CI, Componente, Conector, Transistor, Capacitor, Resistor, Outro)
- `x`, `y` (number, normalized 0..1 relative to the full-resolution image)
- `status` (enum, default `Needs testing`)
- `part` (reference to Part, optional — the inventory link)
- `notes` (text, optional)

Status vocabulary (unchanged): `Good` ("Bom"), `Bad` ("Ruim"), `Needs testing`
("Precisa testar").

## Engineering value objects (pure, no persistence)

- **ESeriesResult** — nearest commercial value(s) and % deviation for a resistor/inductor/capacitor.
- **FlybackDesign** — converter results (turns ratio, duty cycle, inductances, currents, ratings, capacitance).
- **TransformerDesign** — HF transformer design (core area product, air gap, turns, wire sizing, window check).
- **SchematicSpec** — declarative drawing spec (primitives + annotations) for a schematic.
- **Pinout** — recovered pin rows and their geometry for a datasheet diagram.

## Validation rules (from requirements & existing behavior)

- A Part's `name` is mandatory; import skips empty names and case-insensitive duplicates.
- A Stock Item's `quantity` defaults to 0 and is numeric.
- A Stock Location's `label` is derived, never stored, and must stay unique per drawer path.
- A Repair Finding's `x`/`y` are clamped to 0..1; its `label` is mandatory.
- A Repair Finding may link to at most one Part; unlinking clears the reference.
- Deleting a Part cascades to its stock items/pins/parameters/attachments; a Repair
  Finding's link to a deleted Part becomes unlinked (not deleted).

## State transitions

- Stock Item `status` transitions among the eight status values (user-selected, no
  enforced order).
- Repair Finding `status` transitions freely among `Good` / `Bad` / `Needs testing`.
- A Repair Project has no explicit lifecycle states; `created_at`/`updated_at` record history.
