"""Named, fail-closed excited-hyperfine models for the retained MgF basis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from .excited_zeeman import excited_basis_order


ComplexArray = NDArray[np.complex128]


class ExcitedHyperfineModel(str, Enum):
    PYLCP_COLLAPSED_ASTATE = "pylcp_collapsed_astate"
    NO_EXCITED_HYPERFINE_SPLITTING = "no_excited_hyperfine_splitting"
    SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING = (
        "source_aligned_effective_fprime_splitting"
    )
    FULL_DOPPELBAUER_D_OPERATOR = "full_doppelbauer_d_operator"


class SourceAlignedSplittingCase(str, Enum):
    """Explicit samples of Doppelbauer's reported 0 <= splitting < 1 MHz interval."""

    LOWER_LIMIT_0_MHZ = "lower_limit_0_mhz"
    QUARTER_RANGE_0P25_MHZ = "quarter_range_0p25_mhz"
    MID_RANGE_0P5_MHZ = "mid_range_0p5_mhz"
    THREE_QUARTER_RANGE_0P75_MHZ = "three_quarter_range_0p75_mhz"
    UPPER_BOUND_STRESS_1_MHZ = "upper_bound_stress_1_mhz"

    @property
    def splitting_mhz(self) -> float:
        return {
            self.LOWER_LIMIT_0_MHZ: 0.0,
            self.QUARTER_RANGE_0P25_MHZ: 0.25,
            self.MID_RANGE_0P5_MHZ: 0.5,
            self.THREE_QUARTER_RANGE_0P75_MHZ: 0.75,
            self.UPPER_BOUND_STRESS_1_MHZ: 1.0,
        }[self]


class ExcitedHyperfineModelError(ValueError):
    pass


@dataclass(frozen=True)
class ExcitedFProjectors:
    f0: ComplexArray
    f1: ComplexArray
    basis_order: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ExcitedHyperfineOperator:
    model: ExcitedHyperfineModel
    matrix_mhz: ComplexArray
    basis_order: tuple[tuple[int, int], ...]
    splitting_mhz: float
    center_of_gravity_mhz: float
    source: str
    source_locator: str
    source_supported_family: bool
    engineering_stress_test: bool
    changes_eigenvectors: bool
    modifies_transition_strengths: bool
    omitted_physics: tuple[str, ...]
    warnings: tuple[str, ...]
    splitting_case: SourceAlignedSplittingCase | None
    model_application_count: int = 1
    application_location: str = "Hamiltonian boundary"


def build_excited_f_projectors(basis: np.ndarray) -> ExcitedFProjectors:
    order = excited_basis_order(basis)
    f0 = np.diag([1.0 if f == 0 else 0.0 for f, _ in order]).astype(complex)
    f1 = np.eye(4, dtype=complex) - f0
    return ExcitedFProjectors(f0=f0, f1=f1, basis_order=order)


def validate_excited_f_projectors(projectors: ExcitedFProjectors) -> dict[str, object]:
    p0, p1 = projectors.f0, projectors.f1
    return {
        "basis_order": [list(item) for item in projectors.basis_order],
        "shape_f0": list(p0.shape),
        "shape_f1": list(p1.shape),
        "hermitian": bool(np.allclose(p0, p0.conj().T) and np.allclose(p1, p1.conj().T)),
        "idempotent": bool(np.allclose(p0 @ p0, p0) and np.allclose(p1 @ p1, p1)),
        "orthogonal": bool(np.allclose(p0 @ p1, 0) and np.allclose(p1 @ p0, 0)),
        "complete": bool(np.allclose(p0 + p1, np.eye(4))),
        "dimensions": [int(round(np.trace(p0).real)), int(round(np.trace(p1).real))],
    }


def _field_free_summary(matrix: ComplexArray, projectors: ExcitedFProjectors) -> tuple[float, float]:
    e0 = float(np.trace(projectors.f0 @ matrix).real)
    e1 = float(np.trace(projectors.f1 @ matrix).real / 3.0)
    return e1 - e0, float(np.trace(matrix).real / 4.0)


def build_excited_hyperfine_operator(
    model: ExcitedHyperfineModel,
    *,
    basis: np.ndarray,
    pylcp_collapsed_h0_mhz: ComplexArray,
    splitting_case: SourceAlignedSplittingCase | None = None,
) -> ExcitedHyperfineOperator:
    """Build a named model; deliberately offers no arbitrary matrix or float knob."""

    projectors = build_excited_f_projectors(basis)
    raw = np.asarray(pylcp_collapsed_h0_mhz, dtype=np.complex128)
    if raw.shape != (4, 4) or not np.allclose(raw, raw.conj().T):
        raise ExcitedHyperfineModelError("collapsed excited H0 must be Hermitian with shape (4,4)")
    raw_split, cog = _field_free_summary(raw, projectors)
    common_omissions = (
        "The effective four-state model omits d-dependent coupling to J'=3/2 states.",
        "It does not reconstruct d-dependent eigenvector or transition-strength corrections.",
    )
    if model is ExcitedHyperfineModel.PYLCP_COLLAPSED_ASTATE:
        if splitting_case is not None:
            raise ExcitedHyperfineModelError("collapsed model does not accept a splitting case")
        matrix, splitting = raw.copy(), raw_split
        source_supported, stress = False, False
        source = "pylcp 1.0.2 XFmolecules.Astate collapsed project mapping"
        locator = "a=109, b=-52, c=0, p=15, q=0; independent d omitted"
        warnings = ("Comparison baseline; its positive-parity splitting is not source-supported.",)
    elif model is ExcitedHyperfineModel.NO_EXCITED_HYPERFINE_SPLITTING:
        if splitting_case is not None:
            raise ExcitedHyperfineModelError("zero-splitting stress model does not accept a case")
        matrix, splitting = np.eye(4, dtype=complex) * cog, 0.0
        source_supported, stress = False, True
        source = "engineering stress test"
        locator = "not a measured spectroscopy value"
        warnings = ("Engineering stress test only; not a physical candidate.",)
    elif model is ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING:
        if splitting_case is None:
            raise ExcitedHyperfineModelError(
                "source-aligned model requires an explicit SourceAlignedSplittingCase"
            )
        splitting = splitting_case.splitting_mhz
        e0, e1 = cog - 0.75 * splitting, cog + 0.25 * splitting
        matrix = e0 * projectors.f0 + e1 * projectors.f1
        source_supported, stress = True, splitting_case is SourceAlignedSplittingCase.UPPER_BOUND_STRESS_1_MHZ
        source = "Doppelbauer et al., J. Chem. Phys. 156, 134301 (2022)"
        locator = "Conclusion: J'=1/2, P'=+1 hyperfine splitting is less than 1 MHz"
        warnings = (
            "Effective diagonal interval sample, not a measured exact splitting or full d operator.",
            "The 0.5 MHz midpoint is an interval representative, not a fitted spectroscopy value.",
        )
    elif model is ExcitedHyperfineModel.FULL_DOPPELBAUER_D_OPERATOR:
        raise ExcitedHyperfineModelError(
            "FULL_DOPPELBAUER_D_OPERATOR is unavailable: Eq. (1) and Appendix A source the "
            "d term, but a validated projection including J'=3/2 elimination and F'=0 energy "
            "has not been established for this retained four-state basis"
        )
    else:
        raise ExcitedHyperfineModelError(f"unsupported excited-hyperfine model {model!r}")
    return ExcitedHyperfineOperator(
        model=model,
        matrix_mhz=np.asarray(matrix, dtype=np.complex128),
        basis_order=projectors.basis_order,
        splitting_mhz=float(splitting),
        center_of_gravity_mhz=float(cog),
        source=source,
        source_locator=locator,
        source_supported_family=source_supported,
        engineering_stress_test=stress,
        changes_eigenvectors=False,
        modifies_transition_strengths=False,
        omitted_physics=common_omissions,
        warnings=warnings,
        splitting_case=splitting_case,
    )


def validate_excited_hyperfine_operator(operator: ExcitedHyperfineOperator) -> dict[str, object]:
    matrix = np.asarray(operator.matrix_mhz)
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    return {
        "model": operator.model.value,
        "splitting_case": None if operator.splitting_case is None else operator.splitting_case.value,
        "matrix_mhz": matrix.real.tolist(),
        "shape": list(matrix.shape),
        "hermitian": bool(np.allclose(matrix, matrix.conj().T)),
        "eigenvalues_mhz": eigenvalues.tolist(),
        "eigenvectors_columns": eigenvectors.real.tolist(),
        "splitting_mhz": operator.splitting_mhz,
        "center_of_gravity_mhz": operator.center_of_gravity_mhz,
        "changes_eigenvectors": operator.changes_eigenvectors,
        "modifies_transition_strengths": operator.modifies_transition_strengths,
        "source_supported_family": operator.source_supported_family,
        "engineering_stress_test": operator.engineering_stress_test,
    }
