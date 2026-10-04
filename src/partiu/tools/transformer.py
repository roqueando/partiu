"""High-frequency flyback transformer design (pure math, no GUI).

Implements the core/window/wire sizing equations from ``M2A2_calc_transf.m``
(Fontes Chaveadas Iniciantes II — Dr. Eng. Wagner Rambo, 2023).

The design consumes the converter results computed by
:mod:`partiu.tools.flyback` (duty cycle ``D``, ``Vin``, the primary/secondary
currents, the input power, the switching frequency and the turns ratio) plus
the transformer-specific parameters listed in :data:`DEFAULTS`.

Unit conventions (mirroring the reference script):

* ``kw`` / ``kp``  – window / primary utilization factors (dimensionless)
* ``jmax``         – current density [A/cm²]
* ``del_b``        – flux density swing [T]
* ``ae``           – core cross-section area [cm²]
* ``aw``           – core window area [cm²]
* ``ae_aw_use``    – Ae·Aw of the chosen core [cm⁴]
* ``aco_iso``      – wire area with lacquer [cm²]

Outputs: ``AeAw`` in cm⁴, ``entreferro``/``entferr_side`` in mm,
``B_gauss`` in gauss, wire/window areas in cm², ``Dia_max`` in cm,
``DelW`` in J (everything else is dimensionless).
"""

from __future__ import annotations

import math
from typing import Any

#: Permeability of free space [H/m].
U0 = 4 * math.pi * 1e-7

#: Default transformer parameters (EE-20/10/5 core, 25 AWG wire).
DEFAULTS: dict[str, float] = {
    "kw": 0.5,          # window utilization factor
    "kp": 0.5,          # primary utilization factor
    "jmax": 450.0,      # max current density [A/cm²]
    "del_b": 0.39,      # flux density swing [T]
    "ae": 0.31,         # core cross-section [cm²]
    "aw": 0.255,        # core window area [cm²]
    "ae_aw_use": 0.07905,  # chosen core Ae·Aw [cm⁴] (EE-20/10/5)
    "aco_iso": 0.002078,   # 25 AWG wire area w/ lacquer [cm²]
}


def defaults() -> dict[str, float]:
    """Return a copy of the default transformer parameters."""
    return dict(DEFAULTS)


def design(
    *,
    duty: float,
    vin: float,
    il1_rms: float,
    il1_max: float,
    il2_rms: float,
    pin: float,
    freq: float,
    n: float,
    kw: float = DEFAULTS["kw"],
    kp: float = DEFAULTS["kp"],
    jmax: float = DEFAULTS["jmax"],
    del_b: float = DEFAULTS["del_b"],
    ae: float = DEFAULTS["ae"],
    aw: float = DEFAULTS["aw"],
    ae_aw_use: float = DEFAULTS["ae_aw_use"],
    aco_iso: float = DEFAULTS["aco_iso"],
) -> dict[str, Any]:
    """Design the high-frequency transformer for the given operating point.

    The converter arguments come from :func:`partiu.tools.flyback.calculate`
    (``duty`` already recalculated, ``freq`` in Hz, currents in A, ``pin`` in
    W). Returns a dict with the values documented in the module docstring.
    """
    if freq <= 0:
        raise ValueError("frequency must be > 0")
    if not 0 < duty < 1:
        raise ValueError("duty must be in (0, 1)")
    if vin <= 0 or pin <= 0 or n <= 0:
        raise ValueError("Vin, Pin and turns ratio must be > 0")
    if il1_rms <= 0 or il1_max <= 0 or il2_rms <= 0:
        raise ValueError("winding currents must be > 0")
    if kw <= 0 or kp <= 0 or jmax <= 0 or del_b <= 0:
        raise ValueError("Kw, Kp, Jmax and DelB must be > 0")
    if ae <= 0 or aw <= 0 or ae_aw_use <= 0 or aco_iso <= 0:
        raise ValueError("core and wire areas must be > 0")

    # ---- product Ae·Aw (area product) [cm⁴] ----
    ae_aw = (duty * vin * il1_rms) / (kp * kw * jmax * del_b * freq) * 1e4
    ae_aw_margin = ae_aw_use / ae_aw
    ae_aw_ok = ae_aw_use >= ae_aw

    # ---- air gap (energy storage) ----
    del_w = pin / freq                                  # energy swing [J]
    ae_m2 = ae * 1e-4                                   # core area in m²
    entreferro = (2 * U0 * del_w) / (del_b * del_b * ae_m2) * 1000  # [mm]
    entferr_side = entreferro / 3                       # side gap [mm]

    # ---- turns (CGS air-gap MMF balance, as in the reference script) ----
    b_gauss = del_b * 1e4                               # [G]
    entferr_cm = entreferro / 10                        # [cm]
    n1 = (b_gauss * entferr_cm) / (0.4 * math.pi * il1_max)
    n2 = n1 / n

    # ---- wire sizing ----
    awire1 = il1_rms / jmax                             # primary wire area [cm²]
    dia_max = 15 / math.sqrt(freq)                      # max conductor dia [cm]
    n1cond = math.ceil(awire1 / aco_iso)                # parallel conductors
    awire2 = il2_rms / jmax                             # secondary wire area [cm²]
    n2cond = math.ceil(awire2 / aco_iso)

    # ---- window check ----
    ua1 = n1 * aco_iso * n1cond                         # primary area [cm²]
    ua2 = n2 * aco_iso * n2cond                         # secondary area [cm²]
    aw_min = (ua1 + ua2) / kw                           # required area [cm²]
    exec_ = aw_min / aw                                 # ≤ 1 => feasible

    return {
        # Ae·Aw
        "AeAw": ae_aw,
        "AeAw_use": ae_aw_use,
        "AeAw_margin": ae_aw_margin,
        "AeAw_ok": ae_aw_ok,
        # air gap / turns
        "DelW": del_w,
        "entreferro": entreferro,
        "entferr_side": entferr_side,
        "B_gauss": b_gauss,
        "N1": n1,
        "N1_int": math.ceil(n1),
        "N2": n2,
        "N2_int": math.ceil(n2),
        # wire
        "Awire1": awire1,
        "N1cond": n1cond,
        "Awire2": awire2,
        "N2cond": n2cond,
        "Dia_max": dia_max,
        # window check
        "UA1": ua1,
        "UA2": ua2,
        "Aw_min": aw_min,
        "Aw": aw,
        "Exec": exec_,
    }
