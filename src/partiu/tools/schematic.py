"""Schematic definitions (pure data, no GUI).

A schematic is described declaratively as a list of primitives (lines, rects,
ovals, polylines, texts, dots) plus a list of *annotation* slots whose text can
be updated dynamically (e.g. computed component values).

This module is tkinter-free so it can be unit-tested and reused by the GUI
renderer in :mod:`partiu.gui.tools.schematic`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# --------------------------------------------------------------------------- primitives

@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 2.0
    color: str = "#000000"


@dataclass(frozen=True)
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 2.0
    outline: str = "#000000"
    fill: str = ""


@dataclass(frozen=True)
class Oval:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 2.0
    outline: str = "#000000"
    fill: str = ""


@dataclass(frozen=True)
class Polyline:
    points: tuple[tuple[float, float], ...]
    width: float = 2.0
    color: str = "#000000"
    smooth: bool = False


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    text: str
    anchor: str = "center"
    color: str = "#000000"
    font: tuple | None = None


@dataclass(frozen=True)
class Dot:
    x: float
    y: float
    r: float = 3.0
    fill: str = "#000000"


@dataclass(frozen=True)
class Annotation:
    """A dynamic value slot: a text item rendered near a component.

    ``id`` maps to the value key, ``label`` is the human name shown when there
    is no value yet (and prefixed to the value once one is supplied).
    """

    id: str
    label: str
    x: float
    y: float
    anchor: str = "center"
    color: str = "#b00020"
    font: tuple | None = None


@dataclass(frozen=True)
class Schematic:
    width: int
    height: int
    primitives: tuple = ()
    annotations: tuple = ()


# ---------------------------------------------------------------------------- symbol builders
# Each builder returns a tuple of primitives; callers connect symbols with
# explicit Line/Text/Dot primitives so layouts stay explicit and tweakable.

def ground(x: float, y: float, h: float = 14) -> tuple:
    """Earth-ground symbol: a stub and three shrinking bars below (x, y)."""
    return (
        Line(x, y, x, y + h),
        Line(x - 14, y + h, x + 14, y + h),
        Line(x - 8, y + h + 5, x + 8, y + h + 5),
        Line(x - 3, y + h + 10, x + 3, y + h + 10),
    )


def source(x: float, y: float, r: float = 15) -> tuple:
    """DC source: a circle with ``+``/``−`` inside (top positive)."""
    return (
        Oval(x - r, y - r, x + r, y + r),
        Text(x, y - 5, "+", color="#000000", font=("Helvetica", 13, "bold")),
        Text(x, y + 5, "\u2212", color="#000000", font=("Helvetica", 13, "bold")),
    )


def inductor(
    x1: float, y1: float, x2: float, y2: float,
    loops: int = 4, amp: float = 9, width: float = 2.0, color: str = "#000000",
) -> tuple:
    """Inductor/winding: a bumpy polyline between the two endpoints."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return ()
    ux, uy = dx / length, dy / length
    px, py = -uy, ux  # perpendicular unit vector

    points = []
    for i in range(loops + 1):
        t = i / loops
        off = amp if i % 2 == 0 else -amp
        points.append((x1 + dx * t + px * off, y1 + dy * t + py * off))
    return (Polyline(tuple(points), width=width, color=color, smooth=True),)


def capacitor(
    x1: float, y1: float, x2: float, y2: float,
    gap: float = 8, plate: float = 22, width: float = 2.0, color: str = "#000000",
) -> tuple:
    """Capacitor: two parallel plates perpendicular to the (x1,y1)-(x2,y2) axis."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return ()
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    half = gap / 2

    p1 = (mx - ux * half, my - uy * half)
    p2 = (mx + ux * half, my + uy * half)

    def draw_plate(cx: float, cy: float) -> Line:
        return Line(
            cx - px * plate / 2, cy - py * plate / 2,
            cx + px * plate / 2, cy + py * plate / 2,
            width=width, color=color,
        )

    return (
        Line(x1, y1, p1[0], p1[1], width=width, color=color),
        draw_plate(*p1),
        draw_plate(*p2),
        Line(p2[0], p2[1], x2, y2, width=width, color=color),
    )


def resistor(
    x1: float, y1: float, x2: float, y2: float,
    body: float = 46, width: float = 2.0, color: str = "#000000",
) -> tuple:
    """IEC resistor: a rectangle body along the axis with lead wires."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return ()
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    hw, hh = body / 2, 7  # half-length (axis) and half-thickness (perpendicular)

    corners = [
        (mx - ux * hw + px * hh, my - uy * hw + py * hh),
        (mx + ux * hw + px * hh, my + uy * hw + py * hh),
        (mx + ux * hw - px * hh, my + uy * hw - py * hh),
        (mx - ux * hw - px * hh, my - uy * hw - py * hh),
    ]
    near = (mx - ux * hw, my - uy * hw)
    far = (mx + ux * hw, my + uy * hw)

    return (
        Line(x1, y1, near[0], near[1], width=width, color=color),
        Polyline(corners + [corners[0]], width=width, color=color),
        Line(far[0], far[1], x2, y2, width=width, color=color),
    )


def diode(
    ax: float, ay: float, bx: float, by: float,
    width: float = 2.0, color: str = "#000000",
) -> tuple:
    """Diode pointing from anode (ax, ay) to cathode (bx, by)."""
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return ()
    ux, uy = dx / length, dy / length
    px, py = -uy, ux

    base_len = 14
    base_cx, base_cy = bx - ux * base_len, by - uy * base_len
    triangle = (
        (ax, ay),
        (base_cx + px * 7, base_cy + py * 7),
        (base_cx - px * 7, base_cy - py * 7),
        (ax, ay),
    )
    bar = (
        (bx + px * 7, by + py * 7),
        (bx - px * 7, by - py * 7),
    )
    return (
        Polyline(tuple(triangle), width=width, color=color),
        Line(bar[0][0], bar[0][1], bar[1][0], bar[1][1], width=width, color=color),
    )


def mosfet(
    drain_x: float, drain_y: float,
    source_x: float, source_y: float,
    gate_len: float = 20, width: float = 2.0, color: str = "#000000",
) -> tuple:
    """N-MOSFET symbol: vertical channel, gate leg extending to the left."""
    mx, my = (drain_x + source_x) / 2, (drain_y + source_y) / 2
    gx = drain_x - gate_len
    return (
        Line(drain_x, drain_y, drain_x, my, width=width, color=color),
        Line(source_x, my, source_x, source_y, width=width, color=color),
        Line(gx, my - 9, gx, my + 9, width=width, color=color),
        Line(gx, my, drain_x, my, width=width, color=color),
    )


def transformer(
    primary_x: float, secondary_x: float,
    core_x1: float, core_x2: float,
    y_top: float, y_bottom: float,
    primary_dot_top: bool = True,
    secondary_dot_top: bool = False,
    width: float = 1.5, color: str = "#000000",
) -> tuple:
    """Two windings on a magnetic core (two parallel core lines) with dots."""
    prims: list = []
    prims += inductor(primary_x, y_top, primary_x, y_bottom, width=width, color=color)
    prims += inductor(secondary_x, y_top, secondary_x, y_bottom, width=width, color=color)
    prims += (
        Line(core_x1, y_top - 6, core_x1, y_bottom + 6, width=width, color=color),
        Line(core_x2, y_top - 6, core_x2, y_bottom + 6, width=width, color=color),
        Dot(primary_x, y_top + 8 if primary_dot_top else y_bottom - 8),
        Dot(secondary_x, y_top + 8 if secondary_dot_top else y_bottom - 8),
    )
    return tuple(prims)


# ----------------------------------------------------------------------- flyback schematic

_FLYBACK_WIDTH = 720
_FLYBACK_HEIGHT = 360

# Transformer geometry.
_PX, _SX = 300, 420            # primary / secondary winding x
_CX1, _CX2 = 355, 365          # core lines
_TOP, _BOT = 110, 230          # winding vertical extent
_GROUND_Y = 300                # both ground rails


def flyback_schematic() -> Schematic:
    """DCM flyback topology with annotation slots for the 7 key values."""
    prims: list = []

    # -- transformer (primary dot top, secondary dot bottom) --
    prims += transformer(
        _PX, _SX, _CX1, _CX2, _TOP, _BOT,
        primary_dot_top=True, secondary_dot_top=False,
    )

    # -- primary: Vin source --
    prims += source(150, 170)
    prims.append(Text(128, 170, "Vin", anchor="e", color="#000000"))
    prims.append(Line(150, 155, 150, _TOP))                 # Vin+ lead
    prims.append(Line(150, 185, 150, _GROUND_Y))            # Vin− lead
    prims += ground(150, _GROUND_Y)
    prims.append(Dot(150, _TOP))

    # primary + rail to L1 top
    prims.append(Line(150, _TOP, _PX, _TOP))
    prims.append(Dot(_PX, _TOP))

    # primary winding bottom -> MOSFET drain -> source -> ground rail
    prims.append(Line(_PX, _BOT, _PX, 265))
    prims += mosfet(300, 265, 300, 295)
    prims.append(Line(300, 295, 300, _GROUND_Y))
    prims.append(Dot(300, _GROUND_Y))
    prims.append(Line(150, _GROUND_Y, 300, _GROUND_Y))      # primary ground rail
    prims.append(Line(245, 280, 280, 280))                  # gate drive lead
    prims.append(Text(238, 280, "G", anchor="e", color="#000000"))
    prims.append(Text(316, 282, "Q1", anchor="w", color="#000000"))

    # -- secondary: L2 top (non-dot) -> diode -> Vout node -> C || RL -> ground --
    prims.append(Line(_SX, _TOP, 450, _TOP))
    prims += diode(450, _TOP, 510, _TOP)
    prims.append(Text(480, 96, "D1", anchor="s", color="#000000"))

    prims.append(Dot(510, _TOP))
    prims.append(Text(510, 96, "Vout", anchor="s", color="#000000"))
    prims.append(Line(510, _TOP, 630, _TOP))                # output + rail
    prims += capacitor(540, _TOP, 540, _GROUND_Y)           # C
    prims += resistor(630, _TOP, 630, _GROUND_Y)            # RL

    # secondary ground rail + ground
    prims.append(Line(_SX, _BOT, _SX, _GROUND_Y))
    prims.append(Line(420, _GROUND_Y, 630, _GROUND_Y))
    prims += ground(420, _GROUND_Y)

    annotations = (
        Annotation("L1", "L1", 285, 92, anchor="s"),
        Annotation("L2", "L2", 420, 92, anchor="s"),
        Annotation("n", "n", 360, 86, anchor="s"),
        Annotation("C", "C", 528, 205, anchor="e"),
        Annotation("RL", "RL", 640, 205, anchor="w"),
        Annotation("Vds_max", "Vds max", 245, 250, anchor="e"),
        Annotation("VD_max", "VD max", 480, 135, anchor="n"),
    )

    return Schematic(
        width=_FLYBACK_WIDTH,
        height=_FLYBACK_HEIGHT,
        primitives=tuple(prims),
        annotations=annotations,
    )
