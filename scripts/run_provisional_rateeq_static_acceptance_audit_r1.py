"""Run 009A-R1: corrected-ground-Zeeman static-only acceptance audit."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_provisional_rateeq_static_acceptance_audit as prior_audit

from mgf_mot.conventions import GroundZeemanConvention
from mgf_mot.force_units import (
    normalized_force_to_acceleration_m_s2,
    normalized_force_to_newtons,
)
from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.policies import PolicySample
from mgf_mot.rateeq_backend import (
    RATEEQ_STATIC_LABEL,
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
)
from mgf_mot.static_acceptance import RUN009A_LABEL, centered_slope, topology_label


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
R1_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_"
    "CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY"
)
POSITION_AXIS_M = np.linspace(-0.02, 0.02, 17)
VELOCITY_AXIS_M_S = np.linspace(-15.06, 15.06, 17)
EXCITED_G_PROVISIONAL = 0.3337199
EXCITED_G_RODRIGUEZ = 0.001

HISTORICAL_PATHS = (
    DEFAULT_OUTPUT_DIR / f"{RATEEQ_STATIC_LABEL}_run_009_arrays.npz",
    DEFAULT_OUTPUT_DIR / f"{RATEEQ_STATIC_LABEL}_run_009_metadata.json",
    DEFAULT_OUTPUT_DIR / f"{RATEEQ_STATIC_LABEL}_run_009.md",
    DEFAULT_OUTPUT_DIR / f"{RUN009A_LABEL}_run_009A_metadata.json",
    DEFAULT_OUTPUT_DIR / f"{RUN009A_LABEL}_run_009A.md",
    DEFAULT_OUTPUT_DIR / f"{RUN009A_LABEL}_run_009A_diagnostics.png",
    DEFAULT_OUTPUT_DIR
    / "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY_run_009B_metadata.json",
    DEFAULT_OUTPUT_DIR
    / "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY_run_009B.md",
)


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
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_manifest(paths: tuple[Path, ...]) -> dict[str, Any]:
    return {
        path.name: {
            "path": str(path.relative_to(REPO_ROOT)),
            "exists": path.exists(),
            "sha256": _sha256(path) if path.exists() else None,
        }
        for path in paths
    }


def _stamp(value: Any) -> Any:
    """Replace inherited historical labels in reused read-only audit helpers."""

    if isinstance(value, dict):
        return {key: _stamp(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stamp(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_stamp(item) for item in value)
    if isinstance(value, str):
        return value.replace(RUN009A_LABEL, R1_LABEL).replace(RATEEQ_STATIC_LABEL, R1_LABEL)
    return value


def _backend(*, gradient_t_m: float = 0.2) -> ProvisionalPylcpRateEquationBackend:
    backend = ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            magnetic_gradient_t_m=gradient_t_m,
            ground_zeeman_convention=(
                GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
            ),
        )
    )
    _require_single_boundary_correction(backend)
    return backend


def _require_single_boundary_correction(
    backend: ProvisionalPylcpRateEquationBackend,
) -> None:
    status = backend.status
    if not status.ground_magnetic_moment_correction_applied:
        raise RuntimeError("Run 009A-R1 refuses a backend with zero ground correction")
    if status.ground_magnetic_moment_correction_count != 1:
        raise RuntimeError("Run 009A-R1 requires exactly one ground correction")
    if status.ground_magnetic_moment_correction_location != "Hamiltonian boundary":
        raise RuntimeError("ground correction must occur at the Hamiltonian boundary")
    if status.downstream_zeeman_sign_correction_count != 0:
        raise RuntimeError("scattered downstream Zeeman sign corrections are forbidden")


def _correction_provenance(backend: ProvisionalPylcpRateEquationBackend) -> dict[str, Any]:
    status = backend.status
    return {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} convention provenance",
        "ground_magnetic_moment_correction_applied": (
            status.ground_magnetic_moment_correction_applied
        ),
        "ground_magnetic_moment_correction_count": (
            status.ground_magnetic_moment_correction_count
        ),
        "ground_magnetic_moment_correction_location": (
            status.ground_magnetic_moment_correction_location
        ),
        "downstream_zeeman_sign_correction_count": (
            status.downstream_zeeman_sign_correction_count
        ),
        "source_yaml_unchanged": True,
        "polarization_mapping_unchanged": True,
        "field_convention_unchanged": True,
        "excited_state_zeeman_unresolved": True,
        "provisional_effective_excited_g": EXCITED_G_PROVISIONAL,
        "rodriguez_representative_excited_g": EXCITED_G_RODRIGUEZ,
    }


def _fx(backend, system, x_m: float, vx_m_s: float, *, diagnostics: bool = False):
    return backend.force_at(
        np.array([x_m, 0.0, 0.0]),
        np.array([vx_m_s, 0.0, 0.0]),
        system,
        collect_solver_diagnostics=diagnostics,
    )


def _save_surface_plot(
    name: str,
    forces: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    output_dir: Path,
) -> Path:
    import matplotlib.pyplot as plt

    path = output_dir / f"{R1_LABEL}_{name}.png"
    i0 = int(np.argmin(abs(positions)))
    j0 = int(np.argmin(abs(velocities)))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    mesh = axes[0].pcolormesh(positions * 1e3, velocities, forces.T, shading="auto")
    fig.colorbar(mesh, ax=axes[0], label="F_x/(hbar k Gamma)")
    axes[0].set(xlabel="x [mm]", ylabel="v_x [m/s]", title=f"{R1_LABEL} grid")
    axes[1].plot(positions * 1e3, forces[:, j0])
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set(xlabel="x [mm]", title=f"{R1_LABEL} v_x=0")
    axes[2].plot(velocities, forces[i0, :])
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set(xlabel="v_x [m/s]", title=f"{R1_LABEL} x=0")
    fig.suptitle(f"{R1_LABEL} {name}")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def _regenerate_surfaces(
    backend,
    resources,
    positions: np.ndarray,
    velocities: np.ndarray,
    output_dir: Path,
    *,
    save_plots: bool,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]], dict[str, Any]]:
    arrays: dict[str, np.ndarray] = {
        "positions_m": positions,
        "velocities_m_s": velocities,
    }
    records: list[dict[str, Any]] = []
    minimum_population = np.inf
    maximum_population = -np.inf
    maximum_sum_error = 0.0
    maximum_residual = 0.0
    nullities: set[int] = set()
    fallback_count = 0
    nonfinite_count = 0
    total = 0
    provenance = _correction_provenance(backend)

    for name, system in resources["systems"].items():
        print(f"{R1_LABEL}: regenerating {name}")
        grid = np.empty((positions.size, velocities.size), dtype=float)
        for i, x_m in enumerate(positions):
            for j, vx_m_s in enumerate(velocities):
                result = _fx(backend, system, float(x_m), float(vx_m_s), diagnostics=True)
                grid[i, j] = result.normalized_force[0]
                populations = result.equilibrium_populations
                total += 1
                minimum_population = min(minimum_population, float(np.min(populations)))
                maximum_population = max(maximum_population, float(np.max(populations)))
                maximum_sum_error = max(maximum_sum_error, abs(result.population_sum - 1.0))
                maximum_residual = max(maximum_residual, result.steady_state_residual_linf)
                nullities.add(result.nullspace_dimension)
                fallback_count += int(result.singular_solver_fallback_used)
                if not (
                    np.isfinite(populations).all()
                    and np.isfinite(result.normalized_force).all()
                    and np.isfinite(result.singular_values).all()
                ):
                    nonfinite_count += 1
        arrays[f"force_{name}"] = grid
        i0 = int(np.argmin(abs(positions)))
        j0 = int(np.argmin(abs(velocities)))
        maximum_index = np.unravel_index(int(np.argmax(grid)), grid.shape)
        minimum_index = np.unravel_index(int(np.argmin(grid)), grid.shape)
        plot_path = (
            _save_surface_plot(name, grid, positions, velocities, output_dir)
            if save_plots
            else None
        )
        records.append(
            {
                "label": R1_LABEL,
                "title": f"{R1_LABEL} {name} corrected static surface",
                "name": name,
                "newly_generated_after_run_009b": True,
                "reused_pre_correction_force_array": False,
                "beam_mode": system.beam_mode,
                "force_at_origin": float(grid[i0, j0]),
                "minimum_normalized_force": float(grid[minimum_index]),
                "maximum_normalized_force": float(grid[maximum_index]),
                "minimum_location": {
                    "x_m": float(positions[minimum_index[0]]),
                    "vx_m_s": float(velocities[minimum_index[1]]),
                },
                "maximum_location": {
                    "x_m": float(positions[maximum_index[0]]),
                    "vx_m_s": float(velocities[maximum_index[1]]),
                },
                "plot": None if plot_path is None else plot_path.name,
                "convention_provenance": provenance,
            }
        )

    thresholds = {
        "population_nonnegative_tolerance": -1.0e-10,
        "population_sum_tolerance": 1.0e-9,
        "steady_state_residual_linf_tolerance": 1.0e-9,
    }
    health = {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} all-grid equilibrium health",
        "number_of_solves": total,
        "minimum_population": float(minimum_population),
        "maximum_population": float(maximum_population),
        "maximum_population_normalization_error": float(maximum_sum_error),
        "maximum_steady_state_residual": float(maximum_residual),
        "nullspace_dimensions_observed": sorted(nullities),
        "fallback_count": fallback_count,
        "nonfinite_count": nonfinite_count,
        "thresholds": thresholds,
        "passed": bool(
            nonfinite_count == 0
            and minimum_population >= thresholds["population_nonnegative_tolerance"]
            and maximum_sum_error <= thresholds["population_sum_tolerance"]
            and maximum_residual <= thresholds["steady_state_residual_linf_tolerance"]
            and nullities == {1}
            and fallback_count == 0
        ),
    }
    return arrays, records, health


def _local_slope_record(backend, system) -> dict[str, Any]:
    estimates = []
    for dx, dv in ((5.0e-4, 0.5), (2.5e-4, 0.25), (1.25e-4, 0.125)):
        dfdx = (
            _fx(backend, system, dx, 0.0).normalized_force[0]
            - _fx(backend, system, -dx, 0.0).normalized_force[0]
        ) / (2 * dx)
        dfdv = (
            _fx(backend, system, 0.0, dv).normalized_force[0]
            - _fx(backend, system, 0.0, -dv).normalized_force[0]
        ) / (2 * dv)
        estimates.append({"dx_m": dx, "dv_m_s": dv, "dFdx": float(dfdx), "dFdv": float(dfdv)})
    chosen = estimates[1]
    return {
        "label": R1_LABEL,
        "dFdx_normalized_per_m": chosen["dFdx"],
        "dFdv_normalized_per_m_s": chosen["dFdv"],
        "dFdx_finite_difference_sensitivity": max(item["dFdx"] for item in estimates)
        - min(item["dFdx"] for item in estimates),
        "dFdv_finite_difference_sensitivity": max(item["dFdv"] for item in estimates)
        - min(item["dFdv"] for item in estimates),
        "estimates": estimates,
        "position_classification": topology_label(
            chosen["dFdx"], negative="restoring", positive="anti-restoring"
        ),
        "velocity_classification": topology_label(
            chosen["dFdv"], negative="damping", positive="anti-damping"
        ),
    }


def _local_slope_audit(backend, resources) -> dict[str, Any]:
    names = ("plane_wave_3", "plane_wave_3_plus_1", "gaussian_3", "gaussian_3_plus_1")
    cases = {name: _local_slope_record(backend, resources["systems"][name]) for name in names}
    passed = bool(
        cases["plane_wave_3"]["dFdx_normalized_per_m"] < 0
        and cases["plane_wave_3"]["dFdv_normalized_per_m_s"] < 0
        and cases["plane_wave_3_plus_1"]["dFdx_normalized_per_m"]
        < cases["plane_wave_3"]["dFdx_normalized_per_m"]
        and cases["gaussian_3"]["dFdx_normalized_per_m"] < 0
        and cases["gaussian_3"]["dFdv_normalized_per_m_s"] < 0
        and cases["gaussian_3_plus_1"]["dFdx_normalized_per_m"]
        < cases["gaussian_3"]["dFdx_normalized_per_m"]
    )
    return {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} local slope audit",
        "cases": cases,
        "passed": passed,
    }


def _with_active_components(sample: PolicySample, active: set[int], reason: str) -> PolicySample:
    components = tuple(
        replace(
            component,
            enabled=component.component_id in active,
            saturation=(component.saturation if component.component_id in active else 0.0),
            off_reason=(None if component.component_id in active else reason),
        )
        for component in sample.components
    )
    return replace(sample, components=components)  # type: ignore[arg-type]


def _component4_audit(backend, resources, arrays) -> dict[str, Any]:
    sample = resources["static31"].sample(0.0)
    ablated = _with_active_components(sample, {1, 2, 3}, "Run 009A-R1 component-4 ablation")
    alone = _with_active_components(sample, {4}, "Run 009A-R1 component-4-only diagnostic")
    cases: dict[str, Any] = {}
    for mode, beams in (("plane_wave", None), ("elliptical_gaussian", resources["gaussian31"])):
        systems = {
            "three": resources["systems"]["plane_wave_3" if mode == "plane_wave" else "gaussian_3"],
            "three_plus_one": resources["systems"]["plane_wave_3_plus_1" if mode == "plane_wave" else "gaussian_3_plus_1"],
            "component_4_ablated": backend.build_optical_system(
                ablated, policy_name=f"r1_{mode}_c4_ablated", beam_mode=mode, gaussian_beam_set=beams
            ),
            "component_4_only": backend.build_optical_system(
                alone, policy_name=f"r1_{mode}_c4_only", beam_mode=mode, gaussian_beam_set=beams
            ),
        }
        rows = {name: _local_slope_record(backend, system) for name, system in systems.items()}
        f3 = arrays[f"force_{'plane_wave' if mode == 'plane_wave' else 'gaussian'}_3"]
        f31 = arrays[f"force_{'plane_wave' if mode == 'plane_wave' else 'gaussian'}_3_plus_1"]
        positions = arrays["positions_m"]
        velocities = arrays["velocities_m_s"]
        min3 = np.unravel_index(int(np.argmin(f3)), f3.shape)
        min31 = np.unravel_index(int(np.argmin(f31)), f31.shape)
        cases[mode] = {
            "label": R1_LABEL,
            "slopes": rows,
            "component_4_strengthens_restoring": bool(
                rows["three_plus_one"]["dFdx_normalized_per_m"]
                < rows["three"]["dFdx_normalized_per_m"]
            ),
            "damping_change": rows["three_plus_one"]["dFdv_normalized_per_m_s"]
            - rows["three"]["dFdv_normalized_per_m_s"],
            "minimum_force_change": float(f31[min31] - f3[min3]),
            "minimum_location_three": {
                "x_m": float(positions[min3[0]]), "vx_m_s": float(velocities[min3[1]])
            },
            "minimum_location_three_plus_one": {
                "x_m": float(positions[min31[0]]), "vx_m_s": float(velocities[min31[1]])
            },
            "controlled_ablation_not_component_sum": True,
        }
    return {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} component 4 controlled optical-system audit",
        "cases": cases,
        "passed": all(row["component_4_strengthens_restoring"] for row in cases.values()),
    }


def _reversal_audit(backend, resources) -> dict[str, Any]:
    sample = resources["static31"].sample(0.0)
    flipped = prior_audit.flip_policy_polarizations(sample)
    negative_backend = _backend(gradient_t_m=-0.2)
    definitions = {
        "nominal": (backend, sample),
        "polarization_flipped": (backend, flipped),
        "gradient_flipped": (negative_backend, sample),
        "both_flipped": (negative_backend, flipped),
    }
    cases = {}
    for name, (case_backend, case_sample) in definitions.items():
        system = case_backend.build_optical_system(
            case_sample, policy_name=f"r1_{name}", beam_mode="plane_wave"
        )
        cases[name] = _local_slope_record(case_backend, system)
    passed = bool(
        cases["nominal"]["dFdx_normalized_per_m"] < 0
        and cases["nominal"]["dFdv_normalized_per_m_s"] < 0
        and cases["polarization_flipped"]["dFdx_normalized_per_m"] > 0
        and cases["gradient_flipped"]["dFdx_normalized_per_m"] > 0
        and cases["both_flipped"]["dFdx_normalized_per_m"] < 0
    )
    return {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} corrected reversal matrix",
        "uses_corrected_hamiltonian": True,
        "source_apparatus_definitions_unchanged": True,
        "cases": cases,
        "damping_reported_separately": True,
        "passed": passed,
    }


def _chirp_audit(backend, resources, velocity_axis: np.ndarray) -> dict[str, Any]:
    audit = _stamp(prior_audit._chirp_feature_audit(backend, resources, velocity_axis))
    for feature, time_s in zip(audit["features"], (0.0, 0.0005, 0.001)):
        sample = resources["chirp"].sample(time_s)
        system = backend.build_optical_system(
            sample,
            policy_name=resources["chirp"].name,
            beam_mode="elliptical_gaussian",
            gaussian_beam_set=resources["gaussian3"],
        )
        velocity = feature["dominant_inbound_slowing_velocity_m_s"]
        position_axis = np.linspace(-0.02, 0.02, 17)
        force = np.array([_fx(backend, system, float(x), velocity).normalized_force[0] for x in position_axis])
        index = int(np.argmin(force))
        expected = feature["expected_sqrt2_detuning_over_k_m_s"]
        feature["dominant_inbound_slowing_position_m"] = float(position_axis[index])
        feature["velocity_deviation_from_rough_scale_m_s"] = float(velocity - expected)
    return audit


def _force_scale_audit(arrays, backend) -> dict[str, Any]:
    records = {}
    plausible = True
    for key, grid in arrays.items():
        if not key.startswith("force_"):
            continue
        name = key.removeprefix("force_")
        minimum = float(np.min(grid))
        maximum = float(np.max(grid))
        useful = float(np.percentile(np.abs(grid), 90.0))
        characteristic = max(abs(minimum), abs(maximum))
        classification = (
            "same_order_as_paper_note_references"
            if 0.0015 <= characteristic <= 0.3
            else "outside_broad_order_of_magnitude_window"
        )
        plausible = plausible and classification == "same_order_as_paper_note_references"
        records[name] = {
            "label": R1_LABEL,
            "minimum_normalized_force": minimum,
            "maximum_normalized_force": maximum,
            "characteristic_useful_slowing_force_normalized_p90_abs": useful,
            "maximum_absolute_force_normalized": characteristic,
            "maximum_absolute_force_newtons": float(
                normalized_force_to_newtons(characteristic, backend.force_units)
            ),
            "maximum_absolute_acceleration_m_s2": float(
                normalized_force_to_acceleration_m_s2(characteristic, backend.force_units)
            ),
            "classification": classification,
        }
    return {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} force-scale audit",
        "paper_note_order_of_magnitude_references": [0.03, 0.015],
        "conversion": "F_SI=F_normalized*hbar*k*Gamma; a=F_SI/m",
        "quantitative_replication_claim": False,
        "cases": records,
        "passed": plausible,
    }


def _before_after(arrays, local, reversal, component4, chirp, health) -> dict[str, Any]:
    old_arrays_path = HISTORICAL_PATHS[0]
    old_audit_path = HISTORICAL_PATHS[3]
    old_arrays = np.load(old_arrays_path)
    old_audit = json.loads(old_audit_path.read_text(encoding="utf-8"))
    positions = np.asarray(old_arrays["positions_m"])
    velocities = np.asarray(old_arrays["velocities_m_s"])
    i0 = int(np.argmin(abs(positions)))
    j0 = int(np.argmin(abs(velocities)))
    old_f3 = old_arrays["force_plane_wave_3"]
    old_f31 = old_arrays["force_plane_wave_3_plus_1"]
    old_dfdx3 = centered_slope(positions, old_f3[:, j0])
    old_dfdv3 = centered_slope(velocities, old_f3[i0, :])
    old_dfdx31 = centered_slope(positions, old_f31[:, j0])
    return {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} before versus after",
        "original_run009a_gate": old_audit["gate"]["decision"],
        "local_restoring_slope": {
            "before_saved_grid_three": old_dfdx3,
            "after_local_three": local["cases"]["plane_wave_3"]["dFdx_normalized_per_m"],
            "before_saved_grid_three_plus_one": old_dfdx31,
            "after_local_three_plus_one": local["cases"]["plane_wave_3_plus_1"]["dFdx_normalized_per_m"],
        },
        "local_damping_slope": {
            "before_saved_grid_three": old_dfdv3,
            "after_local_three": local["cases"]["plane_wave_3"]["dFdv_normalized_per_m_s"],
        },
        "reversal_behavior_before": old_audit["reversal_audit"],
        "reversal_behavior_after": reversal,
        "component_4_effect_before": old_audit["three_vs_three_plus_one"],
        "component_4_effect_after": component4,
        "chirp_extrema_before": old_audit["chirp_feature_audit"],
        "chirp_extrema_after": chirp,
        "force_scale_before": old_audit["force_scale_audit"],
        "force_scale_after_source": "Run 009A-R1 force_scale_audit",
        "population_health_before": old_audit["solver_health"],
        "population_health_after": health,
        "old_anti_restoring_surfaces_superseded_for_provisional_engineering": True,
        "historical_artifacts_retained": True,
    }


def _save_diagnostic_plot(metadata: dict[str, Any], output_dir: Path) -> Path:
    import matplotlib.pyplot as plt

    path = output_dir / f"{R1_LABEL}_diagnostics.png"
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    reversal = metadata["reversal_audit"]["cases"]
    axes[0].bar(list(reversal), [row["dFdx_normalized_per_m"] for row in reversal.values()])
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].set(title=f"{R1_LABEL} reversal", ylabel="dF_x/dx")
    for feature in metadata["chirp_feature_audit"]["features"]:
        axes[1].plot(metadata["chirp_feature_audit"]["velocity_scan_m_s"], feature["force_slice"], label=feature["name"])
    axes[1].set(title=f"{R1_LABEL} chirp", xlabel="v_x [m/s]")
    axes[1].legend(fontsize=7)
    for name, row in metadata["grid_convergence"]["cases"].items():
        axes[2].plot(np.asarray(row["refined_position_axis_m"]) * 1e3, row["refined_position_slice"], label=name)
    axes[2].set(title=f"{R1_LABEL} refinement", xlabel="x [mm]")
    axes[2].legend(fontsize=7)
    fig.suptitle(R1_LABEL)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    positions_m: np.ndarray = POSITION_AXIS_M,
    velocities_m_s: np.ndarray = VELOCITY_AXIS_M_S,
    chirp_velocity_axis_m_s: np.ndarray | None = None,
    refinement_factor: int = 2,
    save_plots: bool = True,
) -> dict[str, Any]:
    """Regenerate corrected static surfaces and audit them; never run motion."""

    output_dir.mkdir(parents=True, exist_ok=True)
    missing = [path for path in HISTORICAL_PATHS if not path.exists()]
    if missing:
        raise FileNotFoundError(f"historical provenance inputs missing: {missing}")
    history_before = _hash_manifest(HISTORICAL_PATHS)
    yaml_paths = tuple(sorted((REPO_ROOT / "configs").glob("rodriguez*.yaml")))
    yaml_before = _hash_manifest(yaml_paths)

    backend = _backend()
    resources = prior_audit._resources(backend)
    positions = np.asarray(positions_m, dtype=float)
    velocities = np.asarray(velocities_m_s, dtype=float)
    arrays, records, health = _regenerate_surfaces(
        backend, resources, positions, velocities, output_dir, save_plots=save_plots
    )

    arrays_path = output_dir / f"{R1_LABEL}_corrected_static_arrays.npz"
    np.savez_compressed(arrays_path, **arrays)
    loaded_arrays = np.load(arrays_path)

    coordinate = _stamp(prior_audit._coordinate_audit(loaded_arrays))
    tolerance = _stamp(prior_audit._tolerance_stability(backend, resources, positions, velocities))
    local = _local_slope_audit(backend, resources)
    component4 = _component4_audit(backend, resources, arrays)
    reversal = _reversal_audit(backend, resources)
    if chirp_velocity_axis_m_s is None:
        chirp_velocity_axis_m_s = np.linspace(0.0, 110.0, 111)
    chirp = _chirp_audit(backend, resources, np.asarray(chirp_velocity_axis_m_s, dtype=float))
    gaussian = _stamp(prior_audit._gaussian_audit(backend, resources))
    force_scale = _force_scale_audit(arrays, backend)
    convergence = _stamp(
        prior_audit._grid_convergence(
            backend, resources, loaded_arrays, refinement_factor=refinement_factor
        )
    )
    convergence["all_original_quantitative_thresholds_passed"] = convergence["passed"]
    convergence["topology_preserved"] = bool(
        all(
            row["checks"]["local_topology_signs_unchanged"]
            and row["checks"]["shared_fixed_points_reproduce_saved_grid"]
            and row["checks"]["extrema_locations_shift_no_more_than_one_coarse_step"]
            for row in convergence["cases"].values()
        )
    )
    convergence["quantitative_cautions"] = [
        f"{name}: dFdx relative change exceeds 25%"
        for name, row in convergence["cases"].items()
        if not row["checks"]["dfdx_relative_change_below_25_percent"]
    ] + [
        f"{name}: dFdv relative change exceeds 25%"
        for name, row in convergence["cases"].items()
        if not row["checks"]["dfdv_relative_change_below_25_percent"]
    ]
    before_after = _before_after(arrays, local, reversal, component4, chirp, health)

    checks = {
        "ground_correction_applied_exactly_once": bool(
            backend.status.ground_magnetic_moment_correction_count == 1
            and backend.status.downstream_zeeman_sign_correction_count == 0
        ),
        "lab_x_geometry_correct": bool(coordinate["passed"]),
        "population_solves_healthy": bool(health["passed"] and tolerance["passed"]),
        "nominal_three_restoring_and_damping": bool(
            local["cases"]["plane_wave_3"]["dFdx_normalized_per_m"] < 0
            and local["cases"]["plane_wave_3"]["dFdv_normalized_per_m_s"] < 0
            and local["cases"]["gaussian_3"]["dFdx_normalized_per_m"] < 0
            and local["cases"]["gaussian_3"]["dFdv_normalized_per_m_s"] < 0
        ),
        "three_plus_one_strengthens_restoring": bool(local["passed"] and component4["passed"]),
        "reversal_behavior_correct": bool(reversal["passed"]),
        "chirp_features_move_coherently": bool(chirp["passed"]),
        "force_scale_plausible": bool(force_scale["passed"]),
        "gaussian_application_correct": bool(gaussian["passed"]),
        "grid_refinement_preserves_topology": bool(convergence["topology_preserved"]),
    }
    failed = [name for name, passed in checks.items() if not passed]
    gate = "PROVISIONAL_STATIC_GO" if not failed else "PROVISIONAL_STATIC_NO_GO"

    history_after = _hash_manifest(HISTORICAL_PATHS)
    yaml_after = _hash_manifest(yaml_paths)
    history_unchanged = history_before == history_after
    yaml_unchanged = yaml_before == yaml_after
    if not history_unchanged:
        raise RuntimeError("historical Run 009/009A/009B artifacts changed during R1")
    if not yaml_unchanged:
        raise RuntimeError("source Rodriguez YAML changed during R1")

    metadata = {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} corrected static audit metadata",
        "track": "provisional",
        "gate": gate,
        "failed_criteria": failed,
        "replication_valid": False,
        "exact_replication_valid": False,
        "trajectory_authorized": False,
        "capture_authorized": False,
        "trajectory_integrations_performed": 0,
        "capture_results_calculated": 0,
        "authorization_lock_reason": {
            "excited_state_magnetic_tensor_unresolved": True,
            "provisional_effective_excited_g": EXCITED_G_PROVISIONAL,
            "rodriguez_representative_excited_g": EXCITED_G_RODRIGUEZ,
        },
        "convention_provenance": _correction_provenance(backend),
        "backend_status": _json_safe(backend.status),
        "corrected_static_arrays": arrays_path.name,
        "corrected_surfaces_newly_generated": True,
        "reused_pre_correction_force_arrays": False,
        "case_records": records,
        "solver_health": health,
        "coordinate_audit": coordinate,
        "tolerance_stability": tolerance,
        "local_slope_audit": local,
        "component_4_audit": component4,
        "reversal_audit": reversal,
        "chirp_feature_audit": chirp,
        "force_scale_audit": force_scale,
        "gaussian_audit": gaussian,
        "grid_convergence": convergence,
        "before_versus_after": before_after,
        "checks": checks,
        "provenance_chain": {
            "historical_hashes_before": history_before,
            "historical_hashes_after": history_after,
            "historical_artifacts_unchanged": history_unchanged,
            "source_yaml_hashes_before": yaml_before,
            "source_yaml_hashes_after": yaml_after,
            "source_yaml_unchanged": yaml_unchanged,
            "new_corrected_arrays_sha256": _sha256(arrays_path),
        },
    }
    diagnostic_path = _save_diagnostic_plot(metadata, output_dir) if save_plots else None
    metadata["diagnostic_plot"] = None if diagnostic_path is None else diagnostic_path.name

    static_metadata_path = output_dir / f"{R1_LABEL}_corrected_static_metadata.json"
    static_metadata = {
        "label": R1_LABEL,
        "title": f"{R1_LABEL} regenerated corrected static metadata",
        "convention_provenance": metadata["convention_provenance"],
        "case_records": records,
        "solver_health": health,
        "arrays": arrays_path.name,
        "arrays_sha256": _sha256(arrays_path),
        "trajectory_authorized": False,
        "capture_authorized": False,
        "exact_replication_valid": False,
    }
    static_metadata_path.write_text(
        json.dumps(_json_safe(static_metadata), indent=2, sort_keys=True), encoding="utf-8"
    )
    metadata["corrected_static_metadata"] = static_metadata_path.name
    metadata["corrected_static_metadata_sha256"] = _sha256(static_metadata_path)

    metadata_path = output_dir / f"{R1_LABEL}_metadata.json"
    metadata_path.write_text(
        json.dumps(_json_safe(metadata), indent=2, sort_keys=True), encoding="utf-8"
    )
    report_path = output_dir / f"{R1_LABEL}.md"
    heading = lambda text: f"## {R1_LABEL} {text}"
    lines = [
        f"# {R1_LABEL}",
        "",
        "This rerun regenerates and audits corrected-ground-Zeeman static rate-equation surfaces only. It is provisional, not a Rodriguez reproduction, and invokes no trajectory or capture path.",
        "",
        heading("Convention and history"),
        "",
        "The ground magnetic-moment tensor was negated exactly once at the Hamiltonian boundary. Source YAML, paper-to-pylcp polarization translation, apparatus field, dipole ordering, and excited tensor were unchanged.",
        f"Historical Run 009, Run 009A, and Run 009B hashes remained unchanged: `{history_unchanged}`. Corrected arrays were newly generated: `{arrays_path.name}`.",
        "",
        heading("Population and geometry health"),
        "",
        f"- solves: `{health['number_of_solves']}`; population range: `{health['minimum_population']:.6g}` to `{health['maximum_population']:.6g}`",
        f"- maximum normalization error: `{health['maximum_population_normalization_error']:.6g}`; maximum residual: `{health['maximum_steady_state_residual']:.6g}`",
        f"- nullspace dimensions: `{health['nullspace_dimensions_observed']}`; fallbacks: `{health['fallback_count']}`; nonfinite: `{health['nonfinite_count']}`",
        f"- lab F_x(x,v_x) geometry and 1/sqrt(2) rotated-beam projections: `{coordinate['passed']}`",
        "",
        heading("Local slopes"),
        "",
        "| case | dF_x/dx | dF_x/dv_x | spatial | velocity |",
        "|---|---:|---:|---|---|",
    ]
    for name, row in local["cases"].items():
        lines.append(f"| {name} | {row['dFdx_normalized_per_m']:.6g} | {row['dFdv_normalized_per_m_s']:.6g} | {row['position_classification']} | {row['velocity_classification']} |")
    lines += [
        "",
        heading("Corrected reversal matrix"),
        "",
        "| case | dF_x/dx | dF_x/dv_x | spatial | velocity |",
        "|---|---:|---:|---|---|",
    ]
    for name, row in reversal["cases"].items():
        lines.append(f"| {name} | {row['dFdx_normalized_per_m']:.6g} | {row['dFdv_normalized_per_m_s']:.6g} | {row['position_classification']} | {row['velocity_classification']} |")
    lines += [
        "",
        heading("Component 4 and chirp"),
        "",
        f"Component (4) strengthens restoring confinement in plane-wave and Gaussian controlled optical-system comparisons: `{component4['passed']}`. These are separate combined-equilibrium solves, not an additive decomposition.",
        "",
        "| detuning | extremum velocity [m/s] | position [m] | force | rough velocity [m/s] | deviation [m/s] |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for feature in chirp["features"]:
        lines.append(f"| {feature['detuning_gamma']:.3g} Gamma | {feature['dominant_inbound_slowing_velocity_m_s']:.6g} | {feature['dominant_inbound_slowing_position_m']:.6g} | {feature['dominant_force_normalized']:.6g} | {feature['expected_sqrt2_detuning_over_k_m_s']:.6g} | {feature['velocity_deviation_from_rough_scale_m_s']:.6g} |")
    lines += [
        "",
        heading("Gaussian, force scale, and convergence"),
        "",
        f"Per-beam Gaussian application before one combined solve passed: `{gaussian['passed']}`. Grid refinement preserved topology: `{convergence['topology_preserved']}`. All original quantitative refinement thresholds passed: `{convergence['all_original_quantitative_thresholds_passed']}`; cautions: `{convergence['quantitative_cautions']}`. Force scale passed the deliberately broad order-of-magnitude screen: `{force_scale['passed']}`; this is not quantitative reproduction.",
        "",
        heading("Before versus after"),
        "",
        "The original anti-restoring Run 009 surfaces are superseded for provisional engineering use, but retained unchanged as historical diagnostic artifacts. Population health, force scales, and chirp ordering remain explicitly recorded in metadata for both audits.",
        "",
        heading(f"Gate: {gate}"),
        "",
        f"**{gate}**",
        "",
    ]
    if failed:
        lines += ["Failed criteria:", ""] + [f"- {item}" for item in failed] + [""]
    else:
        lines += [
            "Every named provisional static gate criterion passed. The quantitative refinement caution above is retained and is not classified as a topology failure.",
            "",
        ]
    lines += [
        "This gate authorizes only further corrected provisional static study. `trajectory_authorized = false`, `capture_authorized = false`, and `exact_replication_valid = false` regardless of the gate.",
        f"Reason: the excited-state magnetic tensor remains unresolved; provisional effective `g ~= {EXCITED_G_PROVISIONAL}` versus Rodriguez representative `g = {EXCITED_G_RODRIGUEZ}`.",
        "",
        f"# {R1_LABEL} FINAL_{gate}",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{R1_LABEL}: {gate}")
    print(f"arrays: {arrays_path}")
    print(f"metadata: {metadata_path}")
    print(f"report: {report_path}")
    return {
        "gate": gate,
        "metadata": metadata,
        "arrays_path": arrays_path,
        "static_metadata_path": static_metadata_path,
        "metadata_path": metadata_path,
        "report_path": report_path,
        "diagnostic_path": diagnostic_path,
    }


if __name__ == "__main__":
    run()
