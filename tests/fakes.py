"""In-memory fakes (test doubles) implementing the application ports."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FakePartRepository:
    """In-memory implementation of the PartRepository port."""

    def __init__(self) -> None:
        self.parts: dict[int, dict[str, Any]] = {}
        self._next = 1

    def list_parts(self, search: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for pk, data in self.parts.items():
            item = dict(data, pk=pk)
            item.setdefault("in_stock", 0)
            item.setdefault("locations", [])
            rows.append(item)
        if search:
            term = search.lower()
            rows = [
                r for r in rows
                if term in (r.get("name") or "").lower()
                or term in (r.get("ipn") or "").lower()
            ]
        return sorted(rows, key=lambda r: r.get("name") or "")

    def get_part(self, pk: int) -> dict[str, Any] | None:
        if pk not in self.parts:
            return None
        item = dict(self.parts[pk], pk=pk)
        item.setdefault("in_stock", 0)
        return item

    def create_part(self, data: dict[str, Any]) -> dict[str, Any]:
        pk = self._next
        self._next += 1
        self.parts[pk] = dict(data)
        return {"pk": pk}

    def update_part(self, pk: int, data: dict[str, Any]) -> dict[str, Any]:
        self.parts[pk] = dict(data)
        return {"pk": pk}

    def delete_part(self, pk: int) -> None:
        self.parts.pop(pk, None)

    def import_parts(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        existing = {(r.get("name") or "").strip().lower() for r in self.parts.values()}
        created = skipped = duplicates = 0
        for data in rows:
            name = (data.get("name") or "").strip()
            if not name:
                skipped += 1
                continue
            if name.lower() in existing:
                duplicates += 1
                continue
            existing.add(name.lower())
            self.create_part(data)
            created += 1
        return {"created": created, "skipped": skipped, "duplicates": duplicates}


class FakePartsImporter:
    """In-memory implementation of the PartsImporter port."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.template_written_to: Path | None = None

    def read_parts(self, path: Path) -> list[dict[str, Any]]:
        return [dict(r) for r in self.rows]

    def write_template(self, path: Path) -> None:
        self.template_written_to = path


class FakeDatasheetExtractor:
    """In-memory implementation of the DatasheetExtractor port."""

    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.result = result or {
            "manufacturer": "",
            "package": "",
            "package_size": "",
            "pins": [],
            "parameters": [],
        }
        self.calls: list[tuple] = []

    def extract(
        self,
        pdf_path: Path | str,
        part_name: str | None = None,
        part_ipn: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((pdf_path, part_name, part_ipn))
        return self.result
