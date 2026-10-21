"""Use case: extract component data from a datasheet (with OCR fallback)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_datasheet(
    extractor,
    ocr_extractor,
    pdf_path: Path | str,
    part_name: str | None = None,
    part_ipn: str | None = None,
) -> dict[str, Any]:
    """Extract with the primary extractor, falling back to OCR when empty.

    Returns a dict with ``manufacturer``, ``package``, ``package_size``,
    ``pins`` and ``parameters`` keys.
    """
    data = extractor.extract(
        pdf_path, part_name=part_name, part_ipn=part_ipn
    )
    needs_ocr = (
        not data.get("pins")
        or not data.get("parameters")
        or all(
            not (p.get("pin_number") or "").strip()
            for p in data.get("pins", [])
        )
    )
    if needs_ocr:
        ocr_data = ocr_extractor.extract(
            pdf_path, part_name=part_name, part_ipn=part_ipn
        )
        data = _merge(data, ocr_data)
    return data


def _merge(data: dict[str, Any], ocr_data: dict[str, Any]) -> dict[str, Any]:
    """Merge OCR results into the primary extraction without duplicates."""
    for field in ("manufacturer", "package", "package_size"):
        if not data.get(field) and ocr_data.get(field):
            data[field] = ocr_data[field]

    seen_pins = {
        (p.get("pin_number") or "", p.get("name") or "")
        for p in data.get("pins", [])
    }
    for p in ocr_data.get("pins", []):
        key = (p.get("pin_number") or "", p.get("name") or "")
        if key not in seen_pins:
            seen_pins.add(key)
            data["pins"].append(p)

    seen_params = {
        (p.get("name"), p.get("test_conditions"))
        for p in data.get("parameters", [])
    }
    for p in ocr_data.get("parameters", []):
        key = (p.get("name"), p.get("test_conditions"))
        if key not in seen_params:
            seen_params.add(key)
            data["parameters"].append(p)
    return data
