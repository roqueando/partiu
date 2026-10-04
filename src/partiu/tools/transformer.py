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

#: Tabela 1 — EE ferrite cores (``M2A2_FC_Ini_II__ANEXO_1__Projeto.pdf``):
#: ``(name, Ae [cm²], Aw [cm²], Ae·Aw [cm⁴])``.
EE_CORES: list[tuple[str, float, float, float]] = [
    ("E 19/8/5", 0.2212, 0.2112, 0.04671),
    ("E 19/8/6", 0.2696, 0.2574, 0.069395),
    ("E 20/10/5", 0.31, 0.255, 0.07905),
    ("E 20", 0.312, 0.26, 0.08112),
    ("E 30/07", 0.6, 0.8, 0.48),
    ("E 30/14", 1.2, 0.85, 1.02),
    ("E 42/15", 1.81, 1.57, 2.8417),
    ("E 42/20", 2.4, 1.57, 3.768),
    ("E 55", 3.54, 2.5, 8.85),
]

#: Tabela 2 — AWG wires (same PDF):
#: ``(awg, copper dia [cm], copper area [cm²], insulated dia [cm],
#: insulated area [cm²], Imax [A])``.
AWG_WIRES: list[tuple[int, float, float, float, float, float]] = [
    (10, 0.259, 0.052620, 0.273, 0.058572, 23.679),
    (11, 0.231, 0.041729, 0.244, 0.046738, 18.778),
    (12, 0.205, 0.033092, 0.218, 0.037309, 14.892),
    (13, 0.183, 0.026243, 0.195, 0.029793, 11.809),
    (14, 0.163, 0.020811, 0.174, 0.023800, 9.365),
    (15, 0.145, 0.016504, 0.156, 0.019021, 7.427),
    (16, 0.129, 0.013088, 0.139, 0.015207, 5.890),
    (17, 0.115, 0.010379, 0.124, 0.012164, 4.671),
    (18, 0.102, 0.008231, 0.111, 0.009735, 3.704),
    (19, 0.091, 0.006527, 0.100, 0.007794, 2.937),
    (20, 0.081, 0.005176, 0.089, 0.006244, 2.329),
    (21, 0.072, 0.004105, 0.080, 0.005004, 1.847),
    (22, 0.064, 0.003255, 0.071, 0.004013, 1.465),
    (23, 0.057, 0.002582, 0.064, 0.003221, 1.162),
    (24, 0.051, 0.002047, 0.057, 0.002586, 0.921),
    (25, 0.045, 0.001624, 0.051, 0.002078, 0.731),
    (26, 0.040, 0.001287, 0.046, 0.001671, 0.579),
    (27, 0.036, 0.001021, 0.041, 0.001344, 0.459),
    (28, 0.032, 0.000810, 0.037, 0.001083, 0.364),
    (29, 0.029, 0.000642, 0.033, 0.000872, 0.289),
    (30, 0.025, 0.000509, 0.030, 0.000704, 0.229),
    (31, 0.023, 0.000404, 0.027, 0.000568, 0.182),
    (32, 0.020, 0.000320, 0.024, 0.000459, 0.144),
    (33, 0.018, 0.000254, 0.022, 0.000371, 0.114),
    (34, 0.016, 0.000201, 0.020, 0.000300, 0.091),
    (35, 0.014, 0.000160, 0.018, 0.000243, 0.072),
    (36, 0.013, 0.000127, 0.016, 0.000197, 0.057),
    (37, 0.011, 0.000100, 0.014, 0.000160, 0.045),
    (38, 0.010, 0.000080, 0.013, 0.000130, 0.036),
    (39, 0.009, 0.000063, 0.012, 0.000106, 0.028),
    (40, 0.008, 0.000050, 0.010, 0.000086, 0.023),
    (41, 0.007, 0.000040, 0.009, 0.000070, 0.018),
]


def select_core(ae_aw_req: float) -> tuple[str, float, float, float] | None:
    """Smallest EE core whose Ae·Aw covers ``ae_aw_req`` (cm⁴).

    Smallest core = least material; returns ``None`` if no table entry fits.
    """
    for core in EE_CORES:
        if core[3] >= ae_aw_req:
            return core
    return None


def select_wire(dia_max_cm: float) -> tuple[int, float, float, float, float, float] | None:
    """Thickest AWG wire (lowest gauge number) within the skin-effect limit.

    The reference uses ``dia_max = 15/sqrt(f)`` [cm] as the maximum conductor
    diameter; the insulated diameter from Tabela 2 must not exceed it.
    """
    for wire in AWG_WIRES:
        if wire[3] <= dia_max_cm:
            return wire
    return None


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
