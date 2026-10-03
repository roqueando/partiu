"""E-Series "Valores comerciais" dialog (GUI)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ...tools.eseries import (
    SERIES_NAMES,
    TOLERANCES,
    nearest,
    parse_si,
    series_for_tolerance,
)

#: Component type → (unit symbol, inventory search term).
_COMPONENTS: list[tuple[str, str, str]] = [
    ("Resistor", "Ω", "resistor"),
    ("Inductor", "H", "inductor"),
    ("Capacitor", "F", "capacitor"),
]
_COMPONENT_NAMES = [name for name, _unit, _term in _COMPONENTS]
_COMPONENT_BY_NAME = {name: (unit, term) for name, unit, term in _COMPONENTS}

#: "Auto" series option derives the series from the tolerance.
_AUTO = "Auto (by tolerance)"
_SERIES_CHOICES = [_AUTO, *SERIES_NAMES]

_PREFIXES = [
    (1e-12, "p"),
    (1e-9, "n"),
    (1e-6, "µ"),
    (1e-3, "m"),
    (1.0, ""),
    (1e3, "k"),
    (1e6, "M"),
    (1e9, "G"),
]


def _fmt_si(value: float, unit: str) -> str:
    """Format a SI value with the closest standard prefix (p, n, µ, m, k, M)."""
    if value == 0:
        return f"0 {unit}"
    magnitude = abs(value)
    for factor, prefix in _PREFIXES:
        if magnitude < factor * 1000:
            return f"{value / factor:.4g} {prefix}{unit}"
    return f"{value:.4g} {unit}"


def _deviation(x: float, target: float) -> float:
    """Percent deviation of ``x`` relative to ``target``."""
    return (x - target) / target * 100


def _fmt_dev(x: float, target: float) -> str:
    pct = _deviation(x, target)
    if abs(pct) < 0.005:
        return "0.00%"
    return f"{pct:+.2f}%"


class EseriesToolDialog(tk.Toplevel):
    """Modal dialog: value + tolerance + series in, nearest commercial value out."""

    def __init__(self, master, search_inventory: Callable[[str], None] | None = None):
        super().__init__(master)
        self.title("Valores comerciais")
        self.resizable(False, False)
        self.transient(master)

        self._search_inventory = search_inventory or (lambda _term: None)

        self._comp_var = tk.StringVar(value=_COMPONENT_NAMES[0])
        self._value_var = tk.StringVar(value="1k")
        self._tol_var = tk.StringVar(value="5%")
        self._series_var = tk.StringVar(value=_AUTO)

        self._series_out = tk.StringVar(value="")
        self._chosen_out = tk.StringVar(value="")
        self._lower_out = tk.StringVar(value="")
        self._higher_out = tk.StringVar(value="")
        self._error_var = tk.StringVar(value="")

        self._build_ui()
        self.grab_set()
        self._calculate()

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)

        # ---- inputs (left) ----
        inputs = ttk.LabelFrame(body, text="Entrada", padding=10)
        inputs.pack(side="left", fill="y", padx=(0, 12))

        ttk.Label(inputs, text="Componente").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Combobox(
            inputs, textvariable=self._comp_var, values=_COMPONENT_NAMES,
            state="readonly", width=12,
        ).grid(row=0, column=1, sticky="w", pady=3)

        ttk.Label(inputs, text="Valor").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        value_entry = ttk.Entry(inputs, textvariable=self._value_var, width=12)
        value_entry.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(inputs, text="Tolerância").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Combobox(
            inputs, textvariable=self._tol_var, values=TOLERANCES,
            state="readonly", width=12,
        ).grid(row=2, column=1, sticky="w", pady=3)

        ttk.Label(inputs, text="Série").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Combobox(
            inputs, textvariable=self._series_var, values=_SERIES_CHOICES,
            state="readonly", width=12,
        ).grid(row=3, column=1, sticky="w", pady=3)

        ttk.Button(inputs, text="Calcular", command=self._calculate).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )
        ttk.Label(
            inputs,
            text="Ex.: 4.7k, 100n, 10µ, 1m, 4.7M\n(prefixo SI opcional)",
            foreground="#777",
            justify="left",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # ---- results (right) --
        results = ttk.LabelFrame(body, text="Resultado", padding=10)
        results.pack(side="left", fill="both", expand=True)

        ttk.Label(results, text="Valor comercial").grid(row=0, column=0, sticky="w", padx=(0, 16), pady=1)
        ttk.Label(results, textvariable=self._chosen_out, font=("", 12, "bold")).grid(
            row=0, column=1, sticky="w", pady=1
        )

        ttk.Label(results, text="Abaixo").grid(row=1, column=0, sticky="w", padx=(0, 16), pady=1)
        ttk.Label(results, textvariable=self._lower_out).grid(row=1, column=1, sticky="w", pady=1)

        ttk.Label(results, text="Acima").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=1)
        ttk.Label(results, textvariable=self._higher_out).grid(row=2, column=1, sticky="w", pady=1)

        ttk.Label(results, text="Série utilizada").grid(row=3, column=0, sticky="w", padx=(0, 16), pady=(8, 1))
        ttk.Label(results, textvariable=self._series_out, font=("", 10, "bold")).grid(
            row=3, column=1, sticky="w", pady=(8, 1)
        )

        ttk.Button(
            results, text="Find in inventory…", command=self._find_in_inventory,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

        ttk.Button(results, text="Close", command=self.destroy).grid(
            row=5, column=0, columnspan=2, sticky="e", pady=(4, 0)
        )

        ttk.Label(results, textvariable=self._error_var, foreground="#c00",
                  wraplength=240, justify="left").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        # Recalculate on any change.
        for widget in (value_entry,):
            widget.bind("<Return>", lambda _e: self._calculate())
        for var in (self._comp_var, self._tol_var, self._series_var):
            var.trace_add("write", lambda *_args: self._calculate())

    # -------------------------------------------------------------- calculate

    def _calculate(self) -> None:
        self._error_var.set("")
        unit, _term = _COMPONENT_BY_NAME[self._comp_var.get()]

        raw = self._value_var.get().strip()
        try:
            value = parse_si(raw)
        except ValueError:
            self._error_var.set(f"Valor inválido: {raw!r}")
            return

        series = self._series_var.get()
        if series == _AUTO:
            try:
                series = series_for_tolerance(self._tol_var.get())
            except ValueError as exc:
                self._error_var.set(str(exc))
                return

        try:
            result = nearest(value, series)
        except ValueError as exc:
            self._error_var.set(str(exc))
            return

        self._series_out.set(result.series)
        self._chosen_out.set(
            f"{_fmt_si(result.value, unit)}   ({_fmt_dev(result.value, value)})"
        )
        self._lower_out.set(
            f"{_fmt_si(result.lower, unit)}   ({_fmt_dev(result.lower, value)})"
        )
        self._higher_out.set(
            f"{_fmt_si(result.higher, unit)}   ({_fmt_dev(result.higher, value)})"
        )

    # ---------------------------------------------------------------- actions

    def _find_in_inventory(self) -> None:
        _unit, term = _COMPONENT_BY_NAME[self._comp_var.get()]
        self._search_inventory(term)


def launch(master, db, search_inventory: Callable[[str], None] | None = None) -> None:
    """Open the commercial-values dialog.

    ``db`` is accepted for a uniform tool signature but is unused (the
    "Find in inventory" action is delegated to ``search_inventory``).
    """
    EseriesToolDialog(master, search_inventory=search_inventory)
