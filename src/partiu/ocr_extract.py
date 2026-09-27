"""OCR fallback for datasheets that pdfplumber cannot read.

Some datasheets are scanned (no text layer) or keep pin numbers only inside a
graphical pinout.  This module renders pages with ``pypdfium2``, runs a small
offline OCR model (``rapidocr`` + ``onnxruntime``), reconstructs table rows from
the recognised word boxes, and then reuses the exact same header-driven
extractors in :mod:`partiu.pdf_extract` so the output schema is identical.

The OCR pass only runs on pages with no extractable text; the fast heuristic in
``pdf_extract`` remains the primary path.
"""

from __future__ import annotations

import bisect
import re
from pathlib import Path
from typing import Any

from . import pdf_extract as _pe
from . import pinout

#: Normalised header words that mark the start of a logical column.
_ANCHOR_WORDS = {
    "parameter", "characteristic", "symbol", "rating", "definition", "name",
    "pin", "signal", "mnemonic", "test", "unit", "units", "value",
    "description", "function", "desc", "type", "terminal", "lead", "no",
    "dir", "direction",
}

#: Sub-column words (min/typ/max) that may live on their own header row.
_STAT_WORDS = {"min", "typ", "max"}

#: Rendering scale (200 dpi) used when rasterising pages for OCR.
_SCALE = 200 / 72

#: Running-headers that mark the packaging/appendix section — past these there
#: are no more pin/parameter tables worth OCR-ing.
_PACKAGING_MARKERS = (
    "package option addendum",
    "package materials",
    "packaging information",
    "package outline",
    "important notice",
)

_ocr_engine: Any = None


class _Word:
    __slots__ = ("text", "x0", "x1", "y0", "y1")

    def __init__(self, text: str, x0: float, x1: float, y0: float, y1: float):
        self.text = text
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _get_ocr() -> Any:
    global _ocr_engine
    if _ocr_engine is None:
        # Import from ``rapidocr.main`` directly (rather than the lazy
        # ``from rapidocr import RapidOCR``) so Nuitka statically follows the
        # import and bundles the OCR engine in packaged builds.
        from rapidocr.main import RapidOCR

        _ocr_engine = RapidOCR(params={"Global.log_level": "error"})
    return _ocr_engine


def _render_page(pdfium_doc: Any, index: int) -> Any:
    bitmap = pdfium_doc[index].render(scale=_SCALE)
    return bitmap.to_pil().convert("RGB")


def _ocr_words(ocr: Any, image: Any) -> list[_Word]:
    """Run OCR and return a flat list of recognised words with boxes."""
    import numpy as np

    out = ocr(np.array(image), return_word_box=True)
    words: list[_Word] = []
    for line in out.word_results or ():
        for text, _score, box in line:
            if box is None or not (text or "").strip():
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            words.append(_Word(text.strip(), min(xs), max(xs), min(ys), max(ys)))
    return words


def _group_lines(words: list[_Word]) -> list[list[_Word]]:
    """Cluster words into visual lines by vertical centre proximity."""
    if not words:
        return []
    heights = sorted(w.y1 - w.y0 for w in words)
    median_h = heights[len(heights) // 2] if heights else 20
    tol = max(median_h * 0.8, 10)

    words = sorted(words, key=lambda w: w.yc)
    lines: list[list[_Word]] = []
    current: list[_Word] = []
    prev_yc: float | None = None
    for w in words:
        if prev_yc is None or (w.yc - prev_yc) <= tol:
            current.append(w)
        else:
            lines.append(current)
            current = [w]
        prev_yc = w.yc
    if current:
        lines.append(current)

    for line in lines:
        line.sort(key=lambda w: w.x0)
    lines.sort(key=lambda l: min(w.y0 for w in l))
    return lines


def _header_anchors(lines: list[list[_Word]]) -> list[float]:
    """Locate column anchors (left edges) from the leading header lines."""
    strong_idx = None
    for i, line in enumerate(lines[:15]):
        if any(_norm(w.text) in _ANCHOR_WORDS for w in line):
            strong_idx = i
            break
    if strong_idx is None:
        return []

    anchors = [w.x0 for w in lines[strong_idx] if _norm(w.text) in _ANCHOR_WORDS]

    # A following "min typ max" row defines the numeric sub-columns.
    for line in lines[strong_idx + 1 : strong_idx + 3]:
        norms = [_norm(w.text) for w in line]
        if sum(1 for n in norms if n in _STAT_WORDS) >= 2:
            anchors.extend(w.x0 for w, n in zip(line, norms) if n in _STAT_WORDS)
            break

    anchors = sorted(set(anchors))
    merged: list[float] = []
    for x in anchors:
        if merged and x - merged[-1] < 20:
            continue
        merged.append(x)
    return merged


def _is_stat_row(cells: list[str]) -> bool:
    nonempty = [c.strip().lower() for c in cells if c.strip()]
    return bool(nonempty) and all(c in _STAT_WORDS for c in nonempty)


def _merge_wrapped(rows: list[list[str]]) -> list[list[str]]:
    """Fold wrapped continuation lines back into the previous row."""
    merged: list[list[str]] = []
    for row in rows:
        first = next((i for i, c in enumerate(row) if c.strip()), None)
        if merged and first is not None and first > 0 and not _is_stat_row(row):
            prev = merged[-1]
            for i, cell in enumerate(row):
                if cell.strip():
                    prev[i] = f"{prev[i]} {cell}".strip() if prev[i].strip() else cell
        else:
            merged.append(row)
    return merged


def _build_rows(lines: list[list[_Word]]) -> list[list[str]]:
    """Reconstruct ``list[list[str]]`` rows from OCR word boxes."""
    anchors = _header_anchors(lines)
    ncols = len(anchors)

    rows: list[list[str]] = []
    for line in lines:
        if not anchors:
            rows.append([" ".join(w.text for w in line)])
            continue
        cells = ["" for _ in range(ncols)]
        for w in line:
            col = bisect.bisect_right(anchors, w.xc) - 1
            if col < 0:
                col = 0
            cells[col] = f"{cells[col]} {w.text}".strip() if cells[col] else w.text
        rows.append(cells)
    return _merge_wrapped(rows)


def _category_from_text(text: str) -> str:
    lowered = text.lower()
    for key, category in _pe._SECTION_KEYWORDS:
        if key in lowered:
            return category
    return "Electrical"


def _trim_to_header(rows: list[list[str]]) -> list[list[str]]:
    """Drop leading document-header/title rows before the table header."""
    pin_lookup = _pe._build_lookup(_pe.PIN_ALIASES)
    param_lookup = _pe._build_lookup(_pe.PARAM_ALIASES)
    for i, row in enumerate(rows[:15]):
        for cell in row:
            if _pe._fields_in_cell(cell, pin_lookup) or _pe._fields_in_cell(cell, param_lookup):
                return rows[i:]
    return rows


def _extract_from_page(
    rows: list[list[str]],
    category: str,
    part_tokens: list[str],
    result: dict[str, Any],
    seen_pins: set[tuple[str, str]],
    seen_params: set[tuple[str, str]],
) -> None:
    rows = _trim_to_header(rows)
    header_rows = _pe._header_rows(rows)
    if not header_rows:
        return
    header_ids = {id(row) for row in header_rows}
    param_cm = _pe._scan_headers(header_rows, _pe.PARAM_ALIASES)
    pin_cm = _pe._scan_headers(header_rows, _pe.PIN_ALIASES)

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
        # Keep header rows plus data rows that carry a numeric value in a
        # stat column — this drops footnotes, notes and section titles that
        # the OCR reconstruction pulls in alongside the table.
        stat_cols = {c for f in ("min", "typ", "max", "unit", "value") for c in param_cm.get(f, [])}
        name_col = param_cm["name"][0] if param_cm.get("name") else None
        symbol_col = param_cm["symbol"][0] if param_cm.get("symbol") else None
        filtered: list[list[str]] = []
        for row in rows:
            if id(row) in header_ids:
                filtered.append(row)
                continue
            has_digit = any(
                c < len(row) and any(ch.isdigit() for ch in (row[c] or ""))
                for c in stat_cols
            )
            has_name = any(
                c is not None and c < len(row) and (row[c] or "").strip()
                for c in (name_col, symbol_col)
            )
            if has_digit and has_name:
                filtered.append(row)
        _pe._extract_parameters(filtered, param_cm, category, header_ids, result, seen_params)
        return True
    elif is_pin:
        _pe._extract_pins(rows, header_rows, pin_cm, part_tokens, header_ids, result, seen_pins)
        return True
    return False


def extract(
    pdf_path: Path | str,
    part_name: str | None = None,
    part_ipn: str | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """OCR-extract datasheet data from pages that have no text layer."""
    import pdfplumber
    import pypdfium2

    result: dict[str, Any] = {
        "manufacturer": "",
        "package": "",
        "package_size": "",
        "pins": [],
        "parameters": [],
    }

    part_tokens = _pe._part_tokens(part_name, part_ipn)
    seen_pins: set[tuple[str, str]] = set()
    seen_params: set[tuple[str, str]] = set()
    seen_pinout: set[tuple[str, str]] = set()

    with pdfplumber.open(str(pdf_path)) as pdf:
        pdfium_doc = pypdfium2.PdfDocument(str(pdf_path))
        ocr = None
        full_text_parts: list[str] = []
        processed = 0

        for idx, page in enumerate(pdf.pages):
            if max_pages is not None and processed >= max_pages:
                break

            text = page.extract_text() or ""
            lowered = text.lower()
            # Stop at the packaging/appendix section.
            if any(m in lowered for m in _PACKAGING_MARKERS):
                break
            full_text_parts.append(text)
            # OCR pages with little/no text layer (scanned pages typically only
            # carry a running header/footer, ~150-500 chars).
            if len(text.strip()) >= 600:
                continue

            if ocr is None:
                ocr = _get_ocr()
            try:
                image = _render_page(pdfium_doc, idx)
                words = _ocr_words(ocr, image)
            except Exception:  # noqa: BLE001 - render/OCR failure on one page
                continue
            processed += 1

            if not words:
                continue

            # Drop the running footer/page-number band at the bottom of the page.
            words = [w for w in words if w.y1 < image.height * 0.92]

            page_text = " ".join(w.text for w in words)
            full_text_parts.append(page_text)
            rows = _build_rows(_group_lines(words))
            found = _extract_from_page(
                rows,
                _category_from_text(page_text),
                part_tokens,
                result,
                seen_pins,
                seen_params,
            )
            # A page with no table may still be a pinout diagram.
            if not found and pinout.looks_like_pinout(page_text):
                for pin in pinout.parse_pinout(
                    (w.text, w.x0, w.x1, w.y0, w.y1) for w in words
                ):
                    key = (pin["pin_number"], pin["name"])
                    if key not in seen_pinout:
                        seen_pinout.add(key)
                        result["pins"].append(pin)

    full_text = "\n".join(full_text_parts)
    result["manufacturer"] = _pe._detect_manufacturer(full_text)
    _pe._extract_package(full_text, result)
    return result
