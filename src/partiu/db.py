"""SQLite data layer for Partiu.

A single local SQLite database stores parts, stock locations, stock items,
part pins, electrical parameters and file attachments (photo / datasheet).
"""

from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS part (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ipn TEXT,
    category TEXT,
    description TEXT,
    units TEXT,
    manufacturer TEXT,
    package TEXT,
    package_size TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stock_location (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES stock_location(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS stock_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL REFERENCES part(id) ON DELETE CASCADE,
    quantity REAL NOT NULL DEFAULT 0,
    location_id INTEGER REFERENCES stock_location(id) ON DELETE SET NULL,
    serial TEXT,
    batch TEXT,
    status TEXT NOT NULL DEFAULT 'OK',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS part_pin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL REFERENCES part(id) ON DELETE CASCADE,
    pin_number TEXT,
    name TEXT,
    type TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS part_parameter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL REFERENCES part(id) ON DELETE CASCADE,
    category TEXT NOT NULL DEFAULT 'Electrical',
    symbol TEXT,
    name TEXT,
    test_conditions TEXT,
    min TEXT,
    typ TEXT,
    max TEXT,
    unit TEXT
);

CREATE TABLE IF NOT EXISTS part_attachment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL REFERENCES part(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL
);
"""

#: Simple status vocabulary used by the stock form and list.
STATUSES = [
    "OK",
    "Attention needed",
    "Damaged",
    "Destroyed",
    "Rejected",
    "Lost",
    "Quarantined",
    "Returned",
]


def _fmt_qty(value: Any) -> int | float:
    """Return a quantity as int when it is a whole number."""
    value = value or 0
    number = float(value)
    return int(number) if number.is_integer() else number


class Database:
    """Thin CRUD wrapper around a SQLite database file."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.attachments_dir = self.path.parent / "attachments"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        """Add columns that may be missing from older databases."""
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(part)")}
        for column, ddl in [
            ("manufacturer", "TEXT"),
            ("package", "TEXT"),
            ("package_size", "TEXT"),
        ]:
            if column not in existing:
                self.conn.execute(f"ALTER TABLE part ADD COLUMN {column} {ddl}")

    # ------------------------------------------------------------------ parts

    def list_parts(self, search: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT p.id AS pk, p.name, p.ipn AS IPN, p.category, p.description,
                   p.units, p.manufacturer, p.package, p.package_size, p.active,
                   COALESCE((SELECT SUM(s.quantity) FROM stock_item s
                             WHERE s.part_id = p.id), 0) AS in_stock
            FROM part p
        """
        params: list[Any] = []
        if search:
            like = f"%{search}%"
            query += (
                " WHERE p.name LIKE ? OR p.ipn LIKE ? OR p.description LIKE ?"
                " OR p.category LIKE ? OR p.manufacturer LIKE ?"
            )
            params = [like, like, like, like, like]
        query += " ORDER BY p.name"

        rows = self.conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["active"] = bool(item["active"])
            item["in_stock"] = _fmt_qty(item["in_stock"])
            result.append(item)
        return result

    def get_part(self, pk: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT p.id AS pk, p.name, p.ipn AS IPN, p.category, p.description,
                   p.units, p.manufacturer, p.package, p.package_size, p.active,
                   COALESCE((SELECT SUM(s.quantity) FROM stock_item s
                             WHERE s.part_id = p.id), 0) AS in_stock
            FROM part p WHERE p.id = ?
            """,
            (pk,),
        ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["active"] = bool(item["active"])
        item["in_stock"] = _fmt_qty(item["in_stock"])
        return item

    def create_part(self, data: dict[str, Any]) -> dict[str, Any]:
        cursor = self.conn.execute(
            "INSERT INTO part (name, ipn, category, description, units,"
            " manufacturer, package, package_size, active)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data.get("name"),
                data.get("IPN"),
                data.get("category"),
                data.get("description"),
                data.get("units"),
                data.get("manufacturer"),
                data.get("package"),
                data.get("package_size"),
                1 if data.get("active") else 0,
            ),
        )
        self.conn.commit()
        return {"pk": cursor.lastrowid}

    def import_parts(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        """Bulk-insert parts in one transaction, deduplicating by name.

        Rows missing a ``name`` are skipped; rows whose ``name``
        (case-insensitive) already exists in the database are skipped as
        duplicates.  Returns counts for ``created``, ``skipped`` and
        ``duplicates``.
        """
        existing = {
            (row["name"] or "").strip().lower()
            for row in self.conn.execute("SELECT name FROM part").fetchall()
        }
        created = 0
        skipped = 0
        duplicates = 0
        try:
            for data in rows:
                name = (data.get("name") or "").strip()
                if not name:
                    skipped += 1
                    continue
                key = name.lower()
                if key in existing:
                    duplicates += 1
                    continue
                existing.add(key)
                self.conn.execute(
                    "INSERT INTO part (name, ipn, category, description, units,"
                    " manufacturer, package, package_size, active)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        name,
                        data.get("IPN"),
                        data.get("category"),
                        data.get("description"),
                        data.get("units"),
                        data.get("manufacturer"),
                        data.get("package"),
                        data.get("package_size"),
                        1 if data.get("active", True) else 0,
                    ),
                )
                created += 1
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return {"created": created, "skipped": skipped, "duplicates": duplicates}

    def update_part(self, pk: int, data: dict[str, Any]) -> dict[str, Any]:
        self.conn.execute(
            "UPDATE part SET name = ?, ipn = ?, category = ?, description = ?,"
            " units = ?, manufacturer = ?, package = ?, package_size = ?,"
            " active = ? WHERE id = ?",
            (
                data.get("name"),
                data.get("IPN"),
                data.get("category"),
                data.get("description"),
                data.get("units"),
                data.get("manufacturer"),
                data.get("package"),
                data.get("package_size"),
                1 if data.get("active") else 0,
                pk,
            ),
        )
        self.conn.commit()
        return {"pk": pk}

    def delete_part(self, pk: int) -> None:
        self.conn.execute("DELETE FROM part WHERE id = ?", (pk,))
        self.conn.commit()
        shutil.rmtree(self.attachments_dir / str(pk), ignore_errors=True)

    # ------------------------------------------------------------------ stock

    def list_stock_items(self, search: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT s.id AS pk, s.quantity, s.serial, s.batch,
                   s.status AS status_text,
                   p.name AS part_name, p.ipn AS part_ipn,
                   l.name AS location_name
            FROM stock_item s
            JOIN part p ON p.id = s.part_id
            LEFT JOIN stock_location l ON l.id = s.location_id
        """
        params: list[Any] = []
        if search:
            like = f"%{search}%"
            query += (
                " WHERE p.name LIKE ? OR p.ipn LIKE ? OR s.serial LIKE ?"
                " OR s.batch LIKE ? OR l.name LIKE ?"
            )
            params = [like, like, like, like, like]
        query += " ORDER BY s.id DESC"

        rows = self.conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["quantity"] = _fmt_qty(item["quantity"])
            item["part_name"] = item.get("part_name") or item.get("part_ipn") or ""
            item.pop("part_ipn", None)
            result.append(item)
        return result

    def create_stock_item(self, data: dict[str, Any]) -> dict[str, Any]:
        cursor = self.conn.execute(
            "INSERT INTO stock_item (part_id, quantity, location_id, serial, batch, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                data.get("part"),
                data.get("quantity") or 0,
                data.get("location"),
                data.get("serial"),
                data.get("batch"),
                data.get("status") or "OK",
            ),
        )
        self.conn.commit()
        return {"pk": cursor.lastrowid}

    def update_stock_item(self, pk: int, data: dict[str, Any]) -> dict[str, Any]:
        self.conn.execute(
            "UPDATE stock_item SET part_id = ?, quantity = ?, location_id = ?,"
            " serial = ?, batch = ?, status = ? WHERE id = ?",
            (
                data.get("part"),
                data.get("quantity") or 0,
                data.get("location"),
                data.get("serial"),
                data.get("batch"),
                data.get("status") or "OK",
                pk,
            ),
        )
        self.conn.commit()
        return {"pk": pk}

    def delete_stock_item(self, pk: int) -> None:
        self.conn.execute("DELETE FROM stock_item WHERE id = ?", (pk,))
        self.conn.commit()

    # -------------------------------------------------------------- locations

    def list_stock_locations(self, search: str | None = None) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id AS pk, name, description, parent_id FROM stock_location"
            " ORDER BY name"
        ).fetchall()
        locations = {row["pk"]: dict(row) for row in rows}

        item_counts = dict(
            self.conn.execute(
                "SELECT location_id, COUNT(*) FROM stock_item"
                " WHERE location_id IS NOT NULL GROUP BY location_id"
            ).fetchall()
        )
        child_counts = dict(
            self.conn.execute(
                "SELECT parent_id, COUNT(*) FROM stock_location"
                " WHERE parent_id IS NOT NULL GROUP BY parent_id"
            ).fetchall()
        )

        result = []
        for item in locations.values():
            item["pathstring"] = self._location_path(locations, item["pk"])
            item["items"] = item_counts.get(item["pk"], 0)
            item["sublocations"] = child_counts.get(item["pk"], 0)
            result.append(item)

        if search:
            term = search.lower()
            result = [
                d
                for d in result
                if term in str(d.get("name", "")).lower()
                or term in str(d.get("description") or "").lower()
                or term in str(d.get("pathstring", "")).lower()
            ]
        return result

    def _location_path(self, locations: dict[int, dict], pk: int) -> str:
        parts: list[str] = []
        seen: set[int] = set()
        current = locations.get(pk)
        while current and current["pk"] not in seen:
            seen.add(current["pk"])
            parts.append(current["name"])
            parent = current.get("parent_id")
            current = locations.get(parent) if parent else None
        return " / ".join(reversed(parts))

    def create_stock_location(self, data: dict[str, Any]) -> dict[str, Any]:
        cursor = self.conn.execute(
            "INSERT INTO stock_location (name, description, parent_id) VALUES (?, ?, ?)",
            (data.get("name"), data.get("description"), data.get("parent")),
        )
        self.conn.commit()
        return {"pk": cursor.lastrowid}

    def update_stock_location(self, pk: int, data: dict[str, Any]) -> dict[str, Any]:
        self.conn.execute(
            "UPDATE stock_location SET name = ?, description = ?, parent_id = ?"
            " WHERE id = ?",
            (data.get("name"), data.get("description"), data.get("parent"), pk),
        )
        self.conn.commit()
        return {"pk": pk}

    def delete_stock_location(self, pk: int) -> None:
        self.conn.execute("DELETE FROM stock_location WHERE id = ?", (pk,))
        self.conn.commit()

    # ------------------------------------------------------------------ pins

    def list_pins(self, part_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id AS pk, pin_number, name, type, description FROM part_pin"
            " WHERE part_id = ? ORDER BY id",
            (part_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def replace_pins(self, part_id: int, rows: list[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM part_pin WHERE part_id = ?", (part_id,))
        self.conn.executemany(
            "INSERT INTO part_pin (part_id, pin_number, name, type, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (
                    part_id,
                    r.get("pin_number"),
                    r.get("name"),
                    r.get("type"),
                    r.get("description"),
                )
                for r in rows
            ],
        )
        self.conn.commit()

    def add_pin(self, part_id: int, data: dict[str, Any]) -> dict[str, Any]:
        cursor = self.conn.execute(
            "INSERT INTO part_pin (part_id, pin_number, name, type, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                part_id,
                data.get("pin_number"),
                data.get("name"),
                data.get("type"),
                data.get("description"),
            ),
        )
        self.conn.commit()
        return {"pk": cursor.lastrowid}

    def update_pin(self, pk: int, data: dict[str, Any]) -> dict[str, Any]:
        self.conn.execute(
            "UPDATE part_pin SET pin_number = ?, name = ?, type = ?,"
            " description = ? WHERE id = ?",
            (
                data.get("pin_number"),
                data.get("name"),
                data.get("type"),
                data.get("description"),
                pk,
            ),
        )
        self.conn.commit()
        return {"pk": pk}

    def delete_pin(self, pk: int) -> None:
        self.conn.execute("DELETE FROM part_pin WHERE id = ?", (pk,))
        self.conn.commit()

    # ------------------------------------------------------------- parameters

    def list_parameters(self, part_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id AS pk, category, symbol, name, test_conditions,"
            " min, typ, max, unit FROM part_parameter"
            " WHERE part_id = ? ORDER BY id",
            (part_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def replace_parameters(self, part_id: int, rows: list[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM part_parameter WHERE part_id = ?", (part_id,))
        self.conn.executemany(
            "INSERT INTO part_parameter (part_id, category, symbol, name,"
            " test_conditions, min, typ, max, unit)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    part_id,
                    r.get("category") or "Electrical",
                    r.get("symbol"),
                    r.get("name"),
                    r.get("test_conditions"),
                    r.get("min"),
                    r.get("typ"),
                    r.get("max"),
                    r.get("unit"),
                )
                for r in rows
            ],
        )
        self.conn.commit()

    def add_parameter(self, part_id: int, data: dict[str, Any]) -> dict[str, Any]:
        cursor = self.conn.execute(
            "INSERT INTO part_parameter (part_id, category, symbol, name,"
            " test_conditions, min, typ, max, unit)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                part_id,
                data.get("category") or "Electrical",
                data.get("symbol"),
                data.get("name"),
                data.get("test_conditions"),
                data.get("min"),
                data.get("typ"),
                data.get("max"),
                data.get("unit"),
            ),
        )
        self.conn.commit()
        return {"pk": cursor.lastrowid}

    def update_parameter(self, pk: int, data: dict[str, Any]) -> dict[str, Any]:
        self.conn.execute(
            "UPDATE part_parameter SET category = ?, symbol = ?, name = ?,"
            " test_conditions = ?, min = ?, typ = ?, max = ?, unit = ?"
            " WHERE id = ?",
            (
                data.get("category"),
                data.get("symbol"),
                data.get("name"),
                data.get("test_conditions"),
                data.get("min"),
                data.get("typ"),
                data.get("max"),
                data.get("unit"),
                pk,
            ),
        )
        self.conn.commit()
        return {"pk": pk}

    def delete_parameter(self, pk: int) -> None:
        self.conn.execute("DELETE FROM part_parameter WHERE id = ?", (pk,))
        self.conn.commit()

    # ------------------------------------------------------------ attachments

    def list_attachments(self, part_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id AS pk, part_id, kind, filename, stored_name"
            " FROM part_attachment WHERE part_id = ? ORDER BY id",
            (part_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def attachment_path(self, pk: int) -> Path | None:
        row = self.conn.execute(
            "SELECT part_id, stored_name FROM part_attachment WHERE id = ?", (pk,)
        ).fetchone()
        if row is None:
            return None
        path = self.attachments_dir / str(row["part_id"]) / row["stored_name"]
        return path if path.exists() else None

    def set_attachment(self, part_id: int, kind: str, source_path: Path) -> dict[str, Any]:
        """Replace the existing attachment of ``kind`` with a copy of ``source_path``."""
        for att in self.list_attachments(part_id):
            if att["kind"] == kind:
                self.delete_attachment(att["pk"])

        dest_dir = self.attachments_dir / str(part_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = source_path.suffix.lower()
        stored_name = f"{uuid.uuid4().hex}{ext}"
        shutil.copy2(source_path, dest_dir / stored_name)

        cursor = self.conn.execute(
            "INSERT INTO part_attachment (part_id, kind, filename, stored_name)"
            " VALUES (?, ?, ?, ?)",
            (part_id, kind, source_path.name, stored_name),
        )
        self.conn.commit()
        return {"pk": cursor.lastrowid}

    def delete_attachment(self, pk: int) -> None:
        path = self.attachment_path(pk)
        self.conn.execute("DELETE FROM part_attachment WHERE id = ?", (pk,))
        self.conn.commit()
        if path:
            path.unlink(missing_ok=True)

    def get_attachment(self, part_id: int, kind: str) -> dict[str, Any] | None:
        for att in self.list_attachments(part_id):
            if att["kind"] == kind:
                return att
        return None
