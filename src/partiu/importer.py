"""Import component (part) records from CSV or Excel spreadsheets.

The first row is treated as a header.  Columns are matched to part fields by
name (case-insensitive, punctuation/underscores ignored).  Recognized aliases
per field:

- name:          name, part name, part_name, component, component name
- IPN:           ipn, internal part number, part number, pn, mpn
- category:      category, type, group
- description:   description, desc, notes
- units:         units, unit, uom
- manufacturer:  manufacturer, mfr, vendor, brand, make
- package:       package, case, footprint
- package_size:  package size, package_size, case size
- active:        active, enabled  (blank -> active; "0"/"no"/"false" -> inactive)

Only ``name`` is required; rows without it are skipped.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

#: Canonical part field -> accepted header aliases.
FIELD_ALIASES: dict[str, list[str]] = {
    "name": ["name", "partname", "component", "componentname"],
    "IPN": ["ipn", "internalpartnumber", "partnumber", "pn", "mpn"],
    "category": ["category", "type", "group"],
    "description": ["description", "desc", "notes"],
    "units": ["units", "unit", "uom"],
    "manufacturer": ["manufacturer", "mfr", "vendor", "brand", "make"],
    "package": ["package", "case", "footprint"],
    "package_size": ["packagesize", "casesize", "packagesizemm"],
    "active": ["active", "enabled"],
}

_TRUE = {"1", "yes", "y", "true", "active", "enabled", "on"}
_FALSE = {"0", "no", "n", "false", "inactive", "disabled", "off"}


def _normalize(text: str) -> str:
    """Lowercase and strip everything except letters/digits."""
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


_ALIAS_TO_FIELD: dict[str, str] = {
    _normalize(alias): field
    for field, aliases in FIELD_ALIASES.items()
    for alias in aliases
}


def read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    """Return ``(headers, data_rows)`` for a CSV or Excel file."""
    ext = path.suffix.lower()
    if ext == ".csv":
        return _read_csv(path)
    if ext in {".xlsx", ".xlsm"}:
        return _read_excel(path)
    raise ValueError(f"Unsupported file type: {path.suffix or '(none)'}")


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open(newline="", encoding=encoding) as handle:
                rows = [[cell.strip() for cell in row] for row in csv.reader(handle)]
                rows = [row for row in rows if any(row)]
        except UnicodeDecodeError:
            continue
        break
    else:
        raise ValueError("Could not decode CSV (tried UTF-8 and Windows-1252).")

    if not rows:
        return [], []
    return rows[0], rows[1:]


def _read_excel(path: Path) -> tuple[list[str], list[list[str]]]:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        headers: list[str] = []
        data: list[list[str]] = []
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if cell is None else str(cell).strip() for cell in row]
            if not any(cells):
                continue
            if not headers:
                headers = cells
            else:
                data.append(cells)
    finally:
        workbook.close()
    return headers, data


def map_columns(headers: list[str]) -> dict[str, int]:
    """Map canonical part fields to column indexes from ``headers``."""
    mapping: dict[str, int] = {}
    for index, header in enumerate(headers):
        field = _ALIAS_TO_FIELD.get(_normalize(header))
        if field and field not in mapping:
            mapping[field] = index
    return mapping


def _parse_bool(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return True  # blank / unknown -> active


def import_parts_from_file(db, path: Path) -> dict[str, Any]:
    """Read ``path`` and bulk-insert the parts into ``db``.

    Returns ``{"created": int, "skipped": int, "total": int}``.
    """
    headers, rows = read_rows(path)
    mapping = map_columns(headers)
    if "name" not in mapping:
        raise ValueError(
            "No 'name' column found. The first row must be a header row with"
            " a column named 'name' (or 'Part Name', 'Component', etc.)."
        )

    records: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, Any] = {}
        for field, index in mapping.items():
            value = row[index] if index < len(row) else ""
            record[field] = str(value).strip() if value is not None else ""
        record["active"] = _parse_bool(record.get("active"))
        records.append(record)

    counts = db.import_parts(records)
    return {
        "created": counts["created"],
        "skipped": counts["skipped"],
        "duplicates": counts["duplicates"],
        "total": len(records),
    }


TEMPLATE_HEADERS = [
    "name",
    "IPN",
    "category",
    "description",
    "units",
    "manufacturer",
    "package",
    "package_size",
    "active",
]

TEMPLATE_EXAMPLE = [
    "TL062",
    "IPN-0001",
    "OpAmp",
    "Dual low-power JFET-input op-amp",
    "pcs",
    "Texas Instruments",
    "SOIC-8",
    "4.9x3.9 mm",
    "yes",
]


def write_template(path: Path) -> None:
    """Write a ready-to-fill CSV template (with BOM) to ``path``."""
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(TEMPLATE_HEADERS)
        writer.writerow(TEMPLATE_EXAMPLE)
