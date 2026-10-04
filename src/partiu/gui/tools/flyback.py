"""Flyback DCM converter calculator dialog (GUI).

Tabs:

* **Flyback DCM** — the converter calculator (existing behaviour).
* **Transformador HF** — high-frequency transformer design based on
  ``M2A2_calc_transf.m``; consumes the converter results from tab 1.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from ...tools.flyback import calculate, defaults
from ...tools import transformer as transf
from ...tools.transformer import design as transf_design

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

#: Transformer tab input fields: (key, label, unit) — keys match
#: :mod:`partiu.tools.transformer` ``DEFAULTS``.
_TRANSF_INPUT_FIELDS = [
    ("kw", "Kw (util. janela)", "–"),
    ("kp", "Kp (util. primário)", "–"),
    ("jmax", "Jmax (densidade)", "A/cm²"),
    ("del_b", "DelB (ΔB)", "T"),
    ("ae", "Ae (seção núcleo)", "cm²"),
    ("aw", "Aw (janela núcleo)", "cm²"),
    ("ae_aw_use", "Ae·Aw do núcleo", "cm⁴"),
    ("aco_iso", "Área fio (com verniz)", "cm²"),
]

#: Transformer result sections: (title, [(key, label, unit)]).
#: ``unit``: ``None`` = plain number, ``"int"`` = integer, ``"bool"`` = OK/Não,
#: ``"%"`` = percentage.
_TRANSF_RESULT_SECTIONS = [
    (
        "Núcleo (Ae·Aw)",
        [
            ("AeAw", "Ae·Aw necessário", "cm⁴"),
            ("AeAw_use", "Ae·Aw do núcleo", "cm⁴"),
            ("AeAw_margin", "Margem (use/req.)", "x"),
            ("AeAw_ok", "Núcleo atende?", "bool"),
        ],
    ),
    (
        "Entreferro & espiras",
        [
            ("DelW", "Variação de energia", "J"),
            ("entreferro", "Entreferro total", "mm"),
            ("entferr_side", "Entreferro lateral", "mm"),
            ("B_gauss", "ΔB", "G"),
            ("N1", "Espiras primário (N1)", "float"),
            ("N1_int", "N1 (inteiro)", "int"),
            ("N2", "Espiras secundário (N2)", "float"),
            ("N2_int", "N2 (inteiro)", "int"),
        ],
    ),
    (
        "Fiação",
        [
            ("Awire1", "Área fio primário", "cm²"),
            ("N1cond", "Cond. paralelo prim.", "int"),
            ("Awire2", "Área fio secundário", "cm²"),
            ("N2cond", "Cond. paralelo sec.", "int"),
            ("Dia_max", "Diâmetro máx. condutor", "cm"),
        ],
    ),
    (
        "Verificação de janela",
        [
            ("UA1", "Área ocup. primário", "cm²"),
            ("UA2", "Área ocup. secundário", "cm²"),
            ("Aw_min", "Área necessária", "cm²"),
            ("Aw", "Área disponível", "cm²"),
            ("Exec", "Exec (≤ 1 = OK)", "bool_le"),
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


def _fmt_tf(value, unit: str | None) -> str:
    """Format a transformer result value.

    ``unit`` is ``None`` (plain), ``"float"``, ``"int"``, ``"bool"`` (OK/Não),
    ``"bool_le"`` (Exec ≤ 1) or a literal unit string.
    """
    if unit is None:
        return f"{value:.6g}"
    if unit == "float":
        return f"{value:.4g}"
    if unit == "int":
        return str(int(round(value)))
    if unit == "bool":
        return "OK ✓" if value else "Não ✗"
    if unit == "bool_le":
        return f"{value:.3f}  {'OK ✓' if value <= 1 else 'Não ✗'}"
    return f"{value:.4g} {unit}"


class FlybackToolDialog(tk.Toplevel):
    """Modal dialog with two tabs: flyback calculator + HF transformer design."""

    def __init__(self, master, search_inventory: Callable[[str], None] | None = None):
        super().__init__(master)
        self.title("Flyback DCM calculator")
        self.resizable(False, False)
        self.transient(master)

        self._search_inventory = search_inventory or (lambda _term: None)
        self._in_vars: dict[str, tk.StringVar] = {}
        self._out_vars: dict[str, tk.StringVar] = {}
        self._t_in_vars: dict[str, tk.StringVar] = {}
        self._t_out_vars: dict[str, tk.StringVar] = {}
        self._conv_result: dict | None = None

        self._build_ui()
        self.grab_set()
        self._calculate()

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_calculator_tab(notebook)
        self._build_transformer_tab(notebook)

    # ---------------------------------------------------------------- tab 1

    def _build_calculator_tab(self, notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Flyback DCM")

        # ---- inputs (left) ----
        inputs = ttk.LabelFrame(tab, text="Parâmetros do conversor", padding=10)
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
        results = ttk.Frame(tab)
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

    # ---------------------------------------------------------------- tab 2

    def _build_transformer_tab(self, notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Transformador HF")

        # ---- calculations row (inputs left, results right) ----
        top = ttk.Frame(tab)
        top.pack(fill="both", expand=True)

        # ---- inputs (left) ----
        inputs = ttk.LabelFrame(top, text="Parâmetros do transformador", padding=10)
        inputs.pack(side="left", fill="y", padx=(0, 12))

        t_defaults = transf.defaults()
        for i, (key, label, unit) in enumerate(_TRANSF_INPUT_FIELDS):
            ttk.Label(inputs, text=label).grid(
                row=i, column=0, sticky="w", padx=(0, 8), pady=3
            )
            var = tk.StringVar(value=str(t_defaults[key]))
            ttk.Entry(inputs, textvariable=var, width=10).grid(
                row=i, column=1, sticky="w", pady=3
            )
            ttk.Label(inputs, text=unit).grid(
                row=i, column=2, sticky="w", padx=(4, 0), pady=3
            )
            self._t_in_vars[key] = var

        ttk.Button(inputs, text="Calculate", command=self._calculate).grid(
            row=len(_TRANSF_INPUT_FIELDS), column=0, columnspan=3,
            sticky="ew", pady=(8, 0),
        )
        ttk.Label(
            inputs,
            text=(
                "Os dados do conversor (D, Vin, IL1_rms,\n"
                "IL1_max, IL2_rms, Pin, f, n) são os da\n"
                "tab Flyback DCM — calcule lá primeiro."
            ),
            foreground="#777",
            justify="left",
        ).grid(
            row=len(_TRANSF_INPUT_FIELDS) + 1, column=0, columnspan=3,
            sticky="w", pady=(8, 0),
        )

        # ---- results (right) --
        results = ttk.Frame(top)
        results.pack(side="left", fill="both", expand=True)
        results.columnconfigure(0, weight=1)
        results.columnconfigure(1, weight=1)

        for index, (sec_title, fields) in enumerate(_TRANSF_RESULT_SECTIONS):
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
                self._t_out_vars[key] = var

        ttk.Button(results, text="Close", command=self.destroy).grid(
            row=2, column=0, columnspan=2, sticky="e", pady=(4, 0)
        )

        # ---- reference tables (below the calculations) ----
        tables = ttk.Notebook(tab)
        tables.pack(fill="both", expand=True, pady=(12, 0))

        cores_frame = ttk.Frame(tables, padding=8)
        tables.add(cores_frame, text="Tabela 1 — Núcleos EE")
        self._core_tree = self._build_table(
            cores_frame,
            headers=(
                ("name", "Núcleo", "w"),
                ("ae", "Ae [cm²]", "e"),
                ("aw", "Aw [cm²]", "e"),
                ("aeaw", "Ae·Aw [cm⁴]", "e"),
            ),
            rows=[(f"{n}", f"{ae:g}", f"{aw:g}", f"{aeaw:g}")
                  for n, ae, aw, aeaw in transf.EE_CORES],
            iids=[str(i) for i in range(len(transf.EE_CORES))],
        )

        wires_frame = ttk.Frame(tables, padding=8)
        tables.add(wires_frame, text="Tabela 2 — Fios AWG")
        self._wire_tree = self._build_table(
            wires_frame,
            headers=(
                ("awg", "AWG", "e"),
                ("dcu", "Diâm. cobre [cm]", "e"),
                ("acu", "Área cobre [cm²]", "e"),
                ("diso", "Diâm. isol. [cm]", "e"),
                ("aiso", "Área isol. [cm²]", "e"),
                ("imax", "Imax [A]", "e"),
            ),
            rows=[(str(a), f"{dcu:g}", f"{acu:g}", f"{diso:g}", f"{aiso:g}", f"{imax:g}")
                  for a, dcu, acu, diso, aiso, imax in transf.AWG_WIRES],
            iids=[str(i) for i in range(len(transf.AWG_WIRES))],
        )

        self._selection_var = tk.StringVar(value="Selecione Calculate para escolher.")
        ttk.Label(
            tab, textvariable=self._selection_var, foreground="#0a7d2f"
        ).pack(fill="x", pady=(6, 0))

    def _build_table(self, parent, headers, rows, iids):
        """Create a scrollable Treeview table and return it."""
        cols = [c[0] for c in headers]
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for col_id, title, anchor in headers:
            tree.heading(col_id, text=title)
            tree.column(col_id, anchor=anchor, width=140 if col_id in ("name", "awg") else 110)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.tag_configure("selected", background="#cde8cd", font=("", 10, "bold"))

        for iid, values in zip(iids, rows):
            tree.insert("", "end", iid=iid, values=values)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        return tree

    def _calculate(self) -> None:
        """Recompute the converter (tab 1) and, from it, the transformer (tab 2)."""
        if not self._calculate_converter():
            return
        self._calculate_transformer()

    def _calculate_converter(self) -> bool:
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
            return False

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
            return False

        self._conv_result = result
        for _sec_title, _btn_label, _search_key, fields in _RESULT_SECTIONS:
            for key, _label, unit in fields:
                self._out_vars[key].set(_fmt(result[key], unit))
        return True

    def _calculate_transformer(self) -> None:
        if self._conv_result is None:
            return

        try:
            kw = float(self._t_in_vars["kw"].get())
            kp = float(self._t_in_vars["kp"].get())
            jmax = float(self._t_in_vars["jmax"].get())
            del_b = float(self._t_in_vars["del_b"].get())
            ae = float(self._t_in_vars["ae"].get())
            aw = float(self._t_in_vars["aw"].get())
            ae_aw_use = float(self._t_in_vars["ae_aw_use"].get())
            aco_iso = float(self._t_in_vars["aco_iso"].get())
            vin = float(self._in_vars["vin"].get())
            freq = float(self._in_vars["freq"].get()) * 1000
        except ValueError:
            messagebox.showerror(
                "Invalid input", "Todos os campos do transformador devem ser numéricos."
            )
            return

        conv = self._conv_result
        try:
            t_result = transf_design(
                duty=conv["D"],
                vin=vin,
                il1_rms=conv["IL1_rms"],
                il1_max=conv["IL1_max"],
                il2_rms=conv["IL2_rms"],
                pin=conv["Pin"],
                freq=freq,
                n=conv["n"],
                kw=kw,
                kp=kp,
                jmax=jmax,
                del_b=del_b,
                ae=ae,
                aw=aw,
                ae_aw_use=ae_aw_use,
                aco_iso=aco_iso,
            )
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        for _sec_title, fields in _TRANSF_RESULT_SECTIONS:
            for key, _label, unit in fields:
                self._t_out_vars[key].set(_fmt_tf(t_result[key], unit))

        self._update_tables(t_result, freq)

    # ------------------------------------------------------------- selection

    def _update_tables(self, t_result: dict, freq: float) -> None:
        """Highlight the recommended core (Tabela 1) and wire (Tabela 2)."""
        core = transf.select_core(t_result["AeAw"])
        wire = transf.select_wire(t_result["Dia_max"])

        self._highlight(self._core_tree, None if core is None else transf.EE_CORES.index(core))
        self._highlight(self._wire_tree, None if wire is None else transf.AWG_WIRES.index(wire))

        parts = []
        if core is None:
            parts.append("Nenhum núcleo da Tabela 1 cobre o Ae·Aw necessário")
        else:
            parts.append(
                f"Núcleo selecionado: {core[0]} "
                f"(Ae·Aw = {core[3]:g} ≥ {t_result['AeAw']:.4g} cm⁴)"
            )
        if wire is None:
            parts.append("nenhum fio da Tabela 2 cabe no limite de skin")
        else:
            parts.append(
                f"Fio selecionado: {wire[0]} AWG "
                f"(diâm. isol. = {wire[3]:g} cm ≤ {t_result['Dia_max']:.4g} cm)"
            )
        self._selection_var.set("   ·   ".join(parts))

    @staticmethod
    def _highlight(tree: ttk.Treeview, index: int | None) -> None:
        """Select (and scroll to) row ``index``; clear the selection if ``None``."""
        for iid in tree.get_children():
            tree.item(iid, tags=())
        tree.selection_remove(tree.get_children())
        if index is None:
            return
        iid = str(index)
        tree.selection_set(iid)
        tree.item(iid, tags=("selected",))
        tree.see(iid)




def launch(master, db, search_inventory: Callable[[str], None] | None = None) -> None:
    """Open the flyback calculator dialog.

    ``db`` is accepted for a uniform tool signature but is unused by this tool
    (the "Find in inventory" actions are delegated to ``search_inventory``).
    """
    FlybackToolDialog(master, search_inventory=search_inventory)
