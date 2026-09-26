"""Extract component data from a PDF datasheet.

Header-driven, best-effort extraction.  Instead of hard-coding the Texas
Instruments column layout (as the previous version did), each table is
classified by its header cells and its columns are mapped by header label,
with content-based fallbacks when the header is missing or uses package names
(e.g. the TI "Pin Functions" multi-package table).

Extraction is intentionally tolerant: whatever can be recognised is returned
and everything stays editable in the GUI.  Scanned/image-only PDFs (no text
layer) and pin numbers that exist only inside a graphical pinout cannot be
extracted without OCR and are out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

#: Known manufacturers, detected by case-insensitive substring match.
MANUFACTURERS = [
    "Texas Instruments",
    "STMicroelectronics",
    "Analog Devices",
    "ON Semiconductor",
    "onsemi",
    "Infineon",
    "NXP Semiconductors",
    "NXP",
    "Microchip",
    "Vishay",
    "Diodes Incorporated",
    "Renesas",
    "ROHM Semiconductor",
    "Toshiba",
    "Fairchild Semiconductor",
    "Maxim Integrated",
    "Silicon Labs",
    "Murata",
    "Bourns",
    "KEMET",
    "TDK",
    "Samsung",
    "Panasonic",
    "Littelfuse",
    "TE Connectivity",
    "Molex",
    "Würth Elektronik",
    "Yageo",
    "AVX",
    "Nichicon",
    "Rubycon",
]

#: Package names matched (case-insensitively) in the full text.
_PACKAGE_TOKENS = [
    "SOIC", "SOP", "SSOP", "TSSOP", "MSOP", "QSOP", "TSOP",
    "QFN", "DFN", "VQFN", "WSON", "LGA", "BGA",
    "SOT-23", "SOT-223", "SOT-89", "SC-70", "SOT-353",
    "DIP", "PDIP", "CDIP", "SDIP", "CERDIP",
    "TO-220", "TO-247", "TO-263", "TO-252", "TO-92",
    "LCCC", "QFP", "LQFP", "TQFP", "PQFP", "PLCC",
    "SMA", "SMB", "SMC", "DO-214", "DO-35", "DO-41", "SOD-123",
]

#: Header-label aliases for pin tables (keys are already normalised).
PIN_ALIASES = {
    "pin_number": {"pin", "pin no", "pin number", "pin #", "terminal", "lead",
                   "lead no"},
    "name": {"name", "pin name", "signal", "symbol", "mnemonic"},
    "type": {"type", "i o", "io", "dir", "direction"},
    "description": {"description", "function", "desc"},
}

#: Header-label aliases for parameter/electrical tables.
PARAM_ALIASES = {
    "symbol": {"symbol"},
    "name": {"parameter", "characteristic", "rating", "definition"},
    "test_conditions": {"test condition", "test conditions", "conditions",
                        "condition"},
    "min": {"min", "minimum"},
    "typ": {"typ", "typical"},
    "max": {"max", "maximum"},
    "unit": {"unit", "units"},
    "value": {"value"},
}

#: Words that (when they lead a parameter cell) mean the symbol was dropped by
#: the table extractor and the whole cell should be treated as the name.
_NAME_ONLY = {
    "temperature",
    "common-mode",
    "large-signal",
    "maximum",
    "supply",
    "total",
    "unity-gain",
    "input",
    "output",
    "crosstalk",
}

#: Section captions -> category used for extracted parameters.
_SECTION_KEYWORDS = [
    ("absolute maximum", "Maximum Ratings"),
    ("maximum ratings", "Maximum Ratings"),
    ("recommended operating", "Recommended Operating Conditions"),
    ("electrical characteristics", "Electrical"),
    ("dynamic electrical", "Electrical (Dynamic)"),
    ("static electrical", "Electrical (Static)"),
    ("dc characteristics", "DC Characteristics"),
    ("ac characteristics", "AC Characteristics"),
    ("switching characteristics", "Switching Characteristics"),
    ("performance characteristics", "Performance Characteristics"),
]


def _clean(value: str) -> str:
    """Collapse whitespace/newlines in an extracted cell."""
    return re.sub(r"\s+", " ", (value or "").strip())


def _norm(value: str) -> str:
    """Lowercase and keep only alphanumeric runs (single spaces between)."""
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _header_key(cell: str) -> str:
    """Normalise a header cell, dropping footnote markers like ``TYPE(1)``."""
    return _norm(re.sub(r"\([^)]*\)", " ", cell or ""))


def _digit(value: str) -> str:
    """Return ``value`` if it contains a digit, else an empty string."""
    value = (value or "").strip()
    return value if any(ch.isdigit() for ch in value) else ""


def _split_symbol(text: str) -> tuple[str, str]:
    """Split a parameter cell into (symbol, name)."""
    text = re.sub(r"\s+", " ", text).strip()
    match = re.match(r"^(\S+)\s*(?:\(\d+\))?\s*(.*)$", text)
    if not match:
        return "", text

    symbol, name = match.group(1), match.group(2)
    if symbol.lower() in _NAME_ONLY:
        return "", text
    return symbol, name


# --------------------------------------------------------------- manufacturer

def _detect_manufacturer(text: str) -> str:
    lowered = text.lower()
    for name in MANUFACTURERS:
        if name.lower() in lowered:
            return name

    # Fallback: "© 2024 Some Company" style copyright lines.
    match = re.search(r"©\s*\d{4}[,\s]*([A-Z][A-Za-z0-9&.\- ]{2,40})", text)
    if match:
        return match.group(1).strip()

    # Fallback: a vendor domain such as www.infineon.com.
    match = re.search(r"www\.([a-z0-9\-]+)\.(?:com|de|net|org)", lowered)
    if match:
        return match.group(1).capitalize()

    return ""


# ------------------------------------------------------------------ package

def _extract_package(text: str, result: dict[str, Any]) -> None:
    package = ""

    lowered = text.lower()

    def _is_token(word: str) -> bool:
        return word.upper() in {t.upper() for t in _PACKAGE_TOKENS}

    # "<N> Lead <PKG>" / "<N> pin <PKG>" (e.g. "16-Lead SOIC", "8-pin SOIC").
    match = re.search(
        r"(\d{1,3})\s*[-\s]?(?:lead|pin)\s+([A-Za-z][A-Za-z0-9\-]*)",
        text,
        re.IGNORECASE,
    )
    if match and _is_token(match.group(2)):
        package = f"{match.group(2).upper()}-{match.group(1)}"

    # "<CODE> (<PKG>, <N>)" (TI's "D (SOIC, 8)" style).
    if not package:
        match = re.search(r"\(([A-Za-z][A-Za-z0-9\-]+)\s*,\s*(\d{1,3})\)", text)
        if match and _is_token(match.group(1)):
            package = f"{match.group(1).upper()}-{match.group(2)}"

    # "<PKG>-<N>" / "<PKG>−<N>" (e.g. "SOIC−14", "TSSOP-14").
    if not package:
        match = re.search(r"([A-Za-z][A-Za-z0-9\-]+)\s*[−-]\s*(\d{1,3})", text)
        if match and _is_token(match.group(1)):
            package = f"{match.group(1).upper()}-{match.group(2)}"

    # Bare known package token.
    if not package:
        for token in _PACKAGE_TOKENS:
            if token.lower() in lowered:
                package = token.upper()
                break

    if package:
        result["package"] = package

    size = re.search(r"([\d.]+\s*mm\s*[×xX]\s*[\d.]+\s*mm)", text)
    if size:
        result["package_size"] = _clean(size.group(1))


# ------------------------------------------------------------- header parsing

def _build_lookup(aliases: dict[str, set[str]]) -> dict[str, str]:
    return {word: field for field, words in aliases.items() for word in words}


def _fields_in_cell(cell: str, lookup: dict[str, str]) -> list[str]:
    """Return ordered field names found in a header cell.

    Multi-word cells such as ``Symbol Definition`` or ``Typ. Max.`` expand to
    consecutive columns (caller adds the column offset).
    """
    key = _header_key(cell)
    if not key:
        return []
    words = key.split()
    fields: list[str] = []
    i = 0
    while i < len(words):
        matched = None
        for n in (4, 3, 2, 1):
            if i + n > len(words):
                continue
            phrase = " ".join(words[i:i + n])
            field = lookup.get(phrase)
            if field:
                matched = (field, n)
                break
        if matched:
            fields.append(matched[0])
            i += matched[1]
        else:
            i += 1
    return fields


def _scan_headers(header_rows: list[list[str]], aliases: dict[str, set[str]]) -> dict[str, list[int]]:
    """Map field -> list of column indices found across the header rows."""
    lookup = _build_lookup(aliases)
    colmap: dict[str, list[int]] = {}
    for row in header_rows:
        for col, cell in enumerate(row):
            for offset, field in enumerate(_fields_in_cell(cell, lookup)):
                colmap.setdefault(field, []).append(col + offset)
    return colmap


def _header_rows(rows: list[list[str]]) -> list[list[str]]:
    """Collect the leading header rows (max 2) that contain header labels.

    Rows are considered headers while at least one cell matches a known
    pin/parameter header alias; collection stops at the first data row.
    Single-cell merged title rows are skipped.
    """
    pin_lookup = _build_lookup(PIN_ALIASES)
    param_lookup = _build_lookup(PARAM_ALIASES)
    headers: list[list[str]] = []
    for row in rows[:4]:
        nonempty = [(c or "").strip() for c in row if (c or "").strip()]
        if len(nonempty) < 2:
            continue
        has_label = any(
            _fields_in_cell(cell, pin_lookup) or _fields_in_cell(cell, param_lookup)
            for cell in row
        )
        if not has_label:
            break
        headers.append(row)
        if len(headers) >= 2:
            break
    return headers


# ------------------------------------------------------------------ sections

def _section_title(page: Any, table: Any) -> str:
    try:
        top = float(table.bbox[1])
    except Exception:  # noqa: BLE001
        top = None

    try:
        words = page.extract_words()
    except Exception:  # noqa: BLE001
        words = []

    lines: dict[int, list[tuple[float, str]]] = {}
    for w in words:
        y = round(w.get("top", 0))
        lines.setdefault(y, []).append((w.get("x0", 0.0), w.get("text", "")))

    ordered = [
        (y, " ".join(t for _, t in sorted(ws)).lower())
        for y, ws in sorted(lines.items())
    ]
    above = [(y, line) for y, line in ordered if top is None or y < top - 2]
    for _, line in reversed(above):
        for key, category in _SECTION_KEYWORDS:
            if key in line:
                return category
    return "Electrical"


# ---------------------------------------------------------------------- pins

def _part_tokens(part_name: str | None, part_ipn: str | None) -> list[str]:
    tokens: list[str] = []
    for value in (part_name, part_ipn):
        if value:
            token = re.sub(r"[^a-z0-9]+", "", str(value).lower())
            if len(token) >= 3:
                tokens.append(token)
    return tokens


def _matches_part(cell: str, tokens: list[str]) -> bool:
    header = re.sub(r"[^a-z0-9]+", "", (cell or "").lower())
    if len(header) < 3 or not re.search(r"\d", header):
        return False
    for token in tokens:
        if header == token or header.startswith(token) or token.startswith(header):
            return True
    return False


def _is_numeric_column(rows: list[list[str]], col: int) -> bool:
    digits = 0
    others = 0
    for row in rows:
        if col >= len(row):
            continue
        cell = (row[col] or "").strip()
        if not cell or cell in {"—", "–", "-", "−", "–"}:
            continue
        if re.fullmatch(r"\d{1,3}", cell):
            digits += 1
        else:
            others += 1
    return digits >= 2 and others == 0


def _choose_pin_number_col(
    rows: list[list[str]],
    header_rows: list[list[str]],
    colmap: dict[str, list[int]],
    part_tokens: list[str],
) -> int | None:
    if colmap.get("pin_number"):
        return colmap["pin_number"][0]

    # Match the user's part against package-name header cells (TI multi-package).
    for row in header_rows:
        for col, cell in enumerate(row):
            if _matches_part(cell, part_tokens):
                return col

    # Fallback: leftmost purely-numeric column not used for name/type/desc.
    exclude: set[int] = set()
    for field in ("name", "type", "description"):
        exclude.update(colmap.get(field, []))
    width = max((len(r) for r in rows), default=0)
    for col in range(width):
        if col in exclude:
            continue
        if _is_numeric_column(rows, col):
            return col
    return None


def _extract_pins(
    rows: list[list[str]],
    header_rows: list[list[str]],
    colmap: dict[str, list[int]],
    part_tokens: list[str],
    header_ids: set[int],
    result: dict[str, Any],
    seen: set[tuple[str, str]],
) -> None:
    name_col = colmap["name"][0] if colmap.get("name") else None
    type_col = colmap["type"][0] if colmap.get("type") else None
    desc_col = colmap["description"][0] if colmap.get("description") else None
    pin_col = _choose_pin_number_col(rows, header_rows, colmap, part_tokens)

    for row in rows:
        if id(row) in header_ids:
            continue
        cells = [(c or "").strip() for c in row]
        name = cells[name_col] if name_col is not None and name_col < len(cells) else ""
        if not name or name.upper() in {"PIN", "NAME", "SYMBOL", "SIGNAL"}:
            continue
        if len(name) > 60:
            continue

        pin_number = ""
        if pin_col is not None:
            # Package-specific column chosen: keep only rows present in it.
            if pin_col >= len(cells):
                continue
            pin_number = _digit(cells[pin_col])
            if not pin_number or len(pin_number) > 6:
                continue

        description = cells[desc_col] if desc_col is not None and desc_col < len(cells) else ""
        pin_type = cells[type_col] if type_col is not None and type_col < len(cells) else ""

        key = (name, description)
        if key in seen:
            continue
        seen.add(key)
        result["pins"].append(
            {
                "pin_number": pin_number,
                "name": _clean(name),
                "type": _clean(pin_type),
                "description": _clean(description),
            }
        )


# ---------------------------------------------------------------- parameters

def _condition_columns(
    colmap: dict[str, list[int]],
    ncols: int,
    rows: list[list[str]],
) -> list[int]:
    """Columns holding test conditions: the labelled one plus any adjacent
    text-like columns before the numeric stats."""
    cols: set[int] = set(colmap.get("test_conditions", []))

    name_col = colmap["name"][0] if colmap.get("name") else None
    symbol_col = colmap["symbol"][0] if colmap.get("symbol") else None
    text_col = max([c for c in (name_col, symbol_col) if c is not None], default=-1)

    stat_cols = [
        c
        for field in ("min", "typ", "max", "unit", "value")
        for c in colmap.get(field, [])
    ]
    stat_start = min(stat_cols) if stat_cols else ncols

    mapped = {c for idxs in colmap.values() for c in idxs}
    for col in range(text_col + 1, stat_start):
        if col in mapped:
            continue
        if col in cols:
            continue
        # Only include text-like columns (skip figure-reference columns).
        textish = 0
        total = 0
        for row in rows:
            if col >= len(row):
                continue
            cell = (row[col] or "").strip()
            if not cell:
                continue
            total += 1
            if any(ch.isalpha() for ch in cell):
                textish += 1
        if total and textish / total >= 0.5:
            cols.add(col)

    return sorted(cols)


def _extract_parameters(
    rows: list[list[str]],
    colmap: dict[str, list[int]],
    category: str,
    header_ids: set[int],
    result: dict[str, Any],
    seen: set[tuple[str, str]],
) -> None:
    name_col = colmap["name"][0] if colmap.get("name") else None
    symbol_col = colmap["symbol"][0] if colmap.get("symbol") else None
    unit_col = colmap["unit"][0] if colmap.get("unit") else None
    value_col = colmap["value"][0] if colmap.get("value") else None
    min_col = colmap["min"][0] if colmap.get("min") else None
    typ_col = colmap["typ"][0] if colmap.get("typ") else None
    max_col = colmap["max"][0] if colmap.get("max") else None

    has_stats = min_col is not None or typ_col is not None or max_col is not None
    ncols = max((len(r) for r in rows), default=0)
    cond_cols = _condition_columns(colmap, ncols, rows)

    for row in rows:
        if id(row) in header_ids:
            continue
        cells = [(c or "").strip() for c in row]

        raw_name = cells[name_col] if name_col is not None and name_col < len(cells) else ""
        raw_symbol = cells[symbol_col] if symbol_col is not None and symbol_col < len(cells) else ""

        if symbol_col is None:
            symbol, name = _split_symbol(raw_name)
        else:
            symbol, name = _clean(raw_symbol), _clean(raw_name)

        if not name and not symbol:
            continue

        conditions = " ".join(
            _clean(cells[c]) for c in cond_cols if c < len(cells) and (cells[c] or "").strip()
        )

        if has_stats:
            mn = cells[min_col] if min_col is not None and min_col < len(cells) else ""
            ty = cells[typ_col] if typ_col is not None and typ_col < len(cells) else ""
            mx = cells[max_col] if max_col is not None and max_col < len(cells) else ""
        elif value_col is not None and value_col < len(cells):
            mn = ty = ""
            mx = cells[value_col]
            if "maximum" not in category.lower():
                ty, mx = mx, ""
        else:
            mn = ty = mx = ""

        unit = cells[unit_col] if unit_col is not None and unit_col < len(cells) else ""

        key = (name or symbol, conditions)
        if key in seen:
            continue
        seen.add(key)
        result["parameters"].append(
            {
                "category": category,
                "symbol": _clean(symbol),
                "name": _clean(name),
                "test_conditions": conditions,
                "min": _clean(mn),
                "typ": _clean(ty),
                "max": _clean(mx),
                "unit": _clean(unit),
            }
        )


# --------------------------------------------------------------------- entry

def extract(
    pdf_path: Path | str,
    part_name: str | None = None,
    part_ipn: str | None = None,
) -> dict[str, Any]:
    """Extract datasheet data from ``pdf_path`` into a dictionary.

    ``part_name`` / ``part_ipn`` (optional) help pick the right pin-number
    column in multi-package pin tables (e.g. TI's "Pin Functions" table).
    """
    import pdfplumber

    result: dict[str, Any] = {
        "manufacturer": "",
        "package": "",
        "package_size": "",
        "pins": [],
        "parameters": [],
    }

    part_tokens = _part_tokens(part_name, part_ipn)
    seen_pins: set[tuple[str, str]] = set()
    seen_params: set[tuple[str, str]] = set()

    with pdfplumber.open(str(pdf_path)) as pdf:
        full_text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        result["manufacturer"] = _detect_manufacturer(full_text)
        _extract_package(full_text, result)

        for page in pdf.pages:
            try:
                tables = page.find_tables()
            except Exception:  # noqa: BLE001
                continue

            for table in tables:
                try:
                    rows = [[c or "" for c in row] for row in table.extract()]
                except Exception:  # noqa: BLE001
                    continue
                if not rows:
                    continue

                header_rows = _header_rows(rows)
                header_ids = {id(row) for row in header_rows}
                param_cm = _scan_headers(header_rows, PARAM_ALIASES)
                pin_cm = _scan_headers(header_rows, PIN_ALIASES)

                has_stat = any(f in param_cm for f in ("min", "max"))
                has_value_unit = "value" in param_cm and "unit" in param_cm
                has_full = (
                    "unit" in param_cm
                    and "typ" in param_cm
                    and any(f in param_cm for f in ("name", "symbol"))
                )
                is_param = has_stat or has_value_unit or has_full
                is_pin = bool(pin_cm.get("name")) and bool(
                    pin_cm.get("description") or pin_cm.get("pin_number")
                )

                if is_param:
                    _extract_parameters(
                        rows, param_cm, _section_title(page, table), header_ids,
                        result, seen_params,
                    )
                elif is_pin:
                    _extract_pins(
                        rows, header_rows, pin_cm, part_tokens, header_ids,
                        result, seen_pins,
                    )

    return result
