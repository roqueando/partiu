"""Unit tests for the PIC domain package (pure logic, no hardware)."""

from partiu.domain.engineering.pic import (
    DEVICES,
    DeviceSpec,
    Family,
    HexError,
    HexRecord,
    build_image,
    command_bits,
    encode_command,
    parse_hex,
    records_to_bytes,
    serialize_eeprom_byte,
    serialize_word,
)
from partiu.domain.engineering.pic import hexfile

import pytest


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def test_encode_command_msb_first():
    assert encode_command(0x02) == [0, 0, 0, 0, 1, 0]
    assert encode_command(0x0E) == [0, 0, 1, 1, 1, 0]
    assert encode_command(0x1F) == [0, 1, 1, 1, 1, 1]


def test_encode_command_out_of_range():
    with pytest.raises(ValueError):
        encode_command(0x40)
    with pytest.raises(ValueError):
        encode_command(-1)


def test_serialize_word_frames_start_stop_bits():
    assert serialize_word(0x3FFF, 14) == [0] + [1] * 14 + [0]
    assert serialize_word(0x0000, 14) == [0] + [0] * 14 + [0]
    # 0x2000 = bit 13 set
    bits = serialize_word(0x2000, 14)
    assert bits == [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]


def test_serialize_eeprom_byte_lsb_first():
    # 0x01 → data(0:7) LSB-first = 1,0,0,0,0,0,0,0
    assert serialize_eeprom_byte(0x01) == [0, 1, 0, 0, 0, 0, 0, 0, 0] + [0] * 7
    assert len(serialize_eeprom_byte(0xFF)) == 16


def test_command_bits_midrange_and_unsupported_families():
    assert command_bits(Family.MIDRANGE, "increment_address") == encode_command(0x06)
    with pytest.raises(NotImplementedError):
        command_bits(Family.BASELINE, "increment_address")
    with pytest.raises(NotImplementedError):
        command_bits(Family.ENHANCED, "increment_address")


# ---------------------------------------------------------------------------
# hexfile
# ---------------------------------------------------------------------------

def test_parse_hex_two_records():
    text = ":020000040000FA\n:040000000A0B0C0DCE\n:00000001FF\n"
    records = parse_hex(text)
    assert len(records) == 1
    assert records[0].address == 0x0000
    assert records[0].data == bytes([0x0A, 0x0B, 0x0C, 0x0D])


def test_parse_hex_extended_linear_address():
    # base 0x0001 << 16 = 0x10000; data at offset 0x0002 → 0x10002
    text = ":020000040001F9\n:02000200CAFE34\n:00000001FF\n"
    records = parse_hex(text)
    assert len(records) == 1
    assert records[0].address == 0x10002
    assert records[0].data == bytes([0xCA, 0xFE])


def test_parse_hex_rejects_bad_checksum():
    text = ":040000000A0B0C0D9C\n:00000001FF\n"
    with pytest.raises(HexError):
        parse_hex(text)


def test_parse_hex_requires_eof():
    text = ":040000000A0B0C0DCE\n"
    with pytest.raises(HexError):
        parse_hex(text)


def test_records_to_bytes_little_endian_flat():
    records = [HexRecord(hexfile.DATA, 0x0000, bytes([0xFF, 0x3F]))]
    assert records_to_bytes(records) == {0x0000: 0xFF, 0x0001: 0x3F}


# ---------------------------------------------------------------------------
# devices
# ---------------------------------------------------------------------------

def test_word_masks_per_family():
    assert DEVICES["PIC16F628A"].word_mask == 0x3FFF
    assert DEVICES["PIC12F508"].word_mask == 0x0FFF


def test_seed_catalog_has_core_devices():
    for name in ("PIC16F84A", "PIC16F628A", "PIC16F877A", "PIC12F675", "PIC16F1829"):
        assert name in DEVICES


# ---------------------------------------------------------------------------
# memory image
# ---------------------------------------------------------------------------

def _spec(program_words: int = 2, **kw) -> DeviceSpec:
    defaults = dict(
        name="T",
        family=Family.MIDRANGE,
        program_words=program_words,
        config_addresses=(0x2007,),
        id_addresses=(0x2000, 0x2001, 0x2002, 0x2003),
        device_id_address=0x2006,
        eeprom_address=0x2100,
        eeprom_bytes=2,
        osccal_address=0x3FF,
    )
    defaults.update(kw)
    return DeviceSpec(**defaults)


def test_build_image_maps_regions_and_masks():
    spec = _spec()
    records = [
        HexRecord(hexfile.DATA, 0x0000, bytes([0xFF, 0xFF])),  # word 0 → 0x3FFF
        HexRecord(hexfile.DATA, 0x0002, bytes([0x00, 0x20])),  # word 1 → 0x2000
        HexRecord(hexfile.DATA, 0x2007, bytes([0x7A, 0x3F])),  # config → 0x3F7A
        HexRecord(hexfile.DATA, 0x2000, bytes([0x01, 0x02, 0x03, 0x04])),  # ID bytes
        HexRecord(hexfile.DATA, 0x2100, bytes([0x11, 0x22])),  # eeprom
        HexRecord(hexfile.DATA, 0x3FF, bytes([0x84, 0x34])),   # osccal → 0x3484
    ]
    image = build_image(records, spec)
    assert image.program == [0x3FFF, 0x2000]
    assert image.config == [0x3F7A]
    assert image.id == [0x01, 0x02, 0x03, 0x04]
    assert image.eeprom == [0x11, 0x22]
    assert image.osccal == 0x3484


def test_build_image_config_at_doubled_address():
    # MPLAB X / INHX32 stores the config word at 2× the word address.
    spec = _spec(program_words=1)
    records = [
        HexRecord(hexfile.DATA, 0x0000, bytes([0xAA, 0x2A])),  # program
        HexRecord(hexfile.DATA, 0x400E, bytes([0xFF, 0x31])),  # config 0x2007 × 2
    ]
    image = build_image(records, spec)
    assert image.config == [0x31FF]
    assert image.program == [0x2AAA]


def test_build_image_no_config_is_empty():
    spec = _spec(program_words=1)
    records = [HexRecord(hexfile.DATA, 0x0000, bytes([0xAA, 0x2A]))]
    image = build_image(records, spec)
    assert image.config == []  # absent config → empty, not a fake 0x0000


def test_build_image_masks_to_word_bits():
    spec = _spec(program_words=1)
    records = [HexRecord(hexfile.DATA, 0x0000, bytes([0xFF, 0xFF]))]
    image = build_image(records, spec)
    assert image.program == [0x3FFF]  # 0xFFFF masked to 14 bits


def test_image_hex_roundtrip():
    from partiu.domain.engineering.pic import (
        PicMemoryImage,
        format_hex,
        image_to_records,
    )

    spec = _spec(program_words=2)
    original = PicMemoryImage(
        word_bits=14,
        program=[0x2A5, 0x3F7A],
        config=[0x3F7A],
        id=[0x0001, 0x0002, 0x0003, 0x0004],
        eeprom=[0x11, 0x22],
        osccal=0x3484,
    )
    text = format_hex(image_to_records(original, spec))
    restored = build_image(parse_hex(text), spec)

    assert restored.program == original.program
    assert restored.config == original.config
    assert restored.id == original.id
    assert restored.eeprom == original.eeprom
    assert restored.osccal == original.osccal
