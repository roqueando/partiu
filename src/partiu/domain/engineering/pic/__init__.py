"""PIC programmer domain package — pure logic, no I/O.

Everything here is GUI- and hardware-free so it can be unit-tested without a
K150 attached: device descriptors, ICSP command words and bitstream
serialization, Intel HEX parsing and memory-image mapping.
"""

from __future__ import annotations

from . import commands, devices, hexfile, memory, signals
from .commands import (
    BEGIN_PROGRAMMING,
    BEGIN_PROGRAM_ONLY,
    BULK_ERASE_DATA,
    BULK_ERASE_PROGRAM,
    CHIP_ERASE,
    END_PROGRAMMING,
    INCREMENT_ADDRESS,
    LOAD_CONFIGURATION,
    LOAD_DATA_MEMORY,
    LOAD_PROGRAM_DATA,
    MIDRANGE_COMMANDS,
    READ_DATA_MEMORY,
    READ_PROGRAM_DATA,
    SUPPORTED_FAMILIES,
    command_bits,
    encode_command,
    serialize_eeprom_byte,
    serialize_word,
)
from .devices import DEVICES, WORD_BITS, DeviceSpec, Family
from .hexfile import HexError, HexRecord, format_hex, parse_hex, records_to_bytes
from .memory import DeviceConfig, PicMemoryImage, Region, build_image, image_to_records

__all__ = [
    "commands",
    "devices",
    "hexfile",
    "memory",
    "signals",
    "DeviceSpec",
    "Family",
    "DEVICES",
    "WORD_BITS",
    "HexRecord",
    "HexError",
    "parse_hex",
    "format_hex",
    "records_to_bytes",
    "PicMemoryImage",
    "DeviceConfig",
    "Region",
    "build_image",
    "image_to_records",
    "encode_command",
    "serialize_word",
    "serialize_eeprom_byte",
    "command_bits",
    "SUPPORTED_FAMILIES",
    "MIDRANGE_COMMANDS",
    "LOAD_CONFIGURATION",
    "LOAD_PROGRAM_DATA",
    "READ_PROGRAM_DATA",
    "INCREMENT_ADDRESS",
    "BEGIN_PROGRAMMING",
    "BEGIN_PROGRAM_ONLY",
    "LOAD_DATA_MEMORY",
    "READ_DATA_MEMORY",
    "BULK_ERASE_PROGRAM",
    "BULK_ERASE_DATA",
    "END_PROGRAMMING",
    "CHIP_ERASE",
]
