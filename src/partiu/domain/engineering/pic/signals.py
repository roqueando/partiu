"""Logical ICSP signal names shared by the domain, use cases and adapters.

The programmer driver (an adapter) exposes these nets; the use-case layer
manipulates them without knowing which physical pin/line the adapter maps them
to.  Names are lowercase strings so a JSON pin-map can reference them directly.
"""

from __future__ import annotations

#: Programming voltage on MCLR (~13 V high-voltage ICSP).
VPP = "vpp"
#: Device supply during programming.
VDD = "vdd"
#: Ground.
VSS = "vss"
#: Programming clock (PGC) — RB6/GP1 depending on device.
PGC = "pgc"
#: Programming data (PGD) — RB7/GP0 depending on device.
PGD = "pgd"
#: Low-voltage programming enable (PGM) — held low for high-voltage ICSP.
PGM = "pgm"

#: Every logical net the driver must expose.
SIGNALS: tuple[str, ...] = (VPP, VDD, VSS, PGC, PGD, PGM)
