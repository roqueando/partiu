"""PIC10/12/16 programmer tool (kitsrus K150) — GUI dialog.

A single self-contained :class:`tkinter.Toplevel` that talks to a kitsrus K150
over its virtual COM port: pick a port + device, load a ``.hex``, and run
**Detectar / Verificar vazio / Ler / Verificar / Gravar / Apagar**.  Operations
run on a worker thread and stream log lines back to the dialog, so the UI never
freezes during a program/verify cycle.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from ...adapters.kitsrus_k150 import Connection, KitsrusProgrammer, ProgrammerError
from ...adapters.pic_device_catalog import KitsrusDeviceCatalog
from ...application.use_cases import pic_program as uc
from ...domain.engineering.pic import (
    HexError,
    build_image,
    format_hex,
    image_to_records,
    parse_hex,
)

_HEX_FILETYPES = [("Intel HEX", "*.hex"), ("Todos os arquivos", "*.*")]


class PicProgrammerDialog(tk.Toplevel):
    """Programming dialog for PIC10/12/16 via a kitsrus K150."""

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("Programador PIC10/12/16 (K150)")
        self.transient(master)
        self.geometry("780x640")

        self._catalog = KitsrusDeviceCatalog()
        self._connection: Connection | None = None
        self._image = None                # PicMemoryImage (loaded HEX)
        self._image_spec = None           # DeviceSpec the image was built with
        self._last_read = None            # PicMemoryImage from the last Read
        self._last_read_spec = None

        self._busy = False
        self._events: queue.Queue[tuple] = queue.Queue()
        self._op_buttons: list[ttk.Button] = []

        self._port_var = tk.StringVar(value="")
        self._device_var = tk.StringVar(value="")
        self._status_var = tk.StringVar(value="Desconectado")
        self._hex_var = tk.StringVar(value="Nenhum arquivo carregado")

        self._build_ui()
        self._refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        # ---- connection -------------------------------------------------
        conn = ttk.LabelFrame(body, text="Conexão", padding=8)
        conn.pack(fill="x")
        ttk.Label(conn, text="Porta").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._port_combo = ttk.Combobox(
            conn, textvariable=self._port_var, state="readonly", width=28
        )
        self._port_combo.grid(row=0, column=1, sticky="w")
        ttk.Button(conn, text="Atualizar", command=self._refresh_ports).grid(
            row=0, column=2, padx=6
        )
        self._connect_btn = ttk.Button(conn, text="Conectar", command=self._connect)
        self._connect_btn.grid(row=0, column=3, padx=(0, 6))
        self._disconnect_btn = ttk.Button(
            conn, text="Desconectar", command=self._disconnect, state="disabled"
        )
        self._disconnect_btn.grid(row=0, column=4)
        ttk.Label(conn, textvariable=self._status_var, foreground="#006633").grid(
            row=1, column=0, columnspan=5, sticky="w", pady=(6, 0)
        )

        # ---- device -----------------------------------------------------
        dev = ttk.LabelFrame(body, text="Dispositivo", padding=8)
        dev.pack(fill="x", pady=(8, 0))
        ttk.Label(dev, text="PIC").grid(row=0, column=0, sticky="w", padx=(0, 6))
        names = self._catalog.names()
        self._device_var.set(names[0] if names else "")
        self._device_combo = ttk.Combobox(
            dev, textvariable=self._device_var, values=names, state="readonly", width=20
        )
        self._device_combo.grid(row=0, column=1, sticky="w")
        self._device_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_device_changed())
        ttk.Label(
            dev,
            text="— core type / power / erase configurados no catálogo do K150",
            foreground="#666666",
        ).grid(row=0, column=2, sticky="w", padx=12)

        # ---- HEX file ---------------------------------------------------
        hexf = ttk.LabelFrame(body, text="Arquivo HEX", padding=8)
        hexf.pack(fill="x", pady=(8, 0))
        ttk.Button(hexf, text="Abrir HEX…", command=self._load_hex).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Label(hexf, textvariable=self._hex_var, foreground="#333333").grid(
            row=0, column=1, sticky="w"
        )

        # ---- operations -------------------------------------------------
        ops = ttk.LabelFrame(body, text="Operações", padding=8)
        ops.pack(fill="x", pady=(8, 0))

        def _op_button(text: str, command) -> ttk.Button:
            btn = ttk.Button(ops, text=text, command=command)
            self._op_buttons.append(btn)
            return btn

        _op_button("Detectar", lambda: self._run("Detectar dispositivo", self._detect)).grid(
            row=0, column=0, padx=(0, 6), pady=3
        )
        _op_button("Verificar vazio", lambda: self._run("Verificação de chip vazio", self._blank_check)).grid(
            row=0, column=1, padx=6, pady=3
        )
        _op_button("Ler", lambda: self._run("Leitura do chip", self._read)).grid(
            row=0, column=2, padx=6, pady=3
        )
        _op_button("Verificar", lambda: self._run("Verificação contra HEX", self._verify)).grid(
            row=0, column=3, padx=6, pady=3
        )
        _op_button("Gravar", lambda: self._run("Gravação do chip", self._program)).grid(
            row=0, column=4, padx=6, pady=3
        )
        _op_button("Apagar", lambda: self._run("Apagar chip", self._erase)).grid(
            row=0, column=5, padx=(6, 0), pady=3
        )

        self._erase_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ops, text="Apagar antes de gravar", variable=self._erase_var).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )
        self._save_read_btn = ttk.Button(
            ops, text="Salvar leitura…", command=self._save_read, state="disabled"
        )
        self._save_read_btn.grid(row=1, column=4, columnspan=2, sticky="e", pady=(6, 0))

        # ---- progress ---------------------------------------------------
        self._progress = ttk.Progressbar(body, mode="indeterminate")
        self._progress.pack(fill="x", pady=(8, 0))

        # ---- log --------------------------------------------------------
        log_frame = ttk.Frame(body)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))
        self._log_text = tk.Text(
            log_frame, height=12, wrap="word", state="disabled",
            background="#f7f7f7", font=("TkFixedFont", 9),
        )
        scroll = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # ------------------------------------------------------------- logging

    def _log(self, message: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in self._op_buttons:
            btn.configure(state=state)
        self._connect_btn.configure(state=state)
        self._disconnect_btn.configure(
            state="disabled" if (busy or self._connection is None) else "normal"
        )
        if busy:
            self._progress.start(10)
        else:
            self._progress.stop()

    # ------------------------------------------------------------ threading

    def _run(self, label: str, operation: Callable) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._log(f"— {label}…")

        def worker() -> None:
            try:
                result = operation(log=lambda m: self._events.put(("log", m)))
                self._events.put(("done", result))
            except Exception as exc:  # noqa: BLE001 — surface to the UI
                self._events.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        self.after(80, self._poll)

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "done":
                    if payload:
                        self._log(str(payload))
                    self._log("— concluído.")
                    self._set_busy(False)
                    return
                elif kind == "error":
                    self._log(f"ERRO: {payload}")
                    self._set_busy(False)
                    messagebox.showerror("Erro", str(payload), parent=self)
                    return
        except queue.Empty:
            pass
        self.after(80, self._poll)

    # ------------------------------------------------------------ connection

    def _refresh_ports(self) -> None:
        ports: list[str] = []
        try:
            from serial.tools import list_ports

            ports = [p.device for p in list_ports.comports()]
        except Exception as exc:  # noqa: BLE001 — pyserial may be absent
            self._log(f"pyserial indisponível ({exc}). Instale para listar portas.")
        current = self._port_var.get()
        self._port_combo["values"] = ports
        if ports and current not in ports:
            self._port_var.set(ports[0])

    def _connect(self) -> None:
        port = self._port_var.get()
        if not port:
            messagebox.showwarning("Conectar", "Selecione uma porta serial.", parent=self)
            return
        try:
            conn = Connection.open_port(port)
            version = conn.get_version()
            protocol = conn.get_protocol().decode("ascii", errors="ignore")
            self._connection = conn
            self._status_var.set(f"Conectado — {protocol} (firmware type {version})")
            self._log(f"Conectado em {port}: protocolo {protocol}, firmware type {version} (K150=3).")
            self._connect_btn.configure(state="disabled")
            self._disconnect_btn.configure(state="normal")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Conectar", f"Falha ao conectar:\n{exc}", parent=self)

    def _disconnect(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None
        self._status_var.set("Desconectado")
        self._connect_btn.configure(state="normal")
        self._disconnect_btn.configure(state="disabled")
        self._log("Desconectado.")

    # ---------------------------------------------------------------- HEX

    def _load_hex(self) -> None:
        path = filedialog.askopenfilename(
            title="Abrir arquivo HEX", filetypes=_HEX_FILETYPES, parent=self
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                records = parse_hex(fh.read())
            spec = self._selected_spec()
            image = build_image(records, spec.device)
        except (HexError, OSError, ValueError) as exc:
            messagebox.showerror("Abrir HEX", f"Falha ao ler o arquivo:\n{exc}", parent=self)
            return

        self._image = image
        self._image_spec = spec.device
        self._hex_var.set(path)
        used = sum(1 for w in image.program if w != image.blank_word)
        self._log(f"HEX carregado: {path}")
        self._log(
            f"  {used}/{len(image.program)} palavras usadas, "
            f"config {', '.join(hex(c) for c in image.config)}, "
            f"EEPROM {len(image.eeprom)} bytes."
        )

    def _on_device_changed(self) -> None:
        # The loaded image belongs to the device it was built with; warn if the
        # user switches devices afterwards.
        if self._image is not None:
            self._log("Aviso: dispositivo alterado — recarregue o HEX para este dispositivo.")

    # ------------------------------------------------------------ operations

    def _selected_spec(self):
        spec = self._catalog.get(self._device_var.get())
        if spec is None:
            raise RuntimeError("Dispositivo não suportado no catálogo.")
        return spec

    def _get_programmer(self):
        if self._connection is None:
            raise ProgrammerError("Conecte o programador primeiro.")
        spec = self._selected_spec()
        return KitsrusProgrammer(self._connection, spec), spec

    def _detect(self, log) -> str:
        programmer, spec = self._get_programmer()
        chip_id, expected, matched = uc.detect_device(programmer, spec.device)
        if expected is None:
            return f"Device ID lido: 0x{chip_id:04X} (catálogo sem ID esperado)."
        mark = "corresponde" if matched else "NÃO corresponde"
        return f"Device ID lido: 0x{chip_id:04X} — esperado 0x{expected:04X} ({mark})."

    def _blank_check(self, log) -> str:
        programmer, spec = self._get_programmer()
        nonblank = uc.blank_check(programmer, spec.device)
        if not nonblank:
            return "Chip em branco (programa e configuração)."
        log(f"{len(nonblank)} posições não vazias:")
        for region, addr, word in nonblank[:25]:
            log(f"  {region} 0x{addr:04X} = 0x{word:04X}")
        return "Chip NÃO está em branco."

    def _read(self, log) -> str:
        programmer, spec = self._get_programmer()
        image = uc.read_device(programmer, spec.device)
        self._last_read = image
        self._last_read_spec = spec.device
        self._save_read_btn.configure(state="normal")
        dev = f"0x{image.device_id:04X}" if image.device_id is not None else "—"
        return (
            f"Lido: {len(image.program)} palavras, config "
            f"{', '.join(hex(c) for c in image.config)}, device ID {dev}."
        )

    def _verify(self, log) -> str:
        if self._image is None:
            raise ProgrammerError("Carregue um arquivo HEX antes de verificar.")
        programmer, spec = self._get_programmer()
        mismatches = uc.verify_device(programmer, spec.device, self._image)
        if not mismatches:
            return "Verificação OK — chip idêntico ao HEX carregado."
        log(f"{len(mismatches)} diferença(s):")
        for region, addr, expected, actual in mismatches[:25]:
            log(f"  {region} 0x{addr:04X}: esperado 0x{expected:04X}, lido 0x{actual:04X}")
        return "Verificação FALHOU."

    def _program(self, log) -> str:
        if self._image is None:
            raise ProgrammerError("Carregue um arquivo HEX antes de gravar.")
        programmer, spec = self._get_programmer()
        report = uc.program_device(
            programmer, spec.device, self._image, erase=self._erase_var.get()
        )
        lines = [f"Gravadas {report.programmed} palavras + {report.config_programmed} config."]
        if report.verified:
            lines.append("Verificação pós-gravação: OK.")
        else:
            lines.append(f"Falhas de verificação: {len(report.failures)}")
            for region, addr, expected, actual in report.failures[:25]:
                log(f"  {region} 0x{addr:04X}: esperado 0x{expected:04X}, lido 0x{actual:04X}")
        return "\n".join(lines)

    def _erase(self, log) -> str:
        programmer, _spec = self._get_programmer()
        uc.erase_device(programmer)
        return "Chip apagado."

    # ------------------------------------------------------------ save read

    def _save_read(self) -> None:
        if self._last_read is None or self._last_read_spec is None:
            return
        path = filedialog.asksaveasfilename(
            title="Salvar leitura como HEX",
            defaultextension=".hex",
            filetypes=_HEX_FILETYPES,
            parent=self,
        )
        if not path:
            return
        records = image_to_records(self._last_read, self._last_read_spec)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(format_hex(records))
        self._log(f"Leitura salva em {path}.")

    # ------------------------------------------------------------- shutdown

    def _on_close(self) -> None:
        if self._busy:
            if not messagebox.askyesno(
                "Fechar", "Operação em andamento. Fechar mesmo assim?", parent=self
            ):
                return
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:  # noqa: BLE001
                pass
        self.destroy()


def launch(
    master,
    db,
    search_inventory: Callable[[str], None] | None = None,
    open_part: Callable[[int], None] | None = None,
) -> None:
    """Open the PIC10/12/16 programmer dialog (kitsrus K150).

    ``db``, ``search_inventory`` and ``open_part`` are accepted for a uniform
    tool signature but are unused — the programmer is self-contained.
    """
    PicProgrammerDialog(master)
