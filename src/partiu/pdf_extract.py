"""Extract component data from a PDF datasheet.

Heuristic extraction tuned for the Texas Instruments datasheet format (the
TL06xx example): manufacturer, package + size, the "Pin Functions" table and
the "Electrical Characteristics" table.  Extracted values are meant as a
starting point and remain editable in the GUI.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

#: Known manufacturers, detected by a case-insensitive substring match.
MANUFACTURERS = [
    "Texas Instruments",
    "STMicroelectronics",
    "Analog Devices",
    "ON Semiconductor",
    "Infineon",
    "NXP Semiconductors",
    "Microchip",
    "Vishay",
]

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


def _clean(value: str) -> str:
    """Collapse whitespace/newlines in an extracted cell."""
    return re.sub(r"\s+", " ", (value or "").strip())


def _digit(value: str) -> str:
    """Return ``value`` if it contains a digit, else an empty string."""
    return value if value and any(ch.isdigit() for ch in value) else ""


def _detect_manufacturer(text: str) -> str:
    lowered = text.lower()
    for name in MANUFACTURERS:
        if name.lower() in lowered:
            return name
    return ""


def _extract_package(text: str, result: dict[str, Any]) -> None:
    match = re.search(
        r"([A-Z]{1,4})\s+\(([^)]+)\)\s+([\d.]+\s*mm\s*[×xX]\s*[\d.]+\s*mm)",
        text,
    )
    if match:
        result["package"] = f"{match.group(1)} ({match.group(2)})"
        result["package_size"] = match.group(3).strip()


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


def _extract_pins(page: Any, result: dict[str, Any]) -> None:
    for table in page.extract_tables():
        for row in table:
            cells = [(c or "").strip() for c in row]
            if len(cells) < 8:
                continue
            name = cells[0]
            if not name or name in {"PIN", "NAME"}:
                continue

            # Pin number from the TL062 8-pin column (the example part).  Rows
            # without a pin number there belong to other packages / variants,
            # so they are skipped for a clean, package-specific pinout.
            pin_number = _digit(cells[2])
            if not pin_number:
                continue

            result["pins"].append(
                {
                    "pin_number": pin_number,
                    "name": _clean(cells[0]),
                    "type": _clean(cells[6]),
                    "description": _clean(cells[7]),
                }
            )


def _extract_parameters(page: Any, result: dict[str, Any]) -> None:
    for table in page.extract_tables():
        for row in table:
            cells = [(c or "").strip() for c in row]
            if len(cells) < 10:
                continue
            parameter = cells[0]
            if not parameter or parameter == "PARAMETER":
                continue

            symbol, name = _split_symbol(parameter)
            conditions = _clean(f"{cells[1]} {cells[2]}")

            result["parameters"].append(
                {
                    "category": "Electrical",
                    "symbol": _clean(symbol),
                    "name": _clean(name),
                    "test_conditions": conditions,
                    "min": _clean(cells[3]),
                    "typ": _clean(cells[4]),
                    "max": _clean(cells[5]),
                    "unit": _clean(cells[9]),
                }
            )


def extract(pdf_path: Path | str) -> dict[str, Any]:
    """Extract datasheet data from ``pdf_path`` into a dictionary."""
    import pdfplumber

    result: dict[str, Any] = {
        "manufacturer": "",
        "package": "",
        "package_size": "",
        "pins": [],
        "parameters": [],
    }

    with pdfplumber.open(str(pdf_path)) as pdf:
        full_text = "\n".join((page.extract_text() or "") for page in pdf.pages)

        result["manufacturer"] = _detect_manufacturer(full_text)
        _extract_package(full_text, result)

        saw_parameters = False
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Pin Functions" in text and "Table" in text:
                _extract_pins(page, result)
            if (
                not saw_parameters
                and "Electrical Characteristics" in text
                and "TEST CONDITIONS" in text
            ):
                _extract_parameters(page, result)
                saw_parameters = True

    return result
