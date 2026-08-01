"""Source-tagged force-unit conversions for offline Track P audits.

Nothing in this module is wired into the provisional trajectory integrator.
The functions make the single ``hbar*k*Gamma`` conversion explicit so saved
engineering trajectories can be audited without silently changing them.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .spectroscopy import LINEWIDTH_MHZ, WAVELENGTH_NM


FloatArray = NDArray[np.float64]

# 2022 CODATA and NIST isotope-composition values. The molecular mass uses the
# separated neutral-atom sum; omitted chemical binding mass is explicitly below.
REDUCED_PLANCK_CONSTANT_J_S = 1.054_571_817e-34
ATOMIC_MASS_CONSTANT_KG = 1.660_539_068_92e-27
MG24_RELATIVE_ATOMIC_MASS_U = 23.985_041_697
F19_RELATIVE_ATOMIC_MASS_U = 18.998_403_162_73

CODATA_2022_SOURCE = (
    "NIST 2022 CODATA recommended values, atomic mass constant and Planck constant; "
    "https://physics.nist.gov/cuu/pdf/wallet_2022.pdf"
)
NIST_MG24_SOURCE = (
    "NIST Atomic Weights and Isotopic Compositions for Magnesium, 24Mg; "
    "https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=Mg"
)
NIST_F19_SOURCE = (
    "NIST Atomic Weights and Isotopic Compositions for Fluorine, 19F; "
    "https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=F"
)


@dataclass(frozen=True)
class SourceTaggedMass:
    value_kg: float
    isotopologue: str
    source: tuple[str, ...]
    status: str
    note: str

    def __post_init__(self) -> None:
        if not isfinite(self.value_kg) or self.value_kg <= 0.0:
            raise ValueError("source-tagged MgF mass must be finite and positive")


MGF24_MASS = SourceTaggedMass(
    value_kg=(MG24_RELATIVE_ATOMIC_MASS_U + F19_RELATIVE_ATOMIC_MASS_U)
    * ATOMIC_MASS_CONSTANT_KG,
    isotopologue="24Mg19F",
    source=(NIST_MG24_SOURCE, NIST_F19_SOURCE, CODATA_2022_SOURCE),
    status="derived_approximate",
    note=(
        "Sum of neutral-atom isotope masses; molecular binding mass is neglected. "
        "This is sufficient for the Track P unit audit and is not spectroscopy input."
    ),
)


@dataclass(frozen=True)
class MgFForceUnitAudit:
    wavelength_m: float
    wave_number_rad_m: float
    linewidth_rad_s: float
    hbar_k_gamma_n: float
    mass: SourceTaggedMass
    acceleration_per_normalized_force_m_s2: float
    wavelength_source: str
    linewidth_source: str
    conversion_count: int = 1

    def __post_init__(self) -> None:
        values = (
            self.wavelength_m,
            self.wave_number_rad_m,
            self.linewidth_rad_s,
            self.hbar_k_gamma_n,
            self.acceleration_per_normalized_force_m_s2,
        )
        if not all(isfinite(value) and value > 0.0 for value in values):
            raise ValueError("force-unit audit values must be finite and positive")
        if self.conversion_count != 1:
            raise ValueError("hbar*k*Gamma conversion must be applied exactly once")


def build_mgf_force_unit_audit() -> MgFForceUnitAudit:
    wavelength_m = WAVELENGTH_NM.require() * 1.0e-9
    wave_number = 2.0 * pi / wavelength_m
    linewidth = 2.0 * pi * LINEWIDTH_MHZ.require() * 1.0e6
    force_unit = REDUCED_PLANCK_CONSTANT_J_S * wave_number * linewidth
    return MgFForceUnitAudit(
        wavelength_m=wavelength_m,
        wave_number_rad_m=wave_number,
        linewidth_rad_s=linewidth,
        hbar_k_gamma_n=force_unit,
        mass=MGF24_MASS,
        acceleration_per_normalized_force_m_s2=force_unit / MGF24_MASS.value_kg,
        wavelength_source=f"{WAVELENGTH_NM.source}; {WAVELENGTH_NM.locator}",
        linewidth_source=f"{LINEWIDTH_MHZ.source}; {LINEWIDTH_MHZ.locator}",
    )


def normalized_force_to_newtons(
    normalized_force: ArrayLike, audit: MgFForceUnitAudit
) -> FloatArray:
    """Apply ``hbar*k*Gamma`` once to a dimensionless force value."""

    if audit.conversion_count != 1:
        raise ValueError("force conversion audit does not represent exactly one conversion")
    values = np.asarray(normalized_force, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("normalized force must be finite")
    return np.asarray(values * audit.hbar_k_gamma_n, dtype=float)


def normalized_force_to_acceleration_m_s2(
    normalized_force: ArrayLike, audit: MgFForceUnitAudit
) -> FloatArray:
    """Convert normalized force to SI force once, then divide by MgF mass."""

    return normalized_force_to_newtons(normalized_force, audit) / audit.mass.value_kg


def acceleration_m_s2_to_normalized_force(
    acceleration_m_s2: ArrayLike, audit: MgFForceUnitAudit
) -> FloatArray:
    """Invert the single-conversion acceleration relation for testing."""

    values = np.asarray(acceleration_m_s2, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("acceleration must be finite")
    return np.asarray(
        values / audit.acceleration_per_normalized_force_m_s2, dtype=float
    )


def trapezoid_impulse(
    times_s: ArrayLike, forces_n: ArrayLike
) -> FloatArray:
    """Integrate force samples along axis zero; useful for analytic tests too."""

    times = np.asarray(times_s, dtype=float)
    forces = np.asarray(forces_n, dtype=float)
    if times.ndim != 1 or forces.shape[0] != times.size or times.size < 2:
        raise ValueError("force samples must share a time axis with at least two points")
    if not np.isfinite(times).all() or not np.isfinite(forces).all():
        raise ValueError("impulse inputs must be finite")
    if np.any(np.diff(times) <= 0.0):
        raise ValueError("impulse times must be strictly increasing")
    return np.asarray(np.trapezoid(forces, times, axis=0), dtype=float)


def cumulative_trapezoid_impulse(
    times_s: ArrayLike, forces_n: ArrayLike
) -> FloatArray:
    """Cumulative trapezoid impulse with an explicit zero at the first sample."""

    times = np.asarray(times_s, dtype=float)
    forces = np.asarray(forces_n, dtype=float)
    if times.ndim != 1 or forces.shape[0] != times.size or times.size < 2:
        raise ValueError("force samples must share a time axis with at least two points")
    increments = 0.5 * (forces[:-1] + forces[1:]) * np.diff(times).reshape(
        (-1,) + (1,) * (forces.ndim - 1)
    )
    zeros = np.zeros((1,) + forces.shape[1:], dtype=float)
    return np.concatenate((zeros, np.cumsum(increments, axis=0)), axis=0)
