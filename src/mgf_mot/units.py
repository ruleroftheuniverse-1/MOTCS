"""Small, explicit conversions used by the replication."""

from math import pi


def mhz_to_hz(value_mhz: float) -> float:
    return value_mhz * 1.0e6


def mhz_to_angular_frequency(value_mhz: float) -> float:
    return 2.0 * pi * mhz_to_hz(value_mhz)


def angular_frequency_to_mhz(value_rad_s: float) -> float:
    return value_rad_s / (2.0 * pi * 1.0e6)


def gauss_to_tesla(value_gauss: float) -> float:
    return value_gauss * 1.0e-4


def gauss_per_cm_to_tesla_per_metre(value_gauss_per_cm: float) -> float:
    return value_gauss_per_cm * 1.0e-2


def mt_per_cm_to_tesla_per_metre(value_mt_per_cm: float) -> float:
    return value_mt_per_cm * 0.1


def mw_per_cm2_to_w_per_m2(value_mw_per_cm2: float) -> float:
    return value_mw_per_cm2 * 10.0


def mm_to_m(value_mm: float) -> float:
    return value_mm * 1.0e-3

