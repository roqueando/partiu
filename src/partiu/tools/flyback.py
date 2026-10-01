"""Flyback DCM converter design calculator (pure math, no GUI).

Implements the design equations from ``M2A1_FC_Ini_II__ANEXO_1__Projeto.pdf``
and ``M2A1_calc_flyback.m``.

All outputs are returned in SI units (A, V, H, F, Ω, W).  Inputs ``ripple``,
``eta`` and ``duty`` are fractions (0..1); ``freq`` is in Hz.
"""

from __future__ import annotations

import math
from typing import Any


def calculate(
    vin: float,
    vin_max: float,
    vout: float,
    iout: float,
    ripple: float,
    eta: float,
    duty: float,
    freq: float,
) -> dict[str, Any]:
    """Compute every flyback DCM design value for the given parameters.

    Returns ``n`` as an ``int`` (rounded up, ``ceil``) and all other values as
    ``float`` in SI units.
    """
    if vin <= 0 or vin_max <= 0 or vout <= 0 or iout <= 0 or freq <= 0:
        raise ValueError("voltages, current and frequency must be > 0")
    if not 0 < eta <= 1:
        raise ValueError("eta must be in (0, 1]")
    if not 0 < duty < 1:
        raise ValueError("duty must be in (0, 1)")
    if ripple < 0:
        raise ValueError("ripple must be >= 0")

    rl = vout / iout                      # load resistance [Ω]
    pout = vout * iout                    # output power [W]
    pin = pout / eta                      # input power [W]

    n_raw = (vin * duty) / (vout * (1 - duty))
    n = math.ceil(n_raw)                  # turns ratio, rounded up
    duty = 1 / (vin / (n * vout) + 1)     # recalculated max duty cycle

    il1_max = (2 * pout) / (vin * duty)   # max primary (L1) current [A]
    il1_avg = (il1_max * duty) / 2        # avg primary current [A]
    il1_rms = il1_max * math.sqrt(duty / 3)  # RMS primary current [A]
    l1 = (vin * duty) / (il1_max * freq)  # primary inductance [H]

    il2_max = (2 * (vout ** 2) * n) / (vin * duty * rl)  # max secondary current [A]
    il2_avg = iout                        # avg secondary current [A]
    il2_rms = ((2 * vout) / rl) * math.sqrt((vout * n) / (3 * vin * duty))
    l2 = l1 / (n ** 2)                    # secondary inductance [H]

    delta_vout = vout * ripple            # output voltage ripple [V]
    c = (pout * duty) / (vout * delta_vout * freq)  # output capacitance [F]
    ic_rms = (vout / rl) * math.sqrt(
        (((1 - duty) ** 2) - 4 * (1 - duty) + 4) / (3 * (1 - duty)) + duty
    )

    iq1_max = il1_max                     # MOSFET max current [A]
    iq1_avg = il1_avg                     # MOSFET avg current [A]
    iq1_rms = il1_rms                     # MOSFET RMS current [A]
    vds_max = vin + vout * n              # max drain-source voltage @ Vin [V]
    vds_max_vinmax = vin_max + vout * n   # max drain-source voltage @ Vin_max [V]
    d_min = (2 * pout) / (vin_max * il1_max)  # minimum duty cycle

    id_max = il2_max                      # diode max current [A]
    id_avg = iout                         # diode avg current [A]
    id_rms = il2_rms                      # diode RMS current [A]
    vd_max = -((vin_max / n) + vout)      # diode max reverse voltage [V]

    return {
        # converter
        "RL": rl,
        "Pout": pout,
        "Pin": pin,
        "n": n,
        "D": duty,
        "D_min": d_min,
        # primary / MOSFET
        "IL1_max": il1_max,
        "IL1_avg": il1_avg,
        "IL1_rms": il1_rms,
        "L1": l1,
        "IQ1_max": iq1_max,
        "IQ1_avg": iq1_avg,
        "IQ1_rms": iq1_rms,
        "Vds_max": vds_max,
        "Vds_max_vinmax": vds_max_vinmax,
        # secondary / diode
        "IL2_max": il2_max,
        "IL2_avg": il2_avg,
        "IL2_rms": il2_rms,
        "L2": l2,
        "ID_max": id_max,
        "ID_avg": id_avg,
        "ID_rms": id_rms,
        "VD_max": vd_max,
        # output capacitor
        "delta_Vout": delta_vout,
        "C": c,
        "IC_rms": ic_rms,
    }


#: Default input values (UI units: V / A / % / kHz) matching the reference design.
DEFAULTS: dict[str, float] = {
    "vin": 12.0,
    "vin_max": 35.0,
    "vout": 5.0,
    "iout": 2.5,
    "ripple": 0.5,   # %
    "eta": 70.0,     # %
    "duty": 45.0,    # %
    "freq": 65.0,    # kHz
}


def defaults() -> dict[str, float]:
    """Return a copy of the default input values."""
    return dict(DEFAULTS)
