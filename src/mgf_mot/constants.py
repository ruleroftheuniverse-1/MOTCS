"""Published MgF and Rodriguez static-MOT constants.

No unreported spectroscopy constants belong here. In particular, this module
does not supply hyperfine Hamiltonian parameters, transition dipoles, or the
exact excited-state hyperfine splitting.
"""

from dataclasses import dataclass
from math import pi

from .units import gauss_per_cm_to_tesla_per_metre, mhz_to_angular_frequency
from .spectroscopy import (
    EXCITED_G_FACTOR_RODRIGUEZ,
    EXCITED_HYPERFINE_SPLITTING_MHZ as SOURCED_EXCITED_SPLITTING,
    GROUND_EFFECTIVE_G_FACTORS,
    LINEWIDTH_MHZ,
    OPTICAL_FREQUENCY_THZ,
    RODRIGUEZ_GROUND_SPACINGS_MHZ,
)


@dataclass(frozen=True)
class GroundHyperfineLevel:
    label: str
    g_factor: float | None
    spacing_from_previous_mhz: float | None


GROUND_HYPERFINE_LEVELS = (
    GroundHyperfineLevel("lower_F1", GROUND_EFFECTIVE_G_FACTORS["lower_F1"].value, None),
    GroundHyperfineLevel(
        "F0",
        GROUND_EFFECTIVE_G_FACTORS["F0"].value,
        RODRIGUEZ_GROUND_SPACINGS_MHZ["lower_F1_to_F0"].require(),
    ),
    GroundHyperfineLevel(
        "upper_F1",
        GROUND_EFFECTIVE_G_FACTORS["upper_F1"].value,
        RODRIGUEZ_GROUND_SPACINGS_MHZ["F0_to_upper_F1"].require(),
    ),
    GroundHyperfineLevel(
        "F2",
        GROUND_EFFECTIVE_G_FACTORS["F2"].value,
        RODRIGUEZ_GROUND_SPACINGS_MHZ["upper_F1_to_F2"].require(),
    ),
)

# Rodriguez includes F'=0 and F'=1 and uses this nearly-zero g-factor in the
# simulation, but does not report their exact splitting.
EXCITED_HYPERFINE_LEVELS = ("F_prime_0", "F_prime_1")
EXCITED_G_FACTOR_SIMULATION = EXCITED_G_FACTOR_RODRIGUEZ.require()
EXCITED_HYPERFINE_SPLITTING_MHZ: float | None = SOURCED_EXCITED_SPLITTING.value


@dataclass(frozen=True)
class MgFConstants:
    optical_frequency_hz: float = OPTICAL_FREQUENCY_THZ.require() * 1e12
    natural_linewidth_rad_s: float = mhz_to_angular_frequency(LINEWIDTH_MHZ.require())
    saturation_intensity_w_m2: float = 600.0
    velocity_unit_m_s: float = 7.53
    recoil_velocity_m_s: float = 0.026
    ground_state_count: int = 12
    excited_state_count: int = 4
    excited_g_factor_simulation: float = EXCITED_G_FACTOR_SIMULATION

    @property
    def wavelength_m(self) -> float:
        return 299_792_458.0 / self.optical_frequency_hz

    @property
    def wave_number_rad_m(self) -> float:
        return 2.0 * pi / self.wavelength_m


@dataclass(frozen=True)
class RodriguezStaticConstants:
    gradient_t_m: float = gauss_per_cm_to_tesla_per_metre(20.0)
    position_unit_m: float = 7.48e-3


MGF = MgFConstants()
RODRIGUEZ_STATIC = RodriguezStaticConstants()
