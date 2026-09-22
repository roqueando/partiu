"""SQLite data layer for Partiu.

A single local SQLite database stores parts, part categories, stock locations
and stock items.  The public methods mirror the previous ``inventree_client``
interface, so the tkinter views only needed ``client`` renamed to ``db``.
"""

from __future__ import annotations

import sqlite3
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
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ parts

    def list_parts(self, search: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT p.id AS pk, p.name, p.ipn AS IPN, p.category, p.description,
                   p.units, p.active,
                   COALESCE((SELECT SUM(s.quantity) FROM stock_item s
                             WHERE s.part_id = p.id), 0) AS in_stock
            FROM part p
        """
        params: list[Any] = []
        if search:
            like = f"%{search}%"
            query += (
                " WHERE p.name LIKE ? OR p.ipn LIKE ? OR p.description LIKE ?"
                " OR p.category LIKE ?"
            )
            params = [like, like, like, like]
        query += " ORDER BY p.name"

        rows = self.conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["active"] = bool(item["active"])
            item["in_stock"] = _fmt_qty(item["in_stock"])
            result.append(item)
        return result

    def create_part(self, data: dict[str, Any]) -> dict[str, Any]:
        cursor = self.conn.execute(
            "INSERT INTO part (name, ipn, category, description, units, active)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                data.get("name"),
                data.get("IPN"),
                data.get("category"),
                data.get("description"),
                data.get("units"),
                1 if data.get("active") else 0,
            ),
        )
        self.conn.commit()
        return {"pk": cursor.lastrowid}

    def update_part(self, pk: int, data: dict[str, Any]) -> dict[str, Any]:
        self.conn.execute(
            "UPDATE part SET name = ?, ipn = ?, category = ?, description = ?,"
            " units = ?, active = ? WHERE id = ?",
            (
                data.get("name"),
                data.get("IPN"),
                data.get("category"),
                data.get("description"),
                data.get("units"),
                1 if data.get("active") else 0,
                pk,
            ),
        )
        self.conn.commit()
        return {"pk": pk}

    def delete_part(self, pk: int) -> None:
        self.conn.execute("DELETE FROM part WHERE id = ?", (pk,))
        self.conn.commit()

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
