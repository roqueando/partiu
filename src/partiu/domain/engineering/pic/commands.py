"""PIC ICSP command words and bitstream serialization (pure, no I/O).

Command opcodes and payload framing follow Microchip AN910 ("PICmicro Device
Programming") — the 6-bit command set shared by PIC12/PIC16 (mid-range), with
the note that the two MSBs of several commands are "don't care" (must be 0 on
some devices).  Baseline (12-bit) and enhanced mid-range (13-command) variants
are separate families; only mid-range is encoded here initially.

Bit order on the wire:
- Commands: 6 bits, **MSB first**, latched on the falling edge of PGC.
- Program-word payload: ``0, data(N-1:0) MSB-first, 0`` (N+2 clocks).
- EEPROM payload:       ``0, data(0:7) LSB-first, 0000000`` (16 clocks).
"""

from __future__ import annotations

from .devices import Family

# ---------------------------------------------------------------------------
# Mid-range 6-bit opcodes (MSb ... LSb as clocked)
# ---------------------------------------------------------------------------
LOAD_CONFIGURATION = 0x00    # 0 0 0 0 0 0
LOAD_PROGRAM_DATA = 0x02     # 0 0 0 0 1 0
READ_PROGRAM_DATA = 0x04     # 0 0 0 1 0 0
INCREMENT_ADDRESS = 0x06     # 0 0 0 1 1 0
BEGIN_PROGRAMMING = 0x08     # 0 0 1 0 0 0  (erase+program / internally timed)
BEGIN_PROGRAM_ONLY = 0x18    # 0 1 1 0 0 0
LOAD_DATA_MEMORY = 0x03      # x x 0 0 1 1  (data EEPROM)
READ_DATA_MEMORY = 0x05      # x x 0 1 0 1  (data EEPROM)
BULK_ERASE_PROGRAM = 0x09    # x x 1 0 0 1
BULK_ERASE_DATA = 0x0B       # x x 1 0 1 1
END_PROGRAMMING = 0x0E       # 0 0 1 1 1 0
CHIP_ERASE = 0x1F            # x 1 1 1 1 1

#: Mid-range command set, by symbolic name (name → 6-bit opcode).
MIDRANGE_COMMANDS: dict[str, int] = {
    "load_configuration": LOAD_CONFIGURATION,
    "load_program_data": LOAD_PROGRAM_DATA,
    "read_program_data": READ_PROGRAM_DATA,
    "increment_address": INCREMENT_ADDRESS,
    "begin_programming": BEGIN_PROGRAMMING,
    "begin_program_only": BEGIN_PROGRAM_ONLY,
    "load_data_memory": LOAD_DATA_MEMORY,
    "read_data_memory": READ_DATA_MEMORY,
    "bulk_erase_program": BULK_ERASE_PROGRAM,
    "bulk_erase_data": BULK_ERASE_DATA,
    "end_programming": END_PROGRAMMING,
    "chip_erase": CHIP_ERASE,
}

#: Families whose protocol is encoded so far.
SUPPORTED_FAMILIES: frozenset[Family] = frozenset({Family.MIDRANGE})


def encode_command(opcode: int, nbits: int = 6) -> list[int]:
    """Return ``opcode`` as ``nbits`` bits, MSB first."""
    if opcode < 0 or opcode >= (1 << nbits):
        raise ValueError(f"opcode {opcode:#x} does not fit in {nbits} bits")
    return [(opcode >> (nbits - 1 - i)) & 1 for i in range(nbits)]


def serialize_word(word: int, nbits: int) -> list[int]:
    """Serialize a program-memory word: ``0, data(N-1:0) MSB-first, 0``."""
    return [0] + [(word >> (nbits - 1 - i)) & 1 for i in range(nbits)] + [0]


def serialize_eeprom_byte(byte: int) -> list[int]:
    """Serialize an EEPROM byte: ``0, data(0:7) LSB-first, 0000000``."""
    return [0] + [(byte >> i) & 1 for i in range(8)] + [0] * 7


def command_bits(family: Family, name: str) -> list[int]:
    """Return the 6 command bits (MSB first) for a named command in ``family``."""
    if family not in SUPPORTED_FAMILIES:
        raise NotImplementedError(f"command set not implemented for family {family!r}")
    return encode_command(MIDRANGE_COMMANDS[name])
