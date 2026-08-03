"""Complex-preserving diagnostic evaluator for the accepted 12+4 model.

Amplitude-level objects remain complex through eigendecomposition, basis
rotation, spherical-polarization contraction, and dipole contraction.  Only
Hermitian eigenvalues and modulus-squared physical rates are converted to real.
This module is audit-only and is not an accepted force backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray


ComplexArray = NDArray[np.complex128]
FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ComplexModelMatrices:
    ground_h0: ComplexArray
    ground_mu_q: ComplexArray
    excited_h0: ComplexArray
    excited_mu_q: ComplexArray
    dipole_q: ComplexArray
    gamma: float = 1.0


@dataclass(frozen=True)
class ComplexFidelityResult:
    equilibrium_populations: FloatArray
    evolution_matrix: FloatArray
    pumping_rates: FloatArray
    normalized_force: FloatArray
    per_laser_normalized_force: FloatArray
    net_scattering_rate_by_laser_gamma: FloatArray
    total_scattering_rate_gamma: float
    excited_fraction: float
    spontaneous_branching: FloatArray
    ground_energies_gamma: FloatArray
    excited_energies_gamma: FloatArray
    ground_transform: ComplexArray
    excited_transform: ComplexArray
    rotated_dipole_q: ComplexArray
    laser_coupling_amplitudes: ComplexArray
    projected_polarizations: ComplexArray
    residual_linf: float
    final_observable_max_imaginary: float
    amplitude_max_imaginary: float
    conjugate_transpose_used: bool = True
    combined_population_solve_count: int = 1


def matrices_from_hamiltonian(hamiltonian: Any) -> ComplexModelMatrices:
    """Copy accepted pylcp blocks without discarding complex entries."""

    ground = hamiltonian.blocks[0, 0]
    excited = hamiltonian.blocks[1, 1]
    if not isinstance(ground, tuple) or not isinstance(excited, tuple):
        raise ValueError("complex fidelity requires explicit H0/mu_q blocks")
    transition = hamiltonian.blocks[0, 1]
    return ComplexModelMatrices(
        ground_h0=np.asarray(ground[0].matrix, dtype=np.complex128).copy(),
        ground_mu_q=np.asarray(ground[1].matrix, dtype=np.complex128).copy(),
        excited_h0=np.asarray(excited[0].matrix, dtype=np.complex128).copy(),
        excited_mu_q=np.asarray(excited[1].matrix, dtype=np.complex128).copy(),
        dipole_q=np.asarray(transition.matrix, dtype=np.complex128).copy(),
        gamma=float(transition.parameters["gamma"]),
    )


def rephase_matrices(
    matrices: ComplexModelMatrices,
    ground_phases: NDArray[np.complexfloating],
    excited_phases: NDArray[np.complexfloating],
) -> ComplexModelMatrices:
    """Apply one consistent passive diagonal-unitary basis transformation."""

    pg = np.asarray(ground_phases, dtype=np.complex128)
    pe = np.asarray(excited_phases, dtype=np.complex128)
    if pg.shape != (12,) or pe.shape != (4,):
        raise ValueError("ground and excited phase vectors must have lengths 12 and 4")
    if not np.allclose(abs(pg), 1.0) or not np.allclose(abs(pe), 1.0):
        raise ValueError("basis phases must have unit magnitude")
    Ug = np.diag(pg)
    Ue = np.diag(pe)
    return ComplexModelMatrices(
        ground_h0=Ug.conj().T @ matrices.ground_h0 @ Ug,
        ground_mu_q=np.asarray([Ug.conj().T @ item @ Ug for item in matrices.ground_mu_q]),
        excited_h0=Ue.conj().T @ matrices.excited_h0 @ Ue,
        excited_mu_q=np.asarray([Ue.conj().T @ item @ Ue for item in matrices.excited_mu_q]),
        dipole_q=np.asarray([Ug.conj().T @ item @ Ue for item in matrices.dipole_q]),
        gamma=matrices.gamma,
    )


def _collection(beams: Any) -> Any:
    if hasattr(beams, "beam_vector"):
        return beams
    try:
        return beams["g->e"]
    except (KeyError, TypeError) as exc:
        raise ValueError("complex evaluator requires one g->e beam collection") from exc


def _diagonalize(h0: ComplexArray, mu_q: ComplexArray, field_magnitude: float) -> tuple[FloatArray, ComplexArray]:
    matrix = h0 - field_magnitude * mu_q[1]
    hermiticity_error = float(np.max(abs(matrix - matrix.conj().T)))
    if hermiticity_error > 2e-11:
        raise ValueError(f"complex field Hamiltonian is not Hermitian: {hermiticity_error}")
    # Match pylcp's eigenvector convention so this audit isolates only complex
    # conjugation/casting.  ``eigh`` may choose a different rotation inside an
    # exactly degenerate manifold; a population-only rate equation is not
    # invariant to that rotation because it intentionally omits coherences.
    energy_complex, transform = np.linalg.eig(matrix)
    if not np.allclose(np.imag(energy_complex), 0.0, atol=2e-11, rtol=0.0):
        raise ValueError("complex field Hamiltonian produced non-real eigenvalues")
    energy = np.real(energy_complex)
    order = np.argsort(energy)
    return np.asarray(energy[order], dtype=float), np.asarray(transform[:, order], dtype=np.complex128)


def _real_physical(array: NDArray[Any], *, name: str, tolerance: float) -> FloatArray:
    values = np.asarray(array)
    maximum_imaginary = float(np.max(abs(np.imag(values)))) if values.size else 0.0
    scale = max(float(np.max(abs(np.real(values)))) if values.size else 0.0, 1.0)
    if maximum_imaginary > tolerance * scale:
        raise RuntimeError(f"{name} retained a physical imaginary residual {maximum_imaginary}")
    return np.asarray(np.real(values), dtype=float)


def evaluate_complex_fidelity(
    *,
    matrices: ComplexModelMatrices,
    pylcp_beams: Any,
    beam_index: Sequence[tuple[str, int]],
    position_m: NDArray[np.floating],
    velocity_gamma_over_k: NDArray[np.floating],
    magnetic_field_gauss: NDArray[np.floating],
    svd_eps: float = 1e-10,
    reality_tolerance: float = 1e-12,
) -> ComplexFidelityResult:
    """Evaluate physical rates after, never before, complex amplitude sums."""

    position = np.asarray(position_m, dtype=float)
    velocity = np.asarray(velocity_gamma_over_k, dtype=float)
    field = np.asarray(magnetic_field_gauss, dtype=float)
    if any(vector.shape != (3,) for vector in (position, velocity, field)):
        raise ValueError("position, velocity, and field must be 3-vectors")
    collection = _collection(pylcp_beams)
    if len(collection.beam_vector) != len(beam_index):
        raise ValueError("beam_index must identify every laser")

    field_magnitude = float(np.linalg.norm(field))
    qaxis = field / field_magnitude if field_magnitude > 1e-10 else np.array([0.0, 0.0, 1.0])
    Eg, Ug = _diagonalize(matrices.ground_h0, matrices.ground_mu_q, field_magnitude)
    Ee, Ue = _diagonalize(matrices.excited_h0, matrices.excited_mu_q, field_magnitude)
    dipole = np.asarray([Ug.conj().T @ item @ Ue for item in matrices.dipole_q])

    decay_strength = np.sum(abs(dipole) ** 2, axis=0)
    decay_rates = matrices.gamma * np.sum(decay_strength, axis=0)
    branching = decay_strength / np.sum(decay_strength, axis=0, keepdims=True)
    ng, ne = decay_strength.shape
    evolution = np.zeros((ng + ne, ng + ne), dtype=float)
    evolution[ng + np.arange(ne), ng + np.arange(ne)] -= decay_rates
    evolution[:ng, ng:] += matrices.gamma * decay_strength

    kvecs = np.asarray(collection.kvec(position, 0.0), dtype=float)
    intensities = np.asarray(collection.intensity(position, 0.0), dtype=float)
    detunings = np.asarray(collection.delta(0.0), dtype=float)
    polarizations = np.asarray(collection.project_pol(qaxis, R=position, t=0.0), dtype=np.complex128)
    amplitudes = np.empty((len(kvecs), ng, ne), dtype=np.complex128)
    rates = np.empty((len(kvecs), ng, ne), dtype=float)
    transition_energy = Ee[None, :] - Eg[:, None]
    for index, (kvec, intensity, detuning, polarization) in enumerate(zip(kvecs, intensities, detunings, polarizations)):
        amplitudes[index] = (
            dipole[0] * polarization[2]
            + dipole[1] * polarization[1]
            + dipole[2] * polarization[0]
        )
        detuning_matrix = -transition_energy + detuning - float(np.dot(kvec, velocity))
        rate_expression = (
            matrices.gamma * float(intensity) / 2.0 * abs(amplitudes[index]) ** 2
            / (1.0 + 4.0 * detuning_matrix**2 / matrices.gamma**2)
        )
        rates[index] = _real_physical(rate_expression, name="pumping rates", tolerance=reality_tolerance)

    summed = np.sum(rates, axis=0)
    evolution[:ng, ng:] += summed
    evolution[ng:, :ng] += summed.T
    evolution[np.arange(ng), np.arange(ng)] -= np.sum(summed, axis=1)
    evolution[ng + np.arange(ne), ng + np.arange(ne)] -= np.sum(summed, axis=0)
    _, singular, vh = np.linalg.svd(evolution)
    null = np.flatnonzero(singular <= svd_eps)
    if len(null) != 1:
        raise RuntimeError(f"complex reference expected one equilibrium null state, found {len(null)}")
    populations_complex = vh[null[0]].astype(np.complex128)
    populations_complex /= np.sum(populations_complex)
    populations = _real_physical(populations_complex, name="populations", tolerance=reality_tolerance)
    if np.min(populations) < -2e-10:
        raise RuntimeError("complex reference equilibrium has negative population")
    imbalance = populations[:ng, None] - populations[None, ng:]
    scattering_complex = np.sum(rates.astype(complex) * imbalance[None], axis=(1, 2))
    scattering = _real_physical(scattering_complex, name="scattering rates", tolerance=reality_tolerance)
    per_laser_force_complex = kvecs.T.astype(complex) * scattering_complex[None]
    per_laser_force = _real_physical(per_laser_force_complex, name="per-laser force", tolerance=reality_tolerance)
    force_complex = np.sum(per_laser_force_complex, axis=1)
    force = _real_physical(force_complex, name="force", tolerance=reality_tolerance)
    total_scattering_complex = np.dot(decay_rates.astype(complex), populations[ng:].astype(complex))
    total_scattering = float(_real_physical(np.asarray([total_scattering_complex]), name="total scattering", tolerance=reality_tolerance)[0])
    final_imag = max(
        float(np.max(abs(np.imag(populations_complex)))),
        float(np.max(abs(np.imag(scattering_complex)))),
        float(np.max(abs(np.imag(per_laser_force_complex)))),
        float(np.max(abs(np.imag(force_complex)))),
        abs(float(np.imag(total_scattering_complex))),
    )
    return ComplexFidelityResult(
        equilibrium_populations=populations,
        evolution_matrix=evolution,
        pumping_rates=rates,
        normalized_force=force,
        per_laser_normalized_force=per_laser_force,
        net_scattering_rate_by_laser_gamma=scattering,
        total_scattering_rate_gamma=total_scattering,
        excited_fraction=float(np.sum(populations[ng:])),
        spontaneous_branching=np.asarray(branching, dtype=float),
        ground_energies_gamma=Eg,
        excited_energies_gamma=Ee,
        ground_transform=Ug,
        excited_transform=Ue,
        rotated_dipole_q=dipole,
        laser_coupling_amplitudes=amplitudes,
        projected_polarizations=polarizations,
        residual_linf=float(np.linalg.norm(evolution @ populations, ord=np.inf)),
        final_observable_max_imaginary=final_imag,
        amplitude_max_imaginary=float(max(np.max(abs(np.imag(dipole))), np.max(abs(np.imag(polarizations))), np.max(abs(np.imag(amplitudes))))),
    )
