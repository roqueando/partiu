"""Kitsrus K149/K150 device catalog (programming-variables metadata).

Maps each supported PIC10/12/16 to the parameters the K150 firmware needs in
its "Initialise Programming Variables" command (command 3): ROM size, EEPROM
size, **core type**, program flags, program delay, power sequence, erase mode,
program tries and over-program count.

Core types and delays are the factual per-device values used by the K150
firmware (see the kitsrus firmware protocol document and Microchip programming
specifications).  ``core_type`` values 11-13 (the 12-bit "B" core and newer
cores) require **firmware P018/P18A** — the original P014/P016 firmware only
knows cores 0-10, so those devices fail with a clear error on old firmware.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from partiu.domain.engineering.pic import DeviceSpec, Family

#: Kitsrus core-type name → firmware core-type byte (P014/P016 use 0-10;
#: P018/P18A add 11 (16F57) and 12 (10Fxxx)).
CORE_TYPE: dict[str, int] = {
    "bit14_g": 3,   # 16F87/88
    "bit12_a": 4,   # 12C50x / 12F508-509 / 16F505-510
    "bit14_a": 5,   # 12C67x 16C50x 16Cxxx
    "bit14_b": 6,   # 16C8x 16F8x 16F87x 16F62x
    "bit14_c": 7,   # 16F7x
    "bit14_d": 8,   # 12F67x
    "bit14_e": 9,   # 16F87xA
    "bit14_f": 10,  # 16F818/819
    "bit12_b": 11,  # 16F54/57/59 (P018+)
    "newf12b": 12,  # 10Fxxx (P018+)
}

#: Power-sequence name → firmware byte (command 3, field 8).
POWER_SEQUENCE: dict[str, int] = {
    "Vcc": 0,
    "VccVpp1": 1,
    "VccVpp2": 2,
    "Vpp1Vcc": 3,
    "Vpp2Vcc": 4,
    "VccFastVpp1": 1,
    "VccFastVpp2": 2,
}

#: Power sequences that set the "very small VCC→VPP delay" flag (bit 3).
VCC_VPP_DELAY: frozenset[str] = frozenset({"VccFastVpp1", "VccFastVpp2"})

#: Core types that require firmware P018/P18A (not present in P014/P016).
P018_ONLY_CORES: frozenset[int] = frozenset({11, 12})


@dataclass(frozen=True)
class KitsrusDeviceSpec:
    """A device as the K150 firmware sees it, plus its generic PIC descriptor."""

    device: DeviceSpec
    core_type: int
    power_sequence: int
    erase_mode: int
    program_delay: int
    program_tries: int = 1
    over_program: int = 0
    cal_word: bool = False
    band_gap: bool = False
    vcc_vpp_delay: bool = False

    def programming_variables(self) -> bytes:
        """Encode the 11-byte payload of firmware command 3."""
        flags = (
            (1 if self.cal_word else 0)
            | (2 if self.band_gap else 0)
            | (8 if self.vcc_vpp_delay else 0)
        )
        return struct.pack(
            ">HHBBBBBBB",
            self.device.program_words,
            self.device.eeprom_bytes,
            self.core_type,
            flags,
            self.program_delay,
            self.power_sequence,
            self.erase_mode,
            self.program_tries,
            self.over_program,
        )


_ID_ADDRS = (0x2000, 0x2001, 0x2002, 0x2003)


def _mk(
    name: str,
    family: Family,
    words: int,
    core: str,
    power: str,
    erase: int,
    delay: int,
    *,
    eeprom: int = 0,
    cal: bool = False,
    bg: bool = False,
    chip_id: int | None = None,
) -> KitsrusDeviceSpec:
    config = (0xFFF,) if family is Family.BASELINE else (0x2007,)
    device_id_addr = None if family is Family.BASELINE else 0x2006
    eeprom_base = 0x2100 if family is Family.MIDRANGE else None
    device = DeviceSpec(
        name=name,
        family=family,
        program_words=words,
        config_addresses=config,
        id_addresses=_ID_ADDRS,
        device_id_address=device_id_addr,
        eeprom_address=eeprom_base if eeprom else None,
        eeprom_bytes=eeprom,
        osccal_address=0x3FF if cal else None,
        device_id_value=chip_id,
    )
    return KitsrusDeviceSpec(
        device=device,
        core_type=CORE_TYPE[core],
        power_sequence=POWER_SEQUENCE[power],
        erase_mode=erase,
        program_delay=delay,
        cal_word=cal,
        band_gap=bg,
        vcc_vpp_delay=power in VCC_VPP_DELAY,
    )


#: Seed catalog — PIC10/12/16 devices with their real K150 programming variables.
KITSRUS_DEVICES: dict[str, KitsrusDeviceSpec] = {
    spec.device.name: spec
    for spec in [
        # --- baseline 12-bit (PIC10F / PIC12F5xx / PIC16F5x) ---
        _mk("PIC10F200", Family.BASELINE, 0x100, "newf12b", "VccVpp1", 6, 20, cal=True),
        _mk("PIC10F202", Family.BASELINE, 0x200, "newf12b", "VccVpp1", 6, 20, cal=True),
        _mk("PIC10F204", Family.BASELINE, 0x100, "newf12b", "VccVpp1", 6, 20, cal=True),
        _mk("PIC10F206", Family.BASELINE, 0x200, "newf12b", "VccVpp1", 6, 20, cal=True),
        _mk("PIC10F220", Family.BASELINE, 0x100, "newf12b", "VccVpp1", 6, 20, cal=True),
        _mk("PIC10F222", Family.BASELINE, 0x200, "newf12b", "VccVpp1", 6, 20, cal=True),
        _mk("PIC12F508", Family.BASELINE, 0x200, "bit12_a", "VccVpp2", 6, 20, cal=True),
        _mk("PIC12F509", Family.BASELINE, 0x400, "bit12_a", "VccVpp2", 6, 20, cal=True),
        _mk("PIC16F505", Family.BASELINE, 0x400, "bit12_a", "VccVpp2", 6, 20, cal=True),
        _mk("PIC16F506", Family.BASELINE, 0x400, "bit12_a", "VccVpp2", 6, 20, cal=True),
        _mk("PIC16F510", Family.BASELINE, 0x400, "bit12_a", "VccVpp2", 6, 20, cal=True),
        _mk("PIC16F54", Family.BASELINE, 0x200, "bit12_b", "VccVpp2", 7, 50),
        _mk("PIC16F57", Family.BASELINE, 0x800, "bit12_b", "VccVpp1", 7, 50),
        _mk("PIC16F59", Family.BASELINE, 0x800, "bit12_b", "VccVpp1", 7, 50),
        # --- mid-range 14-bit (PIC12F6xx / PIC16Fxx) ---
        _mk("PIC16F84A", Family.MIDRANGE, 0x400, "bit14_b", "VccVpp2", 0, 80, eeprom=0x40, chip_id=0x0560),
        _mk("PIC16F627A", Family.MIDRANGE, 0x400, "bit14_b", "Vpp2Vcc", 2, 50, eeprom=0x80, chip_id=0x1040),
        _mk("PIC16F628A", Family.MIDRANGE, 0x800, "bit14_b", "Vpp2Vcc", 2, 50, eeprom=0x80, chip_id=0x1060),
        _mk("PIC12F629", Family.MIDRANGE, 0x400, "bit14_b", "Vpp2Vcc", 2, 80, eeprom=0x80, cal=True, bg=True, chip_id=0x0F80),
        _mk("PIC12F675", Family.MIDRANGE, 0x400, "bit14_b", "Vpp2Vcc", 2, 80, eeprom=0x80, cal=True, bg=True, chip_id=0x0FC0),
        _mk("PIC12F683", Family.MIDRANGE, 0x800, "bit14_b", "Vpp2Vcc", 2, 60, eeprom=0x100, chip_id=0x0460),
        _mk("PIC16F690", Family.MIDRANGE, 0x1000, "bit14_b", "Vpp2Vcc", 2, 60, eeprom=0x100, chip_id=0x1400),
        _mk("PIC16F819", Family.MIDRANGE, 0x800, "bit14_f", "VccVpp2", 5, 10, eeprom=0x100, chip_id=0x04E0),
        _mk("PIC16F88", Family.MIDRANGE, 0x1000, "bit14_g", "VccVpp2", 5, 10, eeprom=0x100, chip_id=0x0760),
        _mk("PIC16F873A", Family.MIDRANGE, 0x1000, "bit14_e", "VccVpp1", 5, 10, eeprom=0x80, chip_id=0x0E40),
        _mk("PIC16F876A", Family.MIDRANGE, 0x2000, "bit14_e", "VccVpp1", 5, 10, eeprom=0x100, chip_id=0x0E00),
        _mk("PIC16F877A", Family.MIDRANGE, 0x2000, "bit14_e", "VccVpp1", 5, 10, eeprom=0x100, chip_id=0x0E20),
    ]
}


class KitsrusDeviceCatalog:
    """DeviceCatalog adapter backed by :data:`KITSRUS_DEVICES`."""

    def get(self, name: str) -> KitsrusDeviceSpec | None:
        return KITSRUS_DEVICES.get(name.upper())

    def names(self) -> list[str]:
        return sorted(KITSRUS_DEVICES)
