"""Run 009C: static-only excited-state Zeeman sensitivity study."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
from pylcp.common import spherical2cart

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_provisional_rateeq_static_acceptance_audit_r1 as r1

from mgf_mot.conventions import GroundZeemanConvention
from mgf_mot.excited_zeeman import (
    ExcitedZeemanModel,
    validate_excited_zeeman_operator,
)
from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.rateeq_backend import (
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
)
from mgf_mot.spectroscopy import (
    BOHR_MAGNETON_MHZ_PER_GAUSS,
    ELECTRON_G_FACTOR,
    EXCITED_G_FACTOR_RODRIGUEZ,
)
from mgf_mot.static_acceptance import flip_policy_polarizations


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
RUN009C_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY"
)
MODELS = (
    ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT,
    ExcitedZeemanModel.ZERO_EXCITED_ZEEMAN,
    ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001,
)
POSITIONS_M = np.linspace(-0.02, 0.02, 17)
VELOCITIES_M_S = np.linspace(-15.06, 15.06, 17)
SENSITIVITY_THRESHOLDS = {
    "insensitive_relative_max": 0.01,
    "weakly_sensitive_relative_max": 0.05,
    "materially_sensitive_relative_min_exclusive": 0.05,
    "topology_changing": "sign/classification changes",
    "extremum_location_insensitive_max_grid_steps": 1.0,
    "extremum_location_weak_max_grid_steps": 2.0,
}


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        if np.iscomplexobj(value):
            return {"real": value.real.tolist(), "imag": value.imag.tolist()}
        return value.tolist()
    if isinstance(value, np.generic):
        if np.iscomplexobj(value):
            return {"real": float(np.real(value)), "imag": float(np.imag(value))}
        return value.item()
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    return value


def _stamp(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _stamp(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stamp(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_stamp(item) for item in value)
    if isinstance(value, str):
        return value.replace(r1.R1_LABEL, RUN009C_LABEL)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _backend(
    model: ExcitedZeemanModel, *, gradient_t_m: float = 0.2
) -> ProvisionalPylcpRateEquationBackend:
    backend = ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            magnetic_gradient_t_m=gradient_t_m,
            ground_zeeman_convention=(
                GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
            ),
            excited_zeeman_model=model,
        )
    )
    if backend.status.ground_magnetic_moment_correction_count != 1:
        raise RuntimeError("Run 009C requires the unchanged single ground correction")
    if backend.status.excited_zeeman_model_application_count != 1:
        raise RuntimeError("excited Zeeman model must be applied exactly once")
    if backend.status.excited_zeeman_model_application_location != "Hamiltonian boundary":
        raise RuntimeError("excited Zeeman model must be selected at Hamiltonian boundary")
    return backend


def _fx(backend, system, x_m: float, vx_m_s: float, *, diagnostics: bool = False):
    return backend.force_at(
        np.array([x_m, 0.0, 0.0]),
        np.array([vx_m_s, 0.0, 0.0]),
        system,
        collect_solver_diagnostics=diagnostics,
    )


def _current_tensor_audit(backend) -> dict[str, Any]:
    source = backend.source_backend
    h0 = np.asarray(source.hamiltonian.blocks[1, 1][0].matrix, dtype=np.complex128)
    muq = np.asarray(source.hamiltonian.blocks[1, 1][1].matrix, dtype=np.complex128)
    cartesian = np.asarray(spherical2cart(muq))
    basis = source.validation_model.excited_basis
    mu_b = BOHR_MAGNETON_MHZ_PER_GAUSS.require()
    epsilon_g = 1.0e-4
    f0 = np.array([0])
    f1 = np.array([1, 2, 3])
    axes: dict[str, Any] = {}
    for axis_name, mu_axis in zip(("x", "y", "z"), cartesian):
        perturbation = -mu_axis
        f0_slope = float(np.real(perturbation[0, 0]))
        f1_slopes = np.linalg.eigvalsh(perturbation[np.ix_(f1, f1)])
        minus = np.linalg.eigvalsh(h0 - epsilon_g * mu_axis)
        plus = np.linalg.eigvalsh(h0 + epsilon_g * mu_axis)
        zero = np.linalg.eigvalsh(h0)
        finite_difference = (plus - minus) / (2.0 * epsilon_g)
        axes[axis_name] = {
            "field_samples_gauss": [-epsilon_g, 0.0, epsilon_g],
            "f0_first_order_slope_mhz_per_gauss": f0_slope,
            "f1_first_order_slopes_mhz_per_gauss": f1_slopes.tolist(),
            "f1_effective_gm": (f1_slopes / mu_b).tolist(),
            "identifiable_weak_field_character": [
                {"F_prime": 0, "mF_along_field": 0, "dE_dB_mhz_per_gauss": f0_slope},
                *[
                    {
                        "F_prime": 1,
                        "mF_along_field": m_value,
                        "dE_dB_mhz_per_gauss": float(slope),
                        "effective_g": (
                            None if m_value == 0 else float(slope / (mu_b * m_value))
                        ),
                    }
                    for m_value, slope in zip((-1, 0, 1), f1_slopes)
                ],
            ],
            "full_spectrum_one_sided_plus_slopes_mhz_per_gauss": ((plus - zero) / epsilon_g).tolist(),
            "sorted_centered_difference_note": (
                "Centered differences of independently sorted degenerate F'=1 eigenvalues "
                "are branch-ambiguous; the degenerate perturbation eigenvalues above are "
                "the identifiable first-order slopes."
            ),
            "full_eigenvalue_sorted_centered_diagnostic": finite_difference.tolist(),
            "spectrum_at_plus_field_mhz": plus.tolist(),
            "spectrum_at_minus_field_mhz": minus.tolist(),
        }
    off_block_norms = {
        axis: float(np.linalg.norm(cartesian[index][np.ix_(f0, f1)]))
        for index, axis in enumerate(("x", "y", "z"))
    }
    f1_g = float(abs(axes["z"]["f1_effective_gm"][-1]))
    return {
        "label": RUN009C_LABEL,
        "title": f"{RUN009C_LABEL} current collapsed tensor audit",
        "tensor_shape": list(muq.shape),
        "basis_order": [
            {"index": index, "F_prime": int(state["F"]), "mF": int(state["mF"])}
            for index, state in enumerate(basis)
        ],
        "units": "MHz/G before Gamma normalization",
        "construction_source": (
            "pylcp 1.0.2 XFmolecules.Astate Zeeman terms, with project call "
            "gS source-tagged and gL=gl=glprime=gr=greprime=gN=0"
        ),
        "hamiltonian_convention": "H = H0 - mu.B",
        "spherical_q_order": [-1, 0, 1],
        "cartesian_components_hermitian": [
            bool(np.allclose(axis, axis.conj().T, atol=1e-12)) for axis in cartesian
        ],
        "rotationally_isotropic_spectra": bool(
            np.allclose(axes["x"]["f1_first_order_slopes_mhz_per_gauss"], axes["z"]["f1_first_order_slopes_mhz_per_gauss"], atol=1e-12)
            and np.allclose(axes["y"]["f1_first_order_slopes_mhz_per_gauss"], axes["z"]["f1_first_order_slopes_mhz_per_gauss"], atol=1e-12)
        ),
        "diagonal_in_lab_z_F_mF_basis": bool(np.allclose(cartesian[2], np.diag(np.diag(cartesian[2])), atol=1e-12)),
        "mixes_F0_and_F1": bool(any(value > 1e-12 for value in off_block_norms.values())),
        "F0_F1_off_block_norm_by_axis": off_block_norms,
        "axes": axes,
        "reported_effective_F1_g": f1_g,
        "causal_relation": {
            "source_gS": ELECTRON_G_FACTOR.require(),
            "gS_over_6": ELECTRON_G_FACTOR.require() / 6.0,
            "difference_from_reported_g": f1_g - ELECTRON_G_FACTOR.require() / 6.0,
            "explanation": (
                "In the retained J'=I=1/2 Hund-case-(a) block, pylcp's sole active "
                "electronic-spin Zeeman term projects onto F'=1 with gF=gS/6. "
                "The same rank-1 operator has F'=0/F'=1 off-diagonal matrix elements, "
                "which affect finite-field mixing but not the nondegenerate F'=0 first-order slope."
            ),
        },
    }


def _evaluate_grids(backend, resources) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    arrays: dict[str, np.ndarray] = {
        "positions_m": POSITIONS_M,
        "velocities_m_s": VELOCITIES_M_S,
    }
    minimum_population = np.inf
    maximum_population = -np.inf
    maximum_sum_error = 0.0
    maximum_residual = 0.0
    nullities: set[int] = set()
    fallbacks = 0
    nonfinite = 0
    solves = 0
    for name, system in resources["systems"].items():
        grid = np.empty((POSITIONS_M.size, VELOCITIES_M_S.size), dtype=float)
        for i, x_m in enumerate(POSITIONS_M):
            for j, velocity in enumerate(VELOCITIES_M_S):
                result = _fx(backend, system, float(x_m), float(velocity), diagnostics=True)
                grid[i, j] = result.normalized_force[0]
                populations = result.equilibrium_populations
                minimum_population = min(minimum_population, float(np.min(populations)))
                maximum_population = max(maximum_population, float(np.max(populations)))
                maximum_sum_error = max(maximum_sum_error, abs(result.population_sum - 1.0))
                maximum_residual = max(maximum_residual, result.steady_state_residual_linf)
                nullities.add(result.nullspace_dimension)
                fallbacks += int(result.singular_solver_fallback_used)
                solves += 1
                if not np.isfinite(grid[i, j]) or not np.isfinite(populations).all():
                    nonfinite += 1
        arrays[f"force_{name}"] = grid
    health = {
        "label": RUN009C_LABEL,
        "number_of_solves": solves,
        "minimum_population": float(minimum_population),
        "maximum_population": float(maximum_population),
        "maximum_population_normalization_error": float(maximum_sum_error),
        "maximum_steady_state_residual": float(maximum_residual),
        "nullspace_dimensions_observed": sorted(nullities),
        "fallback_count": fallbacks,
        "nonfinite_count": nonfinite,
        "passed": bool(
            minimum_population >= -1e-10
            and maximum_sum_error <= 1e-9
            and maximum_residual <= 1e-9
            and nullities == {1}
            and fallbacks == 0
            and nonfinite == 0
        ),
    }
    return arrays, health


def _reversal_audit(model, backend, resources) -> dict[str, Any]:
    sample = resources["static31"].sample(0.0)
    flipped = flip_policy_polarizations(sample)
    negative = _backend(model, gradient_t_m=-0.2)
    definitions = {
        "nominal": (backend, sample),
        "polarization_flipped": (backend, flipped),
        "gradient_flipped": (negative, sample),
        "both_flipped": (negative, flipped),
    }
    cases = {}
    for name, (case_backend, case_sample) in definitions.items():
        system = case_backend.build_optical_system(
            case_sample, policy_name=f"run009c_{model.value}_{name}", beam_mode="plane_wave"
        )
        cases[name] = _stamp(r1._local_slope_record(case_backend, system))
    passed = bool(
        cases["nominal"]["dFdx_normalized_per_m"] < 0
        and cases["nominal"]["dFdv_normalized_per_m_s"] < 0
        and cases["polarization_flipped"]["dFdx_normalized_per_m"] > 0
        and cases["gradient_flipped"]["dFdx_normalized_per_m"] > 0
        and cases["both_flipped"]["dFdx_normalized_per_m"] < 0
    )
    return {"label": RUN009C_LABEL, "cases": cases, "passed": passed}


def _extrema(arrays) -> dict[str, Any]:
    records = {}
    for key, grid in arrays.items():
        if not key.startswith("force_"):
            continue
        maximum = np.unravel_index(int(np.argmax(grid)), grid.shape)
        minimum = np.unravel_index(int(np.argmin(grid)), grid.shape)
        records[key.removeprefix("force_")] = {
            "minimum_force": float(grid[minimum]),
            "minimum_x_m": float(POSITIONS_M[minimum[0]]),
            "minimum_vx_m_s": float(VELOCITIES_M_S[minimum[1]]),
            "maximum_force": float(grid[maximum]),
            "maximum_x_m": float(POSITIONS_M[maximum[0]]),
            "maximum_vx_m_s": float(VELOCITIES_M_S[maximum[1]]),
            "maximum_absolute_force": float(np.max(np.abs(grid))),
        }
    return records


def _model_observables(model: ExcitedZeemanModel) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    print(f"{RUN009C_LABEL}: evaluating {model.value}")
    backend = _backend(model)
    resources = r1.prior_audit._resources(backend)
    arrays, health = _evaluate_grids(backend, resources)
    local = _stamp(r1._local_slope_audit(backend, resources))
    component4 = _stamp(r1._component4_audit(backend, resources, arrays))
    reversal = _reversal_audit(model, backend, resources)
    chirp = _stamp(r1._chirp_audit(backend, resources, np.linspace(0.0, 110.0, 111)))
    gaussian = _stamp(r1.prior_audit._gaussian_audit(backend, resources))
    force_scale = _stamp(r1._force_scale_audit(arrays, backend))
    convergence = _stamp(
        r1.prior_audit._grid_convergence(
            backend, resources, arrays, refinement_factor=2
        )
    )
    convergence["topology_preserved"] = bool(
        all(row["checks"]["local_topology_signs_unchanged"] for row in convergence["cases"].values())
    )
    validation = validate_excited_zeeman_operator(backend.excited_zeeman_operator)
    record = {
        "label": RUN009C_LABEL,
        "title": f"{RUN009C_LABEL} {model.value}",
        "model": model.value,
        "reported_weak_field_effective_g": (
            ELECTRON_G_FACTOR.require() / 6.0
            if model is ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT
            else backend.excited_zeeman_operator.effective_g
        ),
        "backend_status": _json_safe(backend.status),
        "operator": _json_safe(backend.excited_zeeman_operator),
        "operator_validation": validation,
        "non_zeeman_input_fingerprint": {
            "ground_zeeman_convention": backend.config.ground_zeeman_convention.value,
            "gradient_t_m": backend.config.magnetic_gradient_t_m,
            "policy_names": [resources["static3"].name, resources["static31"].name, resources["chirp"].name],
            "position_axis_m": POSITIONS_M.tolist(),
            "velocity_axis_m_s": VELOCITIES_M_S.tolist(),
            "beam_geometry": "shared +/-x_prime,+/-y_prime,+/-z",
            "gaussian_config": "configs/rodriguez_gaussian_baseline.yaml",
        },
        "local_slopes": local,
        "component_4": component4,
        "reversal": reversal,
        "extrema": _extrema(arrays),
        "force_scale": force_scale,
        "chirp": chirp,
        "population_health": health,
        "gaussian": gaussian,
        "grid_refinement": convergence,
    }
    return record, arrays


def _relative_difference(first: float, second: float) -> float:
    return float(abs(second - first) / max(abs(first), abs(second), 1e-15))


def _classify_scalar(first: float, second: float, *, topology: bool = False) -> dict[str, Any]:
    relative = _relative_difference(first, second)
    if topology and first * second < 0:
        classification = "TOPOLOGY_CHANGING"
    elif relative <= SENSITIVITY_THRESHOLDS["insensitive_relative_max"]:
        classification = "INSENSITIVE"
    elif relative <= SENSITIVITY_THRESHOLDS["weakly_sensitive_relative_max"]:
        classification = "WEAKLY_SENSITIVE"
    else:
        classification = "MATERIALLY_SENSITIVE"
    return {
        "first": first,
        "second": second,
        "absolute_difference": float(abs(second - first)),
        "relative_difference": relative,
        "classification": classification,
    }


def _compare_models(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for case in ("plane_wave_3", "plane_wave_3_plus_1", "gaussian_3", "gaussian_3_plus_1"):
        a = first["local_slopes"]["cases"][case]
        b = second["local_slopes"]["cases"][case]
        metrics[f"{case}.dFdx"] = _classify_scalar(
            a["dFdx_normalized_per_m"], b["dFdx_normalized_per_m"], topology=True
        )
        metrics[f"{case}.dFdv"] = _classify_scalar(
            a["dFdv_normalized_per_m_s"], b["dFdv_normalized_per_m_s"], topology=True
        )
    for mode in ("plane_wave", "elliptical_gaussian"):
        a_slopes = first["component_4"]["cases"][mode]["slopes"]
        b_slopes = second["component_4"]["cases"][mode]["slopes"]
        a_enhancement = (
            a_slopes["three_plus_one"]["dFdx_normalized_per_m"]
            - a_slopes["three"]["dFdx_normalized_per_m"]
        )
        b_enhancement = (
            b_slopes["three_plus_one"]["dFdx_normalized_per_m"]
            - b_slopes["three"]["dFdx_normalized_per_m"]
        )
        metrics[f"{mode}.component_4_confinement_enhancement"] = _classify_scalar(
            a_enhancement, b_enhancement, topology=True
        )
    for case in first["extrema"]:
        a = first["extrema"][case]
        b = second["extrema"][case]
        metrics[f"{case}.maximum_absolute_force"] = _classify_scalar(
            a["maximum_absolute_force"], b["maximum_absolute_force"]
        )
        dx_steps = abs(b["minimum_x_m"] - a["minimum_x_m"]) / abs(POSITIONS_M[1] - POSITIONS_M[0])
        dv_steps = abs(b["minimum_vx_m_s"] - a["minimum_vx_m_s"]) / abs(VELOCITIES_M_S[1] - VELOCITIES_M_S[0])
        shift = max(dx_steps, dv_steps)
        location_class = (
            "INSENSITIVE" if shift <= 1.0 else "WEAKLY_SENSITIVE" if shift <= 2.0 else "MATERIALLY_SENSITIVE"
        )
        metrics[f"{case}.minimum_location"] = {
            "position_shift_grid_steps": dx_steps,
            "velocity_shift_grid_steps": dv_steps,
            "classification": location_class,
        }
    for index, (a, b) in enumerate(zip(first["chirp"]["features"], second["chirp"]["features"])):
        metrics[f"chirp_{index}.velocity"] = _classify_scalar(
            a["dominant_inbound_slowing_velocity_m_s"],
            b["dominant_inbound_slowing_velocity_m_s"],
        )
    metrics["reversal_pattern"] = {
        "first": first["reversal"]["passed"],
        "second": second["reversal"]["passed"],
        "classification": (
            "INSENSITIVE"
            if first["reversal"]["passed"] == second["reversal"]["passed"]
            else "TOPOLOGY_CHANGING"
        ),
    }
    metrics["population_minimum"] = _classify_scalar(
        first["population_health"]["minimum_population"],
        second["population_health"]["minimum_population"],
    )
    metrics["population_health_pass"] = {
        "first": first["population_health"]["passed"],
        "second": second["population_health"]["passed"],
        "classification": (
            "INSENSITIVE"
            if first["population_health"]["passed"] == second["population_health"]["passed"]
            else "TOPOLOGY_CHANGING"
        ),
    }
    classes = [value["classification"] for value in metrics.values()]
    return {
        "label": RUN009C_LABEL,
        "first_model": first["model"],
        "second_model": second["model"],
        "thresholds": SENSITIVITY_THRESHOLDS,
        "metrics": metrics,
        "classification_counts": {name: classes.count(name) for name in (
            "INSENSITIVE", "WEAKLY_SENSITIVE", "MATERIALLY_SENSITIVE", "TOPOLOGY_CHANGING"
        )},
        "any_topology_change": "TOPOLOGY_CHANGING" in classes,
    }


def _save_plot(records: dict[str, Any], arrays_by_model: dict[str, dict[str, np.ndarray]], output_dir: Path) -> Path:
    import matplotlib.pyplot as plt

    path = output_dir / f"{RUN009C_LABEL}_run_009C_comparison.png"
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    for model, record in records.items():
        cases = record["local_slopes"]["cases"]
        axes[0].scatter(cases["plane_wave_3"]["dFdx_normalized_per_m"], cases["plane_wave_3"]["dFdv_normalized_per_m_s"], label=model)
        grid = arrays_by_model[model]["force_plane_wave_3_plus_1"]
        axes[1].plot(POSITIONS_M * 1e3, grid[:, 8], label=model)
        axes[2].plot(VELOCITIES_M_S, grid[8, :], label=model)
    axes[0].set(xlabel="dF_x/dx", ylabel="dF_x/dv_x", title=f"{RUN009C_LABEL} [3] slopes")
    axes[1].set(xlabel="x [mm]", ylabel="normalized force", title=f"{RUN009C_LABEL} [3+1] v=0")
    axes[2].set(xlabel="v_x [m/s]", ylabel="normalized force", title=f"{RUN009C_LABEL} [3+1] x=0")
    for axis in axes:
        axis.legend(fontsize=7)
    fig.suptitle(f"{RUN009C_LABEL} Run 009C")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def run(output_dir: Path = DEFAULT_OUTPUT_DIR, *, save_plot: bool = True) -> dict[str, Any]:
    """Run only static force and operator diagnostics; never integrate motion."""

    output_dir.mkdir(parents=True, exist_ok=True)
    yaml_paths = tuple(sorted((REPO_ROOT / "configs").glob("rodriguez*.yaml")))
    yaml_before = {str(path.relative_to(REPO_ROOT)): _sha256(path) for path in yaml_paths}

    default_backend = _backend(ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT)
    tensor_audit = _current_tensor_audit(default_backend)
    sign_diagnostic = validate_excited_zeeman_operator(
        _backend(ExcitedZeemanModel.NEGATIVE_G_0P001_SIGN_DIAGNOSTIC).excited_zeeman_operator
    )
    records: dict[str, Any] = {}
    arrays_by_model: dict[str, dict[str, np.ndarray]] = {}
    for model in MODELS:
        record, arrays = _model_observables(model)
        records[model.value] = record
        arrays_by_model[model.value] = arrays

    zero = records[ExcitedZeemanModel.ZERO_EXCITED_ZEEMAN.value]
    effective = records[ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001.value]
    collapsed = records[ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT.value]
    zero_vs_effective = _compare_models(zero, effective)
    effective_vs_collapsed = _compare_models(effective, collapsed)

    acceptance_checks = {
        "basis_and_operator_validated": bool(
            effective["operator_validation"]["weak_field_slopes_match_selected_g"]
            and all(effective["operator_validation"]["cartesian_components_hermitian"])
            and effective["operator_validation"]["f0_first_order_slope_zero"]
            and effective["operator_validation"]["f0_f1_off_block_zero"]
        ),
        "operator_applied_exactly_once": effective["operator"]["model_application_count"] == 1,
        "three_restoring_and_damping": bool(
            effective["local_slopes"]["cases"]["plane_wave_3"]["dFdx_normalized_per_m"] < 0
            and effective["local_slopes"]["cases"]["plane_wave_3"]["dFdv_normalized_per_m_s"] < 0
        ),
        "three_plus_one_more_restoring": bool(effective["local_slopes"]["passed"]),
        "reversal_pattern_correct": bool(effective["reversal"]["passed"]),
        "component_4_improves_confinement": bool(effective["component_4"]["passed"]),
        "chirp_features_coherent": bool(effective["chirp"]["passed"]),
        "population_solves_healthy": bool(effective["population_health"]["passed"]),
        "gaussian_application_correct": bool(effective["gaussian"]["passed"]),
        "force_scale_plausible": bool(effective["force_scale"]["passed"]),
        "refined_topology_stable": bool(effective["grid_refinement"]["topology_preserved"]),
        "provenance_explicit": bool(
            effective["operator"]["source"] == EXCITED_G_FACTOR_RODRIGUEZ.source
            and effective["operator"]["effective_g"] == EXCITED_G_FACTOR_RODRIGUEZ.require()
        ),
    }
    failed = [name for name, passed in acceptance_checks.items() if not passed]
    if not acceptance_checks["basis_and_operator_validated"]:
        gate = "EXCITED_ZEEMAN_OVERRIDE_AMBIGUOUS"
    elif failed:
        gate = "EXCITED_ZEEMAN_SENSITIVITY_NO_GO"
    else:
        gate = "RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED"

    arrays_path = output_dir / f"{RUN009C_LABEL}_run_009C_arrays.npz"
    flat_arrays = {}
    for model, arrays in arrays_by_model.items():
        for name, array in arrays.items():
            flat_arrays[f"{model}__{name}"] = array
    np.savez_compressed(arrays_path, **flat_arrays)
    plot_path = _save_plot(records, arrays_by_model, output_dir) if save_plot else None
    yaml_after = {str(path.relative_to(REPO_ROOT)): _sha256(path) for path in yaml_paths}
    if yaml_before != yaml_after:
        raise RuntimeError("source Rodriguez YAML changed during Run 009C")

    zero_counts = zero_vs_effective["classification_counts"]
    collapsed_counts = effective_vs_collapsed["classification_counts"]
    zero_effectively_same = bool(
        not zero_vs_effective["any_topology_change"]
        and zero_counts["MATERIALLY_SENSITIVE"] == 0
    )
    collapsed_material = bool(
        effective_vs_collapsed["any_topology_change"]
        or collapsed_counts["MATERIALLY_SENSITIVE"] > 0
    )
    metadata = {
        "label": RUN009C_LABEL,
        "title": f"{RUN009C_LABEL} Run 009C metadata",
        "gate": gate,
        "preferred_track_p_static_excited_zeeman_model": (
            ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001.value
            if gate == "RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED"
            else None
        ),
        "preferred_model_still_requires_explicit_selection": True,
        "failed_acceptance_checks": failed,
        "track": "provisional",
        "trajectory_authorized": False,
        "capture_authorized": False,
        "exact_replication_valid": False,
        "exact_track_blocked": True,
        "trajectory_integrations_performed": 0,
        "capture_results_calculated": 0,
        "source_yaml_unchanged": True,
        "source_yaml_hashes": yaml_after,
        "current_collapsed_tensor_audit": tensor_audit,
        "negative_g_sign_diagnostic": sign_diagnostic,
        "candidate_models": records,
        "comparisons": {
            "zero_vs_rodriguez_0p001": zero_vs_effective,
            "rodriguez_0p001_vs_pylcp_collapsed": effective_vs_collapsed,
        },
        "sensitivity_interpretation": {
            "g_0p001_effectively_indistinguishable_from_zero": zero_effectively_same,
            "collapsed_g_0p334_materially_changes_any_observable": collapsed_material,
            "retaining_collapsed_tensor_would_contaminate_later_motion_work": collapsed_material,
            "thresholds": SENSITIVITY_THRESHOLDS,
        },
        "acceptance_checks": acceptance_checks,
        "approximation_boundary": {
            "rodriguez_g_0p001_is_representative_source_value": True,
            "paper_aligned_effective_approximation": True,
            "exact_excited_spectroscopy_reconstruction": False,
            "independent_d_operator_unresolved": True,
            "exact_F0_F1_spectroscopy_unresolved": True,
        },
        "arrays": arrays_path.name,
        "arrays_sha256": _sha256(arrays_path),
        "plot": None if plot_path is None else plot_path.name,
    }
    metadata_path = output_dir / f"{RUN009C_LABEL}_run_009C_metadata.json"
    metadata_path.write_text(json.dumps(_json_safe(metadata), indent=2, sort_keys=True), encoding="utf-8")
    report_path = output_dir / f"{RUN009C_LABEL}_run_009C.md"
    h = lambda text: f"## {RUN009C_LABEL} {text}"
    lines = [
        f"# {RUN009C_LABEL} Run 009C",
        "",
        "This is a static-only excited-state Zeeman sensitivity study. It runs no trajectory or capture calculation and makes no exact MgF/Rodriguez claim.",
        "",
        h("Current collapsed tensor"),
        "",
        f"The pylcp tensor has shape `{tensor_audit['tensor_shape']}`, units MHz/G, and basis order `F',mF={[(row['F_prime'], row['mF']) for row in tensor_audit['basis_order']]}`. Its Cartesian components are Hermitian and its weak-field spectra are rotationally isotropic. It mixes F'=0 and F'=1, although that mixing does not give the nondegenerate F'=0 state a first-order shift.",
        f"The F'=1 result is `g={tensor_audit['reported_effective_F1_g']:.9g}` because the sole active collapsed Astate electronic-spin term projects to `gS/6={tensor_audit['causal_relation']['gS_over_6']:.9g}`.",
        "",
        h("Explicit models and weak-field validation"),
        "",
        "| model | effective g | applied once | Hermitian | slopes match |",
        "|---|---:|---|---|---|",
    ]
    for model, record in records.items():
        op = record["operator"]
        val = record["operator_validation"]
        lines.append(f"| {model} | {record['reported_weak_field_effective_g']} | {op['model_application_count'] == 1} | {all(val['cartesian_components_hermitian'])} | {val['weak_field_slopes_match_selected_g']} |")
    lines += [
        "",
        h("Static observables"),
        "",
        "| model | [3] dF/dx | [3] dF/dv | [3+1] dF/dx | [3+1] dF/dv | c4 improves | reversal | health |",
        "|---|---:|---:|---:|---:|---|---|---|",
    ]
    for model, record in records.items():
        cases = record["local_slopes"]["cases"]
        lines.append(f"| {model} | {cases['plane_wave_3']['dFdx_normalized_per_m']:.6g} | {cases['plane_wave_3']['dFdv_normalized_per_m_s']:.6g} | {cases['plane_wave_3_plus_1']['dFdx_normalized_per_m']:.6g} | {cases['plane_wave_3_plus_1']['dFdv_normalized_per_m_s']:.6g} | {record['component_4']['passed']} | {record['reversal']['passed']} | {record['population_health']['passed']} |")
    lines += [
        "",
        h("Sensitivity classification"),
        "",
        f"Thresholds: <=1% `INSENSITIVE`, <=5% `WEAKLY_SENSITIVE`, larger same-topology changes `MATERIALLY_SENSITIVE`, and sign/classification changes `TOPOLOGY_CHANGING`. Extremum locations use one- and two-grid-step thresholds.",
        f"Zero versus g'=0.001 counts: `{zero_counts}`. g'=0.001 versus collapsed g~0.334 counts: `{collapsed_counts}`.",
        f"At this static scale, g'=0.001 is effectively indistinguishable from zero: `{zero_effectively_same}`. The collapsed tensor materially changes at least one audited observable: `{collapsed_material}`.",
        "",
        h("Approximation boundary and locks"),
        "",
        "The `g'=+0.001` value is the representative value used by Rodriguez et al. The direct-sum operator is a paper-aligned effective approximation, not a reconstruction of exact excited-state spectroscopy. The independent Doppelbauer `d` operator and exact F'=0/F'=1 spectroscopy remain unresolved, so Track E remains blocked.",
        "",
        h(f"Final gate: {gate}"),
        "",
        f"**{gate}**",
        "",
        "`trajectory_authorized = false`, `capture_authorized = false`, `exact_replication_valid = false`, and `exact_track_blocked = true` regardless of this result.",
        "",
        f"# {RUN009C_LABEL} FINAL_{gate}",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{RUN009C_LABEL}: {gate}")
    print(f"metadata: {metadata_path}")
    print(f"report: {report_path}")
    return {
        "gate": gate,
        "metadata": metadata,
        "arrays_path": arrays_path,
        "metadata_path": metadata_path,
        "report_path": report_path,
        "plot_path": plot_path,
    }


if __name__ == "__main__":
    run()
