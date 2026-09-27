# Plan: Quality-of-life fixes (edit preload, manufacturer column, drawer search)

## Context

Three small QoL gaps in the Parts flow:

1. **Edit form doesn't preload/show all part fields.** The Parts list "Edit" dialog
   only exposes Name / IPN / Category / Description / Units / Active. The part model
   also has `manufacturer`, `package`, `package_size`, which are editable only in the
   detail window. Worse, saving the list edit form calls `update_part` with those keys
   missing, so `manufacturer`/`package`/`package_size` are **wiped to NULL** on every
   list edit.
2. **Manufacturer missing from the Parts list.** The listing shows Name → IPN →
   Category → … but not Manufacturer.
3. **Cannot search parts by drawer.** The Parts search only matches name/IPN/
   description/category/manufacturer text. We want a `GA[A1]` token that returns all
   parts stored in drawer `A1`.

## Findings (root causes)

- `src/partiu/gui/views/parts.py` → `PartsView.form_fields()` lists only 6 fields;
  `manufacturer`, `package`, `package_size` are absent. `FormDialog` already preloads
  any key present in `initial` (base `CrudView.edit` passes the full row), so adding the
  fields is enough — no widget change needed.
- `src/partiu/db.py` → `list_parts()` already selects `p.manufacturer`, so issue 2 is a
  columns-only change.
- `src/partiu/db.py` → `list_parts()` text search has no location awareness. Drawer
  labels are computed by `Database._location_label()` (root-to-leaf concat, e.g. `A` +
  `1` → `A1`).

## Approach

### 1. Complete the Parts edit form
Add three `FieldSpec`s to `PartsView.form_fields()` after Units:
`Manufacturer`, `Package`, `Package size` (keys `manufacturer`, `package`,
`package_size`). This both preloads existing values and stops the edit form from
nulling those columns.

### 2. Add Manufacturer column
Insert `("manufacturer", "Manufacturer", 160)` right after the IPN column in
`PartsView.columns`.

### 3. Drawer search (`GA[...]`) in Parts
Extend `Database.list_parts()` to recognise `GA[<label>]` tokens (case-insensitive)
in the search string:

- Parse all `GA[...]` tokens with a module-level regex `GA\[([^\]]+)\]`
  (re.IGNORECASE). Strip them from the search string; the remaining text becomes the
  free-text LIKE filter.
- Resolve each token label to `stock_location` ids:
  - Build the existing `_location_map()` and group children by `parent_id`.
  - Compute each location's label via `_location_label()` (case-insensitive).
  - A token matches every location whose label equals it, **plus all its descendants**
    — so `GA[A1]` hits drawer `A1` and `GA[A]` hits cabinet `A` plus every drawer under
    it (`A1`, `A2`, …).
  - Union across all tokens (OR).
- If any token matches nothing → return an empty list.
- Filter parts to those with ≥1 `stock_item` in the matched location set:
  `AND p.id IN (SELECT part_id FROM stock_item WHERE location_id IN (...))`.
- Free-text filter and drawer filter combine with **AND**.

## Files to modify

- `src/partiu/gui/views/parts.py` — form fields + column.
- `src/partiu/db.py` — drawer-aware `list_parts()`.
- `README.md` — document the `GA[...]` search syntax.

## Reuse

- `Database._location_map()` / `Database._location_label()` — existing drawer-label
  helpers in `db.py`; reuse for resolving `GA[<label>]` to location ids.
- `FormDialog` (widgets.py) — already handles `initial=`; no change required for issue 1.
- `list_parts()` already returns `manufacturer`; no SQL change needed for issue 2.

## Decisions (confirmed)

- `GA[A]` (cabinet letter) matches the cabinet and **all its descendant drawers**.
- `GA[...]` search applies to the **Parts** view only for now.
- `GA[...]` **combines with free text** (intersection), e.g. `GA[A1] resistor`.
- Multiple `GA[...]` tokens OR together.

## Steps

- [ ] Add Manufacturer/Package/Package size fields to `PartsView.form_fields()`
      (keys `manufacturer`, `package`, `package_size`, after Units).
- [ ] Add Manufacturer column after IPN in `PartsView.columns`.
- [ ] In `db.py`: add a module-level `GA[...]` regex and a helper
      `_location_ids_for_labels(labels)` (plus a small `_descendants(children, pk)`);
      rewrite the `WHERE`-building part of `list_parts()` to split free text vs.
      location tokens and AND them together.
- [ ] Document the `GA[...]` syntax in `README.md` (storage drawers section).

## Verification

- `poetry run partiu` → Parts view:
  - Edit a part that has manufacturer/package/package size set; confirm the three fields
    are pre-filled, and saving preserves them (not NULL).
  - Confirm a "Manufacturer" column appears between IPN and Category.
  - Type `GA[A1]` (a real drawer) → only parts stored in that drawer are listed;
    Locations column still shows `A1 ×N`.
  - Type `GA[A1] <text>` → list is the intersection of drawer + text matches.
- Quick data-layer check without GUI:
  ```python
  from partiu.db import Database
  from partiu.paths import get_database_file
  db = Database(get_database_file())
  print([p["name"] for p in db.list_parts("GA[A1]")])
  ```
