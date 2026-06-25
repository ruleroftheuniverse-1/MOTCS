"""Source-tagged spectroscopy inputs for the MgF validation model.

Values in this module are data with provenance, not free numerical defaults.
Unknown or backend-incompatible quantities remain explicit ``None`` values.
"""

from dataclasses import dataclass
from typing import Literal

ValueStatus = Literal["exact", "derived", "approximate", "unknown", "model_assumption"]


@dataclass(frozen=True)
class SourcedConstant:
    """A numerical input together with enough provenance to audit its use."""

    name: str
    value: float | None
    units: str
    source: str
    locator: str
    status: ValueStatus
    note: str = ""

    def require(self) -> float:
        if self.value is None:
            raise MissingSpectroscopyConstantError(
                f"{self.name} is unknown: {self.note or self.locator}"
            )
        return self.value


class MissingSpectroscopyConstantError(ValueError):
    """Raised when construction would otherwise replace an unknown value."""


DOPPELBAUER = (
    "M. Doppelbauer et al., J. Chem. Phys. 156, 134301 (2022), "
    "doi:10.1063/5.0081902"
)
ANDERSON = (
    "M. A. Anderson, M. D. Allen, and L. M. Ziurys, J. Chem. Phys. "
    "100, 824 (1994), doi:10.1063/1.466565"
)
RODRIGUEZ = (
    "K. J. Rodriguez et al., Phys. Rev. A 108, 033105 (2023), "
    "doi:10.1103/PhysRevA.108.033105"
)
NORRGARD = (
    "E. B. Norrgard et al., Phys. Rev. A 108, 032809 (2023), "
    "doi:10.1103/PhysRevA.108.032809"
)
PYLCP = (
    "S. Eckel et al., Comput. Phys. Commun. 270, 108166 (2022), "
    "doi:10.1016/j.cpc.2021.108166"
)


def _constant(
    name: str,
    value: float | None,
    units: str,
    source: str,
    locator: str,
    status: ValueStatus,
    note: str = "",
) -> SourcedConstant:
    return SourcedConstant(name, value, units, source, locator, status, note)


# X 2Sigma+, v=0. Doppelbauer Table II reproduces the Anderson values and
# explicitly gives b_F = b + c/3. Frequencies here are ordinary MHz, not rad/s.
GROUND_ROTATIONAL_B_MHZ = _constant(
    "ground_rotational_B", 15496.8125, "MHz", ANDERSON,
    "Doppelbauer Table II (reproduced from Anderson)", "exact"
)
GROUND_CENTRIFUGAL_D_MHZ = _constant(
    "ground_centrifugal_D", 0.03238, "MHz", ANDERSON,
    "Doppelbauer Table II (reproduced from Anderson)", "exact",
    "Not used by pylcp.Xstate; it is a common fixed-N correction in this model."
)
GROUND_SPIN_ROTATION_GAMMA_MHZ = _constant(
    "ground_spin_rotation_gamma", 50.697, "MHz", ANDERSON,
    "Doppelbauer Table II (reproduced from Anderson)", "exact"
)
GROUND_FERMI_CONTACT_BF_MHZ = _constant(
    "ground_fermi_contact_b_F", 214.2, "MHz", ANDERSON,
    "Doppelbauer Table II (reproduced from Anderson)", "exact"
)
GROUND_DIPOLAR_C_MHZ = _constant(
    "ground_dipolar_c", 178.5, "MHz", ANDERSON,
    "Doppelbauer Table II (reproduced from Anderson)", "exact"
)
GROUND_BACKEND_B_MHZ = _constant(
    "ground_backend_b",
    GROUND_FERMI_CONTACT_BF_MHZ.require() - GROUND_DIPOLAR_C_MHZ.require() / 3.0,
    "MHz",
    DOPPELBAUER,
    "Table II note: b_F = b + c/3",
    "derived",
    "This is the isotropic b argument expected by pylcp.Xstate.",
)
GROUND_NUCLEAR_SPIN_ROTATION_CI_MHZ = _constant(
    "ground_nuclear_spin_rotation_CI", 0.0, "MHz", RODRIGUEZ,
    "Model Hamiltonian description and fixed X(v=0,N=1) manifold", "model_assumption",
    "Term excluded from the cited effective model; zero is an explicit model boundary, not a measured value."
)
GROUND_ELECTRIC_QUADRUPOLE_Q0_MHZ = _constant(
    "ground_electric_quadrupole_q0", 0.0, "MHz", PYLCP,
    "XFmolecules.Xstate; fluorine I=1/2", "derived",
    "A spin-1/2 nucleus has no electric quadrupole moment."
)
GROUND_ELECTRIC_QUADRUPOLE_Q2_MHZ = _constant(
    "ground_electric_quadrupole_q2", 0.0, "MHz", PYLCP,
    "XFmolecules.Xstate; fluorine I=1/2", "derived",
    "A spin-1/2 nucleus has no electric quadrupole moment."
)
ELECTRON_G_FACTOR = _constant(
    "electron_g_factor", 2.0023193043622, "dimensionless", PYLCP,
    "Official CaF molecular-MOT example; CODATA value", "exact"
)
BOHR_MAGNETON_MHZ_PER_GAUSS = _constant(
    "bohr_magneton_muB", 1.3996244917100003, "MHz/G", PYLCP,
    "XFmolecules.py default from scipy.constants", "exact",
    "Passed explicitly to avoid inheriting an undocumented pylcp default."
)
NUCLEAR_MAGNETON_MHZ_PER_GAUSS = _constant(
    "nuclear_magneton_muN", 0.0007622593218797592, "MHz/G", PYLCP,
    "XFmolecules.py default from scipy.constants and electron/proton mass ratio", "exact",
    "Passed explicitly to avoid inheriting an undocumented pylcp default."
)
GROUND_NUCLEAR_G_FACTOR = _constant(
    "ground_fluorine_nuclear_g_factor", None, "dimensionless", ANDERSON,
    "Not required for the present zero-field level validation", "unknown",
    "Must be sourced and convention-checked before pylcp magnetic-moment matrices are trusted."
)


# A 2Pi, v'=0. Doppelbauer resolves combinations, not all individual backend
# parameters. They must not be split into invented b/c or p/q values.
EXCITED_ROTATIONAL_B_MHZ = _constant(
    "excited_rotational_B", 15788.2, "MHz", DOPPELBAUER,
    "Table III", "exact"
)
EXCITED_SPIN_ROTATION_GAMMA_MHZ = _constant(
    "excited_spin_rotation_gamma", -53.0, "MHz", DOPPELBAUER,
    "Table III", "approximate",
    "Strongly correlated with A; Table III reports the constrained combination A+gamma."
)
EXCITED_A_PLUS_GAMMA_MHZ = _constant(
    "excited_A_plus_gamma", 1091346.0, "MHz", DOPPELBAUER,
    "Table III", "exact"
)
EXCITED_P_PLUS_2Q_MHZ = _constant(
    "excited_p_plus_2q", 15.0, "MHz", DOPPELBAUER,
    "Table III", "exact",
    "Only the combination is constrained; separate pylcp p and q inputs are unknown."
)
EXCITED_HYPERFINE_A_MHZ = _constant(
    "excited_hyperfine_a", 109.0, "MHz", DOPPELBAUER,
    "Table III", "exact"
)
EXCITED_BF_PLUS_2C_OVER_3_MHZ = _constant(
    "excited_b_F_plus_2c_over_3", -52.0, "MHz", DOPPELBAUER,
    "Table III", "exact",
    "Only this combination is constrained; separate pylcp b and c inputs are unknown."
)
EXCITED_HYPERFINE_D_MHZ = _constant(
    "excited_hyperfine_d", 135.0, "MHz", DOPPELBAUER,
    "Table III and effective-Hamiltonian appendix", "exact",
    "Independent fitted term; pylcp 1.0.2 Astate has no independently adjustable d operator."
)
EXCITED_BACKEND_B_MHZ = _constant(
    "excited_backend_b", None, "MHz", DOPPELBAUER,
    "Table III reports only b_F+2c/3", "unknown",
    "Cannot be separated without an additional sourced constraint."
)
EXCITED_BACKEND_C_MHZ = _constant(
    "excited_backend_c", None, "MHz", DOPPELBAUER,
    "Table III reports only b_F+2c/3", "unknown",
    "Cannot be separated without an additional sourced constraint."
)
EXCITED_BACKEND_P_MHZ = _constant(
    "excited_backend_p", None, "MHz", DOPPELBAUER,
    "Table III reports only p+2q", "unknown",
    "Cannot be separated without an additional sourced constraint."
)
EXCITED_BACKEND_Q_MHZ = _constant(
    "excited_backend_q", None, "MHz", DOPPELBAUER,
    "Table III reports only p+2q", "unknown",
    "Cannot be separated without an additional sourced constraint."
)
EXCITED_HYPERFINE_SPLITTING_MHZ = _constant(
    "excited_F0_F1_splitting", None, "MHz", DOPPELBAUER,
    "Must be calculated from the complete positive-parity effective Hamiltonian", "unknown",
    "Not tabulated by Rodriguez and not yet validated against Doppelbauer line positions."
)
EXCITED_G_FACTOR_RODRIGUEZ = _constant(
    "excited_g_factor", 0.001, "dimensionless", RODRIGUEZ,
    "Page 2, representative simulation value", "approximate",
    "The paper states that the sign and precise value were not known; this is a replication assumption."
)
EXCITED_BACKEND_GL = _constant(
    "excited_backend_gL", None, "dimensionless", RODRIGUEZ,
    "Page 2 discusses gL-prime approximately 1 and the full H1-H7 model", "unknown",
    "A precision value and exact pylcp sign convention have not been established."
)
EXCITED_BACKEND_GL_ANISOTROPIC = _constant(
    "excited_backend_gl", None, "dimensionless", RODRIGUEZ,
    "Page 2, full H1-H7 excited Zeeman discussion", "unknown"
)
EXCITED_BACKEND_GLPRIME = _constant(
    "excited_backend_glprime", None, "dimensionless", RODRIGUEZ,
    "Page 2, parity-dependent Zeeman interaction", "unknown",
    "Rodriguez gives only an order estimate and uses an effective g=0.001."
)
EXCITED_BACKEND_GR = _constant(
    "excited_backend_gr", None, "dimensionless", RODRIGUEZ,
    "Page 2, full H1-H7 excited Zeeman discussion", "unknown"
)
EXCITED_BACKEND_GREPRIME = _constant(
    "excited_backend_greprime", None, "dimensionless", RODRIGUEZ,
    "Page 2, parity-dependent Zeeman interaction", "unknown"
)
EXCITED_BACKEND_GN = _constant(
    "excited_backend_gN", None, "dimensionless", RODRIGUEZ,
    "Page 2, nuclear H7 Zeeman term", "unknown"
)


OPTICAL_FREQUENCY_THZ = _constant(
    "optical_frequency", 834.3, "THz", RODRIGUEZ,
    "Page 2, approximately 2*pi*834.3 THz angular frequency", "approximate"
)
WAVELENGTH_NM = _constant(
    "wavelength", 359.3, "nm", RODRIGUEZ,
    "Cooling-transition description", "approximate"
)
LINEWIDTH_MHZ = _constant(
    "natural_linewidth_Gamma_over_2pi", 20.9, "MHz", NORRGARD,
    "Rodriguez page 2 citing Norrgard; Gamma=2*pi*20.9(2) MHz", "approximate"
)

GROUND_EFFECTIVE_G_FACTORS = {
    "lower_F1": _constant(
        "lower_F1_g", -0.2, "dimensionless", RODRIGUEZ, "Fig. 1", "approximate"
    ),
    "F0": _constant(
        "F0_g", None, "dimensionless", RODRIGUEZ, "Fig. 1 does not label it", "unknown",
        "F=0 has no first-order vector Zeeman shift, but no paper value is inserted here."
    ),
    "upper_F1": _constant(
        "upper_F1_g", 0.7, "dimensionless", RODRIGUEZ, "Fig. 1", "approximate"
    ),
    "F2": _constant(
        "F2_g", 0.5, "dimensionless", RODRIGUEZ, "Fig. 1", "approximate"
    ),
}

RODRIGUEZ_GROUND_SPACINGS_MHZ = {
    "lower_F1_to_F0": _constant(
        "lower_F1_to_F0_spacing", 109.0, "MHz", RODRIGUEZ, "Fig. 1", "approximate"
    ),
    "F0_to_upper_F1": _constant(
        "F0_to_upper_F1_spacing", 120.0, "MHz", RODRIGUEZ, "Fig. 1", "approximate"
    ),
    "upper_F1_to_F2": _constant(
        "upper_F1_to_F2_spacing", 9.0, "MHz", RODRIGUEZ, "Fig. 1", "approximate"
    ),
}

MODEL_ASSUMPTIONS = {
    "ground_N": _constant("ground_N", 1.0, "quantum number", RODRIGUEZ, "Page 2", "exact"),
    "electron_S": _constant("electron_S", 0.5, "quantum number", RODRIGUEZ, "X 2Sigma+ and A 2Pi state labels", "exact"),
    "fluorine_I": _constant("fluorine_I", 0.5, "quantum number", DOPPELBAUER, "Section IV", "exact"),
    "excited_J": _constant("excited_J", 0.5, "quantum number", RODRIGUEZ, "Page 2", "exact"),
    "excited_parity": _constant("excited_parity", 1.0, "parity sign", DOPPELBAUER, "P1/Q12(1) cooling branch", "exact"),
}


ALL_SPECTROSCOPY_CONSTANTS = {
    constant.name: constant
    for constant in (
        GROUND_ROTATIONAL_B_MHZ,
        GROUND_CENTRIFUGAL_D_MHZ,
        GROUND_SPIN_ROTATION_GAMMA_MHZ,
        GROUND_FERMI_CONTACT_BF_MHZ,
        GROUND_DIPOLAR_C_MHZ,
        GROUND_BACKEND_B_MHZ,
        GROUND_NUCLEAR_SPIN_ROTATION_CI_MHZ,
        GROUND_ELECTRIC_QUADRUPOLE_Q0_MHZ,
        GROUND_ELECTRIC_QUADRUPOLE_Q2_MHZ,
        ELECTRON_G_FACTOR,
        BOHR_MAGNETON_MHZ_PER_GAUSS,
        NUCLEAR_MAGNETON_MHZ_PER_GAUSS,
        GROUND_NUCLEAR_G_FACTOR,
        EXCITED_ROTATIONAL_B_MHZ,
        EXCITED_SPIN_ROTATION_GAMMA_MHZ,
        EXCITED_A_PLUS_GAMMA_MHZ,
        EXCITED_P_PLUS_2Q_MHZ,
        EXCITED_HYPERFINE_A_MHZ,
        EXCITED_BF_PLUS_2C_OVER_3_MHZ,
        EXCITED_HYPERFINE_D_MHZ,
        EXCITED_BACKEND_B_MHZ,
        EXCITED_BACKEND_C_MHZ,
        EXCITED_BACKEND_P_MHZ,
        EXCITED_BACKEND_Q_MHZ,
        EXCITED_HYPERFINE_SPLITTING_MHZ,
        EXCITED_G_FACTOR_RODRIGUEZ,
        EXCITED_BACKEND_GL,
        EXCITED_BACKEND_GL_ANISOTROPIC,
        EXCITED_BACKEND_GLPRIME,
        EXCITED_BACKEND_GR,
        EXCITED_BACKEND_GREPRIME,
        EXCITED_BACKEND_GN,
        OPTICAL_FREQUENCY_THZ,
        WAVELENGTH_NM,
        LINEWIDTH_MHZ,
        *GROUND_EFFECTIVE_G_FACTORS.values(),
        *RODRIGUEZ_GROUND_SPACINGS_MHZ.values(),
        *MODEL_ASSUMPTIONS.values(),
    )
}
