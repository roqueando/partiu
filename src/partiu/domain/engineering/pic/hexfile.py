"""Intel HEX parser (pure, no I/O).

Parses the standard Intel HEX record format used by MPLAB X / XC8 / SDCC
``.hex`` output and exposes records as (absolute_address, data_bytes).  Extended
linear (04) and extended segment (02) records are folded into the address;
start-address records (03/05) are accepted and ignored.  Checksums are
validated.

Record layout: ``:LLAAAATT[DD…]CC``
- LL      byte count
- AAAA    address (16-bit)
- TT      record type (00 data, 01 EOF, 02 ext. segment, 03 start seg.,
          04 ext. linear, 05 start linear)
- DD      data bytes
- CC      two's-complement checksum of all preceding bytes
"""

from __future__ import annotations

from dataclasses import dataclass

#: Data record.
DATA = 0x00
#: End-of-file record.
EOF = 0x01
#: Extended segment address (base = value << 4).
EXT_SEGMENT = 0x02
#: Start segment address (ignored here).
START_SEGMENT = 0x03
#: Extended linear address (base = value << 16).
EXT_LINEAR = 0x04
#: Start linear address (ignored here).
START_LINEAR = 0x05


@dataclass(frozen=True)
class HexRecord:
    """One parsed record with the extended address already applied."""

    record_type: int
    address: int
    data: bytes


class HexError(ValueError):
    """Malformed or invalid Intel HEX input."""


def _parse_line(line: str, line_no: int) -> tuple[int, int, bytes]:
    """Parse a single record line, returning (record_type, address, data)."""
    text = line.strip()
    if not text:
        raise HexError(f"line {line_no}: empty record")
    if text[0] != ":":
        raise HexError(f"line {line_no}: missing ':' start code")
    body = text[1:]
    if len(body) < 2 or len(body) % 2 != 0:
        raise HexError(f"line {line_no}: record length is not a whole byte count")
    try:
        raw = bytes.fromhex(body)
    except ValueError as exc:
        raise HexError(f"line {line_no}: non-hex characters") from exc

    if sum(raw) & 0xFF != 0:
        raise HexError(f"line {line_no}: checksum mismatch")

    count = raw[0]
    if count != len(raw) - 5:
        raise HexError(f"line {line_no}: byte count {count} != data length {len(raw) - 5}")

    record_type = raw[3]
    address = (raw[1] << 8) | raw[2]
    data = raw[4:-1]
    return record_type, address, data


def parse_hex(text: str) -> list[HexRecord]:
    """Parse Intel HEX text into a list of :class:`HexRecord` (absolute addresses)."""
    records: list[HexRecord] = []
    base = 0
    seen_eof = False

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        record_type, address, data = _parse_line(line, line_no)

        if record_type == EOF:
            seen_eof = True
            break
        if record_type == EXT_LINEAR:
            base = int.from_bytes(data, "big") << 16
            continue
        if record_type == EXT_SEGMENT:
            base = int.from_bytes(data, "big") << 4
            continue
        if record_type == DATA:
            records.append(HexRecord(DATA, base + address, data))
            continue
        if record_type in (START_SEGMENT, START_LINEAR):
            # Start address — informational only, not part of the memory image.
            continue
        raise HexError(f"line {line_no}: unknown record type {record_type:#04x}")

    if not seen_eof:
        raise HexError("no end-of-file (01) record found")
    return records


def records_to_bytes(records: list[HexRecord]) -> dict[int, int]:
    """Flatten data records into an ``{address: byte}`` map.

    Overlapping data records are allowed (later records win), which matches how
    linker output can emit multiple records for the same region.
    """
    image: dict[int, int] = {}
    for rec in records:
        for i, byte in enumerate(rec.data):
            image[rec.address + i] = byte
    return image


def format_hex(records: list[HexRecord], chunk: int = 16) -> str:
    """Serialize records to Intel HEX text, splitting large records into
    ``chunk``-byte data records (max allowed is 255) and appending EOF."""
    lines: list[str] = []
    for rec in records:
        data = rec.data
        for i in range(0, len(data), chunk):
            piece = data[i:i + chunk]
            address = rec.address + i
            body = bytes([
                len(piece),
                (address >> 8) & 0xFF,
                address & 0xFF,
                rec.record_type,
            ]) + piece
            checksum = (-sum(body)) & 0xFF
            lines.append(":" + (body + bytes([checksum])).hex().upper())
    lines.append(":00000001FF")
    return "\n".join(lines) + "\n"
