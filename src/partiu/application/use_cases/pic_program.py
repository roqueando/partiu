"""PIC programmer use cases — read / program / verify / erase / blank-check / detect.

These drive a :class:`~partiu.application.ports.PicProgrammer` (device-level
port).  They contain no I/O of their own, so they are testable with a fake
programmer that models a chip's memory.

The programmer adapter owns the transport (kitsrus K150 firmware protocol, or a
future JDM bit-bang); these use cases only move words/bytes around and decide
*what* to read/write, never *how* it is clocked on the wire.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ports import PicProgrammer
from ...domain.engineering.pic import DeviceSpec, PicMemoryImage


@dataclass
class ProgramReport:
    """Outcome of a ``program_device`` run."""

    programmed: int = 0
    config_programmed: int = 0
    verified: bool = True
    failures: list[tuple[str, int, int, int]] = field(default_factory=list)
    # failures: (region, address, expected, read_back)


def detect_device(
    programmer: PicProgrammer, spec: DeviceSpec
) -> tuple[int, int | None, bool | None]:
    """Return ``(chip_id, expected_id, matches_catalog)``.

    ``matches_catalog`` is ``None`` when the catalog has no expected ID value.
    """
    programmer.open()
    try:
        cfg = programmer.read_config()
    finally:
        programmer.close()
    matched = None if spec.device_id_value is None else cfg.chip_id == spec.device_id_value
    return cfg.chip_id, spec.device_id_value, matched


def read_device(programmer: PicProgrammer, spec: DeviceSpec) -> PicMemoryImage:
    programmer.open()
    try:
        program = programmer.read_program()
        cfg = programmer.read_config()
        eeprom = programmer.read_eeprom() if spec.eeprom_bytes else []
    finally:
        programmer.close()

    mask = spec.word_mask
    return PicMemoryImage(
        word_bits=spec.word_bits,
        program=[w & mask for w in program],
        config=[(cfg.fuses[0] & mask) if cfg.fuses else 0],
        id=list(cfg.id_words),
        eeprom=eeprom,
        osccal=cfg.calibration if spec.osccal_address is not None else None,
        device_id=cfg.chip_id,
    )


def blank_check(programmer: PicProgrammer, spec: DeviceSpec) -> list[tuple[str, int, int]]:
    """Return non-blank locations as ``(region, address, word)``."""
    blank = spec.word_mask
    programmer.open()
    try:
        program = programmer.read_program()
        cfg = programmer.read_config()
    finally:
        programmer.close()

    nonblank: list[tuple[str, int, int]] = [
        ("program", addr, w & spec.word_mask)
        for addr, w in enumerate(program)
        if (w & spec.word_mask) != blank
    ]
    if cfg.fuses and (cfg.fuses[0] & spec.word_mask) != blank:
        nonblank.append(("config", 0, cfg.fuses[0] & spec.word_mask))
    return nonblank


def erase_device(programmer: PicProgrammer) -> None:
    """Bulk-erase the chip (program memory + configuration)."""
    programmer.open()
    try:
        programmer.erase()
    finally:
        programmer.close()


def program_device(
    programmer: PicProgrammer,
    spec: DeviceSpec,
    image: PicMemoryImage,
    *,
    erase: bool = True,
) -> ProgramReport:
    """Program an image: optional erase, then program / EEPROM / config / calibration."""
    report = ProgramReport()
    mask = spec.word_mask

    programmer.open()
    try:
        if erase:
            programmer.erase()

        words = [w & mask for w in image.program]
        programmer.program_program(words)
        report.programmed = len(words)

        if spec.eeprom_bytes and image.eeprom:
            programmer.program_eeprom([b & 0xFF for b in image.eeprom])

        if image.config:
            fuses = [w & mask for w in image.config]
            id_words = [w & 0xFF for w in image.id]
            programmer.program_config(id_words, fuses)
            report.config_programmed = len(fuses)

        if image.osccal is not None:
            fuse0 = fuses[0] if image.config else 0
            programmer.program_calibration(image.osccal & mask, fuse0 & mask)

        # Verify what we wrote.
        actual_program = programmer.read_program()
        for addr, (expected, actual) in enumerate(zip(words, actual_program)):
            if expected != (actual & mask):
                report.verified = False
                report.failures.append(("program", addr, expected, actual & mask))
        if len(actual_program) != len(words):
            report.verified = False

        if image.config:
            cfg = programmer.read_config()
            expected_config = image.config[0] & mask
            actual_config = (cfg.fuses[0] & mask) if cfg.fuses else None
            if actual_config != expected_config:
                report.verified = False
                report.failures.append(("config", 0, expected_config, actual_config or 0))
    finally:
        programmer.close()
    return report


def verify_device(
    programmer: PicProgrammer,
    spec: DeviceSpec,
    image: PicMemoryImage,
) -> list[tuple[str, int, int, int]]:
    """Compare device contents against ``image``; return ``(region, addr, expected, actual)``."""
    mask = spec.word_mask
    programmer.open()
    try:
        actual_program = programmer.read_program()
        cfg = programmer.read_config()
    finally:
        programmer.close()

    mismatches: list[tuple[str, int, int, int]] = []
    for addr in range(len(image.program)):
        expected = image.program[addr] & mask
        actual = (actual_program[addr] & mask) if addr < len(actual_program) else -1
        if expected != actual:
            mismatches.append(("program", addr, expected, actual))
    if len(actual_program) != len(image.program):
        mismatches.append(("program", len(image.program), 0, len(actual_program)))

    if image.config:
        expected = image.config[0] & mask
        actual = (cfg.fuses[0] & mask) if cfg.fuses else -1
        if expected != actual:
            mismatches.append(("config", 0, expected, actual))
    return mismatches
