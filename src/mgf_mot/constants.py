"""Published MgF and Rodriguez static-MOT constants.

No unreported spectroscopy constants belong here. In particular, this module
does not supply hyperfine Hamiltonian parameters, transition dipoles, or the
exact excited-state hyperfine splitting.
"""

from dataclasses import dataclass
from math import pi

from .units import gauss_per_cm_to_tesla_per_metre, mhz_to_angular_frequency


@dataclass(frozen=True)
class GroundHyperfineLevel:
    label: str
    g_factor: float | None
    spacing_from_previous_mhz: float | None


GROUND_HYPERFINE_LEVELS = (
    GroundHyperfineLevel("lower_F1", -0.2, None),
    GroundHyperfineLevel("F0", None, 109.0),
    GroundHyperfineLevel("upper_F1", 0.7, 120.0),
    GroundHyperfineLevel("F2", 0.5, 9.0),
)

# Rodriguez includes F'=0 and F'=1 and uses this nearly-zero g-factor in the
# simulation, but does not report their exact splitting.
EXCITED_HYPERFINE_LEVELS = ("F_prime_0", "F_prime_1")
EXCITED_G_FACTOR_SIMULATION = 0.001
EXCITED_HYPERFINE_SPLITTING_MHZ: None = None


@dataclass(frozen=True)
class MgFConstants:
    optical_frequency_hz: float = 834.3e12
    natural_linewidth_rad_s: float = mhz_to_angular_frequency(20.9)
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
