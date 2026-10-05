"""Flyback DCM converter calculator dialog (GUI).

Tabs:

* **Flyback DCM** — the converter calculator (existing behaviour).
* **Transformador HF** — high-frequency transformer design based on
  ``M2A2_calc_transf.m``; consumes the converter results from tab 1
  (echoed in the "Dados do conversor" frame). Clicking a table row applies
  the core (``Ae``/``Aw``/``Ae·Aw``) or the wire (``Aco``) to the inputs.
* **Montagem HF** — winding/assembly guide (primary/secondary parallel
  conductors, minimum wire areas, window occupancy) for the design of tab 2,
  using the very same wire/counts so both tabs coincide.
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

#: Converter values echoed in tabs 2/3 so the design inputs are visible:
#: ``(key, label, unit)`` — ``vin``/``freq`` come from the tab 1 fields, the
#: other keys from the converter result (see :data:`_RESULT_SECTIONS`).
_CONV_FEED_FIELDS = [
    ("vin", "Vin (min)", "V"),
    ("freq", "f", "kHz"),
    ("n", "n (razão)", None),
    ("D", "D (recalc)", "%"),
    ("IL1_rms", "IL1 RMS", "A"),
    ("IL1_max", "IL1 máx", "A"),
    ("IL2_rms", "IL2 RMS", "A"),
    ("Pin", "Pin", "W"),
]

#: Assembly tab (Montagem HF) sections: (title, [(key, label, unit)]).
#: Values come from :func:`partiu.tools.transformer.winding_guide`, which
#: mirrors the tab 2 design (same wire, same counts, same ``Exec``).
#: ``unit``: ``"int"`` = integer, ``"raw"`` = 3 decimals (uncut ratio),
#: ``"awg"`` = gauge number, ``"bool"`` = OK/Não, ``"bool_le"`` = Exec ≤ 1.
_ASSEMBLY_SECTIONS = [
    (
        "Fio & entreferro",
        [
            ("wire_awg", "Fio do cálculo", "awg"),
            ("wire_area_iso", "Área com verniz", "cm²"),
            ("wire_dia_iso", "Diâm. com verniz", "cm"),
            ("wire_imax", "Imax do fio", "A"),
            ("entreferro", "Entreferro total", "mm"),
            ("entferr_side", "Entreferro lateral", "mm"),
        ],
    ),
    (
        "Primário (N1)",
        [
            ("N1", "Espiras no primário", "int"),
            ("Awire1", "Área mínima do fio", "cm²"),
            ("N1cond_raw", "Cond. (sem arredondar)", "raw"),
            ("N1cond", "Condutores a bobinar", "int"),
            ("N1cond_rating", "Cond. p/ Imax (Tabela 2)", "int"),
            ("i1_cond", "Corrente por condutor", "A"),
            ("UA1", "Área ocupada", "cm²"),
        ],
    ),
    (
        "Secundário (N2)",
        [
            ("N2", "Espiras no secundário", "int"),
            ("Awire2", "Área mínima do fio", "cm²"),
            ("N2cond_raw", "Cond. (sem arredondar)", "raw"),
            ("N2cond", "Condutores a bobinar", "int"),
            ("N2cond_rating", "Cond. p/ Imax (Tabela 2)", "int"),
            ("i2_cond", "Corrente por condutor", "A"),
            ("UA2", "Área ocupada", "cm²"),
        ],
    ),
    (
        "Verificação da montagem",
        [
            ("Aw_min", "Área necessária", "cm²"),
            ("Aw", "Área disponível", "cm²"),
            ("Exec", "Exec (≤ 1 = OK)", "bool_le"),
            ("core_ok", "Núcleo atende Ae·Aw?", "bool"),
            ("skin_ok", "Limite de skin (15/√f)", "bool"),
            ("cond_ok", "Densidade (Imax do fio)", "bool"),
            ("window_ok", "Cabe na janela?", "bool"),
            ("wire_count", "Total de fios", "int"),
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
    """Format a transformer/assembly result value.

    ``unit`` is ``None`` (plain), ``"float"``, ``"int"``, ``"raw"`` (ratio
    with 3 decimals), ``"awg"`` (gauge), ``"bool"`` (OK/Não),
    ``"bool_le"`` (Exec ≤ 1) or a literal unit string.  ``None`` values (a
    check without data, e.g. a wire outside Tabela 2) render as "—".
    """
    if value is None:
        return "—"
    if unit is None:
        return f"{value:.6g}"
    if unit == "float":
        return f"{value:.4g}"
    if unit == "int":
        return str(int(round(value)))
    if unit == "raw":
        return f"{value:.3f}"
    if unit == "awg":
        return f"{int(round(value))} AWG"
    if unit == "bool":
        return "OK ✓" if value else "Não ✗"
    if unit == "bool_le":
        return f"{value:.3f}  {'OK ✓' if value <= 1 else 'Não ✗'}"
    return f"{value:.4g} {unit}"


class FlybackToolDialog(tk.Toplevel):
    """Modal dialog with three tabs: converter, HF transformer, assembly."""

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
        self._a_out_vars: dict[str, tk.StringVar] = {}
        self._feed_var_sets: list[dict[str, tk.StringVar]] = []
        self._conv_result: dict | None = None
        self._conv_feed: dict | None = None
        self._t_result: dict | None = None
        self._guide: dict | None = None

        self._build_ui()
        self.grab_set()
        self._calculate()

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_calculator_tab(notebook)
        self._build_transformer_tab(notebook)
        self._build_assembly_tab(notebook)

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

        # ---- converter values feeding this design (refreshed on Calculate) ----
        self._build_conv_feed(tab).pack(fill="x", pady=(0, 8))

        # ---- calculations row (inputs left, results right) ----
        top = ttk.Frame(tab)
        top.pack(fill="both", expand=True)

        # ---- inputs (left) ----
        left = ttk.Frame(top)
        left.pack(side="left", fill="y", padx=(0, 12))

        inputs = ttk.LabelFrame(left, text="Parâmetros do transformador", padding=10)
        inputs.pack(fill="x")
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

        # ---- converter feed (above) + table hint (below) ----
        ttk.Label(
            left,
            text=(
                "Clique numa linha das tabelas abaixo para\n"
                "aplicar Ae/Aw ou a Área fio aos campos acima\n"
                "(eles continuam editáveis)."
            ),
            foreground="#777",
            justify="left",
        ).pack(fill="x", pady=(8, 0))

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

        # click/Enter on a row applies it to the inputs above (still editable)
        for tree in (self._core_tree, self._wire_tree):
            tree.bind("<ButtonRelease-1>", lambda _e, t=tree: self._on_row_pick(t))
            tree.bind("<Return>", lambda _e, t=tree: self._on_row_pick(t))

        self._selection_var = tk.StringVar(
            value="Verde = linha aplicada · Azul = recomendada. Clique numa linha para aplicá-la."
        )
        ttk.Label(
            tab, textvariable=self._selection_var, foreground="#0a7d2f"
        ).pack(fill="x", pady=(6, 0))

    # ---------------------------------------------------------------- tab 3

    def _build_assembly_tab(self, notebook) -> None:
        """Winding/assembly guide fed by the transformer design (tab 2)."""
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Montagem HF")

        # ---- converter values feeding the design (same frame as tab 2) ----
        self._build_conv_feed(tab).pack(fill="x", pady=(0, 8))

        # ---- results grid ----
        results = ttk.Frame(tab)
        results.pack(fill="both", expand=True)
        for col in range(2):
            results.columnconfigure(col, weight=1)

        for index, (sec_title, fields) in enumerate(_ASSEMBLY_SECTIONS):
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
                self._a_out_vars[key] = var

        # ---- step-by-step winding instructions ----
        guide_frame = ttk.LabelFrame(tab, text="Passo a passo da bobinagem", padding=8)
        guide_frame.pack(fill="both", expand=True, pady=(4, 0))

        self._guide_text = tk.Text(
            guide_frame,
            width=78,
            height=7,
            wrap="word",
            relief="flat",
            background=self.cget("background"),
            font=("", 10),
            state="disabled",
            cursor="arrow",
        )
        self._guide_text.tag_configure("step", lmargin1=18, lmargin2=18, spacing3=3)
        self._guide_text.tag_configure("warn", foreground="#a33", lmargin1=18, lmargin2=18)
        self._guide_text.tag_configure("ok", foreground="#0a7d2f", lmargin1=18, lmargin2=18)
        self._guide_text.pack(fill="both", expand=True)

        footer = ttk.Frame(tab)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(
            footer,
            text=(
                "Mesmos valores da aba Transformador HF (fio do cálculo);\n"
                "limite de skin (15/√f) e Imax da Tabela 2 são conferências."
            ),
            foreground="#777",
            justify="left",
        ).pack(side="left")
        ttk.Button(footer, text="Close", command=self.destroy).pack(side="right")

    def _build_table(self, parent, headers, rows, iids):
        """Create a scrollable Treeview table and return it."""
        cols = [c[0] for c in headers]
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for col_id, title, anchor in headers:
            tree.heading(col_id, text=title)
            tree.column(col_id, anchor=anchor, width=140 if col_id in ("name", "awg") else 110)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for iid, values in zip(iids, rows):
            tree.insert("", "end", iid=iid, values=values)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        tree.tag_configure("selected", background="#cde8cd", font=("", 10, "bold"))
        tree.tag_configure("recommended", background="#cfe3f7")
        return tree

    # ------------------------------------------------------- converter feed

    def _build_conv_feed(self, parent) -> ttk.LabelFrame:
        """Frame echoing the tab 1 values consumed by this design.

        A frame is created per tab, each with its own vars (all of them are
        refreshed together by :meth:`_update_conv_feed`).
        """
        frame = ttk.LabelFrame(
            parent,
            text="Dados do conversor (aba Flyback DCM, atualizado a cada Calculate)",
            padding=8,
        )
        vars_: dict[str, tk.StringVar] = {}
        for i, (key, label, _unit) in enumerate(_CONV_FEED_FIELDS):
            ttk.Label(frame, text=label).grid(
                row=0, column=i * 2, sticky="w", padx=(0, 5), pady=1
            )
            var = tk.StringVar(value="—")
            ttk.Label(frame, textvariable=var, font=("", 10, "bold")).grid(
                row=0, column=i * 2 + 1, sticky="w", padx=(0, 14), pady=1
            )
            vars_[key] = var
        self._feed_var_sets.append(vars_)
        return frame

    def _update_conv_feed(self) -> None:
        """Refresh the echoed converter values (after a converter recalc)."""
        for vars_ in self._feed_var_sets:
            for key, _label, unit in _CONV_FEED_FIELDS:
                if self._conv_feed is None or self._conv_result is None:
                    vars_[key].set("—")
                    continue
                value = (
                    self._conv_feed[key]
                    if key in ("vin", "freq")
                    else self._conv_result[key]
                )
                vars_[key].set(_fmt(value, unit))

    def _calculate(self) -> None:
        """Recompute converter (tab 1), transformer (tab 2), assembly (tab 3)."""
        if not self._calculate_converter():
            return
        if not self._calculate_transformer():
            return
        self._calculate_assembly()

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
        self._conv_feed = {"vin": vin, "freq": freq / 1000}
        for _sec_title, _btn_label, _search_key, fields in _RESULT_SECTIONS:
            for key, _label, unit in fields:
                self._out_vars[key].set(_fmt(result[key], unit))
        self._update_conv_feed()
        return True

    def _calculate_transformer(self) -> bool:
        if self._conv_result is None:
            return False

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
            return False

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
            return False

        for _sec_title, fields in _TRANSF_RESULT_SECTIONS:
            for key, _label, unit in fields:
                self._t_out_vars[key].set(_fmt_tf(t_result[key], unit))

        self._t_result = t_result
        self._update_tables(t_result, ae=ae, aw=aw, aco_iso=aco_iso)
        return True

    # ------------------------------------------------------------- assembly

    def _calculate_assembly(self) -> None:
        """Fill the Montagem HF tab from the transformer design (tab 2)."""
        if self._t_result is None:
            return

        guide = transf.winding_guide(self._t_result)
        self._guide = guide
        for _sec_title, fields in _ASSEMBLY_SECTIONS:
            for key, _label, unit in fields:
                self._a_out_vars[key].set(_fmt_tf(guide[key], unit))
        self._set_guide(self._guide_lines(guide))

    def _guide_lines(self, g: dict) -> list[tuple[str, str]]:
        """Build the step-by-step winding instructions (tag, text) pairs."""
        awg = g["wire_awg"]
        wire_txt = (
            f"{awg} AWG"
            if awg is not None
            else f"{g['wire_area_iso']:.4g} cm² (personalizado)"
        )
        area = g["wire_area_iso"]
        n1, n2 = g["N1"], g["N2"]
        c1, c2 = g["N1cond"], g["N2cond"]
        core = g["core_name"] or "personalizado"
        lines: list[tuple[str, str]] = [
            (
                "step",
                f"1. Primário: bobinar {n1} espiras com {c1} fio(s) {wire_txt} "
                "em paralelo (torsionados).",
            ),
            (
                "step",
                f"   Área mínima do fio: {g['Awire1']:.4g} cm² → "
                f"{c1} × {area:.4g} cm² = {c1 * area:.4g} cm².",
            ),
            (
                "step",
                f"2. Secundário: bobinar {n2} espiras com {c2} fio(s) {wire_txt} "
                "em paralelo (torsionados).",
            ),
            (
                "step",
                f"   Área mínima do fio: {g['Awire2']:.4g} cm² → "
                f"{c2} × {area:.4g} cm² = {c2 * area:.4g} cm².",
            ),
            (
                "step",
                f"3. Núcleo {core}: entreferro de {g['entreferro']:.4g} mm no total, "
                f"{g['entferr_side']:.4g} mm em cada lateral.",
            ),
            (
                "step",
                f"4. Janela: ocupa {g['Aw_min']:.4g} cm² de {g['Aw']:g} cm² "
                f"(Exec = {g['Exec']:.3f}).",
            ),
        ]

        # ---- checks against the Tabela 1/Tabela 2 limits (advisory only) ----
        if not g["core_ok"]:
            lines.append(
                (
                    "warn",
                    f"⚠ O núcleo aplicado não cobre o Ae·Aw necessário "
                    f"({g['AeAw_use']:.4g} < {g['AeAw']:.4g} cm⁴) — escolha um "
                    "maior na Tabela 1.",
                )
            )
        if not g["wire_found"]:
            lines.append(
                (
                    "warn",
                    "⚠ Fio fora da Tabela 2 (área personalizada): Imax e limite "
                    "de skin não puderam ser conferidos.",
                )
            )
        elif g["skin_ok"] is False:
            lines.append(
                (
                    "warn",
                    f"⚠ Diâmetro do fio {g['wire_dia_iso']:g} cm excede o limite "
                    f"de skin {g['Dia_max']:.4g} cm (15/√f) — troque de fio.",
                )
            )
        if g["cond_ok"] is False:
            lines.append(
                (
                    "warn",
                    f"⚠ Pelo Imax do fio ({g['wire_imax']:g} A) seriam "
                    f"{g['N1cond_rating']} condutores no primário e "
                    f"{g['N2cond_rating']} no secundário; o cálculo usa {c1} e {c2}.",
                )
            )
        elif g["cond_ok"] is True:
            lines.append(
                (
                    "ok",
                    f"✓ Densidade de corrente: {g['i1_cond']:.3f} A (prim.) e "
                    f"{g['i2_cond']:.3f} A (sec.) por condutor, "
                    f"Imax = {g['wire_imax']:g} A.",
                )
            )
        lines.append(
            (
                "ok" if g["window_ok"] else "warn",
                f"{'✓' if g['window_ok'] else '⚠'} "
                + (
                    "O transformador cabe na janela do núcleo."
                    if g["window_ok"]
                    else "A janela do núcleo NÃO comporta os enrolamentos — use outro núcleo."
                ),
            )
        )
        return lines

    def _set_guide(self, lines: list[tuple[str, str]]) -> None:
        """Replace the step-by-step text widget contents."""
        self._guide_text.configure(state="normal")
        self._guide_text.delete("1.0", "end")
        for tag, text in lines:
            self._guide_text.insert("end", text + "\n", tag)
        self._guide_text.configure(state="disabled")

    # ------------------------------------------------------------- selection

    def _on_row_pick(self, tree: ttk.Treeview) -> None:
        """Apply the clicked Tabela 1/Tabela 2 row to the transformer inputs.

        The fields keep being plain entries, so the applied values can still
        be edited freely (a custom value simply clears the highlight).
        """
        selection = tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if tree is self._core_tree:
            _name, ae, aw, ae_aw = transf.EE_CORES[index]
            self._t_in_vars["ae"].set(f"{ae:g}")
            self._t_in_vars["aw"].set(f"{aw:g}")
            self._t_in_vars["ae_aw_use"].set(f"{ae_aw:g}")
        else:
            self._t_in_vars["aco_iso"].set(f"{transf.AWG_WIRES[index][4]:g}")
        self._calculate()

    def _update_tables(
        self, t_result: dict, *, ae: float, aw: float, aco_iso: float
    ) -> None:
        """Mark the applied row (green) and the recommendation (blue).

        ``applied`` comes from the tab 2 inputs (what the design really uses);
        ``recommended`` is :func:`select_core`/:func:`select_wire`, shown only
        when it differs from the applied row.
        """
        applied_core = transf.match_core(ae, aw)
        applied_wire = transf.match_wire(aco_iso)
        rec_core = transf.select_core(t_result["AeAw"])
        rec_wire = transf.select_wire(t_result["Dia_max"])

        self._highlight(
            self._core_tree,
            None if applied_core is None else transf.EE_CORES.index(applied_core),
            None if rec_core is None else transf.EE_CORES.index(rec_core),
        )
        self._highlight(
            self._wire_tree,
            None if applied_wire is None else transf.AWG_WIRES.index(applied_wire),
            None if rec_wire is None else transf.AWG_WIRES.index(rec_wire),
        )

        parts = []
        if applied_core is None:
            parts.append(f"Núcleo aplicado: personalizado (Ae·Aw = {ae * aw:.4g} cm⁴)")
        else:
            parts.append(f"Núcleo aplicado: {applied_core[0]}")
        if rec_core is None:
            parts.append("nenhum núcleo da Tabela 1 cobre o Ae·Aw necessário")
        elif rec_core is not applied_core:
            parts.append(
                f"recomendado: {rec_core[0]} (Ae·Aw = {rec_core[3]:g} ≥ "
                f"{t_result['AeAw']:.4g} cm⁴)"
            )

        if applied_wire is None:
            parts.append(f"fio aplicado: personalizado ({aco_iso:.4g} cm²)")
        else:
            parts.append(f"fio aplicado: {applied_wire[0]} AWG")
        if rec_wire is None:
            parts.append("nenhum fio da Tabela 2 cabe no limite de skin")
        elif rec_wire is not applied_wire:
            parts.append(
                f"recomendado: {rec_wire[0]} AWG (diâm. isol. = {rec_wire[3]:g} ≤ "
                f"{t_result['Dia_max']:.4g} cm)"
            )
        self._selection_var.set("   ·   ".join(parts))

    @staticmethod
    def _highlight(
        tree: ttk.Treeview, index: int | None, rec_index: int | None = None
    ) -> None:
        """Green = row applied to the inputs, blue = recommendation (if other)."""
        for iid in tree.get_children():
            tree.item(iid, tags=())
        tree.selection_remove(tree.get_children())
        if rec_index is not None and rec_index != index:
            tree.item(str(rec_index), tags=("recommended",))
        if index is None:
            if rec_index is not None:
                tree.see(str(rec_index))
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
