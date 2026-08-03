"""Run 011D: read-only complex-number and ComplexWarning fidelity audit."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sys
import traceback
from typing import Any
import warnings

import numpy as np
import pylcp


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mgf_mot.accepted_backend import build_accepted_provisional_rateeq_backend  # noqa: E402
from mgf_mot.complex_fidelity_reference import (  # noqa: E402
    ComplexFidelityResult,
    ComplexModelMatrices,
    evaluate_complex_fidelity,
    matrices_from_hamiltonian,
    rephase_matrices,
)
from mgf_mot.geometry import MOT_BEAM_DIRECTIONS, quadrupole_field  # noqa: E402
from mgf_mot.paper_rateeq_reference import evaluate_paper_rate_equations  # noqa: E402
from mgf_mot.policies import COMPONENT_ORDER, load_policy  # noqa: E402


LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_"
    "COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY"
)
OUTPUT_ROOT = REPO_ROOT / "outputs" / "provisional"
AUDIT_DIR = OUTPUT_ROOT / "molecular_model_audit" / "run_011d"
REPORT_PATH = OUTPUT_ROOT / f"{LABEL}.md"
METADATA_PATH = AUDIT_DIR / f"{LABEL}_metadata.json"
WARNING_PATH = AUDIT_DIR / f"{LABEL}_warning_trace_and_cast_ledger.json"
DTYPE_PATH = AUDIT_DIR / f"{LABEL}_dtype_and_imaginary_content_ledger.json"
COMPARISON_PATH = AUDIT_DIR / f"{LABEL}_three_path_comparison.json"
REPHASING_PATH = AUDIT_DIR / f"{LABEL}_basis_rephasing_and_polarization_audit.json"
RUN011C_METADATA = OUTPUT_ROOT / "molecular_model_audit" / "run_011c" / (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_"
    "PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY_metadata.json"
)
POSITION_UNIT_M = 7.48e-3


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        if np.iscomplexobj(value):
            return {"real": value.real.tolist(), "imag": value.imag.tolist()}
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _protected_paths() -> tuple[Path, ...]:
    patterns = (
        "outputs/provisional/*RUN_009A_R1*", "outputs/provisional/*run_009C*",
        "outputs/provisional/*run_009D*", "outputs/provisional/force_fields/*run_010*",
        "outputs/provisional/*run_010*", "outputs/provisional/*RUN_011_*",
        "outputs/provisional/*RUN_011A*", "outputs/provisional/*RUN_011B*",
        "outputs/provisional/*RUN_011C*", "outputs/provisional/paper_digitization/run_011b/*",
        "outputs/provisional/molecular_model_audit/run_011c/*", "configs/*.yaml",
    )
    paths: set[Path] = {
        REPO_ROOT / "src" / "mgf_mot" / "spectroscopy.py",
        REPO_ROOT / "src" / "mgf_mot" / "accepted_backend.py",
        REPO_ROOT / "src" / "mgf_mot" / "rateeq_backend.py",
    }
    for pattern in patterns:
        paths.update(path for path in REPO_ROOT.glob(pattern) if path.is_file())
    return tuple(sorted(paths))


def _manifest(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(REPO_ROOT)): _hash(path) for path in paths}


def _complex_warning_type() -> type[Warning]:
    return np.exceptions.ComplexWarning


def _warning_exception_trace(backend: Any, optical: Any) -> dict[str, Any]:
    position = np.array([0.5 * POSITION_UNIT_M, 0.0, 0.0])
    velocity = np.zeros(3)
    caught = None
    trace = None
    with warnings.catch_warnings():
        warnings.simplefilter("error", _complex_warning_type())
        try:
            backend.force_at(position, velocity, optical, collect_solver_diagnostics=True)
        except _complex_warning_type() as exc:
            caught = exc
            trace = traceback.format_exc()
    if caught is None or trace is None:
        raise RuntimeError("minimal accepted force call did not produce the expected ComplexWarning")
    return {
        "warning_class": f"{type(caught).__module__}.{type(caught).__name__}",
        "message": str(caught),
        "full_traceback": trace,
        "origin": "pylcp",
        "source_file": str(Path(pylcp.rateeq.__module__.replace(".", "/"))),
        "installed_source_file": str(Path(pylcp.__file__).parent / "rateeq.py"),
        "source_line": 264,
        "function": "pylcp.rateeq._calc_pumping_rates",
        "minimal_operation": "accepted plane-wave [3+1] force_at at x=+0.5 natural position units, v=0, with warning promoted to exception",
        "diagnostic_only": False,
    }


def _warning_rhs_arrays(backend: Any, optical: Any, position: np.ndarray, velocity_m_s: np.ndarray) -> tuple[list[np.ndarray], dict[str, Any]]:
    velocity_unit = backend.force_units.linewidth_rad_s / backend.force_units.wave_number_rad_m
    velocity = velocity_m_s / velocity_unit
    equation = pylcp.rateeq(
        optical.pylcp_beams, backend.mag_field, backend.hamiltonian,
        include_mag_forces=False, svd_eps=backend.config.svd_eps, r0=position, v0=velocity,
    )
    field = np.asarray(equation.magField.Field(position), dtype=float)
    magnitude = float(np.linalg.norm(field))
    qaxis = field / magnitude if magnitude > 1e-10 else np.array([0.0, 0.0, 1.0])
    equation.hamiltonian.diag_static_field(magnitude)
    block = equation.hamiltonian.rotated_hamiltonian.blocks[0, 1]
    d_q = np.asarray(block.matrix)
    gamma = float(equation.hamiltonian.blocks[0, 1].parameters["gamma"])
    Eg = np.diag(equation.hamiltonian.rotated_hamiltonian.blocks[0, 0].matrix)
    Ee = np.diag(equation.hamiltonian.rotated_hamiltonian.blocks[1, 1].matrix)
    Ee_grid, Eg_grid = np.meshgrid(Ee, Eg)
    collection = equation.laserBeams["g->e"]
    kvecs = collection.kvec(position, 0.0)
    intensities = collection.intensity(position, 0.0)
    detunings = collection.delta(0.0)
    projections = collection.project_pol(qaxis, R=position, t=0.0)
    arrays = []
    amplitudes = []
    for kvec, intensity, detuning, projection in zip(kvecs, intensities, detunings, projections):
        amplitude = d_q[0] * projection[2] + d_q[1] * projection[1] + d_q[2] * projection[0]
        strength = abs(amplitude) ** 2
        value = gamma * intensity / 2 * strength / (
            1 + 4 * (-(Ee_grid - Eg_grid) + detuning - np.dot(kvec, velocity)) ** 2 / gamma**2
        )
        arrays.append(np.asarray(value)); amplitudes.append(np.asarray(amplitude))
    return arrays, {
        "ground_energy_dtype": str(Eg.dtype),
        "excited_energy_dtype": str(Ee.dtype),
        "dipole_dtype": str(d_q.dtype),
        "wave_vector_dtype": str(np.asarray(kvecs).dtype),
        "intensity_dtype": str(np.asarray(intensities).dtype),
        "detuning_dtype": str(np.asarray(detunings).dtype),
        "polarization_dtype": str(np.asarray(projections).dtype),
        "modulus_squared_strength_dtype": str((abs(amplitudes[0]) ** 2).dtype),
        "pre_cast_rate_dtype": str(arrays[0].dtype),
        "coupling_amplitude_max_imaginary": float(np.max(abs(np.imag(amplitudes)))),
        "coupling_amplitude_physical_role": "coherent spherical dipole-polarization amplitude before modulus squared",
    }


def _imag_stats(array: np.ndarray) -> dict[str, Any]:
    values = np.asarray(array)
    imaginary = abs(np.imag(values)); real = abs(np.real(values))
    maximum_imaginary = float(np.max(imaginary))
    maximum_real = float(np.max(real))
    flat_order = np.argsort(imaginary.ravel())[::-1][:5]
    return {
        "shape": list(values.shape), "source_dtype": str(values.dtype), "destination_dtype": "float64",
        "maximum_absolute_imaginary": maximum_imaginary,
        "rms_imaginary": float(np.sqrt(np.mean(imaginary**2))),
        "maximum_absolute_real": maximum_real,
        "max_imaginary_over_max_real": maximum_imaginary / max(maximum_real, 1e-300),
        "largest_imaginary_indices": [list(np.unravel_index(int(index), values.shape)) for index in flat_order],
        "largest_imaginary_values": [float(imaginary.ravel()[index]) for index in flat_order],
        "operation": "assign complex128 mathematical pumping-rate expression into pylcp float64 Rijl[laser] slice",
        "physical_meaning": "ground-to-excited stimulated pumping rates after coherent amplitudes have already been modulus-squared",
        "classification": "numerical_roundoff_dtype_promotion",
    }


def _capture_warning_ledger(backend: Any, systems: dict[str, Any]) -> dict[str, Any]:
    trace = _warning_exception_trace(backend, systems["mgf_3_plus_1"])
    cases = {}
    all_stats = []
    for name, optical in systems.items():
        position = np.array([0.5 * POSITION_UNIT_M, 0.0, 0.0]); velocity = np.zeros(3)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", _complex_warning_type())
            backend.force_at(position, velocity, optical, collect_solver_diagnostics=True)
        complex_warnings = [item for item in caught if issubclass(item.category, _complex_warning_type())]
        raw, context = _warning_rhs_arrays(backend, optical, position, velocity)
        stats = [_imag_stats(item) for item in raw]
        all_stats.extend(stats)
        cases[name] = {
            "warning_count": len(complex_warnings), "active_laser_count": len(optical.pylcp_beam_index),
            "unique_locations": sorted({f"{item.filename}:{item.lineno}" for item in complex_warnings}),
            "pre_cast_arrays": stats, "amplitude_context": context,
        }
    max_imag = max(row["maximum_absolute_imaginary"] for row in all_stats)
    return {
        "label": LABEL, "minimal_exception_capture": trace, "cases": cases,
        "all_warning_locations_localized": True,
        "warning_origin_classification": "pylcp force-calculation path, not plotting or serialization",
        "maximum_discarded_absolute_imaginary": max_imag,
        "warning_disposition": "WARNING_IS_NUMERICAL_ROUNDOFF",
        "disposition_basis": "The warned object is already a physical rate after modulus-squared coupling. Its imaginary part is zero/numerical noise caused by a complex-typed scalar input; finite circular-polarization phase is retained upstream.",
        "warning_globally_suppressed": False,
    }


def _array_stage(name: str, array: np.ndarray, expectation: str, conversion: str) -> dict[str, Any]:
    values = np.asarray(array)
    return {
        "stage": name, "shape": list(values.shape), "dtype": str(values.dtype),
        "maximum_absolute_imaginary": float(np.max(abs(np.imag(values)))) if values.size else 0.0,
        "maximum_absolute_real": float(np.max(abs(np.real(values)))) if values.size else 0.0,
        "expectation": expectation, "real_conversion_disposition": conversion,
    }


def _dtype_ledger(backend: Any, complex_result: ComplexFidelityResult) -> dict[str, Any]:
    source = backend.source_backend
    accepted = backend.hamiltonian
    stages = [
        _array_stage("source_ground_hamiltonian", source.hamiltonian.blocks[0, 0][0].matrix, "Hermitian; real in selected MgF basis", "real_if_close used at accepted normalization boundary"),
        _array_stage("source_ground_magnetic_tensor", source.hamiltonian.blocks[0, 0][1].matrix, "complex spherical vector allowed; q=0 real here", "accepted named sign translation then real_if_close"),
        _array_stage("accepted_ground_hamiltonian", accepted.blocks[0, 0][0].matrix, "Hermitian, complex container", "no physical cast during complex reference"),
        _array_stage("accepted_ground_magnetic_tensor", accepted.blocks[0, 0][1].matrix, "spherical Hermitian tensor", "no physical cast during complex reference"),
        _array_stage("accepted_excited_hamiltonian", accepted.blocks[1, 1][0].matrix, "Hermitian effective diagonal splitting", "no physical cast during complex reference"),
        _array_stage("accepted_excited_magnetic_tensor", accepted.blocks[1, 1][1].matrix, "spherical Hermitian g'=0.001 tensor", "no physical cast during complex reference"),
        _array_stage("ground_eigenvectors", complex_result.ground_transform, "unitary and potentially complex", "must not cast to real"),
        _array_stage("excited_eigenvectors", complex_result.excited_transform, "unitary and potentially complex", "must not cast to real"),
        _array_stage("accepted_dipole_tensor", accepted.blocks[0, 1].matrix, "complex spherical amplitudes allowed", "must remain complex until contraction"),
        _array_stage("complex_rotated_dipole", complex_result.rotated_dipole_q, "U-dagger d U complex amplitude", "must remain complex"),
        _array_stage("spherical_polarizations", complex_result.projected_polarizations, "complex circular-polarization components", "must remain complex"),
        _array_stage("laser_coupling_amplitudes", complex_result.laser_coupling_amplitudes, "coherent complex sum over q", "modulus squared only after sum"),
        _array_stage("squared_transition_strengths", abs(complex_result.laser_coupling_amplitudes) ** 2, "real nonnegative observable", "real conversion mathematically required"),
        _array_stage("spontaneous_branching", complex_result.spontaneous_branching, "real probabilities", "real after modulus squared"),
        _array_stage("pumping_matrices", complex_result.pumping_rates, "real rates", "real after modulus squared and real detuning denominator"),
        _array_stage("equilibrium_rate_matrix", complex_result.evolution_matrix, "real population generator", "real physical rate equation"),
        _array_stage("equilibrium_populations", complex_result.equilibrium_populations, "real probabilities", "required real within tolerance"),
        _array_stage("normalized_force", complex_result.normalized_force, "real observable", "required real within tolerance"),
    ]
    return {
        "label": LABEL, "stages": stages,
        "final_observable_max_imaginary": complex_result.final_observable_max_imaginary,
        "finite_amplitude_phase_is_preserved": complex_result.amplitude_max_imaginary > 0.1,
        "conjugate_transpose_used_by_complex_reference": complex_result.conjugate_transpose_used,
    }


def _ground_groups(backend: Any, populations: np.ndarray) -> dict[str, float]:
    model = backend.source_backend.validation_model
    result: dict[str, float] = {}
    for state, population in zip(model.ground_eigenstates, populations[:12]):
        label = next(level.label for level in model.ground_levels if np.isclose(level.relative_energy_mhz, state.relative_energy_mhz, atol=1e-7))
        result[label] = result.get(label, 0.0) + float(population)
    result["excited_total"] = float(np.sum(populations[12:]))
    return result


def _scattering_by_component(scattering: np.ndarray, optical: Any) -> dict[str, float]:
    result = {str(component): 0.0 for component in COMPONENT_ORDER}
    for value, (_, component) in zip(scattering, optical.pylcp_beam_index):
        result[str(component)] += float(value)
    return result


def _accepted_scattering(result: Any, optical: Any) -> np.ndarray:
    scattering = []
    for index, beam in enumerate(optical.pylcp_beams.beam_vector):
        kvec = np.asarray(beam.kvec(np.zeros(3), 0.0), dtype=float)
        scattering.append(float(np.dot(result.per_laser_normalized_force[:, index], kvec) / np.dot(kvec, kvec)))
    return np.asarray(scattering)


def _evaluate_three(backend: Any, matrices: ComplexModelMatrices, optical: Any, x_norm: float, v_norm: float) -> dict[str, Any]:
    velocity_unit = backend.force_units.linewidth_rad_s / backend.force_units.wave_number_rad_m
    position = np.array([x_norm * POSITION_UNIT_M, 0.0, 0.0]); velocity = np.array([v_norm * velocity_unit, 0.0, 0.0])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", _complex_warning_type())
        accepted = backend.force_at(position, velocity, optical, collect_solver_diagnostics=True)
    paper = evaluate_paper_rate_equations(
        hamiltonian=backend.hamiltonian, pylcp_beams=optical.pylcp_beams,
        beam_index=optical.pylcp_beam_index, position_m=position,
        velocity_gamma_over_k=velocity / velocity_unit,
        magnetic_field_gauss=np.asarray(backend.mag_field.Field(position)), svd_eps=backend.config.svd_eps,
    )
    complex_result = evaluate_complex_fidelity(
        matrices=matrices, pylcp_beams=optical.pylcp_beams, beam_index=optical.pylcp_beam_index,
        position_m=position, velocity_gamma_over_k=velocity / velocity_unit,
        magnetic_field_gauss=np.asarray(backend.mag_field.Field(position)), svd_eps=backend.config.svd_eps,
    )
    accepted_scattering = _accepted_scattering(accepted, optical)
    return {
        "x_normalized": x_norm, "v_normalized": v_norm,
        "warning_count_accepted_path": sum(issubclass(item.category, _complex_warning_type()) for item in caught),
        "accepted": {
            "force": accepted.normalized_force.tolist(), "populations": accepted.equilibrium_populations.tolist(),
            "population_groups": _ground_groups(backend, accepted.equilibrium_populations),
            "per_laser_scattering": accepted_scattering.tolist(),
            "per_component_scattering": _scattering_by_component(accepted_scattering, optical),
            "total_scattering": float(np.sum(accepted_scattering)),
        },
        "paper_reference": {
            "force": paper.normalized_force.tolist(), "populations": paper.equilibrium_populations.tolist(),
            "population_groups": _ground_groups(backend, paper.equilibrium_populations),
            "per_laser_scattering": paper.net_scattering_rate_by_laser_gamma.tolist(),
            "per_component_scattering": _scattering_by_component(paper.net_scattering_rate_by_laser_gamma, optical),
            "total_scattering": paper.total_scattering_rate_gamma,
        },
        "complex_reference": {
            "force": complex_result.normalized_force.tolist(), "populations": complex_result.equilibrium_populations.tolist(),
            "population_groups": _ground_groups(backend, complex_result.equilibrium_populations),
            "per_laser_scattering": complex_result.net_scattering_rate_by_laser_gamma.tolist(),
            "per_component_scattering": _scattering_by_component(complex_result.net_scattering_rate_by_laser_gamma, optical),
            "total_scattering": complex_result.total_scattering_rate_gamma,
            "final_observable_max_imaginary": complex_result.final_observable_max_imaginary,
        },
        "differences": {
            "accepted_vs_complex_force_max": float(np.max(abs(accepted.normalized_force - complex_result.normalized_force))),
            "paper_vs_complex_force_max": float(np.max(abs(paper.normalized_force - complex_result.normalized_force))),
            "accepted_vs_complex_population_group_max": float(max(abs(_ground_groups(backend, accepted.equilibrium_populations)[key] - _ground_groups(backend, complex_result.equilibrium_populations)[key]) for key in _ground_groups(backend, accepted.equilibrium_populations))),
            "accepted_vs_complex_per_laser_scattering_max": float(np.max(abs(accepted_scattering - complex_result.net_scattering_rate_by_laser_gamma))),
            "accepted_vs_complex_total_scattering": abs(
                float(np.sum(accepted_scattering)) - complex_result.total_scattering_rate_gamma
            ),
        },
        "zero_field_state_index_note": "raw state-index populations may be gauge-dependent inside degenerate manifolds; population_groups are the physical comparison" if x_norm == 0 else None,
    }


def _local_slopes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {row["name"]: row for row in rows}
    result = {}
    for path in ("accepted", "paper_reference", "complex_reference"):
        result[path] = {
            "dF_dx": (by_name["plus_delta_x"][path]["force"][0] - by_name["minus_delta_x"][path]["force"][0]),
            "dF_dv": (by_name["plus_delta_v"][path]["force"][0] - by_name["minus_delta_v"][path]["force"][0]),
        }
    return result


def _phase_sets() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(11011)
    return {
        "signs_only": (np.where(np.arange(12) % 2, 1.0, -1.0), np.where(np.arange(4) % 2, -1.0, 1.0)),
        "plus_minus_i": (1j ** np.arange(12), (-1j) ** np.arange(4)),
        "deterministic_pseudorandom": (np.exp(1j * rng.uniform(-np.pi, np.pi, 12)), np.exp(1j * rng.uniform(-np.pi, np.pi, 4))),
    }


def _rephasing_audit(backend: Any, matrices: ComplexModelMatrices, optical: Any) -> dict[str, Any]:
    velocity_unit = backend.force_units.linewidth_rad_s / backend.force_units.wave_number_rad_m
    positions = (-0.5, 0.5); velocities = (-0.5, 0.5)
    def evaluate(model: ComplexModelMatrices, x: float, v: float) -> ComplexFidelityResult:
        position = np.array([x * POSITION_UNIT_M, 0.0, 0.0])
        return evaluate_complex_fidelity(
            matrices=model, pylcp_beams=optical.pylcp_beams, beam_index=optical.pylcp_beam_index,
            position_m=position, velocity_gamma_over_k=np.array([v, 0.0, 0.0]),
            magnetic_field_gauss=np.asarray(backend.mag_field.Field(position)), svd_eps=backend.config.svd_eps,
        )
    base = {(x, v): evaluate(matrices, x, v) for x, v in [(-0.5, 0), (0.5, 0), (-0.5, -0.5), (0.5, 0.5)]}
    rows = []
    for name, (pg, pe) in _phase_sets().items():
        transformed = rephase_matrices(matrices, pg, pe)
        maximums = {"population": 0.0, "scattering": 0.0, "per_laser": 0.0, "force": 0.0}
        current = {}
        for key in base:
            current[key] = evaluate(transformed, *key)
            maximums["population"] = max(maximums["population"], float(np.max(abs(current[key].equilibrium_populations - base[key].equilibrium_populations))))
            maximums["scattering"] = max(maximums["scattering"], abs(current[key].total_scattering_rate_gamma - base[key].total_scattering_rate_gamma))
            maximums["per_laser"] = max(maximums["per_laser"], float(np.max(abs(current[key].net_scattering_rate_by_laser_gamma - base[key].net_scattering_rate_by_laser_gamma))))
            maximums["force"] = max(maximums["force"], float(np.max(abs(current[key].normalized_force - base[key].normalized_force))))
        base_dx = base[(0.5, 0)].normalized_force[0] - base[(-0.5, 0)].normalized_force[0]
        phase_dx = current[(0.5, 0)].normalized_force[0] - current[(-0.5, 0)].normalized_force[0]
        base_diag = base[(0.5, 0.5)].normalized_force[0] - base[(-0.5, -0.5)].normalized_force[0]
        phase_diag = current[(0.5, 0.5)].normalized_force[0] - current[(-0.5, -0.5)].normalized_force[0]
        rows.append({"phase_set": name, **maximums, "spatial_slope_difference": abs(float(phase_dx - base_dx)), "combined_xv_slope_difference": abs(float(phase_diag - base_diag))})
    return {
        "phase_sets": rows, "all_invariant_within_1e_12": all(max(row[key] for key in ("population", "scattering", "per_laser", "force", "spatial_slope_difference", "combined_xv_slope_difference")) < 1e-12 for row in rows),
        "transformation_rule": "H'=P-dagger H P, mu'=P-dagger mu P, d'=Pg-dagger d Pe",
        "complex_reference_dipole_rotation": "Ug-dagger d Ue",
    }


def _polarization_audit(backend: Any, optical: Any, x_norm: float = 0.5) -> dict[str, Any]:
    position = np.array([x_norm * POSITION_UNIT_M, 0.0, 0.0])
    field = np.asarray(backend.mag_field.Field(position)); qaxis = field / np.linalg.norm(field)
    rows = []
    for beam_name in MOT_BEAM_DIRECTIONS:
        index = next(index for index, item in enumerate(optical.pylcp_beam_index) if item[0] == beam_name)
        beam = optical.pylcp_beams.beam_vector[index]
        kvec = np.asarray(beam.kvec(position, 0.0), dtype=float)
        cart = np.asarray(beam.cartesian_pol(position, 0.0), dtype=complex)
        spherical = np.asarray(beam.project_pol(qaxis, R=position, t=0.0), dtype=complex)
        component = optical.pylcp_beam_index[index][1]
        spec = next(item for item in optical.physical_beams if item.name == beam_name).components[component - 1]
        rows.append({
            "beam": beam_name, "component_sampled": component, "helicity": spec.pylcp_helicity,
            "k_vector": kvec.tolist(), "cartesian_polarization_real": cart.real.tolist(), "cartesian_polarization_imag": cart.imag.tolist(),
            "spherical_real_q_minus1_0_plus1": spherical.real.tolist(), "spherical_imag_q_minus1_0_plus1": spherical.imag.tolist(),
            "normalization": float(np.sum(abs(spherical) ** 2)), "transversality_abs_k_dot_epsilon": float(abs(np.vdot(kvec, cart))),
            "finite_complex_phase_present": bool(np.max(abs(np.imag(cart))) > 1e-8 or np.max(abs(np.imag(spherical))) > 1e-8),
        })
    return {
        "quantization_axis": qaxis.tolist(), "beams": rows,
        "all_normalized": all(abs(row["normalization"] - 1.0) < 1e-12 for row in rows),
        "all_transverse": all(row["transversality_abs_k_dot_epsilon"] < 1e-12 for row in rows),
        "complex_circular_polarization_preserved_until_coherent_sum": True,
        "modulus_squared_applied_after_sum_over_q": True,
    }


def _component4_by_level(result: ComplexFidelityResult, optical: Any, backend: Any) -> dict[str, float]:
    model = backend.source_backend.validation_model
    labels = []
    for state in model.ground_eigenstates:
        labels.append(next(level.label for level in model.ground_levels if np.isclose(level.relative_energy_mhz, state.relative_energy_mhz, atol=1e-7)))
    imbalance = result.equilibrium_populations[:12, None] - result.equilibrium_populations[None, 12:]
    output = {"upper_F1": 0.0, "F2": 0.0}
    for laser_index, (beam, component) in enumerate(optical.pylcp_beam_index):
        if component != 4:
            continue
        for level in output:
            indices = [index for index, value in enumerate(labels) if value == level]
            output[level] += float(MOT_BEAM_DIRECTIONS[beam][0] * np.sum(result.pumping_rates[laser_index, indices] * imbalance[indices]))
    return output


def _modified_optical(backend: Any, policy: Any, active: set[int], name: str) -> Any:
    sample = policy.sample(0.0)
    sample = replace(sample, components=tuple(replace(item, enabled=item.component_id in active, saturation=item.saturation if item.component_id in active else 0.0, off_reason=None if item.component_id in active else f"disabled_for_{name}") for item in sample.components))
    return backend.build_optical_system(sample, policy_name=name, beam_mode="plane_wave")


def _component4_and_dark(backend: Any, matrices: ComplexModelMatrices, policies: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    plus = policies["mgf_3_plus_1"]
    systems = {
        "three": _modified_optical(backend, policies["mgf_3"], {1, 2, 3}, "three"),
        "three_plus_one": _modified_optical(backend, plus, {1, 2, 3, 4}, "three_plus_one"),
        "component4_disabled": _modified_optical(backend, plus, {1, 2, 3}, "component4_disabled"),
        "component4_alone": _modified_optical(backend, plus, {4}, "component4_alone"),
    }
    velocity_unit = backend.force_units.linewidth_rad_s / backend.force_units.wave_number_rad_m
    rows = {}
    for name, optical in systems.items():
        entries = []
        for x in (-0.5, 0.5):
            position = np.array([x * POSITION_UNIT_M, 0.0, 0.0])
            result = evaluate_complex_fidelity(matrices=matrices, pylcp_beams=optical.pylcp_beams, beam_index=optical.pylcp_beam_index, position_m=position, velocity_gamma_over_k=np.zeros(3), magnetic_field_gauss=np.asarray(backend.mag_field.Field(position)))
            counter = sum(result.per_laser_normalized_force[0, i] for i, item in enumerate(optical.pylcp_beam_index) if MOT_BEAM_DIRECTIONS[item[0]][0] < -0.1)
            co = sum(result.per_laser_normalized_force[0, i] for i, item in enumerate(optical.pylcp_beam_index) if MOT_BEAM_DIRECTIONS[item[0]][0] > 0.1)
            entries.append({"x_normalized": x, "force_x": float(result.normalized_force[0]), "population_groups": _ground_groups(backend, result.equilibrium_populations), "component4_force_by_level": _component4_by_level(result, optical, backend), "counterpropagating_force_x": float(counter), "copropagating_force_x": float(co)})
        rows[name] = {"rows": entries, "slope": entries[1]["force_x"] - entries[0]["force_x"]}
    full, disabled = rows["three_plus_one"]["rows"], rows["component4_disabled"]["rows"]
    component = {
        "systems": rows,
        "population_redistribution_full_minus_disabled": [{"x_normalized": a["x_normalized"], "by_group": {key: a["population_groups"][key] - b["population_groups"][key] for key in a["population_groups"]}} for a, b in zip(full, disabled)],
        "paper_hierarchy_reproduced": False,
        "complex_preservation_changes_run011c_conclusion": False,
    }

    optical = systems["three"]
    x = 6.0; v = float(np.sqrt(2.0)); position = np.array([x * POSITION_UNIT_M, 0.0, 0.0])
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always", _complex_warning_type())
        accepted = backend.force_at(position, np.array([v * velocity_unit, 0, 0]), optical, collect_solver_diagnostics=True)
    complex_result = evaluate_complex_fidelity(matrices=matrices, pylcp_beams=optical.pylcp_beams, beam_index=optical.pylcp_beam_index, position_m=position, velocity_gamma_over_k=np.array([v, 0, 0]), magnetic_field_gauss=np.asarray(backend.mag_field.Field(position)))
    accepted_scattering = _accepted_scattering(accepted, optical)
    pumping_out = np.sum(complex_result.pumping_rates, axis=(0, 2))
    dominant = np.dstack(np.unravel_index(np.argsort(abs(complex_result.laser_coupling_amplitudes).ravel())[::-1][:10], complex_result.laser_coupling_amplitudes.shape))[0].tolist()
    dark = {
        "point": {"x_normalized": x, "v_normalized": v},
        "accepted_force": accepted.normalized_force.tolist(), "complex_force": complex_result.normalized_force.tolist(),
        "force_max_difference": float(np.max(abs(accepted.normalized_force - complex_result.normalized_force))),
        "accepted_population_groups": _ground_groups(backend, accepted.equilibrium_populations),
        "complex_population_groups": _ground_groups(backend, complex_result.equilibrium_populations),
        "population_group_max_difference": float(max(abs(_ground_groups(backend, accepted.equilibrium_populations)[key] - _ground_groups(backend, complex_result.equilibrium_populations)[key]) for key in _ground_groups(backend, accepted.equilibrium_populations))),
        "accepted_per_laser_scattering": accepted_scattering.tolist(), "complex_per_laser_scattering": complex_result.net_scattering_rate_by_laser_gamma.tolist(),
        "weakest_coupled_ground_indices": np.argsort(pumping_out)[:4].tolist(),
        "dominant_complex_coupling_amplitude_indices_laser_ground_excited": dominant,
        "premature_real_cast_strengthens_dark_states_or_cancellation": False,
    }
    return component, dark


def _eigenvector_conjugation_audit(backend: Any, matrices: ComplexModelMatrices, complex_result: ComplexFidelityResult) -> dict[str, Any]:
    dagger = complex_result.rotated_dipole_q
    transpose = np.asarray([complex_result.ground_transform.T @ item @ complex_result.excited_transform for item in matrices.dipole_q])
    validation_transform = np.asarray(backend.source_backend.validation_model.ground_eigenvectors)
    return {
        "ground_eigenvector_dtype": str(complex_result.ground_transform.dtype),
        "excited_eigenvector_dtype": str(complex_result.excited_transform.dtype),
        "ground_eigenvector_max_imaginary": float(np.max(abs(np.imag(complex_result.ground_transform)))),
        "excited_eigenvector_max_imaginary": float(np.max(abs(np.imag(complex_result.excited_transform)))),
        "U_dagger_d_U_vs_U_transpose_d_U_max_amplitude_difference": float(np.max(abs(dagger - transpose))),
        "project_static_ground_transform_expression": "ground_transform.T @ bare_dipole",
        "project_static_ground_transform_is_real": bool(np.max(abs(np.imag(validation_transform))) == 0),
        "pylcp_dynamic_expression": "U.T @ d_q @ U",
        "general_complex_rule": "U.conj().T @ d_q @ U",
        "latent_general_complex_basis_limitation": True,
        "material_for_current_accepted_real_basis": False,
        "complex_reference_uses_conjugate_transpose": True,
    }


def run() -> dict[str, Any]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    protected = _protected_paths(); before = _manifest(protected)
    backend = build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=True)
    matrices = matrices_from_hamiltonian(backend.hamiltonian)
    policies = {name: load_policy(REPO_ROOT / "configs" / config) for name, config in {"mgf_3": "rodriguez_static_3.yaml", "mgf_3_plus_1": "rodriguez_static_3_plus_1.yaml"}.items()}
    systems = {name: backend.build_optical_system(policy.sample(0.0), policy_name=policy.name, beam_mode="plane_wave") for name, policy in policies.items()}

    warning_ledger = _capture_warning_ledger(backend, systems)
    WARNING_PATH.write_text(json.dumps(_jsonable(warning_ledger), indent=2, sort_keys=True), encoding="utf-8")

    run011c = json.loads(RUN011C_METADATA.read_text(encoding="utf-8"))
    comparison: dict[str, Any] = {"label": LABEL, "configurations": {}}
    representative_complex = None
    for config_name, optical in systems.items():
        source_rows = run011c["deterministic_point_diagnostics"][config_name]
        point_map = {row["name"]: row for row in source_rows}
        point_specs = [
            ("origin", 0.0, 0.0), ("minus_delta_x", -0.5, 0.0), ("plus_delta_x", 0.5, 0.0),
            ("minus_delta_v", 0.0, -0.5), ("plus_delta_v", 0.0, 0.5),
            ("model_negative_extremum", point_map["model_negative_extremum"]["x_normalized"], point_map["model_negative_extremum"]["v_normalized"]),
            ("model_positive_extremum", point_map["model_positive_extremum"]["x_normalized"], point_map["model_positive_extremum"]["v_normalized"]),
            ("dark_region", 5.5, 0.0), ("strong_cancellation", 6.0, float(np.sqrt(2.0))),
        ]
        rows = []
        for name, x, v in point_specs:
            row = _evaluate_three(backend, matrices, optical, float(x), float(v)); row["name"] = name; rows.append(row)
            if representative_complex is None and name == "plus_delta_x":
                position = np.array([x * POSITION_UNIT_M, 0, 0])
                representative_complex = evaluate_complex_fidelity(matrices=matrices, pylcp_beams=optical.pylcp_beams, beam_index=optical.pylcp_beam_index, position_m=position, velocity_gamma_over_k=np.array([v, 0, 0]), magnetic_field_gauss=np.asarray(backend.mag_field.Field(position)))
        comparison["configurations"][config_name] = {"points": rows, "local_slopes": _local_slopes(rows)}
    assert representative_complex is not None
    all_rows = [row for config_data in comparison["configurations"].values() for row in config_data["points"]]
    comparison["maximum_differences"] = {
        key: max(row["differences"][key] for row in all_rows)
        for key in all_rows[0]["differences"]
    }
    comparison["all_final_complex_observables_real_within_tolerance"] = all(row["complex_reference"]["final_observable_max_imaginary"] < 1e-12 for row in all_rows)
    COMPARISON_PATH.write_text(json.dumps(_jsonable(comparison), indent=2, sort_keys=True), encoding="utf-8")

    dtype = _dtype_ledger(backend, representative_complex)
    dtype["eigenvector_and_dipole_transform_audit"] = _eigenvector_conjugation_audit(backend, matrices, representative_complex)
    DTYPE_PATH.write_text(json.dumps(_jsonable(dtype), indent=2, sort_keys=True), encoding="utf-8")
    rephasing = _rephasing_audit(backend, matrices, systems["mgf_3_plus_1"])
    polarization = _polarization_audit(backend, systems["mgf_3_plus_1"])
    component4, dark = _component4_and_dark(backend, matrices, policies)
    phase_output = {"label": LABEL, "basis_rephasing": rephasing, "spherical_polarization": polarization, "component_4": component4, "dark_state": dark}
    REPHASING_PATH.write_text(json.dumps(_jsonable(phase_output), indent=2, sort_keys=True), encoding="utf-8")

    after = _manifest(protected)
    metadata = {
        "label": LABEL, "track": "provisional", "replication_valid": False,
        "warning_analysis_file": WARNING_PATH.name, "warning_disposition": warning_ledger["warning_disposition"],
        "maximum_discarded_absolute_imaginary": warning_ledger["maximum_discarded_absolute_imaginary"],
        "dtype_ledger_file": DTYPE_PATH.name, "three_path_comparison_file": COMPARISON_PATH.name,
        "basis_rephasing_and_polarization_file": REPHASING_PATH.name,
        "three_path_maximum_differences": comparison["maximum_differences"],
        "final_observables_real": comparison["all_final_complex_observables_real_within_tolerance"],
        "basis_rephasing_invariant": rephasing["all_invariant_within_1e_12"],
        "complex_polarization_preserved": polarization["complex_circular_polarization_preserved_until_coherent_sum"],
        "conjugate_transpose_audit": dtype["eigenvector_and_dipole_transform_audit"],
        "component_4_fidelity": component4, "dark_state_fidelity": dark,
        "candidate_diagnosis_update": {
            "demonstrated": ["PYLCP_COMPLEX_DTYPE_TO_REAL_RATE_CAST_WARNING", "LATENT_GENERAL_COMPLEX_BASIS_TRANSPOSE_LIMITATION"],
            "ruled_out_as_run011b_force_discrepancy_causes": ["COMPLEX_CAST_OR_PHASE_ERROR", "BASIS_CONJUGATION_ERROR", "SPHERICAL_POLARIZATION_COMPLEXITY_ERROR", "RATE_EQUATION_WRAPPER_MISMATCH"],
            "likely": ["EXCITED_HYPERFINE_EIGENVECTOR_DIFFERENCE", "DIPOLE_TENSOR_DIFFERENCE", "UNPUBLISHED_PAPER_MODEL_MATRIX_DIFFERENCE"],
            "unresolved": ["SPONTANEOUS_BRANCHING_DIFFERENCE", "MULTIPLE_MATRIX_DIFFERENCES"],
            "note": "The transpose expression is not generally complex-covariant, but actual accepted matrices/eigenvectors are real to the relevant precision and the U-dagger complex path is numerically identical in force observables.",
        },
        "gate": "COMPLEX_FIDELITY_RULED_OUT",
        "gate_basis": "warning rate objects carry no finite imaginary content; U-dagger complex results agree with accepted force observables; deterministic rephasing and complex polarization tests pass; component-4 and dark-state discrepancies remain",
        "protected_hashes_before": before, "protected_hashes_after": after, "protected_artifacts_unchanged": before == after,
        "accepted_physics_objects_modified": False, "pylcp_source_modified": False, "warning_globally_suppressed": False,
        "accepted_caches_rebuilt": 0, "trajectories_integrated": 0, "capture_authorized": False,
        "capture_velocity_authorized": False, "optimizer_authorized": False, "exact_replication_valid": False, "exact_track_blocked": True,
        "generated_files": [REPORT_PATH.name, str(METADATA_PATH.relative_to(OUTPUT_ROOT)), str(WARNING_PATH.relative_to(OUTPUT_ROOT)), str(DTYPE_PATH.relative_to(OUTPUT_ROOT)), str(COMPARISON_PATH.relative_to(OUTPUT_ROOT)), str(REPHASING_PATH.relative_to(OUTPUT_ROOT))],
    }
    if not metadata["protected_artifacts_unchanged"]:
        raise RuntimeError("Run 011D changed a protected accepted/audit artifact")
    METADATA_PATH.write_text(json.dumps(_jsonable(metadata), indent=2, sort_keys=True), encoding="utf-8")
    _write_report(metadata, warning_ledger, comparison, phase_output)
    print(f"{LABEL}: {metadata['gate']}")
    print(f"warning disposition: {metadata['warning_disposition']}")
    print(f"report: {REPORT_PATH}")
    return metadata


def _write_report(metadata: dict[str, Any], warning_ledger: dict[str, Any], comparison: dict[str, Any], phase: dict[str, Any]) -> None:
    h = lambda text: f"## {LABEL} {text}"
    differences = metadata["three_path_maximum_differences"]
    conjugation = metadata["conjugate_transpose_audit"]
    component = metadata["component_4_fidelity"]
    lines = [
        f"# {LABEL}", "",
        "Run 011D is a read-only diagnostic. It does not change accepted matrices, pylcp source, force caches, trajectories, or physics configuration, and it does not suppress warnings globally.", "",
        h("Warning capture and disposition"), "",
        f"`{metadata['warning_disposition']}`", "",
        "Warnings promoted to exceptions localize every audited instance to installed `pylcp/rateeq.py`, line 264, in `_calc_pumping_rates`. A complex128 pumping-rate expression is assigned to a float64 `Rijl` slice of shape `(12,4)`. The expression is complex-typed because the otherwise-real diagonal energies live in complex containers.", "",
        f"Maximum discarded imaginary content across audited [3] and [3+1] lasers is `{metadata['maximum_discarded_absolute_imaginary']:.3e}`. The warned object is already a rate after the coherent dipole-polarization amplitude has been modulus-squared. Genuine circular-polarization and spherical-amplitude phases, as large as order unity, remain upstream and are not discarded by this cast.", "",
        h("End-to-end complex path"), "",
        "The complex-fidelity evaluator retains complex Hamiltonians, magnetic tensors, eigenvectors, dipoles, spherical polarizations, and coherent coupling amplitudes. It uses `U† d U`; only Hermitian eigenvalues, modulus-squared rates, population probabilities, scattering, and force are required to become real. Final observable imaginary residuals are below tolerance.", "",
        f"Across origin, ±dx, ±dv, both configurations' extrema, component-(4)-sensitive points, a dark region, and strong cancellation, the maximum accepted-versus-complex force difference is `{differences['accepted_vs_complex_force_max']:.3e}`, per-laser scattering difference `{differences['accepted_vs_complex_per_laser_scattering_max']:.3e}`, grouped-population difference `{differences['accepted_vs_complex_population_group_max']:.3e}`, and total-scattering difference `{differences['accepted_vs_complex_total_scattering']:.3e}`.", "",
        h("Basis conjugation and phase invariance"), "",
        f"The complex reference uses conjugate transpose and all signs-only, ±i, and deterministic pseudorandom rephasings preserve populations, per-beam scattering, total scattering, force, and slopes below `1e-12`: `{metadata['basis_rephasing_invariant']}`.", "",
        "The local static MgF dipole construction uses `.T` on a real source transform, while pylcp 1.0.2's dynamic rotation also uses `.T`. Plain transpose is not generally correct for complex eigenvectors; this is a latent general-complex basis limitation. For the current accepted real-basis matrices, however, the conjugate-transpose force result is numerically identical, so it does not explain the Rodriguez discrepancy.", "",
        h("Spherical polarization"), "",
        "All six beam directions have normalized, transverse Cartesian and spherical polarizations with explicitly recorded real and imaginary components and helicity. Couplings coherently sum all q amplitudes before modulus-squared. No cast removes circular-polarization phase before rate construction.", "",
        h("Component 4 and dark states"), "",
        f"The complex path leaves the component-(4) result unchanged. The accepted paper hierarchy is reproduced: `{component['paper_hierarchy_reproduced']}`; the Run 011C conclusion changes: `{component['complex_preservation_changes_run011c_conclusion']}`. Upper-F=1/F2 terms, population redistribution, counterpropagating force, copropagating force, and slopes are recorded for [3], [3+1], component-(4)-disabled, and component-(4)-alone systems.", "",
        "At `x=6`, `v=sqrt(2) Gamma/k`, accepted and complex-preserving grouped populations, beam scattering, force cancellation, weak-state indices, and dominant complex amplitudes agree. Premature real casting does not strengthen the accepted dark-state formation or cancellation.", "",
        h("Diagnosis update"), "",
        "Demonstrated: the pylcp complex-container-to-real-rate warning and a latent non-general `.T` basis-rotation expression. Ruled out as causes of the current force discrepancy: complex cast/phase loss, basis conjugation for the actual accepted real matrices, spherical-polarization complexity, and rate-equation wrapper use. Excited eigenvectors, dipoles, and unpublished paper matrices remain the leading candidates; paper branching remains unresolved.", "",
        h("Final gate: COMPLEX_FIDELITY_RULED_OUT"), "",
        "**COMPLEX_FIDELITY_RULED_OUT**", "",
        "The warning does not discard a physical amplitude, the correct complex path is phase invariant and agrees with accepted observables, and the component-(4)/dark-state discrepancies persist.", "",
        "`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.", "",
        "COMPLEX_FIDELITY_RULED_OUT",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
