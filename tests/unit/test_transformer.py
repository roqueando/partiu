"""Unit tests for the HF transformer design (domain layer)."""

from partiu.domain.engineering.transformer import (
    AWG_WIRES,
    EE_CORES,
    design,
    select_core,
    select_wire,
)


def test_select_core_picks_smallest_fitting():
    core = select_core(0.05)
    assert core is not None
    # The selected core's Ae·Aw covers the requirement.
    assert core[3] >= 0.05


def test_select_core_returns_none_when_too_large():
    assert select_core(1000.0) is None


def test_select_wire_picks_thickest_fitting():
    wire = select_wire(0.05)  # 0.05 cm skin limit
    assert wire is not None
    assert wire[3] <= 0.05


def test_design_produces_expected_keys():
    result = design(
        duty=0.45,
        vin=12.0,
        il1_rms=1.0,
        il1_max=2.0,
        il2_rms=1.0,
        pin=17.857,
        freq=65000.0,
        n=2,
    )
    for key in ("AeAw", "entreferro", "N1", "N2", "Awire1", "Awire2", "Exec"):
        assert key in result
    assert result["N1"] > 0
    assert result["N2"] > 0


def test_design_rejects_bad_duty():
    try:
        design(duty=0, vin=12, il1_rms=1, il1_max=2, il2_rms=1, pin=10, freq=65000, n=2)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
