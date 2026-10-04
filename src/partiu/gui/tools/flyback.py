"""Flyback DCM converter calculator dialog (GUI)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from ...tools.flyback import calculate, defaults

#: Suggested free-text terms used by "Find in inventory" (Parts search).
_SEARCH_TERMS = {
    "inductor": "transformer",
    "mosfet": "MOSFET",
    "diode": "diode",
    "capacitor": "capacitor",
}

#: Input fields: (key, label, unit shown to the right of the entry).
_INPUT_FIELDS = [
    ("vin", "Vin (min)", "V"),
    ("vin_max", "Vin (max)", "V"),
    ("vout", "Vout", "V"),
    ("iout", "Iout", "A"),
    ("ripple", "Ripple", "%"),
    ("eta", "Efficiency (η)", "%"),
    ("duty", "Duty cycle (D)", "%"),
    ("freq", "Frequency (f)", "kHz"),
]

#: Result sections: (title, search button label, search key, [(key, label, unit)]).
#: ``unit`` of ``None`` means dimensionless (turns ratio); ``"%"`` means percentage.
_RESULT_SECTIONS = [
    (
        "Conversor DC-DC",
        "Find inductor / transformer…",
        "inductor",
        [
            ("RL", "Load resistance", "Ω"),
            ("Pout", "Output power", "W"),
            ("Pin", "Input power", "W"),
            ("n", "Turns ratio (n)", None),
            ("D", "Duty cycle (recalc)", "%"),
            ("D_min", "Duty cycle (min)", "%"),
        ],
    ),
    (
        "Primário (L1 / MOSFET)",
        "Find MOSFET…",
        "mosfet",
        [
            ("IL1_max", "L1 max current", "A"),
            ("IL1_avg", "L1 avg current", "A"),
            ("IL1_rms", "L1 RMS current", "A"),
            ("L1", "L1 inductance", "H"),
            ("Vds_max", "Vds max @ Vin", "V"),
            ("Vds_max_vinmax", "Vds max @ Vin_max", "V"),
        ],
    ),
    (
        "Secundário (L2 / Diodo)",
        "Find diode…",
        "diode",
        [
            ("IL2_max", "L2 max current", "A"),
            ("IL2_avg", "L2 avg current", "A"),
            ("IL2_rms", "L2 RMS current", "A"),
            ("L2", "L2 inductance", "H"),
            ("VD_max", "Diode reverse voltage", "V"),
        ],
    ),
    (
        "Capacitor de saída",
        "Find capacitor…",
        "capacitor",
        [
            ("delta_Vout", "Output ripple (ΔVout)", "V"),
            ("C", "Output capacitance", "F"),
            ("IC_rms", "Capacitor RMS current", "A"),
        ],
    ),
]

_PREFIXES = [
    (1e-9, "n"),
    (1e-6, "µ"),
    (1e-3, "m"),
    (1.0, ""),
    (1e3, "k"),
    (1e6, "M"),
]


def _fmt_si(value: float, unit: str) -> str:
    """Format a SI value with the closest standard prefix (µ, m, k, …)."""
    if value == 0:
        return f"0 {unit}"
    magnitude = abs(value)
    for factor, prefix in _PREFIXES:
        if magnitude < factor * 1000:
            return f"{value / factor:.4g} {prefix}{unit}"
    return f"{value:.4g} {unit}"


def _fmt(value, unit: str | None) -> str:
    if unit is None:
        return str(int(round(value)))
    if unit == "%":
        return f"{value * 100:.2f} %"
    return _fmt_si(value, unit)


class FlybackToolDialog(tk.Toplevel):
    """Modal dialog: inputs on the left, computed results on the right."""

    def __init__(self, master, search_inventory: Callable[[str], None] | None = None):
        super().__init__(master)
        self.title("Flyback DCM calculator")
        self.resizable(False, False)
        self.transient(master)

        self._search_inventory = search_inventory or (lambda _term: None)
        self._in_vars: dict[str, tk.StringVar] = {}
        self._out_vars: dict[str, tk.StringVar] = {}

        self._build_ui()
        self.grab_set()
        self._calculate()

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)

        # ---- inputs (left) ----
        inputs = ttk.LabelFrame(body, text="Parâmetros do conversor", padding=10)
        inputs.pack(side="left", fill="y", padx=(0, 12))

        defaults_ = defaults()
        for i, (key, label, unit) in enumerate(_INPUT_FIELDS):
            ttk.Label(inputs, text=label).grid(
                row=i, column=0, sticky="w", padx=(0, 8), pady=3
            )
            var = tk.StringVar(value=str(defaults_[key]))
            ttk.Entry(inputs, textvariable=var, width=10).grid(
                row=i, column=1, sticky="w", pady=3
            )
            ttk.Label(inputs, text=unit).grid(
                row=i, column=2, sticky="w", padx=(4, 0), pady=3
            )
            self._in_vars[key] = var

        ttk.Button(inputs, text="Calculate", command=self._calculate).grid(
            row=len(_INPUT_FIELDS), column=0, columnspan=3, sticky="ew", pady=(8, 0)
        )
        ttk.Label(
            inputs,
            text="Dica: dimensione Iout com margem\n(ex.: 25% acima, como no projeto).",
            foreground="#777",
            justify="left",
        ).grid(row=len(_INPUT_FIELDS) + 1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # ---- results (right) --
        results = ttk.Frame(body)
        results.pack(side="left", fill="both", expand=True)
        results.columnconfigure(0, weight=1)
        results.columnconfigure(1, weight=1)

        for index, (sec_title, btn_label, search_key, fields) in enumerate(_RESULT_SECTIONS):
            grid_row, grid_col = divmod(index, 2)
            frame = ttk.LabelFrame(results, text=sec_title, padding=8)
            frame.grid(
                row=grid_row,
                column=grid_col,
                sticky="nsew",
                padx=(0 if grid_col == 0 else 8, 0),
                pady=(0, 8),
            )

            for row, (key, label, unit) in enumerate(fields):
                ttk.Label(frame, text=label).grid(
                    row=row, column=0, sticky="w", padx=(0, 16), pady=1
                )
                var = tk.StringVar(value="")
                ttk.Label(frame, textvariable=var, font=("", 11, "bold")).grid(
                    row=row, column=1, sticky="w", pady=1
                )
                self._out_vars[key] = var

            ttk.Button(
                frame,
                text=btn_label,
                command=lambda k=search_key: self._search_inventory(_SEARCH_TERMS[k]),
            ).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Button(results, text="Close", command=self.destroy).grid(
            row=2, column=0, columnspan=2, sticky="e", pady=(4, 0)
        )

        # ---- schematic (bottom) ----
        # Schematic rendering removed as requested.

    # -------------------------------------------------------------- calculate

    def _calculate(self) -> None:
        try:
            vin = float(self._in_vars["vin"].get())
            vin_max = float(self._in_vars["vin_max"].get())
            vout = float(self._in_vars["vout"].get())
            iout = float(self._in_vars["iout"].get())
            ripple = float(self._in_vars["ripple"].get()) / 100
            eta = float(self._in_vars["eta"].get()) / 100
            duty = float(self._in_vars["duty"].get()) / 100
            freq = float(self._in_vars["freq"].get()) * 1000
        except ValueError:
            messagebox.showerror(
                "Invalid input", "Todos os campos devem ser numéricos."
            )
            return

        try:
            result = calculate(
                vin=vin,
                vin_max=vin_max,
                vout=vout,
                iout=iout,
                ripple=ripple,
                eta=eta,
                duty=duty,
                freq=freq,
            )
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        for _sec_title, _btn_label, _search_key, fields in _RESULT_SECTIONS:
            for key, _label, unit in fields:
                self._out_vars[key].set(_fmt(result[key], unit))




def launch(master, db, search_inventory: Callable[[str], None] | None = None) -> None:
    """Open the flyback calculator dialog.

    ``db`` is accepted for a uniform tool signature but is unused by this tool
    (the "Find in inventory" actions are delegated to ``search_inventory``).
    """
    FlybackToolDialog(master, search_inventory=search_inventory)
