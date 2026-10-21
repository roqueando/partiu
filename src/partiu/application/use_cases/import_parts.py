"""Use case: import parts from a spreadsheet file."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def import_parts_from_file(repo, importer, path: Path) -> dict[str, Any]:
    """Read ``path`` and bulk-insert the parts into ``repo``.

    Returns ``{"created": int, "skipped": int, "duplicates": int,
    "total": int}``.
    """
    records = importer.read_parts(path)
    counts = repo.import_parts(records)
    return {
        "created": counts["created"],
        "skipped": counts["skipped"],
        "duplicates": counts["duplicates"],
        "total": len(records),
    }
