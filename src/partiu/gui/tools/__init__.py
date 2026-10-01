"""Partiu engineering tools registry (GUI).

Each tool is a :class:`Tool` entry with an ``launch`` callback receiving
``(master, db, search_inventory)``.  Adding a new tool is just registering it
here; the main window's ``Tools`` menu is built from :data:`TOOLS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .flyback import launch as flyback_launch


@dataclass
class Tool:
    """A single entry in the Tools menu."""

    id: str
    label: str
    launch: Callable


TOOLS: list[Tool] = [
    Tool(id="flyback_dcm", label="Flyback DCM calculator…", launch=flyback_launch),
]
