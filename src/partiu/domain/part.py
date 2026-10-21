"""Part entity and its fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Part:
    """A tracked component.

    ``in_stock`` is derived (sum of its stock items' quantities) and is not a
    stored field.
    """

    name: str
    ipn: str | None = None
    category: str | None = None
    description: str | None = None
    units: str | None = None
    manufacturer: str | None = None
    package: str | None = None
    package_size: str | None = None
    active: bool = True
