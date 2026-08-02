"""Independent evaluator for Rodriguez et al. rate equations (1)-(5).

The evaluator deliberately does not instantiate or call :class:`pylcp.rateeq`.
It accepts the same already-selected Hamiltonian, optical beams, and field as
data, diagonalizes the two manifolds, constructs pumping and spontaneous-decay
rates, solves one combined 16-state equilibrium system, and evaluates the
stimulated longitudinal force.  It is an audit reference, not a second MgF
backend and not an exact-replication claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


@dataclass(frozen=True)
class PaperRateEquationResult:
    """One shared equilibrium-population solution and its diagnostics."""

    equilibrium_populations: FloatArray
    evolution_matrix: FloatArray
    pumping_rates: FloatArray
    spontaneous_branching: FloatArray
    spontaneous_decay_rates: FloatArray
    normalized_force: FloatArray
    per_laser_normalized_force: FloatArray
    net_scattering_rate_by_laser_gamma: FloatArray
    total_scattering_rate_gamma: float
    excited_fraction: float
    residual_linf: float
    residual_l2: float
    singular_values: FloatArray
    nullspace_dimension: int
    ground_energies_gamma: FloatArray
    excited_energies_gamma: FloatArray
    ground_zero_field_energies_gamma: FloatArray
    excited_zero_field_energies_gamma: FloatArray
    ground_transform: ComplexArray
    excited_transform: ComplexArray
    rotated_dipole_q: ComplexArray
    magnetic_field_gauss: FloatArray
    quantization_axis: FloatArray
    combined_population_solve_count: int = 1
    paper_equations: tuple[str, ...] = (
        "Rodriguez et al. Eqs. (1)-(2): combined ground/excited population balance",
        "Rodriguez et al. Eqs. (3)-(4): R=(Gamma*s/2)|d.epsilon|^2/(1+4 delta^2/Gamma^2)",
        "Rodriguez et al. Eq. (5): beam momentum times stimulated population imbalance",
    )


def _block_matrices(hamiltonian: Any, index: int) -> tuple[ComplexArray, ComplexArray]:
    block = hamiltonian.blocks[index, index]
    if not isinstance(block, tuple) or len(block) != 2:
        raise ValueError("reference evaluator requires explicit H0 and mu_q blocks")
    return (
        np.asarray(block[0].matrix, dtype=np.complex128),
        np.asarray(block[1].matrix, dtype=np.complex128),
    )


def _diagonalize_manifold(
    h0: ComplexArray, mu_q: ComplexArray, field_magnitude_gauss: float
) -> tuple[FloatArray, ComplexArray]:
    matrix = h0 - float(field_magnitude_gauss) * mu_q[1]
    if not np.allclose(matrix, matrix.conj().T, atol=2e-11):
        raise ValueError("field-dependent manifold Hamiltonian is not Hermitian")
    # Use the same deterministic branch ordering as pylcp's static-field
    # diagonalizer so state-indexed populations can be compared directly.
    # This is only an eigensystem convention; all rate/force algebra below is
    # independently constructed from the paper equations.
    energies, transform = np.linalg.eig(matrix)
    if not np.allclose(np.imag(energies), 0.0, atol=2e-11):
        raise ValueError("field-dependent manifold energies are not real")
    order = np.argsort(np.real(energies))
    return np.asarray(np.real(energies[order]), dtype=float), np.asarray(transform[:, order], dtype=np.complex128)


def _solve_nullspace(matrix: FloatArray, svd_eps: float) -> tuple[FloatArray, FloatArray, int]:
    _, singular_values, vh = np.linalg.svd(matrix)
    null_indices = np.flatnonzero(singular_values <= svd_eps)
    if len(null_indices) != 1:
        raise RuntimeError(
            f"reference equilibrium requires one null state, found {len(null_indices)}"
        )
    population = np.real_if_close(vh[null_indices[0]]).astype(float)
    normalization = float(np.sum(population))
    if abs(normalization) < 1e-14:
        raise RuntimeError("reference equilibrium null vector has zero population sum")
    population /= normalization
    if np.min(population) < -2e-10:
        raise RuntimeError("reference equilibrium contains materially negative populations")
    population[np.abs(population) < 1e-15] = 0.0
    return population, np.asarray(singular_values, dtype=float), len(null_indices)


def evaluate_paper_rate_equations(
    *,
    hamiltonian: Any,
    pylcp_beams: Any,
    beam_index: Sequence[tuple[str, int]],
    position_m: NDArray[np.floating],
    velocity_gamma_over_k: NDArray[np.floating],
    magnetic_field_gauss: NDArray[np.floating],
    svd_eps: float = 1e-10,
) -> PaperRateEquationResult:
    """Evaluate the paper equations without using the pylcp rateeq class.

    ``velocity_gamma_over_k`` is dimensionless because the accepted Hamiltonian
    uses ``Gamma=k=1``.  Every beam and component participates in this one
    population solve; no separately solved contribution is summed afterward.
    """

    position = np.asarray(position_m, dtype=float)
    velocity = np.asarray(velocity_gamma_over_k, dtype=float)
    field = np.asarray(magnetic_field_gauss, dtype=float)
    if position.shape != (3,) or velocity.shape != (3,) or field.shape != (3,):
        raise ValueError("position, velocity, and magnetic field must be 3-vectors")
    if not np.isfinite(position).all() or not np.isfinite(velocity).all() or not np.isfinite(field).all():
        raise ValueError("reference-evaluator inputs must be finite")
    if not np.isfinite(svd_eps) or svd_eps <= 0:
        raise ValueError("svd_eps must be finite and positive")

    key = "g->e"
    if hasattr(pylcp_beams, "beam_vector"):
        collection = pylcp_beams
    else:
        try:
            collection = pylcp_beams[key]
        except (KeyError, TypeError) as exc:
            raise ValueError("reference evaluator requires one g->e beam collection") from exc
    if len(beam_index) != len(collection.beam_vector):
        raise ValueError("beam_index must identify every active laser exactly once")

    ground_h0, ground_muq = _block_matrices(hamiltonian, 0)
    excited_h0, excited_muq = _block_matrices(hamiltonian, 1)
    dipole = np.asarray(hamiltonian.blocks[0, 1].matrix, dtype=np.complex128)
    gamma = float(hamiltonian.blocks[0, 1].parameters["gamma"])
    field_magnitude = float(np.linalg.norm(field))
    quantization_axis = field / field_magnitude if field_magnitude > 1e-10 else np.array([0.0, 0.0, 1.0])

    ground_energy, ground_u = _diagonalize_manifold(ground_h0, ground_muq, field_magnitude)
    excited_energy, excited_u = _diagonalize_manifold(excited_h0, excited_muq, field_magnitude)
    rotated_dipole = np.empty_like(dipole)
    for q_index in range(3):
        # pylcp 1.0.2's molecular matrices/eigenvectors are real to numerical
        # precision and its documented basis convention applies U.T d U.  Use
        # that convention exactly so tiny roundoff imaginary parts do not turn
        # a basis-gauge difference into an apparent rate-equation discrepancy.
        rotated_dipole[q_index] = ground_u.T @ dipole[q_index] @ excited_u

    ng, ne = dipole.shape[1:]
    decay_strength = np.sum(np.abs(rotated_dipole) ** 2, axis=0)
    decay_rates = gamma * np.sum(decay_strength, axis=0)
    branching = np.divide(
        decay_strength,
        np.sum(decay_strength, axis=0, keepdims=True),
        out=np.zeros_like(decay_strength, dtype=float),
        where=np.sum(decay_strength, axis=0, keepdims=True) > 0,
    )
    evolution = np.zeros((ng + ne, ng + ne), dtype=float)
    evolution[np.arange(ng, ng + ne), np.arange(ng, ng + ne)] -= decay_rates
    evolution[:ng, ng:] += gamma * decay_strength

    kvecs = np.asarray(collection.kvec(position, 0.0), dtype=float)
    intensities = np.asarray(collection.intensity(position, 0.0), dtype=float)
    detunings = np.asarray(collection.delta(0.0), dtype=float)
    projections = np.asarray(collection.project_pol(quantization_axis, R=position, t=0.0), dtype=np.complex128)
    pumping = np.zeros((len(kvecs), ng, ne), dtype=float)
    transition_energy = excited_energy[None, :] - ground_energy[:, None]
    for laser_index, (kvec, intensity, detuning, projection) in enumerate(
        zip(kvecs, intensities, detunings, projections)
    ):
        coupling = (
            rotated_dipole[0] * projection[2]
            + rotated_dipole[1] * projection[1]
            + rotated_dipole[2] * projection[0]
        )
        line_detuning = -transition_energy + detuning - float(np.dot(kvec, velocity))
        pumping[laser_index] = (
            gamma * float(intensity) / 2.0
            * np.abs(coupling) ** 2
            / (1.0 + 4.0 * line_detuning**2 / gamma**2)
        )

    summed_pumping = np.sum(pumping, axis=0)
    evolution[:ng, ng:] += summed_pumping
    evolution[ng:, :ng] += summed_pumping.T
    evolution[np.arange(ng), np.arange(ng)] -= np.sum(summed_pumping, axis=1)
    evolution[ng + np.arange(ne), ng + np.arange(ne)] -= np.sum(summed_pumping, axis=0)

    populations, singular_values, nullity = _solve_nullspace(evolution, svd_eps)
    ground_population = populations[:ng]
    excited_population = populations[ng:]
    imbalance = ground_population[:, None] - excited_population[None, :]
    net_scattering = np.sum(pumping * imbalance[None, :, :], axis=(1, 2))
    per_laser_force = kvecs.T * net_scattering[None, :]
    force = np.sum(per_laser_force, axis=1)
    residual = evolution @ populations

    return PaperRateEquationResult(
        equilibrium_populations=populations,
        evolution_matrix=evolution,
        pumping_rates=pumping,
        spontaneous_branching=branching,
        spontaneous_decay_rates=decay_rates,
        normalized_force=np.asarray(force, dtype=float),
        per_laser_normalized_force=np.asarray(per_laser_force, dtype=float),
        net_scattering_rate_by_laser_gamma=np.asarray(net_scattering, dtype=float),
        total_scattering_rate_gamma=float(np.dot(decay_rates, excited_population)),
        excited_fraction=float(np.sum(excited_population)),
        residual_linf=float(np.linalg.norm(residual, ord=np.inf)),
        residual_l2=float(np.linalg.norm(residual)),
        singular_values=singular_values,
        nullspace_dimension=nullity,
        ground_energies_gamma=ground_energy,
        excited_energies_gamma=excited_energy,
        ground_zero_field_energies_gamma=np.sort(np.real(np.linalg.eigvalsh(ground_h0))),
        excited_zero_field_energies_gamma=np.sort(np.real(np.linalg.eigvalsh(excited_h0))),
        ground_transform=ground_u,
        excited_transform=excited_u,
        rotated_dipole_q=rotated_dipole,
        magnetic_field_gauss=field,
        quantization_axis=np.asarray(quantization_axis, dtype=float),
    )
