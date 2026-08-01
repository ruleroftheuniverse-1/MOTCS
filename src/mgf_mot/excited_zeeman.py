"""Named excited-state Zeeman models for provisional MgF static studies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray
from pylcp.common import spherical2cart

from .spectroscopy import (
    BOHR_MAGNETON_MHZ_PER_GAUSS,
    EXCITED_G_FACTOR_RODRIGUEZ,
)


ComplexArray = NDArray[np.complex128]


class ExcitedZeemanModel(str, Enum):
    """Explicit, non-interchangeable excited magnetic-tensor choices."""

    PYLCP_COLLAPSED_DEFAULT = "pylcp_collapsed_default"
    ZERO_EXCITED_ZEEMAN = "zero_excited_zeeman"
    RODRIGUEZ_EFFECTIVE_G_0P001 = "rodriguez_effective_g_0p001"
    NEGATIVE_G_0P001_SIGN_DIAGNOSTIC = "negative_g_0p001_sign_diagnostic"


@dataclass(frozen=True)
class ExcitedZeemanOperator:
    model: ExcitedZeemanModel
    tensor_mhz_per_gauss: ComplexArray
    effective_g: float | None
    source: str
    source_note: str
    basis_order: tuple[tuple[int, int], ...]
    model_application_count: int
    application_location: str
    override_applied: bool
    ground_tensor_modified: bool
    exact_spectroscopy_reconstruction: bool
    warnings: tuple[str, ...]


EXPECTED_BASIS_ORDER = ((0, 0), (1, -1), (1, 0), (1, 1))


def excited_basis_order(basis: np.ndarray) -> tuple[tuple[int, int], ...]:
    """Return and strictly validate the retained ``(F,mF)`` ordering."""

    if basis.shape != (4,) or "F" not in basis.dtype.names or "mF" not in basis.dtype.names:
        raise ValueError("excited basis must be the four-state pylcp F,mF structured array")
    order = tuple((int(round(float(state["F"]))), int(round(float(state["mF"])))) for state in basis)
    if order != EXPECTED_BASIS_ORDER:
        raise ValueError(
            f"effective excited Zeeman model requires basis {EXPECTED_BASIS_ORDER}, got {order}"
        )
    return order


def _angular_momentum_cartesian(basis: np.ndarray) -> ComplexArray:
    """Dimensionless F operators in the explicit direct-sum F=0 plus F=1 basis."""

    order = excited_basis_order(basis)
    dimension = len(order)
    fz = np.zeros((dimension, dimension), dtype=np.complex128)
    raising = np.zeros_like(fz)
    lookup = {state: index for index, state in enumerate(order)}
    for index, (f_value, m_value) in enumerate(order):
        fz[index, index] = m_value
        target = (f_value, m_value + 1)
        if target in lookup:
            raising[lookup[target], index] = np.sqrt(
                f_value * (f_value + 1) - m_value * (m_value + 1)
            )
    lowering = raising.conj().T
    fx = 0.5 * (raising + lowering)
    fy = (raising - lowering) / (2.0j)
    return np.stack((fx, fy, fz))


def _cartesian_to_spherical(cartesian: ComplexArray) -> ComplexArray:
    """Convert Cartesian operators to pylcp q order ``(-1,0,+1)``."""

    fx, fy, fz = cartesian
    return np.stack(
        ((fx - 1j * fy) / np.sqrt(2.0), fz, -(fx + 1j * fy) / np.sqrt(2.0))
    )


def _effective_isotropic_excited_muq(
    basis: np.ndarray,
    *,
    g_factor: float,
    mu_b_mhz_per_gauss: float | None = None,
) -> ComplexArray:
    """Build ``mu_q=-g*mu_B*F_q`` for pylcp's ``H=H0-mu.B`` convention."""

    if not np.isfinite(g_factor):
        raise ValueError("effective excited g factor must be finite")
    mu_b = (
        BOHR_MAGNETON_MHZ_PER_GAUSS.require()
        if mu_b_mhz_per_gauss is None
        else float(mu_b_mhz_per_gauss)
    )
    if not np.isfinite(mu_b) or mu_b <= 0:
        raise ValueError("Bohr magneton must be finite and positive")
    return -float(g_factor) * mu_b * _cartesian_to_spherical(
        _angular_momentum_cartesian(basis)
    )


def build_excited_zeeman_operator(
    model: ExcitedZeemanModel,
    *,
    basis: np.ndarray,
    pylcp_collapsed_tensor_mhz_per_gauss: ComplexArray,
) -> ExcitedZeemanOperator:
    """Select one named model; no arbitrary runtime g-factor is accepted."""

    order = excited_basis_order(basis)
    raw = np.asarray(pylcp_collapsed_tensor_mhz_per_gauss, dtype=np.complex128)
    if raw.shape != (3, 4, 4):
        raise ValueError("collapsed excited magnetic tensor must have shape (3,4,4)")
    source = EXCITED_G_FACTOR_RODRIGUEZ.source
    source_note = EXCITED_G_FACTOR_RODRIGUEZ.locator
    warnings: tuple[str, ...]
    if model is ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT:
        tensor = raw.copy()
        effective_g = None
        source = "pylcp 1.0.2 XFmolecules.Astate collapsed MgF approximation"
        source_note = "gS term retained; gL, gl, glprime, gr, greprime, gN explicitly zero"
        override = False
        warnings = ("Comparison model only; its effective F=1 g is about +0.334.",)
    elif model is ExcitedZeemanModel.ZERO_EXCITED_ZEEMAN:
        tensor = np.zeros_like(raw)
        effective_g = 0.0
        override = True
        warnings = ("Near-zero comparison model; not an exact spectroscopy reconstruction.",)
    elif model is ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001:
        effective_g = EXCITED_G_FACTOR_RODRIGUEZ.require()
        tensor = _effective_isotropic_excited_muq(basis, g_factor=effective_g)
        override = True
        warnings = (
            "Paper-aligned effective model only; independent d and exact excited spectroscopy remain unresolved.",
        )
    elif model is ExcitedZeemanModel.NEGATIVE_G_0P001_SIGN_DIAGNOSTIC:
        effective_g = -EXCITED_G_FACTOR_RODRIGUEZ.require()
        tensor = _effective_isotropic_excited_muq(basis, g_factor=effective_g)
        override = True
        source_note = "Sign diagnostic only; Rodriguez uses representative +0.001"
        warnings = ("Convention diagnostic only; not a source-supported physical candidate.",)
    else:
        raise ValueError(f"unsupported excited Zeeman model {model!r}")
    return ExcitedZeemanOperator(
        model=model,
        tensor_mhz_per_gauss=tensor,
        effective_g=effective_g,
        source=source,
        source_note=source_note,
        basis_order=order,
        model_application_count=1,
        application_location="Hamiltonian boundary",
        override_applied=override,
        ground_tensor_modified=False,
        exact_spectroscopy_reconstruction=False,
        warnings=warnings,
    )


def validate_excited_zeeman_operator(operator: ExcitedZeemanOperator) -> dict[str, object]:
    """Validate Cartesian Hermiticity and weak-field slopes for named models."""

    tensor = np.asarray(operator.tensor_mhz_per_gauss)
    cartesian = spherical2cart(tensor)
    hermitian = [bool(np.allclose(axis, axis.conj().T, atol=1e-12)) for axis in cartesian]
    mu_b = BOHR_MAGNETON_MHZ_PER_GAUSS.require()
    axes: dict[str, object] = {}
    for axis_name, mu_axis in zip(("x", "y", "z"), cartesian):
        slopes = np.linalg.eigvalsh(-np.asarray(mu_axis, dtype=np.complex128))
        axes[axis_name] = {
            "dE_dB_mhz_per_gauss_sorted": slopes.tolist(),
            "effective_gm_sorted": (slopes / mu_b).tolist(),
        }
    expected = None
    slopes_match: bool | None = None
    if operator.effective_g is not None:
        expected = np.sort(
            np.array(
                [0.0, -operator.effective_g * mu_b, 0.0, operator.effective_g * mu_b]
            )
        )
        slopes_match = all(
            np.allclose(
                np.asarray(record["dE_dB_mhz_per_gauss_sorted"]), expected, atol=1e-12
            )
            for record in axes.values()
        )
    return {
        "model": operator.model.value,
        "tensor_shape": list(tensor.shape),
        "basis_order": [list(item) for item in operator.basis_order],
        "spherical_q_order": [-1, 0, 1],
        "cartesian_components_hermitian": hermitian,
        "spherical_hermiticity_relation": bool(
            np.allclose(tensor[0].conj().T, -tensor[2], atol=1e-12)
            and np.allclose(tensor[1].conj().T, tensor[1], atol=1e-12)
        ),
        "axes": axes,
        "expected_slopes_sorted": None if expected is None else expected.tolist(),
        "weak_field_slopes_match_selected_g": slopes_match,
        "f0_first_order_slope_zero": bool(
            all(abs(np.asarray(cartesian)[axis, 0, 0]) <= 1e-12 for axis in range(3))
        ),
        "f0_f1_off_block_zero": bool(
            all(
                np.allclose(np.asarray(cartesian)[axis, 0, 1:], 0.0, atol=1e-12)
                and np.allclose(np.asarray(cartesian)[axis, 1:, 0], 0.0, atol=1e-12)
                for axis in range(3)
            )
        ),
        "model_application_count": operator.model_application_count,
        "application_location": operator.application_location,
        "ground_tensor_modified": operator.ground_tensor_modified,
    }
