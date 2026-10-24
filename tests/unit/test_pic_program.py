"""Unit tests for the PIC programmer use cases (fake device-level programmer)."""

from partiu.application.use_cases import pic_program as uc
from partiu.domain.engineering.pic import DeviceConfig, DeviceSpec, Family, PicMemoryImage


def _spec(**kw) -> DeviceSpec:
    defaults = dict(
        name="T",
        family=Family.MIDRANGE,
        program_words=4,
        config_addresses=(0x2007,),
        id_addresses=(0x2000, 0x2001, 0x2002, 0x2003),
        device_id_address=0x2006,
        eeprom_address=0x2100,
        eeprom_bytes=0,
        device_id_value=0x1060,
    )
    defaults.update(kw)
    return DeviceSpec(**defaults)


class FakePicProgrammer:
    """Models a 14-bit PIC's memory behind the PicProgrammer port."""

    def __init__(self, spec: DeviceSpec, *, program=None, fuses=None, calibration=None):
        self.spec = spec
        self.mask = spec.word_mask
        self.blank = self.mask
        self.program = list(program) if program else [self.blank] * spec.program_words
        self.fuses = list(fuses) if fuses else [self.blank]
        self.eeprom: list[int] = []
        self.id_words: list[int] = [0] * 4
        self.calibration = calibration
        self.chip_id = spec.device_id_value or 0x1060
        self.opened = False
        self.erase_calls = 0

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False

    def read_program(self):
        return list(self.program)

    def read_eeprom(self):
        return list(self.eeprom)

    def read_config(self):
        return DeviceConfig(
            chip_id=self.chip_id,
            id_words=list(self.id_words),
            fuses=list(self.fuses),
            calibration=self.calibration,
        )

    def erase(self):
        self.erase_calls += 1
        self.program = [self.blank] * len(self.program)
        self.fuses = [self.blank] * len(self.fuses)

    def program_program(self, words):
        self.program = [w & self.mask for w in words]

    def program_eeprom(self, data):
        self.eeprom = [b & 0xFF for b in data]

    def program_config(self, id_words, fuses):
        self.id_words = [w & self.mask for w in id_words]
        self.fuses = [w & self.mask for w in fuses]

    def program_calibration(self, cal, fuse):
        self.calibration = cal & self.mask
        if self.fuses:
            self.fuses[0] = fuse & self.mask


# ---------------------------------------------------------------------------
# detect_device
# ---------------------------------------------------------------------------

def test_detect_device_matches_catalog():
    spec = _spec(device_id_value=0x1060)
    programmer = FakePicProgrammer(spec)
    chip_id, expected, matched = uc.detect_device(programmer, spec)
    assert chip_id == 0x1060
    assert expected == 0x1060
    assert matched is True


def test_detect_device_no_expected_id():
    spec = _spec(device_id_value=None)
    programmer = FakePicProgrammer(spec)
    _, expected, matched = uc.detect_device(programmer, spec)
    assert expected is None
    assert matched is None


# ---------------------------------------------------------------------------
# read_device
# ---------------------------------------------------------------------------

def test_read_device_builds_image():
    spec = _spec()
    programmer = FakePicProgrammer(spec, program=[0x2A5, 0x3F7A, 0x3FFF, 0x3FFF])
    image = uc.read_device(programmer, spec)
    assert image.program == [0x2A5, 0x3F7A, 0x3FFF, 0x3FFF]
    assert image.config == [0x3FFF]
    assert image.device_id == 0x1060


# ---------------------------------------------------------------------------
# program_device
# ---------------------------------------------------------------------------

def test_program_device_writes_and_verifies():
    spec = _spec()
    programmer = FakePicProgrammer(spec)
    image = PicMemoryImage(
        word_bits=14,
        program=[0x2A5, 0x3F7A, 0x1000, 0x0001],
        config=[0x3F7A],
    )
    report = uc.program_device(programmer, spec, image)
    assert report.verified is True
    assert report.failures == []
    assert report.programmed == 4
    assert report.config_programmed == 1
    assert programmer.program == [0x2A5, 0x3F7A, 0x1000, 0x0001]
    assert programmer.fuses == [0x3F7A]
    assert programmer.erase_calls == 1  # erase by default


def test_program_device_without_erase():
    spec = _spec()
    programmer = FakePicProgrammer(spec)
    image = PicMemoryImage(word_bits=14, program=[0x0001, 0x0002, 0x0003, 0x0004])
    uc.program_device(programmer, spec, image, erase=False)
    assert programmer.erase_calls == 0


def test_program_device_reports_verify_failure():
    spec = _spec()
    programmer = FakePicProgrammer(spec)

    class _Broken(FakePicProgrammer):
        # Read-back always returns a wrong word.
        def read_program(self):
            return [0x0000] * self.spec.program_words

    broken = _Broken(spec)
    image = PicMemoryImage(word_bits=14, program=[0x2A5, 0x3F7A, 0x1000, 0x0001])
    report = uc.program_device(broken, spec, image)
    assert report.verified is False
    assert report.failures


# ---------------------------------------------------------------------------
# verify_device
# ---------------------------------------------------------------------------

def test_verify_device_detects_mismatch():
    spec = _spec()
    programmer = FakePicProgrammer(spec, program=[0x0001, 0x0002, 0x0003, 0x0004])
    image = PicMemoryImage(
        word_bits=14, program=[0x0001, 0x0002, 0x3FFF, 0x0004], config=[0x3FFF]
    )
    mismatches = uc.verify_device(programmer, spec, image)
    assert mismatches == [("program", 2, 0x3FFF, 0x0003)]


# ---------------------------------------------------------------------------
# blank_check
# ---------------------------------------------------------------------------

def test_blank_check_reports_nonblank():
    spec = _spec()
    programmer = FakePicProgrammer(spec, program=[0x3FFF, 0x0000, 0x3FFF, 0x3FFF])
    nonblank = uc.blank_check(programmer, spec)
    assert nonblank == [("program", 1, 0x0000)]


def test_erase_device():
    spec = _spec()
    programmer = FakePicProgrammer(spec, program=[0x0001, 0x0002, 0x0003, 0x0004])
    uc.erase_device(programmer)
    assert programmer.erase_calls == 1
    assert programmer.program == [0x3FFF] * 4
