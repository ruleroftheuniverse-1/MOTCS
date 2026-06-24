from math import isclose, pi

from mgf_mot.units import (
    angular_frequency_to_mhz,
    gauss_per_cm_to_tesla_per_metre,
    gauss_to_tesla,
    mhz_to_angular_frequency,
    mt_per_cm_to_tesla_per_metre,
    mw_per_cm2_to_w_per_m2,
)


def test_frequency_conversions_round_trip() -> None:
    linewidth = mhz_to_angular_frequency(20.9)
    assert isclose(linewidth, 2 * pi * 20.9e6)
    assert isclose(angular_frequency_to_mhz(linewidth), 20.9)


def test_magnetic_field_conversions() -> None:
    assert isclose(gauss_to_tesla(1.0), 1e-4)
    assert isclose(gauss_per_cm_to_tesla_per_metre(20.0), 0.2)
    assert isclose(mt_per_cm_to_tesla_per_metre(2.0), 0.2)


def test_intensity_conversion() -> None:
    assert isclose(mw_per_cm2_to_w_per_m2(60.0), 600.0)

