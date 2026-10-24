"""Unit tests for the kitsrus K150 adapter (firmware protocol emulated in-memory).

A ``FakeSerial`` emulates the on-board PIC16F628 firmware: it answers the
power-up banner, walks the command jump table, and implements the read / program
/ erase / config commands against a small memory model.  This lets us verify the
adapter's byte-level protocol handling without any hardware.
"""

from partiu.adapters.kitsrus_k150 import (
    CMD_INIT,
    Connection,
    KitsrusProgrammer,
    ProgrammerError,
)
from partiu.adapters.pic_device_catalog import KITSRUS_DEVICES


# ---------------------------------------------------------------------------
# Firmware emulation
# ---------------------------------------------------------------------------

class FakeSerial:
    """pyserial-like object that emulates the kitsrus firmware."""

    def __init__(self, *, firmware_type=3, protocol=b"P016", word_bits=14, program_words=0x400, eeprom_bytes=0x40, chip_id=0x0560):
        self.firmware_type = firmware_type
        self.protocol = protocol
        self.word_mask = (1 << word_bits) - 1
        self.program_words = program_words
        self.eeprom_bytes = eeprom_bytes
        self.chip_id = chip_id

        self.rom = bytearray(b"\xff" * (program_words * 2))
        self.eeprom = bytearray(b"\xff" * eeprom_bytes)
        self.fuse = self.word_mask
        self.id_bytes = b"\xff\xff\xff\xff"
        self.calibration = None

        self._dtr = False
        self.rx = bytearray()
        self.state = "wait"          # 'wait' for 'P', or 'jump' (command table)
        self._collecting = False
        self._collect_n = 0
        self._collect_buf = bytearray()
        self._collect_cb = None
        self._prog_mode = None       # 'rom' | 'ee' during buffered writes
        self._prog_count = 0
        self._prog_buf = bytearray()

    # -- serial-like surface -------------------------------------------------

    @property
    def dtr(self):
        return self._dtr

    @dtr.setter
    def dtr(self, value):
        if self._dtr and not value:
            # Falling DTR edge resets the firmware → re-emit the banner.
            self.rx.clear()
            self.state = "wait"
            self.rx.extend(b"B" + bytes([self.firmware_type]))
        self._dtr = value

    def reset_input_buffer(self):
        self.rx.clear()

    def write(self, data):
        for byte in data:
            self._handle(byte)

    def read(self, count=1):
        take = min(count, len(self.rx))
        out = bytes(self.rx[:take])
        del self.rx[:take]
        return out

    def close(self):
        pass

    # -- firmware logic ------------------------------------------------------

    def _emit(self, data: bytes):
        self.rx.extend(data)

    def _handle(self, byte: int):
        if self.state == "wait":
            if byte == 0x01:                       # command end
                self._emit(b"Q")
            elif byte == 0x50:                     # 'P' → jump table
                self._emit(b"P")
                self.state = "jump"
            else:
                self._emit(b"Q")
            return

        # jump table — consume any in-progress multi-byte transfer first (a
        # 0x01 byte inside a payload is data, not a command end).
        if self._prog_mode is not None:
            self._prog_byte(byte)
            return
        if self._collecting:
            self._collect_buf.append(byte)
            if len(self._collect_buf) == self._collect_n:
                data = bytes(self._collect_buf)
                self._collecting = False
                self._collect_buf.clear()
                self._collect_cb(data)
            return

        # idle at the jump table
        if byte == 0x01:                           # command end
            self._emit(b"Q")
            self.state = "wait"
            return

        self._command(byte)

    def _collect(self, n, cb):
        self._collecting = True
        self._collect_n = n
        self._collect_buf.clear()
        self._collect_cb = cb

    def _command(self, byte: int):
        if byte == CMD_INIT:
            self._collect(11, lambda _data: self._emit(b"I"))
        elif byte == 0x04:
            self._emit(b"V")
        elif byte == 0x05:
            self._emit(b"v")
        elif byte == 0x0B:                         # read ROM
            self._emit(bytes(self.rom))
        elif byte == 0x0C:                         # read EEPROM
            self._emit(bytes(self.eeprom))
        elif byte == 0x0D:                         # read config
            self._emit(b"C" + self._config_payload())
        elif byte == 0x0F:                         # erase
            self.rom[:] = b"\xff" * len(self.rom)
            self.fuse = self.word_mask
            self._emit(b"Y")
        elif byte == 0x07:                         # program ROM
            self._collect(2, self._start_prog_rom)
        elif byte == 0x08:                         # program EEPROM
            self._collect(2, self._start_prog_eeprom)
        elif byte == 0x09:                         # program ID + fuse
            self._collect(22, self._finish_prog_idfuse)
        elif byte == 0x0A:                         # program calibration
            self._collect(4, self._finish_prog_cal)
        elif byte == 0x15:                         # get version
            self._emit(bytes([self.firmware_type]))
        elif byte == 0x16:                         # get protocol
            self._emit(self.protocol)
        else:
            self._emit(b"Q")

    def _start_prog_rom(self, data: bytes):
        self._prog_count = int.from_bytes(data, "big")
        self._prog_buf = bytearray()
        self._prog_mode = "rom"
        self._emit(b"Y")

    def _start_prog_eeprom(self, data: bytes):
        self._prog_count = int.from_bytes(data, "big")
        self._prog_buf = bytearray()
        self._prog_mode = "ee"
        self._emit(b"Y")

    def _prog_byte(self, byte: int):
        self._prog_buf.append(byte)
        if self._prog_mode == "rom":
            if len(self._prog_buf) == self._prog_count * 2:
                self.rom[: len(self._prog_buf)] = self._prog_buf
                self._prog_mode = None
                self._emit(b"P")
            elif len(self._prog_buf) % 32 == 0:
                self._emit(b"Y")
        else:  # eeprom
            if len(self._prog_buf) == self._prog_count + 2:
                self.eeprom[: self._prog_count] = self._prog_buf[: self._prog_count]
                self._prog_mode = None
                self._emit(b"P")
            elif len(self._prog_buf) % 2 == 0 and len(self._prog_buf) <= self._prog_count:
                self._emit(b"Y")

    def _finish_prog_idfuse(self, data: bytes):
        # body: '00' (2) + 4 ID bytes + 'FFFF' (4) + fuse lo/hi (2) + 0xFF*10
        self.id_bytes = data[2:6]
        self.fuse = (data[11] << 8 | data[10]) & self.word_mask
        self._emit(b"\x00")

    def _finish_prog_cal(self, data: bytes):
        self.calibration = ((data[0] << 8 | data[1])) & self.word_mask
        self.fuse = (data[2] << 8 | data[3]) & self.word_mask
        self._emit(b"Y")

    def _config_payload(self) -> bytes:
        payload = bytearray()
        payload += self.chip_id.to_bytes(2, "little")
        payload += self.id_bytes + b"\xff\xff\xff\xff"
        fuses = [self.fuse] + [0xFFFF] * 6
        for f in fuses:
            payload += f.to_bytes(2, "little")
        payload += (self.calibration if self.calibration is not None else 0xFFFF).to_bytes(2, "little")
        return bytes(payload)


def _make(spec):
    device = spec.device
    fake = FakeSerial(
        word_bits=device.word_bits,
        program_words=device.program_words,
        eeprom_bytes=device.eeprom_bytes,
        chip_id=device.device_id_value or 0xFFFF,
    )
    return KitsrusProgrammer(Connection(fake), spec)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_open_sends_init_variables():
    spec = KITSRUS_DEVICES["PIC16F84A"]
    fake = FakeSerial(word_bits=14, program_words=0x400, eeprom_bytes=0x40, chip_id=0x0560)
    conn = Connection(fake)
    programmer = KitsrusProgrammer(conn, spec)

    programmer.open()
    programmer.close()

    # 16F84A: ROM 0x400 words, EEPROM 0x40, core 6 (bit14_b), erase 0, delay 80,
    # power sequence 2 (VccVpp2), no flags.
    assert spec.programming_variables() == (
        b"\x04\x00"       # ROM size hi/lo
        b"\x00\x40"       # EEPROM size hi/lo
        b"\x06"           # core type
        b"\x00"           # flags
        b"\x50"           # program delay (80)
        b"\x02"           # power sequence
        b"\x00"           # erase mode
        b"\x01"           # tries
        b"\x00"           # over-program
    )
    assert fake.firmware_type == 3


def test_program_and_read_rom_roundtrip():
    spec = KITSRUS_DEVICES["PIC16F84A"]
    programmer = _make(spec)

    programmer.open()
    assert programmer.read_program() == [0x3FFF] * 0x400  # blank

    words = [0x2A5, 0x3F7A] + [0x3FFF] * (0x400 - 2)
    programmer.program_program(words)
    assert programmer.read_program() == words
    programmer.close()


def test_erase_and_blank():
    spec = KITSRUS_DEVICES["PIC16F84A"]
    programmer = _make(spec)
    programmer.open()
    programmer.program_program([0x0001] * 0x400)
    programmer.erase()
    assert programmer.read_program() == [0x3FFF] * 0x400
    programmer.close()


def test_program_config_and_read_back():
    spec = KITSRUS_DEVICES["PIC16F84A"]
    programmer = _make(spec)
    programmer.open()

    programmer.program_config([0x01, 0x02, 0x03, 0x04], [0x3F7A])
    cfg = programmer.read_config()
    assert cfg.chip_id == 0x0560
    assert cfg.fuses[0] == 0x3F7A
    assert cfg.id_words == [0x01, 0x02, 0x03, 0x04]
    programmer.close()


def test_program_calibration():
    spec = KITSRUS_DEVICES["PIC12F675"]
    programmer = _make(spec)
    programmer.open()

    programmer.program_calibration(0x3484, 0x31A4)
    cfg = programmer.read_config()
    assert cfg.calibration == 0x3484
    programmer.close()


def test_old_firmware_rejects_p018_only_core():
    # PIC10F200 needs core type 12, which P016 firmware does not support.
    spec = KITSRUS_DEVICES["PIC10F200"]
    fake = FakeSerial(protocol=b"P016", word_bits=12, program_words=0x100, eeprom_bytes=0)
    conn = Connection(fake)
    programmer = KitsrusProgrammer(conn, spec)

    try:
        programmer.open()
    except ProgrammerError as exc:
        assert "P018" in str(exc) or "P18A" in str(exc)
    else:
        raise AssertionError("expected ProgrammerError for P018-only core on P016")


def test_new_firmware_accepts_p018_only_core():
    spec = KITSRUS_DEVICES["PIC10F200"]
    fake = FakeSerial(protocol=b"P18A", word_bits=12, program_words=0x100, eeprom_bytes=0)
    conn = Connection(fake)
    programmer = KitsrusProgrammer(conn, spec)
    programmer.open()
    programmer.close()
