"""PIC device model: families and per-device programming descriptors.

``DeviceSpec`` is pure data.  The seed catalog below is *reference data* — every
address / ID value must be validated against the device's own Microchip
programming specification before that device is enabled in the GUI.  Entries
carry a ``notes`` field to flag exactly what still needs checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Family(str, Enum):
    """PIC programming family — each has its own command set / memory map."""

    BASELINE = "baseline"            # PIC10F / PIC12F5xx  (12-bit words)
    MIDRANGE = "midrange"            # PIC12F6xx / PIC16Fxx (14-bit words)
    ENHANCED = "enhanced"            # PIC16F1xxx           (14-bit words)


#: Word size (program memory) per family.
WORD_BITS: dict[Family, int] = {
    Family.BASELINE: 12,
    Family.MIDRANGE: 14,
    Family.ENHANCED: 14,
}


@dataclass(frozen=True)
class DeviceSpec:
    """Static description of a single PIC device's programming interface.

    Addresses are the HEX-file (memory-map) addresses used by the Intel HEX
    records, *not* the physical flash row addresses.
    """

    name: str
    family: Family
    program_words: int                     # number of program-memory words
    config_addresses: tuple[int, ...]      # configuration word address(es)
    id_addresses: tuple[int, ...]          # ID location address(es)
    device_id_address: int | None          # where the device ID word lives
    eeprom_address: int | None = None      # base HEX address of data EEPROM
    eeprom_bytes: int = 0
    osccal_address: int | None = None      # OSCCAL / calibration word, if any
    device_id_value: int | None = None     # expected device-ID word (verify)
    vpp: tuple[float, float] = (12.0, 13.5)
    vdd: tuple[float, float] = (4.5, 5.5)
    pgc_pin: str = "RB6"
    pgd_pin: str = "RB7"
    pgm_pin: str = "RB4"
    notes: str = ""

    @property
    def word_bits(self) -> int:
        return WORD_BITS[self.family]

    @property
    def word_mask(self) -> int:
        return (1 << self.word_bits) - 1


def _spec(
    name: str,
    family: Family,
    program_words: int,
    *,
    config: tuple[int, ...],
    device_id_addr: int | None = 0x2006,
    eeprom_addr: int | None = None,
    eeprom_bytes: int = 0,
    osccal: int | None = None,
    id_addrs: tuple[int, ...] = (0x2000, 0x2001, 0x2002, 0x2003),
    device_id: int | None = None,
    pgc: str = "RB6",
    pgd: str = "RB7",
    notes: str = "",
) -> DeviceSpec:
    return DeviceSpec(
        name=name,
        family=family,
        program_words=program_words,
        config_addresses=config,
        id_addresses=id_addrs,
        device_id_address=device_id_addr,
        eeprom_address=eeprom_addr,
        eeprom_bytes=eeprom_bytes,
        osccal_address=osccal,
        device_id_value=device_id,
        pgc_pin=pgc,
        pgd_pin=pgd,
        notes=notes,
    )


#: Seed catalog — reference data pending per-device specification review.
DEVICES: dict[str, DeviceSpec] = {
    d.name: d
    for d in [
        _spec(
            "PIC16F84A", Family.MIDRANGE, 1024,
            config=(0x2007,),
            notes="verify device-ID value; no EEPROM",
        ),
        _spec(
            "PIC16F628A", Family.MIDRANGE, 2048,
            config=(0x2007,),
            eeprom_addr=0x2100, eeprom_bytes=128,
            notes="verify device-ID value and OSCCAL (none on 628A)",
        ),
        _spec(
            "PIC16F877A", Family.MIDRANGE, 8192,
            config=(0x2007,),
            eeprom_addr=0x2100, eeprom_bytes=256,
            notes="verify device-ID value",
        ),
        _spec(
            "PIC12F629", Family.MIDRANGE, 1024,
            config=(0x2007,),
            eeprom_addr=0x2100, eeprom_bytes=128,
            osccal=0x3FF,
            pgc="GP1", pgd="GP0",
            notes="verify OSCCAL address and device-ID value",
        ),
        _spec(
            "PIC12F675", Family.MIDRANGE, 1024,
            config=(0x2007,),
            eeprom_addr=0x2100, eeprom_bytes=128,
            osccal=0x3FF,
            pgc="GP1", pgd="GP0",
            notes="verify OSCCAL address and device-ID value",
        ),
        _spec(
            "PIC16F690", Family.MIDRANGE, 4096,
            config=(0x2007,),
            eeprom_addr=0x2100, eeprom_bytes=256,
            notes="verify device-ID value",
        ),
        _spec(
            "PIC16F1829", Family.ENHANCED, 8192,
            config=(0x8007, 0x8008),
            device_id_addr=0x8006,
            eeprom_addr=0xF000, eeprom_bytes=256,
            osccal=0x8008,
            notes="enhanced mid-range: 13-command protocol, not yet implemented",
        ),
        _spec(
            "PIC12F508", Family.BASELINE, 512,
            config=(0xFFF,),
            device_id_addr=None,
            pgc="GP1", pgd="GP0",
            notes="baseline 12-bit: verify OSCCAL address; protocol not yet implemented",
        ),
    ]
}
