"""Unit tests for the E-Series calculator (domain layer)."""

from partiu.domain.engineering.eseries import (
    nearest,
    parse_si,
    series_for_tolerance,
)

import pytest


def test_parse_si_prefixes():
    assert parse_si("4.7k") == 4700.0
    assert parse_si("100n") == pytest.approx(1e-7)
    assert parse_si("10µ") == pytest.approx(1e-5)
    assert parse_si("47") == 47.0


def test_parse_si_rejects_bad_input():
    try:
        parse_si("abc")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_series_for_tolerance():
    assert series_for_tolerance("20%") == "E6"
    assert series_for_tolerance("5%") == "E24"
    assert series_for_tolerance("1%") == "E96"


def test_nearest_exact():
    result = nearest(470.0, "E24")
    assert result.value == 470.0
    assert result.series == "E24"


def test_nearest_returns_neighbours():
    result = nearest(1000.0, "E24")
    assert result.value == 1000.0
    assert result.lower <= result.value <= result.higher


def test_nearest_rejects_nonpositive():
    try:
        nearest(0.0, "E24")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
