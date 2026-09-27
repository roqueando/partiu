"""Geometric pinout parser.

Pinout diagrams (DIP/SOIC/QFP style) place a pin *number* next to a short pin
*name* on each row, with no extractable table.  This module pairs the two from
word boxes: numbers and names are grouped into rows by their vertical centre,
adjacent words are glued into phrases, and each name is paired with the nearest
pin number on the same row.

``words`` is an iterable of ``(text, x0, x1, y0, y1)`` tuples — the same shape
produced by ``pdfplumber``'s ``extract_words()`` and by :mod:`partiu.ocr_extract`.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

#: Words that appear in package/caption text near pinouts but are not pin names.
_NON_PIN_NAMES = {
    "lead", "soic", "pdip", "dip", "body", "wide", "package", "part",
    "number", "pin", "no", "assignments", "suffix", "case", "connections",
    "international", "rectifier", "connection",
}

#: Page-text markers that indicate a pinout diagram rather than a graph/table.
PINOUT_KEYWORDS = (
    "pin connection", "pin configuration", "pin assignment", "pin function",
    "pin description", "lead assignment", "terminal assignment",
    "pin diagram", "pinout", "pin number", "pin numbers",
)


def looks_like_pinout(text: str) -> bool:
    """Return True if ``text`` mentions a pinout/lead-assignment section."""
    lowered = (text or "").lower()
    return any(kw in lowered for kw in PINOUT_KEYWORDS)


def _clean(text: str) -> str:
    return (text or "").strip()


def _pin_number(text: str) -> str | None:
    t = re.sub(r"[()\[\]]", "", text).strip()
    return t if re.fullmatch(r"\d{1,3}", t) else None


def _is_name(text: str) -> bool:
    lowered = _clean(text).lower()
    if not lowered or not re.search(r"[a-z]", lowered):
        return False
    return not any(word in _NON_PIN_NAMES for word in lowered.split())


def _rows(words: list[tuple[str, float, float, float, float]], tol: float):
    ordered = sorted(words, key=lambda w: (w[3] + w[4]) / 2)
    rows: list[list[tuple[str, float, float, float, float]]] = []
    current: list[tuple[str, float, float, float, float]] = []
    prev: float | None = None
    for w in ordered:
        yc = (w[3] + w[4]) / 2
        if prev is None or (yc - prev) <= tol:
            current.append(w)
        else:
            rows.append(current)
            current = [w]
        prev = yc
    if current:
        rows.append(current)
    return rows


def _phrases(row, gap: float) -> list[tuple[str, float, float]]:
    """Merge horizontally adjacent words and return (text, xc, yc) phrases."""
    row = sorted(row, key=lambda w: w[1])
    phrases: list[tuple[str, float, float]] = []
    texts: list[str] = []
    x0 = x1 = y0 = y1 = 0.0
    for text, wx0, wx1, wy0, wy1 in row:
        if texts and (wx0 - x1) <= gap:
            texts.append(text)
            x1 = wx1
            y0 = min(y0, wy0)
            y1 = max(y1, wy1)
        else:
            if texts:
                phrases.append((" ".join(texts), (x0 + x1) / 2, (y0 + y1) / 2))
            texts = [text]
            x0, x1, y0, y1 = wx0, wx1, wy0, wy1
    if texts:
        phrases.append((" ".join(texts), (x0 + x1) / 2, (y0 + y1) / 2))
    return phrases


def parse_pinout(words: Iterable[Any]) -> list[dict[str, str]]:
    """Return ``[{pin_number, name}]`` pairs recognised in ``words``."""
    w: list[tuple[str, float, float, float, float]] = []
    for item in words:
        text, x0, x1, y0, y1 = item
        text = _clean(text)
        if not text or "cid" in text.lower():
            continue
        w.append((text, float(x0), float(x1), float(y0), float(y1)))
    if not w:
        return []

    heights = sorted(y1 - y0 for _, _, _, y0, y1 in w)
    med_h = heights[len(heights) // 2] or 1.0
    row_tol = med_h * 0.6
    merge_gap = med_h * 0.4
    max_dist = med_h * 5.0

    pins: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in _rows(w, row_tol):
        phrases = _phrases(row, merge_gap)
        numbers = [(n, xc, yc) for text, xc, yc in phrases if (n := _pin_number(text))]
        names = [(text, xc, yc) for text, xc, yc in phrases if _is_name(text)]
        for name, nxc, _nyc in names:
            best: str | None = None
            best_d: float | None = None
            for number, xc, _yc in numbers:
                d = abs(nxc - xc)
                if best_d is None or d < best_d:
                    best_d = d
                    best = number
            if best is not None and best_d is not None and best_d <= max_dist:
                key = (best, name)
                if key not in seen:
                    seen.add(key)
                    pins.append(
                        {"pin_number": best, "name": name, "type": "", "description": ""}
                    )

    if len({p["pin_number"] for p in pins}) < 4:
        return []
    return pins
