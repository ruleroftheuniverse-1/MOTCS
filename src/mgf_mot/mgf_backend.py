"""First-stage MgF validation model built on official pylcp utilities.

This module intentionally stops before constructing a complete
``pylcp.hamiltonian``. The sourced ground Hamiltonian and angular coupling
tensor are available for validation, while the excited Hamiltonian remains
blocked by unresolved parameter mappings and pylcp's missing independent
Doppelbauer ``d`` term.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

import numpy as np
from numpy.typing import NDArray
import pylcp

from .spectroscopy import ALL_SPECTROSCOPY_CONSTANTS, SourcedConstant

FloatArray = NDArray[np.float64]


class MgFBackendCapabilityError(RuntimeError):
    """Raised when official pylcp cannot yet represent the sourced model."""


class ApproximationMode(str, Enum):
    """Explicit non-default modes for provisional, non-faithful construction."""

    NONE = "none"
    COLLAPSED_PYLCP_ASTATE = "collapsed_pylcp_astate"


@dataclass(frozen=True)
class GroundEigenstateLabel:
    index: int
    energy_mhz: float
    relative_energy_mhz: float
    dominant_J: float
    F: float
    mF: float
    dominant_basis_index: int
    dominant_weight: float


@dataclass(frozen=True)
class GroundLevel:
    label: str
    F: int
    degeneracy: int
    relative_energy_mhz: float


@dataclass(frozen=True)
class MgFValidationModel:
    """Constructible, explicitly incomplete 12+4 MgF validation model."""

    ground_h0_mhz: FloatArray
    ground_eigenvectors: FloatArray
    ground_bare_basis: np.ndarray
    ground_eigenstates: tuple[GroundEigenstateLabel, ...]
    ground_levels: tuple[GroundLevel, ...]
    excited_basis: np.ndarray
    excited_energies_mhz: tuple[None, ...]
    transition_dipole_q: FloatArray
    missing_constants: tuple[SourcedConstant, ...]
    approximate_constants: tuple[SourcedConstant, ...]
    backend_limitations: tuple[str, ...]

    @property
    def ground_state_count(self) -> int:
        return self.ground_h0_mhz.shape[0]

    @property
    def excited_state_count(self) -> int:
        return len(self.excited_basis)

    @property
    def is_complete_hamiltonian(self) -> bool:
        return False


@dataclass(frozen=True)
class MgFApproximationReport:
    """Audit trail for an explicitly requested provisional Hamiltonian."""

    mode: ApproximationMode
    missing_or_collapsed_terms: tuple[str, ...]
    undocumented_defaults_used: tuple[str, ...]
    force_ready_by_default: bool = False


@dataclass(frozen=True)
class ApproximateMgFHamiltonian:
    """A pylcp-compatible object plus a warning label for provisional use."""

    hamiltonian: pylcp.hamiltonian
    validation_model: MgFValidationModel
    report: MgFApproximationReport


def _required(
    constants: Mapping[str, SourcedConstant], name: str
) -> float:
    try:
        constant = constants[name]
    except KeyError as exc:
        raise KeyError(f"source-tagged constant {name!r} was not supplied") from exc
    return constant.require()


def _ground_eigenstate_labels(
    h0: FloatArray, transform: FloatArray, bare_basis: np.ndarray
) -> tuple[GroundEigenstateLabel, ...]:
    energies = np.asarray(np.diag(h0), dtype=float)
    energy_zero = float(np.min(energies))
    labels: list[GroundEigenstateLabel] = []

    # pylcp sorts the eigenvectors/eigenvalues but returns the original bare
    # basis array. Label each eigenstate through the dominant transform column;
    # zipping the sorted energies directly to bare_basis would be incorrect.
    for index, energy in enumerate(energies):
        weights = np.abs(transform[:, index]) ** 2
        dominant_index = int(np.argmax(weights))
        state = bare_basis[dominant_index]
        labels.append(
            GroundEigenstateLabel(
                index=index,
                energy_mhz=float(energy),
                relative_energy_mhz=float(energy - energy_zero),
                dominant_J=float(state["J"]),
                F=float(state["F"]),
                mF=float(state["mF"]),
                dominant_basis_index=dominant_index,
                dominant_weight=float(weights[dominant_index]),
            )
        )
    return tuple(labels)


def _ground_levels(
    labels: tuple[GroundEigenstateLabel, ...], tolerance_mhz: float = 1e-7
) -> tuple[GroundLevel, ...]:
    groups: list[list[GroundEigenstateLabel]] = []
    for state in labels:
        if not groups or not np.isclose(
            state.relative_energy_mhz,
            groups[-1][0].relative_energy_mhz,
            atol=tolerance_mhz,
            rtol=0.0,
        ):
            groups.append([state])
        else:
            groups[-1].append(state)

    result: list[GroundLevel] = []
    f1_seen = 0
    for group in groups:
        f_values = {round(state.F) for state in group}
        if len(f_values) != 1:
            raise RuntimeError(f"energy group contains inconsistent F labels: {f_values}")
        F = int(f_values.pop())
        if F == 1:
            label = "lower_F1" if f1_seen == 0 else "upper_F1"
            f1_seen += 1
        else:
            label = f"F{F}"
        result.append(
            GroundLevel(
                label=label,
                F=F,
                degeneracy=len(group),
                relative_energy_mhz=group[0].relative_energy_mhz,
            )
        )
    return tuple(result)


def _enumerate_excited_basis(constants: Mapping[str, SourcedConstant]) -> np.ndarray:
    """Use pylcp to enumerate the 4-state basis without accepting placeholder H0.

    ``Astate`` has no basis-only mode, so explicit zeros are passed solely to
    enumerate states. Its returned Hamiltonian and magnetic operators are
    discarded and never exposed as MgF data.
    """
    _, _, basis = pylcp.hamiltonians.XFmolecules.Astate(
        J=_required(constants, "excited_J"),
        I=_required(constants, "fluorine_I"),
        P=int(_required(constants, "excited_parity")),
        B=0.0,
        D=0.0,
        H=0.0,
        a=0.0,
        b=0.0,
        c=0.0,
        eQq0=0.0,
        p=0.0,
        q=0.0,
        gS=0.0,
        gL=0.0,
        gl=0.0,
        glprime=0.0,
        gr=0.0,
        greprime=0.0,
        gN=0.0,
        muB=_required(constants, "bohr_magneton_muB"),
        muN=_required(constants, "nuclear_magneton_muN"),
        return_basis=True,
    )
    return basis


def _ground_state_with_explicit_magnetic_inputs(
    constants: Mapping[str, SourcedConstant], *, gI: float
) -> tuple[FloatArray, FloatArray, FloatArray, np.ndarray]:
    return pylcp.hamiltonians.XFmolecules.Xstate(
        N=int(_required(constants, "ground_N")),
        I=_required(constants, "fluorine_I"),
        B=_required(constants, "ground_rotational_B"),
        gamma=_required(constants, "ground_spin_rotation_gamma"),
        b=_required(constants, "ground_backend_b"),
        c=_required(constants, "ground_dipolar_c"),
        CI=_required(constants, "ground_nuclear_spin_rotation_CI"),
        q0=_required(constants, "ground_electric_quadrupole_q0"),
        q2=_required(constants, "ground_electric_quadrupole_q2"),
        gS=_required(constants, "electron_g_factor"),
        gI=gI,
        muB=_required(constants, "bohr_magneton_muB"),
        muN=_required(constants, "nuclear_magneton_muN"),
        return_basis=True,
    )


def _dipole_tensor(
    ground_basis: np.ndarray,
    excited_basis: np.ndarray,
    ground_transform: FloatArray,
    nuclear_spin: float,
    electron_spin: float,
) -> FloatArray:
    # pylcp 1.0.2 compares UX == [], which raises for a NumPy matrix. Generate
    # the official bare tensor and apply the intended UX.T rotation explicitly.
    bare = pylcp.hamiltonians.XFmolecules.dipoleXandAstates(
        ground_basis,
        excited_basis,
        I=nuclear_spin,
        S=electron_spin,
    )
    rotated = np.empty_like(bare, dtype=float)
    for q_index in range(3):
        rotated[q_index] = ground_transform.T @ bare[q_index]
    return rotated


def _factory_blockers(
    model: MgFValidationModel,
) -> tuple[str, ...]:
    details = [constant.name for constant in model.missing_constants]
    details.extend(model.backend_limitations)
    return tuple(details)


def build_mgf_validation_model_from_sources(
    constants: Mapping[str, SourcedConstant] | None = None,
) -> MgFValidationModel:
    """Build the source-supported validation subset of the MgF model.

    No unknown quantity is substituted into a physical Hamiltonian. The
    excited basis is enumerated structurally, and its energies remain ``None``.
    """
    constants = ALL_SPECTROSCOPY_CONSTANTS if constants is None else constants

    # gI is irrelevant to H0. It is explicitly set to zero only for this pylcp
    # call, and the returned magnetic operator is discarded because the
    # fluorine nuclear g-factor mapping has not yet been sourced.
    ground_h0, _, transform, ground_basis = _ground_state_with_explicit_magnetic_inputs(
        constants, gI=0.0
    )

    excited_basis = _enumerate_excited_basis(constants)
    eigenstates = _ground_eigenstate_labels(ground_h0, transform, ground_basis)
    levels = _ground_levels(eigenstates)
    dipole = _dipole_tensor(
        ground_basis,
        excited_basis,
        transform,
        nuclear_spin=_required(constants, "fluorine_I"),
        electron_spin=_required(constants, "electron_S"),
    )

    blocking_names = (
        "ground_fluorine_nuclear_g_factor",
        "excited_backend_b",
        "excited_backend_c",
        "excited_backend_p",
        "excited_backend_q",
        "excited_F0_F1_splitting",
        "excited_backend_gL",
        "excited_backend_gl",
        "excited_backend_glprime",
        "excited_backend_gr",
        "excited_backend_greprime",
        "excited_backend_gN",
    )
    missing = tuple(constants[name] for name in blocking_names if constants[name].value is None)
    approximate = tuple(
        constant
        for constant in constants.values()
        if constant.status in ("approximate", "model_assumption")
    )
    limitations = (
        "pylcp 1.0.2 XFmolecules.Astate has no independently adjustable "
        "Doppelbauer excited-state hyperfine d term (sourced d=135 MHz).",
        "Doppelbauer reports b_F+2c/3 and p+2q combinations; separate pylcp "
        "b, c, p, and q inputs are not source-determined.",
        "The excited-state field-free Hamiltonian and energies are therefore "
        "not constructed in this validation layer.",
        "Ground magnetic operators are not certified until the fluorine "
        "nuclear g-factor and convention are source-checked.",
    )

    return MgFValidationModel(
        ground_h0_mhz=np.asarray(ground_h0, dtype=float),
        ground_eigenvectors=np.asarray(transform, dtype=float),
        ground_bare_basis=ground_basis,
        ground_eigenstates=eigenstates,
        ground_levels=levels,
        excited_basis=excited_basis,
        excited_energies_mhz=tuple(None for _ in range(len(excited_basis))),
        transition_dipole_q=dipole,
        missing_constants=missing,
        approximate_constants=approximate,
        backend_limitations=limitations,
    )


def build_mgf_approximate_hamiltonian_from_sources(
    constants: Mapping[str, SourcedConstant] | None = None,
    *,
    approximation_mode: ApproximationMode = ApproximationMode.NONE,
) -> ApproximateMgFHamiltonian:
    """Build an explicitly provisional pylcp-compatible Hamiltonian.

    This is not a faithful MgF Hamiltonian. It exists so that any future
    approximation is named, auditable, and opt-in instead of silently replacing
    unresolved spectroscopy or backend terms.
    """
    if approximation_mode is ApproximationMode.NONE:
        raise MgFBackendCapabilityError(
            "approximate MgF Hamiltonian construction requires an explicit "
            "ApproximationMode; exact mode remains blocked"
        )
    if approximation_mode is not ApproximationMode.COLLAPSED_PYLCP_ASTATE:
        raise MgFBackendCapabilityError(f"unsupported approximation mode: {approximation_mode}")

    constants = ALL_SPECTROSCOPY_CONSTANTS if constants is None else constants
    model = build_mgf_validation_model_from_sources(constants)

    # The ground nuclear g-factor is unknown. Use an explicit zero only in this
    # opt-in approximation and report the omission.
    ground_h0, ground_muq, _, _ = _ground_state_with_explicit_magnetic_inputs(
        constants, gI=0.0
    )

    # Astate has no d operator. The Doppelbauer combination is collapsed into
    # the single fermicontact coefficient that Astate actually uses, and every
    # unmapped Zeeman term is explicitly zeroed rather than inherited from a
    # pylcp default.
    excited_h0, excited_muq, _ = pylcp.hamiltonians.XFmolecules.Astate(
        J=_required(constants, "excited_J"),
        I=_required(constants, "fluorine_I"),
        P=int(_required(constants, "excited_parity")),
        B=_required(constants, "excited_rotational_B"),
        D=0.0,
        H=0.0,
        a=_required(constants, "excited_hyperfine_a"),
        b=_required(constants, "excited_b_F_plus_2c_over_3"),
        c=0.0,
        eQq0=0.0,
        p=_required(constants, "excited_p_plus_2q"),
        q=0.0,
        gS=_required(constants, "electron_g_factor"),
        gL=0.0,
        gl=0.0,
        glprime=0.0,
        gr=0.0,
        greprime=0.0,
        gN=0.0,
        muB=_required(constants, "bohr_magneton_muB"),
        muN=_required(constants, "nuclear_magneton_muN"),
        return_basis=True,
    )

    ham = pylcp.hamiltonian(
        np.asarray(ground_h0, dtype=float),
        np.asarray(excited_h0, dtype=float),
        np.asarray(ground_muq, dtype=float),
        np.asarray(excited_muq, dtype=float),
        model.transition_dipole_q,
        mass=1.0,
        muB=1.0,
        gamma=1.0,
        k=1.0,
    )
    report = MgFApproximationReport(
        mode=approximation_mode,
        missing_or_collapsed_terms=(
            "ground_fluorine_nuclear_g_factor is unknown and set to 0 in this opt-in mode",
            "Doppelbauer independent excited hyperfine d=135 MHz is omitted; pylcp Astate has no d input",
            "Doppelbauer excited b_F+2c/3 is collapsed into pylcp Astate b+c/3 by setting b=-52 MHz and c=0",
            "Doppelbauer p+2q is passed as p=15 MHz and q=0; for single J and single parity this is a common/unused field-free term in pylcp Astate",
            "excited D and H centrifugal constants are set to 0 because they are common/unused in the retained single-J block",
            "all unmapped excited Zeeman parameters gL, gl, glprime, gr, greprime, and gN are set to 0",
            "Rodriguez effective excited g=+0.001 is not converted into a pylcp Zeeman operator",
        ),
        undocumented_defaults_used=(),
        force_ready_by_default=False,
    )
    return ApproximateMgFHamiltonian(ham, model, report)


def build_mgf_hamiltonian_from_sources(
    constants: Mapping[str, SourcedConstant] | None = None,
    *,
    approximation_mode: ApproximationMode = ApproximationMode.NONE,
) -> pylcp.hamiltonian | ApproximateMgFHamiltonian:
    """Strict complete-Hamiltonian factory.

    This currently fails by design rather than replacing the unresolved
    excited-state constants or independent ``d`` term with zeros.
    """
    if approximation_mode is not ApproximationMode.NONE:
        return build_mgf_approximate_hamiltonian_from_sources(
            constants, approximation_mode=approximation_mode
        )
    model = build_mgf_validation_model_from_sources(constants)
    details = _factory_blockers(model)
    raise MgFBackendCapabilityError(
        "complete MgF Hamiltonian construction is blocked:\n- "
        + "\n- ".join(details)
    )
