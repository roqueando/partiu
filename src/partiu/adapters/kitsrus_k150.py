"""Kitsrus K149/K150 programmer adapter (firmware protocol P014/P016/P018/P18A).

The original kitsrus K150 has a PIC16F628 running firmware; it does the ICSP
bit-banging itself and talks to the PC over a 19200-8N1 virtual COM port using
a small byte-oriented protocol.  This adapter implements that protocol and
exposes the device-level :class:`~partiu.application.ports.PicProgrammer` port.

Protocol reference: the kitsrus "Programmer Firmware Protocol" documents
(P014/P016/P018) and the open-source ``picpro`` / ``picprogrammer`` projects.
The wire format and command bytes are factual protocol details.

The serial object is injected (a ``pyserial`` ``Serial`` in production, a fake
in tests), so importing this module does not require ``pyserial``.
"""

from __future__ import annotations

import struct
import time

from partiu.domain.engineering.pic import DeviceConfig

from .pic_device_catalog import P018_ONLY_CORES, KitsrusDeviceSpec

# ---------------------------------------------------------------------------
# Protocol bytes (firmware command jump table)
# ---------------------------------------------------------------------------
CMD_END = 0x01             # returns 'Q', voltages off — end of command
CMD_ECHO = 0x02
CMD_INIT = 0x03            # initialise programming variables
CMD_VPP_ON = 0x04          # returns 'V'
CMD_VPP_OFF = 0x05         # returns 'v'
CMD_VPP_CYCLE = 0x06
CMD_PROGRAM_ROM = 0x07
CMD_PROGRAM_EEPROM = 0x08
CMD_PROGRAM_ID_FUSES = 0x09
CMD_PROGRAM_CAL = 0x0A
CMD_READ_ROM = 0x0B
CMD_READ_EEPROM = 0x0C
CMD_READ_CONFIG = 0x0D
CMD_READ_CAL = 0x0E
CMD_ERASE = 0x0F
CMD_ERASE_CHECK_ROM = 0x10
CMD_ERASE_CHECK_EEPROM = 0x11
CMD_PROGRAM_18F_FUSE = 0x12
CMD_GET_VERSION = 0x15
CMD_GET_PROTOCOL = 0x16

# P18A renumbered the info/erase commands (14 = erase, 20 = version,
# 21 = protocol).  The core programming commands 3-13 are unchanged.
CMD_ERASE_P18A = 0x0E
CMD_GET_VERSION_P18A = 0x14
CMD_GET_PROTOCOL_P18A = 0x15

# Response bytes.
RSP_BANNER = b"B"   # power-up: 'B' + firmware type
RSP_WAIT = b"Q"     # at "wait for command start"
RSP_JUMP = b"P"     # at command jump table / command ack
RSP_YES = b"Y"
RSP_NO = b"N"
RSP_INIT = b"I"
RSP_V_ON = b"V"
RSP_V_OFF = b"v"
RSP_CONFIG = b"C"   # read-configuration header


class ProgrammerError(Exception):
    """Base error for programmer adapter failures."""


class ProtocolError(ProgrammerError):
    """The firmware answered with an unexpected byte."""


class Connection:
    """Serial framing for the kitsrus firmware protocol."""

    def __init__(self, serial_port, timeout: float = 1.0) -> None:
        self._sp = serial_port
        self._timeout = timeout
        self.firmware_type: int | None = None
        self.protocol: bytes | None = None

    @classmethod
    def open_port(cls, port: str) -> "Connection":
        """Open a real serial port and reset the programmer."""
        import serial  # lazy: keep this module importable without pyserial

        sp = serial.Serial(
            port=port,
            baudrate=19200,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=0.1,
            xonxoff=False,
            rtscts=False,
        )
        conn = cls(sp)
        conn.reset()
        return conn

    # -- low-level I/O -------------------------------------------------------

    def write(self, data: bytes) -> None:
        self._sp.write(data)

    def read(self, count: int = 1, timeout: float | None = None) -> bytes:
        """Read ``count`` bytes, polling until satisfied or the timeout elapses.

        ``timeout`` defaults to 5 s so a firmware that goes silent can never
        hang the caller forever (callers that legitimately need longer pass an
        explicit timeout).
        """
        if timeout is None:
            timeout = 5.0
        deadline = time.time() + timeout
        result = b""
        while count > 0 and time.time() < deadline:
            chunk = self._sp.read(count)
            count -= len(chunk)
            result += chunk
        return result

    def expect(self, expected: bytes, timeout: float | None = None, *, send_command_end: bool = False) -> None:
        response = self.read(len(expected), timeout=timeout)
        if send_command_end:
            self.command_end()
        if response != expected:
            raise ProtocolError(f"expected {expected!r}, got {response!r}")

    # -- framing -------------------------------------------------------------

    def reset(self) -> None:
        """Reset the on-board PIC via DTR and read the power-up banner."""
        self._sp.dtr = True
        time.sleep(0.1)
        self._sp.reset_input_buffer()
        self._sp.dtr = False
        time.sleep(0.1)
        banner = self.read(2, timeout=0.5)
        if len(banner) != 2 or banner[0:1] != RSP_BANNER:
            raise ProtocolError(f"no firmware banner (got {banner!r}); is a K150 connected?")
        self.firmware_type = banner[1]

    def command_start(self, cmd: int | None = None) -> None:
        """Move the firmware to the command jump table (and optionally send a command)."""
        self.write(bytes([CMD_END]))
        self.expect(RSP_WAIT)
        self.write(b"P")
        ack = self.read(1)
        if ack != RSP_JUMP:
            raise ProtocolError(f"no command-start ack (got {ack!r})")
        if cmd is not None:
            self.write(bytes([cmd]))

    def command_end(self) -> None:
        self.write(bytes([CMD_END]))
        ack = self.read(1, timeout=10)
        if ack != RSP_WAIT:
            raise ProtocolError(f"no command-end ack (got {ack!r})")

    # -- info commands -------------------------------------------------------

    def detect(self) -> bytes:
        """Detect the firmware protocol (P014/P016/P018 → P18A) and version.

        P18A renumbered the info commands (get-version is 20, get-protocol is
        21); older firmware uses 21/22.  Probe command 21: P18A answers with
        the 4-byte protocol string, older firmware answers with the 1-byte
        version number.
        """
        self.command_start(CMD_GET_PROTOCOL_P18A)  # 21
        response = self.read(4, timeout=0.4)
        if len(response) == 4 and response[:1] == b"P":
            self.command_end()
            self.protocol = response
            self.command_start(CMD_GET_VERSION_P18A)  # 20
            version = self.read(1)
            self.command_end()
            if version:
                self.firmware_type = version[0]
        elif response and response[0] in (0, 1, 2, 3):
            self.command_end()
            self.firmware_type = response[0]
            self.command_start(CMD_GET_PROTOCOL)  # 22
            protocol = self.read(4, timeout=0.4)
            self.command_end()
            self.protocol = protocol or b"P016"
        else:
            self.command_end()
            raise ProtocolError(f"unable to detect programmer protocol (got {response!r})")
        return self.protocol

    def close(self) -> None:
        try:
            self._sp.close()
        except Exception:
            pass


def _is_p18a(protocol: bytes) -> bool:
    return protocol.decode("ascii", errors="ignore").upper() == "P18A"


def _uses_new_fuse_format(protocol: bytes) -> bool:
    """P018/P18A changed PROGRAM ID FUSES (cmd 9): 24-byte body + 'Y' ack
    (P014/P016 use a 22-byte body + 0x00 ack)."""
    text = protocol.decode("ascii", errors="ignore").upper().lstrip("P")
    return text in ("018", "18A")


def _protocol_supports_core(protocol: bytes, core_type: int) -> bool:
    """P014/P016 know cores 0-10; P018/P18A know 0-12."""
    if core_type <= 10:
        return True
    text = protocol.decode("ascii", errors="ignore").upper().lstrip("P")
    return text.startswith("018") or text.startswith("18A")


def _parse_config(data: bytes, word_mask: int) -> DeviceConfig:
    if len(data) != 26:
        raise ProtocolError(f"read-configuration payload is {len(data)} bytes, expected 26")
    chip_id = int.from_bytes(data[0:2], "little")
    id_bytes = data[2:10]
    id_words = list(id_bytes[0:4])  # ID1..ID4 — one byte per ID location
    fuses = [
        int.from_bytes(data[10 + 2 * i:12 + 2 * i], "little") & word_mask
        for i in range(7)
    ]
    cal_raw = int.from_bytes(data[24:26], "little")
    calibration = None if (cal_raw & word_mask) == word_mask else (cal_raw & word_mask)
    return DeviceConfig(chip_id=chip_id, id_words=id_words, fuses=fuses, calibration=calibration)


class KitsrusProgrammer:
    """Device-level ``PicProgrammer`` over a kitsrus K149/K150 firmware."""

    def __init__(self, connection: Connection, spec: KitsrusDeviceSpec) -> None:
        self._conn = connection
        self._spec = spec
        self._opened = False
        self._op = "idle"

    # -- PicProgrammer port --------------------------------------------------

    def open(self) -> None:
        protocol = self._conn.protocol or self._conn.detect()
        if self._spec.core_type in P018_ONLY_CORES and not _protocol_supports_core(
            protocol, self._spec.core_type
        ):
            raise ProgrammerError(
                f"{self._spec.device.name} needs core type {self._spec.core_type} "
                f"(firmware P018/P18A); detected protocol {protocol!r}. "
                "Upgrade the K150 firmware to program this device."
            )
        self._init_variables()
        self._opened = True

    def close(self) -> None:
        # Command 1 (command_end) already implies "voltages off", and each
        # operation ends with command_end(), so there is nothing to clean up.
        self._opened = False

    def read_program(self) -> list[int]:
        self._op = "ler ROM"
        mask = self._spec.device.word_mask
        self._conn.command_start()
        self._voltage(True)
        self._conn.write(bytes([CMD_READ_ROM]))
        data = self._conn.read(self._spec.device.program_words * 2, timeout=180)
        self._voltage(False)
        self._conn.command_end()
        return [
            int.from_bytes(data[i:i + 2], "big") & mask
            for i in range(0, len(data), 2)
        ]

    def read_eeprom(self) -> list[int]:
        self._op = "ler EEPROM"
        size = self._spec.device.eeprom_bytes
        if not size:
            return []
        self._conn.command_start()
        self._voltage(True)
        self._conn.write(bytes([CMD_READ_EEPROM]))
        data = self._conn.read(size, timeout=60)
        self._voltage(False)
        self._conn.command_end()
        return list(data)

    def read_config(self) -> DeviceConfig:
        self._op = "ler configuração"
        self._conn.command_start()
        self._voltage(True)
        self._conn.write(bytes([CMD_READ_CONFIG]))
        header = self._conn.read(1)
        if header != RSP_CONFIG:
            raise ProtocolError(f"read-configuration header mismatch (got {header!r})")
        data = self._conn.read(26)
        self._voltage(False)
        self._conn.command_end()
        return _parse_config(data, self._spec.device.word_mask)

    def erase(self) -> None:
        self._op = "apagar chip"
        self._conn.command_start()
        self._voltage(True)
        self._conn.write(bytes([self._erase_command()]))
        response = self._conn.read(1)
        self._voltage(False)
        self._conn.command_end()
        if response != RSP_YES:
            raise ProgrammerError(f"erase failed (got {response!r})")

    def _erase_command(self) -> int:
        # P18A moved ERASE CHIP from 15 → 14.
        protocol = self._conn.protocol or b"P016"
        return CMD_ERASE_P18A if _is_p18a(protocol) else CMD_ERASE

    def program_program(self, words: list[int]) -> None:
        self._op = "gravar ROM"
        mask = self._spec.device.word_mask
        data = b"".join((w & mask).to_bytes(2, "big") for w in words)
        if len(data) % 32 != 0:
            raise ValueError("program data must be a multiple of 32 bytes (16 words)")

        self._conn.command_start()
        self._voltage(True)
        self._conn.write(bytes([CMD_PROGRAM_ROM]))
        self._conn.write(struct.pack(">H", len(words)))
        self._conn.expect(RSP_YES, timeout=20)

        done = False
        for i in range(0, len(data), 32):
            self._conn.write(data[i:i + 32])
            response = self._conn.read(1, timeout=20)
            if response == RSP_JUMP:          # 'P' — all programmed
                done = True
                break
            if response == RSP_NO:            # 'N' — programming error
                address = self._conn.read(2, timeout=5)
                self._voltage(False)
                self._conn.command_end()
                raise ProgrammerError(
                    f"ROM programming failed near address {int.from_bytes(address, 'big')}"
                )
            if response != RSP_YES:
                self._voltage(False)
                self._conn.command_end()
                raise ProtocolError(f"unexpected ROM acknowledgement {response!r}")
        if not done:                          # some firmware sends the final 'P' separately
            self._conn.expect(RSP_JUMP, timeout=20)
        self._voltage(False)
        self._conn.command_end()

    def program_eeprom(self, data: list[int]) -> None:
        self._op = "gravar EEPROM"
        payload = bytes(b & 0xFF for b in data)
        if len(payload) % 2 != 0:
            raise ValueError("EEPROM data must be a multiple of 2 bytes")

        self._conn.command_start()
        self._voltage(True)
        self._conn.write(bytes([CMD_PROGRAM_EEPROM]))
        self._conn.write(struct.pack(">H", len(payload)))
        self._conn.expect(RSP_YES, timeout=20)
        for i in range(0, len(payload), 2):
            self._conn.write(payload[i:i + 2])
            self._conn.expect(RSP_YES, timeout=20)
        # Firmware expects two extra bytes (protocol quirk) before the final ack.
        self._conn.write(b"\x00\x00")
        self._conn.expect(RSP_JUMP, timeout=20)
        self._voltage(False)
        self._conn.command_end()

    def program_config(self, id_words: list[int], fuses: list[int]) -> None:
        self._op = "gravar ID+fuses"
        if not fuses:
            return
        # 12/14-bit path: '00' + 4 ID bytes + 'FFFF' + fuse lo/hi + trailing 0xFF.
        # P014/P016 use 10 × 0xFF and ack 0x00; P018/P18A use 12 × 0xFF and ack 'Y'.
        protocol = self._conn.protocol or b"P016"
        id_bytes = bytes(w & 0xFF for w in id_words[:4]).ljust(4, b"\xff")
        if _uses_new_fuse_format(protocol):
            body = b"00" + id_bytes + b"FFFF" + struct.pack("<H", fuses[0]) + b"\xff" * 12
            ok = RSP_YES
        else:
            body = b"00" + id_bytes + b"FFFF" + struct.pack("<H", fuses[0]) + b"\xff" * 10
            ok = b"\x00"

        self._conn.command_start()
        self._voltage(True)
        self._conn.write(bytes([CMD_PROGRAM_ID_FUSES]))
        self._conn.write(body)
        response = self._conn.read(1, timeout=20)
        self._voltage(False)
        self._conn.command_end()
        if response != ok:
            raise ProgrammerError(f"program ID/fuses failed (got {response!r})")

    def program_calibration(self, cal: int, fuse: int) -> None:
        self._op = "gravar calibração"
        body = (cal & 0xFFFF).to_bytes(2, "big") + (fuse & 0xFFFF).to_bytes(2, "big")
        self._conn.command_start()
        self._voltage(True)
        self._conn.write(bytes([CMD_PROGRAM_CAL]))
        self._conn.write(body)
        response = self._conn.read(1, timeout=10)
        self._voltage(False)
        self._conn.command_end()
        if response != RSP_YES:
            raise ProgrammerError(f"program calibration failed (got {response!r})")

    # -- internals -----------------------------------------------------------

    def _init_variables(self) -> None:
        self._conn.command_start(CMD_INIT)
        self._conn.write(self._spec.programming_variables())
        self._conn.expect(RSP_INIT, send_command_end=True)

    def _voltage(self, on: bool) -> None:
        self._conn.write(bytes([CMD_VPP_ON if on else CMD_VPP_OFF]))
        try:
            self._conn.expect(RSP_V_ON if on else RSP_V_OFF)
        except ProtocolError as exc:
            raise ProtocolError(f"[{self._op}] {exc}") from exc
