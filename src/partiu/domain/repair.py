"""Repair project, photo, and finding entities."""

from __future__ import annotations

from dataclasses import dataclass

#: Repair finding status keys → Portuguese labels.
FINDING_STATUSES = {
    "Good": "Bom",
    "Bad": "Ruim",
    "Needs testing": "Precisa testar",
}

#: (value, label) pairs for status comboboxes.
FINDING_STATUS_OPTIONS = [(key, label) for key, label in FINDING_STATUSES.items()]

#: Default status for a new finding.
DEFAULT_FINDING_STATUS = "Needs testing"

#: Fixed category suggestions (editable — users may type their own).
CATEGORIES = [
    "Trilha",
    "CI",
    "Componente",
    "Conector",
    "Transistor",
    "Capacitor",
    "Resistor",
    "Outro",
]


@dataclass
class RepairProject:
    """A repair session."""

    name: str
    equipment: str | None = None
    notes: str | None = None


@dataclass
class RepairPhoto:
    """An image captured/imported for a repair project."""

    project_id: int
    filename: str
    stored_name: str
    position: int = 0


@dataclass
class RepairFinding:
    """A labeled point on a repair photo, optionally linked to a part.

    ``x`` / ``y`` are normalized 0..1 relative to the full-resolution image.
    """

    project_id: int
    photo_id: int
    label: str
    x: float
    y: float
    category: str | None = None
    status: str = DEFAULT_FINDING_STATUS
    part_id: int | None = None
    notes: str | None = None
