"""PIC memory image: HEX records → named regions (pure, no I/O).

``build_image`` takes parsed HEX records and a :class:`DeviceSpec`, then maps
the flat byte stream into the device's logical regions (program / config / ID /
EEPROM / OSCCAL), assembling 12- or 14-bit words little-endian and masking to
the device word size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .devices import DeviceSpec
from .hexfile import DATA, HexRecord, records_to_bytes


class Region(str, Enum):
    PROGRAM = "program"
    CONFIG = "config"
    ID = "id"
    EEPROM = "eeprom"
    OSCCAL = "osccal"
    DEVICE_ID = "device_id"


@dataclass
class PicMemoryImage:
    """A device's memory contents, split by region.

    Program/config/OSCCAL hold one masked word per element; ID holds one byte
    per ID location; EEPROM holds one byte per element.
    """

    word_bits: int
    program: list[int] = field(default_factory=list)
    config: list[int] = field(default_factory=list)
    id: list[int] = field(default_factory=list)
    eeprom: list[int] = field(default_factory=list)
    osccal: int | None = None
    device_id: int | None = None

    @property
    def word_mask(self) -> int:
        return (1 << self.word_bits) - 1

    @property
    def blank_word(self) -> int:
        """Erased (blank) flash reads back as all ones."""
        return self.word_mask


@dataclass
class DeviceConfig:
    """Device identification + configuration read back from a programmed chip.

    This is the transport-agnostic shape returned by a device-level programmer
    (e.g. the kitsrus K150 ``Read Configuration`` command).  For 12/14-bit
    PIC10/12/16 devices, ``fuses[0]`` is the configuration word; ``calibration``
    is the OSCCAL word (``0xFFFF`` when the device has none).
    """

    chip_id: int
    id_words: list[int]          # ID location words (4 for 12/14-bit)
    fuses: list[int]             # fuse / configuration words
    calibration: int | None = None


def _read_word(byte_map: dict[int, int], address: int, mask: int) -> int | None:
    """Assemble a little-endian 16-bit word at ``address``, or ``None``."""
    lo = byte_map.get(address)
    hi = byte_map.get(address + 1)
    if lo is None and hi is None:
        return None
    return ((hi or 0) << 8 | (lo or 0)) & mask


def _read_word_dual(byte_map: dict[int, int], word_address: int, mask: int) -> int | None:
    """Read a config / device-ID / OSCCAL word, handling both HEX conventions.

    Microchip INHX32 stores words at **2× the word address** (e.g. config word
    ``0x2007`` → HEX bytes ``0x400E-0x400F``); gputils and some older tools emit
    the literal word address instead.  Try the official 2× address first, then
    the literal one.
    """
    for address in (word_address * 2, word_address):
        word = _read_word(byte_map, address, mask)
        if word is not None:
            return word
    return None


def build_image(records: list[HexRecord], spec: DeviceSpec) -> PicMemoryImage:
    """Map parsed HEX records onto ``spec``'s regions.

    Words are assembled little-endian and masked to ``spec.word_bits``.  Regions
    whose address is absent from the HEX data are left empty (``None`` OSCCAL /
    device ID; ``config`` only holds words actually present in the HEX).
    """
    byte_map = records_to_bytes(records)
    mask = spec.word_mask

    program = [
        _read_word(byte_map, word_index * 2, mask) or 0
        for word_index in range(spec.program_words)
    ]
    config = [
        word
        for addr in spec.config_addresses
        if (word := _read_word_dual(byte_map, addr, mask)) is not None
    ]
    id_words = [
        byte_map.get(addr, 0xFF) & 0xFF for addr in spec.id_addresses
    ]
    eeprom = [
        byte_map.get(spec.eeprom_address + i, 0xFF)
        for i in range(spec.eeprom_bytes)
    ] if spec.eeprom_address is not None else []

    osccal = (
        _read_word_dual(byte_map, spec.osccal_address, mask)
        if spec.osccal_address is not None
        else None
    )
    device_id = (
        _read_word_dual(byte_map, spec.device_id_address, mask)
        if spec.device_id_address is not None
        else None
    )

    return PicMemoryImage(
        word_bits=spec.word_bits,
        program=program,
        config=config,
        id=id_words,
        eeprom=eeprom,
        osccal=osccal,
        device_id=device_id,
    )


def image_to_records(image: PicMemoryImage, spec: DeviceSpec) -> list[HexRecord]:
    """Inverse of :func:`build_image`: emit HEX records for a memory image.

    Program words are encoded little-endian (two bytes each) at ``0x0000``;
    config / ID / OSCCAL words and EEPROM bytes are emitted at their device
    addresses, masked to the device word size.
    """
    mask = spec.word_mask
    records: list[HexRecord] = []

    def _word(addr: int, word: int) -> None:
        w = word & mask
        records.append(HexRecord(DATA, addr, bytes([w & 0xFF, (w >> 8) & 0xFF])))

    program = bytearray()
    for w in image.program:
        w &= mask
        program += bytes([w & 0xFF, (w >> 8) & 0xFF])
    records.append(HexRecord(DATA, 0x0000, bytes(program)))

    for addr, w in zip(spec.config_addresses, image.config):
        _word(addr * 2, w)  # official INHX32: config word at 2× word address
    for addr, w in zip(spec.id_addresses, image.id):
        records.append(HexRecord(DATA, addr, bytes([w & 0xFF])))
    if image.osccal is not None and spec.osccal_address is not None:
        _word(spec.osccal_address * 2, image.osccal)
    if spec.eeprom_address is not None and image.eeprom:
        records.append(
            HexRecord(DATA, spec.eeprom_address, bytes(b & 0xFF for b in image.eeprom))
        )
    return records
