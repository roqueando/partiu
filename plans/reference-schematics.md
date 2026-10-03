# Plan: Reference schematics in tools (dynamic flyback schematic)

## Context

The Tools menu hosts engineering tools (flyback calculator, E-Series values). Today
none of them show a **schematic** — the flyback tool prints only numeric results, and
the E-Series tool doesn't need one.

Goal: add a reusable "reference schematic" capability to the tooling, and use it in
the **flyback DCM calculator** to show a **dynamic schematic** — the flyback topology
with component values that update when the user presses **Calculate**. E-Series is
explicitly out of scope.

## Decisions (confirmed)

1. **Rendering**: programmatic — draw with `tk.Canvas` primitives. No image assets, no
   Nuitka data-file bundling changes, scales with window/DPI.
2. **Scope**: one reusable `SchematicCanvas` widget + one flyback schematic. No other
   tools for now (E-Series untouched).
3. **Annotated values**: `L1`, `L2`, `n` (turns ratio), `C`, `RL`, `Vds_max`, `VD_max`.
4. **Layout/update**: schematic sits **below** the existing inputs+results form; values
   refresh only on **Calculate**.

## Approach

Declarative, programmatically-rendered schematic, split to match the project's
pure-logic vs GUI convention:

- **`src/partiu/tools/schematic.py`** (pure data, no tkinter → unit-testable):
  - Primitive spec types: `line`, `rect`, `oval`, `polyline`, `text`, `dot`.
  - Symbol builders that append primitives to a list: `inductor`, `transformer`
    (two windings + core + dot polarity), `mosfet`, `diode`, `capacitor`, `resistor`,
    `source`, `ground`.
  - A schematic *spec* = `{primitives: [...], annotations: [{id, x, y, anchor, format}]}`.
  - `FLYBACK_SCHEMATIC`: the DCM flyback topology (Vin → primary winding w/ dot →
    MOSFET → GND; secondary winding → diode → C → RL → GND) with annotation slots for
    the 7 values above.

- **`src/partiu/gui/tools/schematic.py`** (GUI):
  - `SchematicCanvas(tk.Canvas)` that renders a spec (`draw()` for static primitives)
    and exposes `update(values: dict)` to re-render only the annotation labels
    (formatted via a shared SI formatter).

- **`src/partiu/gui/tools/flyback.py`**:
  - Add a `ttk.LabelFrame("Esquemático")` **below** the current `body` frame holding the
    `SchematicCanvas` with `FLYBACK_SCHEMATIC`.
  - In `_calculate()`, after updating `_out_vars`, also call
    `self._schematic.update({...})` with the formatted `calculate()` results.

## Files to modify

| File | Purpose |
|------|---------|
| `src/partiu/tools/schematic.py` | NEW — primitive/spec types, symbol builders, `FLYBACK_SCHEMATIC` |
| `src/partiu/gui/tools/schematic.py` | NEW — `SchematicCanvas` widget |
| `src/partiu/gui/tools/flyback.py` | Add schematic panel below the form; feed it `calculate()` results |
| `README.md` | Document the schematic feature |

## Reuse

- `src/partiu/tools/flyback.py::calculate()` — already returns `L1`, `L2`, `n`, `C`,
  `RL`, `Vds_max`, `VD_max` in SI units.
- `src/partiu/gui/tools/flyback.py::_fmt_si()` — SI-prefix formatting; extract to a
  shared helper (e.g. `src/partiu/tools/format.py`) so both `eseries.py`, `flyback.py`
  and the schematic module use one implementation (small, optional refactor).
- `tk.Canvas` usage pattern from `src/partiu/gui/views/detail.py` (`photo_canvas`) and
  `src/partiu/gui/camera.py` (Canvas + create_* items).
- Tool registry `src/partiu/gui/tools/__init__.py` — no change needed.

## Steps

- [x] Create `src/partiu/tools/schematic.py`: primitive types + symbol builders
      (`inductor`, `transformer`, `mosfet`, `diode`, `capacitor`, `resistor`, `source`,
      `ground`) + `FLYBACK_SCHEMATIC` spec with annotation slots for the 7 values.
- [x] Create `src/partiu/gui/tools/schematic.py`: `SchematicCanvas` rendering a spec
      and `update(values)` for annotation labels.
- [x] (Optional) Extract shared `fmt_si` into `src/partiu/tools/format.py`; update
      `flyback.py` and `eseries.py` to use it.
- [x] Wire into `FlybackToolDialog`: add `LabelFrame("Esquemático")` below `body`,
      instantiate `SchematicCanvas` with `FLYBACK_SCHEMATIC`, and update it at the end
      of `_calculate()`.
- [x] Update `README.md` (Tools → Flyback section) to mention the dynamic schematic.

## Verification

- Run `poetry run partiu` → Tools → "Flyback DCM calculator…": confirm the schematic
  renders below the form with default values.
- Change `Vin` / `Vout` / `freq` / `Iout`, press **Calculate**, and confirm the 7
  annotated values on the schematic match the numeric result sections.
- Confirm the schematic is static until **Calculate** is pressed (no live updates).
- Confirm the E-Series tool is unchanged.
- (If `fmt_si` extracted) run the app once through both tools to confirm formatting
  is identical.
