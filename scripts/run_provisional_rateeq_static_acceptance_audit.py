"""Run 009A: static-only acceptance audit of saved Run 009 force results."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.force_units import normalized_force_to_acceleration_m_s2
from mgf_mot.conventions import GroundZeemanConvention
from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.geometry import MOT_BEAM_DIRECTIONS
from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.policies import PolicySample, load_policy
from mgf_mot.rateeq_backend import (
    RATEEQ_STATIC_LABEL,
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
)
from mgf_mot.static_acceptance import (
    RUN009A_LABEL,
    centered_slope,
    decide_acceptance_gate,
    flip_policy_polarizations,
    relative_change,
    topology_label,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
DEFAULT_RUN009_ARRAYS = DEFAULT_OUTPUT_DIR / f"{RATEEQ_STATIC_LABEL}_run_009_arrays.npz"
DEFAULT_RUN009_METADATA = DEFAULT_OUTPUT_DIR / f"{RATEEQ_STATIC_LABEL}_run_009_metadata.json"


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


def _backend(*, gradient_t_m: float = 0.2, svd_eps: float = 1.0e-10):
    return ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            magnetic_gradient_t_m=gradient_t_m,
            svd_eps=svd_eps,
            ground_zeeman_convention=GroundZeemanConvention.RAW_XFMOLECULES,
        )
    )


def _resources(backend: ProvisionalPylcpRateEquationBackend) -> dict[str, Any]:
    static3 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3.yaml")
    static31 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    chirp = load_policy(REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml")
    gaussian_config = load_gaussian_envelope_config(
        REPO_ROOT / "configs" / "rodriguez_gaussian_baseline.yaml"
    )
    gaussian3 = build_rodriguez_gaussian_beam_set(
        gaussian_config, (1.45, 1.45, 2.89, 0.0)
    )
    gaussian31 = build_rodriguez_gaussian_beam_set(
        gaussian_config, (1.45, 1.45, 2.17, 0.72)
    )

    def system(sample: PolicySample, name: str, mode: str, beams=None):
        return backend.build_optical_system(
            sample,
            policy_name=name,
            beam_mode=mode,
            gaussian_beam_set=beams,
        )

    systems = {
        "plane_wave_3": system(static3.sample(0.0), static3.name, "plane_wave"),
        "plane_wave_3_plus_1": system(
            static31.sample(0.0), static31.name, "plane_wave"
        ),
        "gaussian_3": system(
            static3.sample(0.0), static3.name, "elliptical_gaussian", gaussian3
        ),
        "gaussian_3_plus_1": system(
            static31.sample(0.0), static31.name, "elliptical_gaussian", gaussian31
        ),
        "gaussian_chirp_minus_8_gamma": system(
            chirp.sample(0.0), chirp.name, "elliptical_gaussian", gaussian3
        ),
        "gaussian_chirp_minus_4p5_gamma": system(
            chirp.sample(0.0005), chirp.name, "elliptical_gaussian", gaussian3
        ),
        "gaussian_chirp_minus_1_gamma": system(
            chirp.sample(0.001), chirp.name, "elliptical_gaussian", gaussian3
        ),
    }
    return {
        "static3": static3,
        "static31": static31,
        "chirp": chirp,
        "gaussian3": gaussian3,
        "gaussian31": gaussian31,
        "systems": systems,
    }


def _fx(
    backend,
    system,
    x_m: float,
    vx_m_s: float,
    *,
    diagnostics: bool = False,
    svd_eps: float | None = None,
):
    return backend.force_at(
        np.array([x_m, 0.0, 0.0]),
        np.array([vx_m_s, 0.0, 0.0]),
        system,
        collect_solver_diagnostics=diagnostics,
        svd_eps=svd_eps,
    )


def _coordinate_audit(saved_arrays: Any) -> dict[str, Any]:
    directions = {
        name: {
            "vector_lab": list(vector),
            "lab_x_projection": float(vector[0]),
            "lab_y_projection": float(vector[1]),
            "lab_z_projection": float(vector[2]),
        }
        for name, vector in MOT_BEAM_DIRECTIONS.items()
    }
    inv_sqrt_two = 1.0 / np.sqrt(2.0)
    rotated = all(
        np.isclose(abs(MOT_BEAM_DIRECTIONS[name][0]), inv_sqrt_two, atol=1e-12)
        for name in ("+x_prime", "-x_prime", "+y_prime", "-y_prime")
    )
    z_has_no_x_projection = all(
        np.isclose(MOT_BEAM_DIRECTIONS[name][0], 0.0, atol=1e-12)
        for name in ("+z", "-z")
    )
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} lab-x coordinate audit",
        "reported_force_component": "F_x",
        "position_vector_m": "[x, 0, 0]",
        "velocity_vector_m_s": "[v_x, 0, 0]",
        "saved_axes": sorted(key for key in saved_arrays.files if key in {"positions_m", "velocities_m_s"}),
        "beam_directions": directions,
        "rotated_beam_abs_lab_x_projection": float(inv_sqrt_two),
        "forty_five_degree_doppler_projection_verified": bool(rotated),
        "z_beams_have_zero_lab_x_doppler_projection": bool(z_has_no_x_projection),
        "not_z_map": True,
        "passed": bool(rotated and z_has_no_x_projection),
    }


def _solver_health(backend, systems, positions, velocities, *, stride: int) -> dict[str, Any]:
    if stride < 1:
        raise ValueError("solver audit stride must be positive")
    total = 0
    finite = True
    minimum_population = np.inf
    maximum_sum_error = 0.0
    maximum_residual_linf = 0.0
    nullities: set[int] = set()
    fallback_count = 0
    by_case: dict[str, Any] = {}
    for name, system in systems.items():
        case_count = 0
        case_max_residual = 0.0
        case_min_population = np.inf
        for x_m in positions[::stride]:
            for vx_m_s in velocities[::stride]:
                result = _fx(backend, system, float(x_m), float(vx_m_s), diagnostics=True)
                total += 1
                case_count += 1
                finite = finite and bool(
                    np.isfinite(result.equilibrium_populations).all()
                    and np.isfinite(result.normalized_force).all()
                    and np.isfinite(result.singular_values).all()
                )
                minimum_population = min(minimum_population, result.population_minimum)
                case_min_population = min(case_min_population, result.population_minimum)
                maximum_sum_error = max(maximum_sum_error, abs(result.population_sum - 1.0))
                maximum_residual_linf = max(
                    maximum_residual_linf, result.steady_state_residual_linf
                )
                case_max_residual = max(case_max_residual, result.steady_state_residual_linf)
                nullities.add(result.nullspace_dimension)
                fallback_count += int(result.singular_solver_fallback_used)
        by_case[name] = {
            "label": RUN009A_LABEL,
            "title": f"{RUN009A_LABEL} {name} equilibrium health",
            "points_audited": case_count,
            "minimum_population": float(case_min_population),
            "maximum_residual_linf": float(case_max_residual),
        }
    thresholds = {
        "population_nonnegative_tolerance": -1.0e-10,
        "population_sum_tolerance": 1.0e-9,
        "steady_state_residual_linf_tolerance": 1.0e-9,
    }
    passed = bool(
        finite
        and minimum_population >= thresholds["population_nonnegative_tolerance"]
        and maximum_sum_error <= thresholds["population_sum_tolerance"]
        and maximum_residual_linf <= thresholds["steady_state_residual_linf_tolerance"]
        and nullities == {1}
        and fallback_count == 0
    )
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} equilibrium-solver health",
        "grid_stride": stride,
        "points_audited": total,
        "all_requested_saved_grid_points_audited": stride == 1,
        "populations_and_forces_finite": finite,
        "minimum_population": float(minimum_population),
        "maximum_population_sum_error": float(maximum_sum_error),
        "maximum_steady_state_residual_linf": float(maximum_residual_linf),
        "nullspace_dimensions_observed": sorted(nullities),
        "solver_method": "pylcp SVD nullspace",
        "singular_solver_fallback_count": fallback_count,
        "pylcp_has_singular_solver_fallback_path": False,
        "thresholds": thresholds,
        "by_case": by_case,
        "passed": passed,
    }


def _tolerance_stability(backend, resources, positions, velocities) -> dict[str, Any]:
    eps_values = (1.0e-9, 1.0e-10, 1.0e-11)
    points = (
        (float(positions[0]), float(velocities[0])),
        (0.0, 0.0),
        (float(positions[-1]), float(velocities[-1])),
    )
    max_force_difference = 0.0
    max_population_difference = 0.0
    comparisons = 0
    for name, system in resources["systems"].items():
        for point in points:
            reference = _fx(backend, system, *point, svd_eps=1.0e-10)
            for eps in (1.0e-9, 1.0e-11):
                other = _fx(backend, system, *point, svd_eps=eps)
                max_force_difference = max(
                    max_force_difference,
                    float(np.max(np.abs(other.normalized_force - reference.normalized_force))),
                )
                max_population_difference = max(
                    max_population_difference,
                    float(
                        np.max(
                            np.abs(
                                other.equilibrium_populations
                                - reference.equilibrium_populations
                            )
                        )
                    ),
                )
                comparisons += 1
    passed = max_force_difference <= 1.0e-9 and max_population_difference <= 1.0e-9
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} SVD-tolerance stability",
        "svd_eps_values": list(eps_values),
        "points_per_case": [list(point) for point in points],
        "comparisons": comparisons,
        "maximum_absolute_force_difference": max_force_difference,
        "maximum_absolute_population_difference": max_population_difference,
        "acceptance_tolerance": 1.0e-9,
        "passed": passed,
    }


def _local_slopes(backend, system, *, dx_m: float = 2.5e-4, dv_m_s: float = 0.25):
    dfdx = (
        _fx(backend, system, dx_m, 0.0).normalized_force[0]
        - _fx(backend, system, -dx_m, 0.0).normalized_force[0]
    ) / (2.0 * dx_m)
    dfdv = (
        _fx(backend, system, 0.0, dv_m_s).normalized_force[0]
        - _fx(backend, system, 0.0, -dv_m_s).normalized_force[0]
    ) / (2.0 * dv_m_s)
    return float(dfdx), float(dfdv)


def _reversal_audit(nominal_backend, nominal_resources) -> dict[str, Any]:
    sample = nominal_resources["static31"].sample(0.0)
    flipped_sample = flip_policy_polarizations(sample)
    negative_backend = _backend(gradient_t_m=-0.2)
    cases = {
        "nominal": (
            nominal_backend,
            nominal_backend.build_optical_system(
                sample, policy_name="run009a_nominal", beam_mode="plane_wave"
            ),
        ),
        "polarization_flipped": (
            nominal_backend,
            nominal_backend.build_optical_system(
                flipped_sample,
                policy_name="run009a_polarization_flipped",
                beam_mode="plane_wave",
            ),
        ),
        "gradient_flipped": (
            negative_backend,
            negative_backend.build_optical_system(
                sample, policy_name="run009a_gradient_flipped", beam_mode="plane_wave"
            ),
        ),
        "both_flipped": (
            negative_backend,
            negative_backend.build_optical_system(
                flipped_sample,
                policy_name="run009a_both_flipped",
                beam_mode="plane_wave",
            ),
        ),
    }
    rows: dict[str, Any] = {}
    for name, (backend, system) in cases.items():
        dfdx, dfdv = _local_slopes(backend, system)
        rows[name] = {
            "label": RUN009A_LABEL,
            "title": f"{RUN009A_LABEL} {name} reversal case",
            "dFdx_normalized_per_m": dfdx,
            "dFdv_normalized_per_m_s": dfdv,
            "position_behavior": topology_label(
                dfdx, negative="restoring", positive="anti-restoring"
            ),
            "velocity_behavior": topology_label(
                dfdv, negative="damping", positive="anti-damping"
            ),
        }
    nominal = rows["nominal"]["dFdx_normalized_per_m"]
    passed = bool(
        nominal < 0
        and rows["nominal"]["dFdv_normalized_per_m_s"] < 0
        and rows["polarization_flipped"]["dFdx_normalized_per_m"] > 0
        and rows["gradient_flipped"]["dFdx_normalized_per_m"] > 0
        and rows["both_flipped"]["dFdx_normalized_per_m"] < 0
    )
    sign_relationships = {
        "polarization_flip_reverses_nominal": bool(
            nominal * rows["polarization_flipped"]["dFdx_normalized_per_m"] < 0
        ),
        "gradient_flip_reverses_nominal": bool(
            nominal * rows["gradient_flipped"]["dFdx_normalized_per_m"] < 0
        ),
        "both_flips_restore_nominal_sign": bool(
            nominal * rows["both_flipped"]["dFdx_normalized_per_m"] > 0
        ),
    }
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} real rate-equation reversal matrix",
        "cases": rows,
        "sign_relationships": sign_relationships,
        "expected": {
            "nominal": "restoring and damping",
            "polarization_flipped": "anti-restoring",
            "gradient_flipped": "anti-restoring",
            "both_flipped": "restoring",
        },
        "passed": passed,
    }


def _three_vs_three_plus_one(saved_arrays, resources) -> dict[str, Any]:
    positions = saved_arrays["positions_m"]
    velocities = saved_arrays["velocities_m_s"]
    f3 = saved_arrays["force_plane_wave_3"]
    f31 = saved_arrays["force_plane_wave_3_plus_1"]
    i0 = int(np.argmin(abs(positions)))
    j0 = int(np.argmin(abs(velocities)))
    dx3 = centered_slope(positions, f3[:, j0])
    dx31 = centered_slope(positions, f31[:, j0])
    dv3 = centered_slope(velocities, f3[i0, :])
    dv31 = centered_slope(velocities, f31[i0, :])
    positive = velocities > 0
    damping_fraction3 = float(np.mean(f3[i0, positive] < 0))
    damping_fraction31 = float(np.mean(f31[i0, positive] < 0))
    stronger = bool(dx3 < 0 and dx31 < dx3)

    def extrema(grid: np.ndarray) -> dict[str, Any]:
        maximum_index = np.unravel_index(int(np.argmax(grid)), grid.shape)
        minimum_index = np.unravel_index(int(np.argmin(grid)), grid.shape)
        return {
            "maximum_normalized_force": float(grid[maximum_index]),
            "maximum_location": {
                "x_m": float(positions[maximum_index[0]]),
                "vx_m_s": float(velocities[maximum_index[1]]),
            },
            "minimum_normalized_force": float(grid[minimum_index]),
            "minimum_location": {
                "x_m": float(positions[minimum_index[0]]),
                "vx_m_s": float(velocities[minimum_index[1]]),
            },
        }
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} [3] versus [3+1] audit",
        "three": {
            "label": RUN009A_LABEL,
            "dFdx_normalized_per_m": dx3,
            "dFdv_normalized_per_m_s": dv3,
            "maximum_absolute_force": float(np.max(np.abs(f3))),
            "positive_velocity_damping_fraction": damping_fraction3,
            "extrema": extrema(f3),
        },
        "three_plus_one": {
            "label": RUN009A_LABEL,
            "dFdx_normalized_per_m": dx31,
            "dFdv_normalized_per_m_s": dv31,
            "maximum_absolute_force": float(np.max(np.abs(f31))),
            "positive_velocity_damping_fraction": damping_fraction31,
            "extrema": extrema(f31),
        },
        "component_4_materially_changes_surface": bool(not np.allclose(f3, f31)),
        "three_plus_one_strengthens_restoring_confinement": stronger,
        "three_plus_one_reduces_wide_interval_damping": bool(
            damping_fraction31 < damping_fraction3
        ),
        "passed": bool(not np.allclose(f3, f31) and stronger),
    }


def _chirp_feature_audit(backend, resources, velocity_axis) -> dict[str, Any]:
    sample_times = (0.0, 0.0005, 0.001)
    names = ("minus_8_gamma", "minus_4p5_gamma", "minus_1_gamma")
    records: list[dict[str, Any]] = []
    velocity_unit = backend.force_units.linewidth_rad_s / backend.force_units.wave_number_rad_m
    for name, time_s in zip(names, sample_times):
        sample = resources["chirp"].sample(time_s)
        system = backend.build_optical_system(
            sample,
            policy_name=resources["chirp"].name,
            beam_mode="elliptical_gaussian",
            gaussian_beam_set=resources["gaussian3"],
        )
        forces = np.array(
            [_fx(backend, system, 0.0, float(v)).normalized_force[0] for v in velocity_axis]
        )
        minimum_index = int(np.argmin(forces))
        detuning = abs(sample.components[0].detuning_gamma)
        expected = float(np.sqrt(2.0) * detuning * velocity_unit)
        found = float(velocity_axis[minimum_index])
        records.append(
            {
                "label": RUN009A_LABEL,
                "title": f"{RUN009A_LABEL} chirp feature {name}",
                "name": name,
                "detuning_gamma": float(sample.components[0].detuning_gamma),
                "expected_sqrt2_detuning_over_k_m_s": expected,
                "dominant_inbound_slowing_velocity_m_s": found,
                "dominant_force_normalized": float(forces[minimum_index]),
                "feature_to_rough_expectation_ratio": found / expected,
                "extremum_on_scan_boundary": minimum_index in (0, len(velocity_axis) - 1),
                "force_slice": forces,
            }
        )
    expected = np.array([item["expected_sqrt2_detuning_over_k_m_s"] for item in records])
    found = np.array([item["dominant_inbound_slowing_velocity_m_s"] for item in records])
    monotonic = bool(np.all(np.diff(found) < 0))
    correlation = float(np.corrcoef(expected, found)[0, 1]) if np.ptp(found) > 0 else 0.0
    all_slowing = all(item["dominant_force_normalized"] < 0 for item in records)
    no_boundary = not any(item["extremum_on_scan_boundary"] for item in records)
    passed = bool(monotonic and correlation >= 0.9 and all_slowing and no_boundary)
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} moving-boat chirp-feature audit",
        "velocity_scan_m_s": velocity_axis,
        "features": records,
        "feature_velocity_decreases_with_less_negative_detuning": monotonic,
        "expected_found_velocity_correlation": correlation,
        "all_features_are_inbound_slowing_extrema": all_slowing,
        "no_feature_is_scan_boundary_limited": no_boundary,
        "passed": passed,
    }


def _gaussian_audit(backend, resources) -> dict[str, Any]:
    plane = resources["systems"]["plane_wave_3"]
    gaussian = resources["systems"]["gaussian_3"]
    points = ((0.0, 5.0), (0.005, 0.0), (0.010, -5.0), (0.010, 0.0), (0.010, 5.0), (0.020, 10.0))
    records = []
    attenuated = 0
    non_scalar = False
    ratios_at_x10 = []
    for x_m, velocity in points:
        plane_result = _fx(backend, plane, x_m, velocity)
        gaussian_result = _fx(backend, gaussian, x_m, velocity)
        fp = float(plane_result.normalized_force[0])
        fg = float(gaussian_result.normalized_force[0])
        envelopes = resources["gaussian3"].envelopes(np.array([x_m, 0.0, 0.0]))
        mean_envelope = float(np.mean(tuple(envelopes.values())))
        if abs(fg) <= abs(fp) + 1.0e-12:
            attenuated += 1
        if abs(fg - fp * mean_envelope) > 1.0e-7:
            non_scalar = True
        if np.isclose(x_m, 0.010) and abs(fp) > 1.0e-12:
            ratios_at_x10.append(fg / fp)
        records.append(
            {
                "label": RUN009A_LABEL,
                "title": f"{RUN009A_LABEL} Gaussian point x={x_m} vx={velocity}",
                "x_m": x_m,
                "vx_m_s": velocity,
                "plane_force_normalized": fp,
                "gaussian_force_normalized": fg,
                "gaussian_to_plane_ratio": None if abs(fp) <= 1e-12 else fg / fp,
                "mean_envelope": mean_envelope,
                "mean_after_sum_prediction": fp * mean_envelope,
                "per_beam_envelopes": envelopes,
            }
        )
    center = records[0]
    center_agreement = bool(
        np.isclose(
            center["plane_force_normalized"],
            center["gaussian_force_normalized"],
            atol=1.0e-12,
            rtol=1.0e-10,
        )
    )
    envelope_probe = resources["gaussian3"].envelopes(np.array([0.010, 0.0, 0.0]))
    pair_symmetric = all(
        np.isclose(envelope_probe[f"+{pair}"], envelope_probe[f"-{pair}"], atol=1e-12)
        for pair in ("x_prime", "y_prime", "z")
    )
    rotated_groups_distinct = len({round(value, 12) for value in envelope_probe.values()}) > 1
    velocity_dependent_ratio = len(ratios_at_x10) >= 2 and np.ptp(ratios_at_x10) > 1.0e-4
    passed = bool(
        center_agreement
        and attenuated >= len(points) - 1
        and non_scalar
        and pair_symmetric
        and rotated_groups_distinct
        and velocity_dependent_ratio
    )
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} plane-wave versus per-beam Gaussian audit",
        "manual_points": records,
        "center_agreement_at_nonzero_velocity": center_agreement,
        "off_center_points_attenuated_count": attenuated,
        "manual_point_count": len(points),
        "not_mean_envelope_after_sum": non_scalar,
        "gaussian_to_plane_ratio_varies_with_velocity_at_fixed_position": velocity_dependent_ratio,
        "counterpropagating_pair_envelopes_match": pair_symmetric,
        "rotated_and_z_beam_envelope_groups_are_distinct": rotated_groups_distinct,
        "passed": passed,
    }


def _force_scale(saved_arrays, backend) -> dict[str, Any]:
    records = {}
    plausible = True
    for name in ("plane_wave_3", "plane_wave_3_plus_1", "gaussian_3", "gaussian_3_plus_1"):
        maximum = float(np.max(np.abs(saved_arrays[f"force_{name}"])))
        acceleration = float(normalized_force_to_acceleration_m_s2(maximum, backend.force_units))
        if maximum < 0.003:
            classification = "more_than_ten_times_smaller_than_0p03"
        elif maximum > 0.3:
            classification = "more_than_ten_times_larger_than_0p03"
        else:
            classification = "same_order_as_0p03"
        plausible = plausible and classification == "same_order_as_0p03"
        records[name] = {
            "label": RUN009A_LABEL,
            "maximum_absolute_force_hbar_k_gamma": maximum,
            "acceleration_m_s2": acceleration,
            "classification": classification,
        }
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} force-scale audit",
        "paper_note_reference_hbar_k_gamma": [0.03, 0.015],
        "cases": records,
        "conversion": "a = F_normalized * hbar*k*Gamma / m",
        "trajectory_integration_performed": False,
        "passed": bool(plausible),
    }


def _grid_convergence(backend, resources, saved_arrays, *, refinement_factor: int) -> dict[str, Any]:
    if refinement_factor < 2:
        raise ValueError("refinement_factor must be at least two")
    positions = np.asarray(saved_arrays["positions_m"])
    velocities = np.asarray(saved_arrays["velocities_m_s"])
    refined_positions = np.linspace(positions[0], positions[-1], (positions.size - 1) * refinement_factor + 1)
    refined_velocities = np.linspace(velocities[0], velocities[-1], (velocities.size - 1) * refinement_factor + 1)
    i0 = int(np.argmin(abs(positions)))
    j0 = int(np.argmin(abs(velocities)))
    records = {}
    all_passed = True
    for name in ("plane_wave_3", "plane_wave_3_plus_1"):
        system = resources["systems"][name]
        coarse_grid = saved_arrays[f"force_{name}"]
        coarse_x = coarse_grid[:, j0]
        coarse_v = coarse_grid[i0, :]
        fine_x = np.array([_fx(backend, system, float(x), 0.0).normalized_force[0] for x in refined_positions])
        fine_v = np.array([_fx(backend, system, 0.0, float(v)).normalized_force[0] for v in refined_velocities])
        coarse_dfdx = centered_slope(positions, coarse_x)
        fine_dfdx = centered_slope(refined_positions, fine_x)
        coarse_dfdv = centered_slope(velocities, coarse_v)
        fine_dfdv = centered_slope(refined_velocities, fine_v)
        x_max_coarse = float(positions[int(np.argmax(abs(coarse_x)))])
        x_max_fine = float(refined_positions[int(np.argmax(abs(fine_x)))])
        v_max_coarse = float(velocities[int(np.argmax(abs(coarse_v)))])
        v_max_fine = float(refined_velocities[int(np.argmax(abs(fine_v)))])
        shared_x = fine_x[::refinement_factor]
        shared_v = fine_v[::refinement_factor]
        fixed_point_error = max(
            float(np.max(np.abs(shared_x - coarse_x))),
            float(np.max(np.abs(shared_v - coarse_v))),
        )
        checks = {
            "dfdx_relative_change_below_25_percent": relative_change(coarse_dfdx, fine_dfdx) <= 0.25,
            "dfdv_relative_change_below_25_percent": relative_change(coarse_dfdv, fine_dfdv) <= 0.25,
            "slice_extrema_magnitude_change_below_15_percent": max(
                relative_change(float(np.max(abs(coarse_x))), float(np.max(abs(fine_x)))),
                relative_change(float(np.max(abs(coarse_v))), float(np.max(abs(fine_v)))),
            ) <= 0.15,
            "extrema_locations_shift_no_more_than_one_coarse_step": bool(
                abs(abs(x_max_fine) - abs(x_max_coarse))
                <= abs(positions[1] - positions[0]) + 1e-15
                and abs(abs(v_max_fine) - abs(v_max_coarse))
                <= abs(velocities[1] - velocities[0]) + 1e-15
            ),
            "shared_fixed_points_reproduce_saved_grid": fixed_point_error <= 1.0e-10,
            "local_topology_signs_unchanged": bool(
                coarse_dfdx * fine_dfdx > 0 and coarse_dfdv * fine_dfdv > 0
            ),
        }
        passed = all(checks.values())
        all_passed = all_passed and passed
        records[name] = {
            "label": RUN009A_LABEL,
            "title": f"{RUN009A_LABEL} {name} slice convergence",
            "coarse_shape": [positions.size, velocities.size],
            "refined_position_count": refined_positions.size,
            "refined_velocity_count": refined_velocities.size,
            "coarse_dFdx": coarse_dfdx,
            "refined_dFdx": fine_dfdx,
            "coarse_dFdv": coarse_dfdv,
            "refined_dFdv": fine_dfdv,
            "coarse_position_extremum_location_m": x_max_coarse,
            "refined_position_extremum_location_m": x_max_fine,
            "coarse_velocity_extremum_location_m_s": v_max_coarse,
            "refined_velocity_extremum_location_m_s": v_max_fine,
            "maximum_shared_fixed_point_error": fixed_point_error,
            "extrema_location_comparison": (
                "absolute coordinate; odd-symmetric slices have equivalent +/- extrema"
            ),
            "checks": checks,
            "passed": passed,
            "refined_position_axis_m": refined_positions,
            "refined_velocity_axis_m_s": refined_velocities,
            "refined_position_slice": fine_x,
            "refined_velocity_slice": fine_v,
        }
    return {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} grid-convergence audit",
        "scope": "selected lab-x position and velocity slices; no trajectories",
        "refinement_factor": refinement_factor,
        "cases": records,
        "passed": bool(all_passed),
    }


def _save_plot(metadata, output_dir: Path) -> Path:
    import matplotlib.pyplot as plt

    path = output_dir / f"{RUN009A_LABEL}_run_009A_diagnostics.png"
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    reversal = metadata["reversal_audit"]["cases"]
    axes[0].bar(list(reversal), [row["dFdx_normalized_per_m"] for row in reversal.values()])
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].set(ylabel="dF_x/dx", title="restoring reversal matrix")
    chirp = metadata["chirp_feature_audit"]
    velocity = np.asarray(chirp["velocity_scan_m_s"])
    for feature in chirp["features"]:
        axes[1].plot(velocity, feature["force_slice"], label=feature["name"])
    axes[1].set(xlabel="v_x [m/s]", ylabel="F_x/(hbar k Gamma)", title="inbound chirp slices")
    axes[1].legend(fontsize=8)
    convergence = metadata["grid_convergence"]["cases"]
    for name, record in convergence.items():
        axes[2].plot(
            np.asarray(record["refined_position_axis_m"]) * 1e3,
            record["refined_position_slice"],
            label=name,
        )
    axes[2].set(xlabel="x [mm]", ylabel="F_x/(hbar k Gamma)", title="refined v_x=0 slices")
    axes[2].legend(fontsize=8)
    fig.suptitle(f"{RUN009A_LABEL} Run 009A")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    run009_arrays_path: Path = DEFAULT_RUN009_ARRAYS,
    run009_metadata_path: Path = DEFAULT_RUN009_METADATA,
    solver_stride: int = 1,
    refinement_factor: int = 2,
    chirp_velocity_axis_m_s: np.ndarray | None = None,
    save_plot: bool = True,
) -> dict[str, Any]:
    """Audit static force results only and emit an explicit GO/NO-GO gate."""

    output_dir.mkdir(parents=True, exist_ok=True)
    if not run009_arrays_path.exists() or not run009_metadata_path.exists():
        raise FileNotFoundError("saved labeled Run 009 arrays and metadata are required")
    saved_arrays = np.load(run009_arrays_path)
    saved_metadata = json.loads(run009_metadata_path.read_text(encoding="utf-8"))
    if saved_metadata.get("label") != RATEEQ_STATIC_LABEL:
        raise ValueError("input metadata is not the quarantined Run 009 result")
    if saved_metadata.get("trajectory_integrations_performed") != 0:
        raise ValueError("Run 009A accepts only static Run 009 inputs")

    positions = np.asarray(saved_arrays["positions_m"], dtype=float)
    velocities = np.asarray(saved_arrays["velocities_m_s"], dtype=float)
    if chirp_velocity_axis_m_s is None:
        chirp_velocity_axis_m_s = np.linspace(0.0, 110.0, 111)
    backend = _backend()
    resources = _resources(backend)

    print(f"{RUN009A_LABEL}: coordinate audit")
    coordinate = _coordinate_audit(saved_arrays)
    print(f"{RUN009A_LABEL}: equilibrium health ({len(resources['systems'])} cases)")
    solver_health = _solver_health(
        backend, resources["systems"], positions, velocities, stride=solver_stride
    )
    tolerance_stability = _tolerance_stability(backend, resources, positions, velocities)
    comparison = _three_vs_three_plus_one(saved_arrays, resources)
    reversal = _reversal_audit(backend, resources)
    chirp = _chirp_feature_audit(
        backend, resources, np.asarray(chirp_velocity_axis_m_s, dtype=float)
    )
    gaussian = _gaussian_audit(backend, resources)
    force_scale = _force_scale(saved_arrays, backend)
    convergence = _grid_convergence(
        backend, resources, saved_arrays, refinement_factor=refinement_factor
    )

    checks = {
        "lab_x_geometry_correct": bool(coordinate["passed"]),
        "population_solves_healthy": bool(
            solver_health["passed"] and tolerance_stability["passed"]
        ),
        "nominal_restoring_and_damping": bool(
            reversal["cases"]["nominal"]["dFdx_normalized_per_m"] < 0
            and reversal["cases"]["nominal"]["dFdv_normalized_per_m_s"] < 0
        ),
        "reversal_matrix_correct": bool(reversal["passed"]),
        "three_plus_one_strengthens_confinement": bool(comparison["passed"]),
        "chirp_features_move_coherently": bool(chirp["passed"]),
        "gaussian_application_healthy": bool(gaussian["passed"]),
        "force_scale_plausible": bool(force_scale["passed"]),
        "grid_refinement_stable": bool(convergence["passed"]),
    }
    diagnosis_by_check = {
        "lab_x_geometry_correct": "coordinate mismatch",
        "population_solves_healthy": "equilibrium-solver instability",
        "nominal_restoring_and_damping": "polarization/component wiring error: nominal local signs are not both restoring and damping",
        "reversal_matrix_correct": "polarization or magnetic-gradient reversal behavior is wrong",
        "three_plus_one_strengthens_confinement": "component (4) behavior wrong: [3+1] does not strengthen restoring confinement",
        "chirp_features_move_coherently": "chirp-feature movement wrong or scan-boundary limited",
        "gaussian_application_healthy": "Gaussian application wrong or inconsistent with per-beam geometry",
        "force_scale_plausible": "force scale implausible",
        "grid_refinement_stable": "grid not converged",
    }
    gate = decide_acceptance_gate(checks, diagnosis_by_check)
    metadata = {
        "label": RUN009A_LABEL,
        "title": f"{RUN009A_LABEL} Run 009A metadata",
        "track": "provisional",
        "replication_valid": False,
        "audit_only": True,
        "new_physics_added": False,
        "trajectory_integrations_performed": 0,
        "capture_results_calculated": 0,
        "input_run009_arrays": run009_arrays_path.name,
        "input_run009_metadata": run009_metadata_path.name,
        "coordinate_audit": coordinate,
        "solver_health": solver_health,
        "tolerance_stability": tolerance_stability,
        "three_vs_three_plus_one": comparison,
        "reversal_audit": reversal,
        "chirp_feature_audit": chirp,
        "gaussian_audit": gaussian,
        "force_scale_audit": force_scale,
        "grid_convergence": convergence,
        "gate": _json_safe(gate),
    }
    plot_path = _save_plot(metadata, output_dir) if save_plot else None
    metadata["diagnostic_plot"] = None if plot_path is None else plot_path.name

    metadata_path = output_dir / f"{RUN009A_LABEL}_run_009A_metadata.json"
    metadata_path.write_text(
        json.dumps(_json_safe(metadata), indent=2, sort_keys=True), encoding="utf-8"
    )
    report_path = output_dir / f"{RUN009A_LABEL}_run_009A.md"
    heading = lambda text: f"## {RUN009A_LABEL} {text}"
    lines = [
        f"# {RUN009A_LABEL} Run 009A",
        "",
        "This is a static acceptance audit of the saved Run 009 provisional pylcp rate-equation results. It adds no physics, runs no trajectory, calculates no capture result, and makes no Rodriguez-replication claim.",
        "Exact Track E remains blocked. Trajectories must remain disconnected unless every gate condition passes.",
        "",
        heading("Coordinate conventions"),
        "",
        "The audited quantity is `F_x(x,v_x)`: position `[x,0,0]`, velocity `[v_x,0,0]`, and returned force component 0. The four rotated beams have lab-x projection magnitude `1/sqrt(2)`; the z beams have zero lab-x Doppler projection. This is not an inherited z map.",
        "",
        heading("Equilibrium solves"),
        "",
        f"- points audited: `{solver_health['points_audited']}`; all saved points: `{solver_health['all_requested_saved_grid_points_audited']}`",
        f"- minimum population: `{solver_health['minimum_population']:.6g}`",
        f"- maximum population-sum error: `{solver_health['maximum_population_sum_error']:.6g}`",
        f"- maximum steady-state residual infinity norm: `{solver_health['maximum_steady_state_residual_linf']:.6g}`",
        f"- nullspace dimensions: `{solver_health['nullspace_dimensions_observed']}`; fallbacks: `{solver_health['singular_solver_fallback_count']}`",
        f"- tolerance stability: `{tolerance_stability['passed']}`, max force difference `{tolerance_stability['maximum_absolute_force_difference']:.6g}`",
        "",
        heading("[3] versus [3+1] and reversal signs"),
        "",
        f"- [3] dF_x/dx: `{comparison['three']['dFdx_normalized_per_m']:.6g}`; dF_x/dv_x: `{comparison['three']['dFdv_normalized_per_m_s']:.6g}`",
        f"- [3+1] dF_x/dx: `{comparison['three_plus_one']['dFdx_normalized_per_m']:.6g}`; dF_x/dv_x: `{comparison['three_plus_one']['dFdv_normalized_per_m_s']:.6g}`",
        f"- component (4) materially changes the surface: `{comparison['component_4_materially_changes_surface']}`",
        f"- [3] extrema: `{comparison['three']['extrema']}`",
        f"- [3+1] extrema: `{comparison['three_plus_one']['extrema']}`",
        "",
        "| case | dF_x/dx | dF_x/dv_x | spatial | velocity |",
        "|---|---:|---:|---|---|",
    ]
    for name, row in reversal["cases"].items():
        lines.append(
            f"| {name} | {row['dFdx_normalized_per_m']:.6g} | {row['dFdv_normalized_per_m_s']:.6g} | {row['position_behavior']} | {row['velocity_behavior']} |"
        )
    lines += [
        "",
        heading("Chirp moving-boat audit"),
        "",
        "| detuning | rough sqrt(2)|Delta|/k [m/s] | found slowing extremum [m/s] | force | boundary limited |",
        "|---:|---:|---:|---:|---|",
    ]
    for feature in chirp["features"]:
        lines.append(
            f"| {feature['detuning_gamma']:.3g} Gamma | {feature['expected_sqrt2_detuning_over_k_m_s']:.6g} | {feature['dominant_inbound_slowing_velocity_m_s']:.6g} | {feature['dominant_force_normalized']:.6g} | {feature['extremum_on_scan_boundary']} |"
        )
    lines += [
        "",
        f"Feature velocity decreases coherently: `{chirp['feature_velocity_decreases_with_less_negative_detuning']}`; expected/found correlation: `{chirp['expected_found_velocity_correlation']:.6g}`.",
        "",
        heading("Gaussian manual points"),
        "",
        f"Center agreement at nonzero velocity: `{gaussian['center_agreement_at_nonzero_velocity']}`. Off-center attenuation count: `{gaussian['off_center_points_attenuated_count']}/{gaussian['manual_point_count']}`. Not a mean-envelope-after-sum result: `{gaussian['not_mean_envelope_after_sum']}`.",
        "Counterpropagating envelope pairs agree exactly while the rotated and z beam groups differ along lab x; these differences are geometric rather than numerical asymmetry.",
        "",
        heading("Force scale and convergence"),
        "",
    ]
    for name, row in force_scale["cases"].items():
        lines.append(
            f"- `{name}`: `{row['maximum_absolute_force_hbar_k_gamma']:.6g} hbar*k*Gamma`, `{row['acceleration_m_s2']:.6g} m/s^2`, `{row['classification']}`"
        )
    lines += [
        "",
        f"Selected [3]/[3+1] lab-x slices refined by `{refinement_factor}x`: convergence passed `{convergence['passed']}`. No acceleration was integrated.",
        "",
        heading(f"Gate: {gate.decision}"),
        "",
        f"**{gate.decision}**",
        "",
    ]
    if gate.diagnoses:
        lines.append("Failed conditions:")
        lines.append("")
        lines.extend(f"- {diagnosis}" for diagnosis in gate.diagnoses)
    else:
        lines.append("Every static acceptance condition passed; this gate alone still does not make the backend exact or replication-valid.")
    lines += [
        "",
        f"Trajectory reconnection authorized by this audit: `{gate.trajectories_authorized}`.",
        "",
        f"# {RUN009A_LABEL} FINAL_GATE_{gate.decision}",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{RUN009A_LABEL}: {gate.decision}")
    for diagnosis in gate.diagnoses:
        print(f"- {diagnosis}")
    print(f"metadata: {metadata_path}")
    print(f"report: {report_path}")
    return {
        "metadata": metadata,
        "gate": gate,
        "metadata_path": metadata_path,
        "report_path": report_path,
        "plot_path": plot_path,
    }


if __name__ == "__main__":
    run()
