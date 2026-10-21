"""Unit tests for the flyback DCM calculator (domain layer)."""

from partiu.domain.engineering.flyback import calculate, defaults


def test_calculate_defaults_returns_expected_shapes():
    d = defaults()
    result = calculate(
        vin=d["vin"],
        vin_max=d["vin_max"],
        vout=d["vout"],
        iout=d["iout"],
        ripple=d["ripple"] / 100,
        eta=d["eta"] / 100,
        duty=d["duty"] / 100,
        freq=d["freq"] * 1000,
    )
    assert isinstance(result["n"], int)
    assert result["n"] >= 1
    assert result["Pout"] == 12.5
    assert abs(result["Pin"] - 12.5 / 0.70) < 1e-9
    assert result["L1"] > 0
    assert result["C"] > 0
    assert result["Vds_max"] > result["vin"] if "vin" in result else True


def test_calculate_rejects_bad_inputs():
    try:
        calculate(vin=0, vin_max=35, vout=5, iout=2.5, ripple=0.005, eta=0.7, duty=0.45, freq=65000)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_defaults_are_ui_units():
    d = defaults()
    assert d["vin"] == 12.0
    assert 0 < d["duty"] < 100
    assert 0 < d["eta"] <= 100
