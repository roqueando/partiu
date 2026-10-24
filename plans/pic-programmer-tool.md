# Plan: PIC10/12/16 programmer tool (gravação via K150)

## Context

Partiu is an offline tkinter + SQLite component tracker with a **Tools** menu
(`src/partiu/gui/tools/__init__.py`, `Tool(id, label, launch)`).

We are adding a **programming (gravação) tool** for Microchip **PIC10 / PIC12 /
PIC16**, driving a **kitsrus K150** programmer. The tool loads a `.hex`, picks a
device, and performs **Detect / Blank-check / Read / Program / Verify / Erase** —
with a live log, progress, and (like the other tools) links into the inventory
when useful.

## Hardware: the kitsrus K150 (original, firmware-based)

The **original kitsrus K150** (Tony Nixon) is *not* a bit-banged serial
programmer. It has a **PIC16F628 running firmware** plus an FTDI USB-serial chip
(VCP). The firmware does the ICSP bit-banging itself; the PC talks to it over a
**19200-8N1 virtual COM port** using a small **byte-oriented protocol**.

- Power-up banner: `'B'` + firmware type byte (K150 = 3).
- Framing: `0x01` ends a command (`'Q'` ack); `'P'` opens the command jump table
  (`'P'` ack); then a **command byte** (0-24) and its payload.
- Key commands: **3** init variables, **4/5** VPP on/off, **7** program ROM,
  **8** program EEPROM, **9** program ID+fuses, **10** program calibration,
  **11** read ROM, **12** read EEPROM, **13** read config, **15** erase,
  **16/17** blank-check, **21** get version, **22** get protocol.
- Command **3** ("Initialise Programming Variables") needs, per device: ROM size
  (words), EEPROM size (bytes), **core type**, program flags, program delay,
  power sequence, erase mode, program tries and over-program count.

Protocol versions **P014 / P016 / P018 / P18A** differ mainly in the **core-type
numbering**: P014/P016 know cores 0-10; **P018/P18A add 11 (16F57/16F54/16F59)
and 12 (10Fxxx)**. So **PIC10F2xx and PIC16F5x need P018/P18A firmware** — the
adapter detects the protocol via command 22 and errors clearly on old firmware.

Reference implementations: `almost/picprogrammer` (P014) and `Salamek/picpro`
(P18A). Wire format and per-device core types are factual protocol parameters.

## Architecture (fits the existing Clean Architecture)

- **`domain/engineering/pic/`** — pure logic, zero I/O, unit-tested:
  - `devices.py` — `Family` + `DeviceSpec` (sizes, word size, memory map).
  - `hexfile.py` — Intel HEX parser.
  - `memory.py` — `PicMemoryImage`, `DeviceConfig`, `build_image`.
  - `commands.py` / `signals.py` — ICSP 6-bit opcodes + logical signals (kept for
    a future JDM-style clone adapter; not used by the kitsrus path).
- **`application/`**:
  - `ports.py` — `PicProgrammer` (**device-level** port) + `DeviceCatalog`.
  - `use_cases/pic_program.py` — `detect_device`, `read_device`, `program_device`,
    `verify_device`, `blank_check` — drive the port, transport-agnostic.
- **`adapters/`**:
  - `kitsrus_k150.py` — `Connection` (serial framing) + `KitsrusProgrammer`
    (implements `PicProgrammer` over the firmware protocol, P016→P18A).
  - `pic_device_catalog.py` — `KitsrusDeviceSpec` (core type, power sequence,
    erase mode, delay, flags) + seed catalog (~25 PIC10/12/16 devices).
- **`gui/tools/pic_programmer.py`** *(next step)* — dialog: port/device/hex
  selection, operation buttons, progress, log; operations on a background thread.

## Key design decisions

1. **Device-level port, not signal-level.** `PicProgrammer` exposes
   `read_program / program_program / read_config / erase / program_config / …`.
   A kitsrus adapter speaks the firmware protocol; a future JDM adapter would
   bit-bang ICSP behind the same port. Use cases never see the wire.
2. **Serial object is injected** (pyserial in production, a fake in tests), so
   the adapter is unit-testable without hardware or pyserial installed.
3. **Device DB is data.** Adding a PIC = one catalog entry (core type, delay,
   power sequence, erase mode, sizes) — no algorithm change.
4. **Protocol-version aware.** On open, read the protocol (cmd 22) and reject
   devices whose core type needs newer firmware, with a clear message.
5. **Firmware emulated in tests.** A `FakeSerial` models the firmware's jump
   table + memory, so the byte protocol is exercised end-to-end in CI.

## Operations / use cases

- **detect_device** — read config → chip ID, compare to the catalog.
- **blank_check** — read program + config, list non-blank words.
- **read_device** — read program / EEPROM / config / calibration → `PicMemoryImage`.
- **program_device** — optional erase → program ROM → EEPROM → ID+config →
  calibration → verify (bounded retry is handled by the firmware).
- **verify_device** — compare device contents against a loaded image.
- **erase_device** — bulk erase (firmware command 15).

## Files (current state)

| File | Status |
|------|--------|
| `plans/pic-programmer-tool.md` | this plan |
| `src/partiu/domain/engineering/pic/{devices,hexfile,memory,commands,signals}.py` | done + tested |
| `src/partiu/application/ports.py` | done — `PicProgrammer`, `DeviceCatalog` |
| `src/partiu/application/use_cases/pic_program.py` | done + tested |
| `src/partiu/adapters/kitsrus_k150.py` | done + tested (firmware emulation) |
| `src/partiu/adapters/pic_device_catalog.py` | done + tested |
| `pyproject.toml` | `pyserial>=3.5` added (run `poetry lock` / `poetry add pyserial`) |
| `src/partiu/gui/tools/pic_programmer.py` | done — dialog + `launch` |
| `src/partiu/gui/tools/__init__.py` | done — registered as `pic_programmer` |
| `README.md` | done — documented under Tools menu |

## Next steps

1. Hardware bring-up on a real chip: `poetry run partiu` → Tools → Programador
   PIC10/12/16 — **Conectar** (confirm the firmware protocol via cmd 22), then
   **Detectar** first, then read/blank-check, then program+verify.
2. Validate the seed catalog against each device's programming spec (chip IDs,
   OSCCAL, core types) before enabling more devices.
3. (Optional) Add EEPROM read/write and enhanced mid-range (PIC16F1xxx) handling.

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Firmware is P016 (no PIC10F/16F5x cores) | cmd-22 detection + clear "upgrade firmware" error; docs explain P018/P18A |
| Core-type numbering differs across protocol versions | Catalog stores the name; single mapping + per-protocol capability check |
| Device metadata (chip ID, OSCCAL, delays) off by one device | Seed catalog marked as reference data; detect_device reports the raw ID |
| Windows COM latency / drivers | FTDI VCP driver required; operations are block-oriented (firmware-paced), not bit-bang |
| No hardware in CI | Firmware emulated in tests; real-chip bring-up is manual |

## Verification

- `poetry run pytest` — 52 tests green (domain + use cases + adapter emulation + architecture gate).
- (After GUI) `poetry run partiu` → Tools → PIC programmer: detect/read/blank-check/program/verify on a real K150.
