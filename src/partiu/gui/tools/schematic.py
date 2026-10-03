"""Schematic rendering widget (GUI).

Renders a :class:`~partiu.tools.schematic.Schematic` spec onto a tk.Canvas and
exposes :meth:`SchematicCanvas.update` to refresh only the dynamic annotation
labels.
"""

from __future__ import annotations

import tkinter as tk

from ...tools.schematic import (
    Annotation,
    Dot,
    Line,
    Oval,
    Polyline,
    Rect,
    Schematic,
    Text,
)

_DEFAULT_FONT = ("Helvetica", 11)
_ANNOTATION_FONT = ("Helvetica", 11, "bold")


class SchematicCanvas(tk.Canvas):
    """A fixed-size Canvas that draws a schematic spec and its value labels."""

    def __init__(
        self,
        parent,
        schematic: Schematic,
        background: str = "#ffffff",
        highlightthickness: int = 0,
    ):
        super().__init__(
            parent,
            width=schematic.width,
            height=schematic.height,
            background=background,
            highlightthickness=highlightthickness,
        )
        self._schematic = schematic
        self._annotation_items: dict[str, int] = {}

        for primitive in schematic.primitives:
            self._render(primitive)
        self.update({})

    # ------------------------------------------------------------------ render

    def _render(self, primitive) -> None:
        if isinstance(primitive, Line):
            self.create_line(
                primitive.x1, primitive.y1, primitive.x2, primitive.y2,
                width=primitive.width, fill=primitive.color,
            )
        elif isinstance(primitive, Rect):
            self.create_rectangle(
                primitive.x1, primitive.y1, primitive.x2, primitive.y2,
                width=primitive.width, outline=primitive.outline, fill=primitive.fill,
            )
        elif isinstance(primitive, Oval):
            self.create_oval(
                primitive.x1, primitive.y1, primitive.x2, primitive.y2,
                width=primitive.width, outline=primitive.outline, fill=primitive.fill,
            )
        elif isinstance(primitive, Polyline):
            coords = [c for point in primitive.points for c in point]
            self.create_line(
                *coords,
                width=primitive.width, fill=primitive.color, smooth=primitive.smooth,
            )
        elif isinstance(primitive, Text):
            self.create_text(
                primitive.x, primitive.y, text=primitive.text,
                anchor=primitive.anchor, fill=primitive.color,
                font=primitive.font or _DEFAULT_FONT,
            )
        elif isinstance(primitive, Dot):
            self.create_oval(
                primitive.x - primitive.r, primitive.y - primitive.r,
                primitive.x + primitive.r, primitive.y + primitive.r,
                fill=primitive.fill, outline="",
            )

    # ------------------------------------------------------------------ update

    def update(self, values: dict[str, str]) -> None:
        """Refresh annotation labels from ``{annotation_id: formatted_text}``.

        A missing/empty value leaves the label alone (shows just the name).
        """
        for annotation in self._schematic.annotations:
            item = self._annotation_items.get(annotation.id)
            if item is None:
                item = self.create_text(
                    annotation.x, annotation.y,
                    anchor=annotation.anchor, fill=annotation.color,
                    font=annotation.font or _ANNOTATION_FONT,
                )
                self._annotation_items[annotation.id] = item

            value = values.get(annotation.id)
            if value:
                text = f"{annotation.label} = {value}"
            else:
                text = annotation.label
            self.itemconfig(item, text=text)
