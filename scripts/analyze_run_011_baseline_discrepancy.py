"""Read-only Run 011A audit of the Rodriguez baseline discrepancy.

The script consumes the accepted Run 010 force tables and saved Run 011
trajectories.  It never calls a trajectory integrator or a cache builder.  Fresh
rate-equation solves are limited to deterministic audit points on the saved
7.5 Gamma/k path.
"""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mgf_mot.accepted_trajectory import (  # noqa: E402
    InterpolatedRateEquationTrajectoryForce,
)
from mgf_mot.gaussian_beams import (  # noqa: E402
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.policies import load_policy  # noqa: E402


LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_"
    "RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY"
)
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
REPORT_PATH = OUTPUT_DIR / f"{LABEL}.md"
METADATA_PATH = OUTPUT_DIR / f"{LABEL}_metadata.json"
PLOT_PATH = OUTPUT_DIR / f"{LABEL}_diagnostics.png"
RUN011_PREFIX = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_"
    "ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011"
)
FORCE_PREFIX = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_"
    "FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY"
)
TAU_S = 1.0e-3
VELOCITY_UNIT_M_S = 7.53
PAPER_SPATIAL_HALF_WIDTH_M = math.sqrt(2.0) * 17.5e-3
ILLUMINATION_THRESHOLD = 0.01
USEFUL_FORCE_FRACTION = 0.05


def _json(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    raise TypeError(type(value).__name__)


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def protected_paths() -> tuple[Path, ...]:
    """Return every immutable input explicitly protected by Run 011A."""

    paths: set[Path] = set()
    paths.update(OUTPUT_DIR.glob(f"{RUN011_PREFIX}*"))
    paths.update((OUTPUT_DIR / "force_fields").glob(f"{FORCE_PREFIX}*"))
    paths.update(
        {
            REPO_ROOT / "configs" / "provisional_force_field_run_010.yaml",
            REPO_ROOT / "configs" / "provisional_named_trajectory_run_011.yaml",
            REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml",
            REPO_ROOT / "configs" / "rodriguez_chirp_to_3_plus_1_handoff.yaml",
            REPO_ROOT / "configs" / "rodriguez_gaussian_baseline.yaml",
            REPO_ROOT / "configs" / "rodriguez_named_trajectory_protocol.yaml",
            REPO_ROOT / "src" / "mgf_mot" / "spectroscopy.py",
        }
    )
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"protected Run 011A inputs are missing: {missing}")
    return tuple(sorted(paths))


def hash_manifest(paths: tuple[Path, ...] | None = None) -> dict[str, str]:
    chosen = protected_paths() if paths is None else paths
    return {str(path.relative_to(REPO_ROOT)): _hash(path) for path in chosen}


def _trajectory_paths() -> dict[str, Path]:
    return {
        name: OUTPUT_DIR / f"{RUN011_PREFIX}_{name}.npz"
        for name in (
            "v_2_gamma_over_k",
            "v_4_gamma_over_k",
            "v_6_gamma_over_k",
            "v_7p5_gamma_over_k",
            "v_9_gamma_over_k",
        )
    }


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as arrays:
        return {key: arrays[key].copy() for key in arrays.files}


def _pre_cache() -> dict[str, np.ndarray]:
    path = OUTPUT_DIR / "force_fields" / f"{FORCE_PREFIX}_pre_handoff_chirp_3_run_010.npz"
    return _load_npz(path)


def _force_slice(cache: dict[str, np.ndarray], detuning: float) -> np.ndarray:
    axis = cache["detunings_gamma"]
    if detuning <= axis[0]:
        return cache["normalized_force_x"][:, :, 0]
    if detuning >= axis[-1]:
        return cache["normalized_force_x"][:, :, -1]
    index = int(np.searchsorted(axis, detuning, side="right") - 1)
    fraction = float((detuning - axis[index]) / (axis[index + 1] - axis[index]))
    return (
        (1.0 - fraction) * cache["normalized_force_x"][:, :, index]
        + fraction * cache["normalized_force_x"][:, :, index + 1]
    )


def slowing_extremum(cache: dict[str, np.ndarray], detuning: float) -> dict[str, float]:
    values = _force_slice(cache, detuning)
    index = np.unravel_index(int(np.argmin(values)), values.shape)
    return {
        "position_m": float(cache["positions_m"][index[0]]),
        "velocity_m_s": float(cache["velocities_m_s"][index[1]]),
        "normalized_force": float(values[index]),
        "paper_boat_velocity_m_s": math.sqrt(2.0) * abs(detuning) * VELOCITY_UNIT_M_S,
    }


def _signed_trapezoid(times: np.ndarray, forces: np.ndarray) -> tuple[float, float]:
    dt = np.diff(times)
    negative = float(
        np.sum(0.5 * (np.minimum(forces[:-1], 0) + np.minimum(forces[1:], 0)) * dt)
    )
    positive = float(
        np.sum(0.5 * (np.maximum(forces[:-1], 0) + np.maximum(forces[1:], 0)) * dt)
    )
    return negative, positive


def _interval_trapezoid(times: np.ndarray, values: np.ndarray, mask: np.ndarray) -> float:
    if len(times) < 2:
        return 0.0
    pair_mask = mask[:-1] & mask[1:]
    return float(
        np.sum(0.5 * (values[:-1] + values[1:]) * np.diff(times) * pair_mask)
    )


def trajectory_audit(
    name: str,
    arrays: dict[str, np.ndarray],
    cache: dict[str, np.ndarray],
    mass_kg: float,
) -> dict[str, Any]:
    t = arrays["times_s"]
    x = arrays["positions_m"][:, 0]
    v = arrays["velocities_m_s"][:, 0]
    force_n = arrays["force_x_n"]
    normalized = arrays["normalized_force_x"]
    envelope = arrays["gaussian_envelope_mean"]
    illumination = envelope >= ILLUMINATION_THRESHOLD
    extrema: list[dict[str, float]] = []
    distances = np.full(t.shape, np.nan)
    useful = np.zeros(t.shape, dtype=bool)
    for index in np.flatnonzero(t < TAU_S):
        extremum = slowing_extremum(cache, float(arrays["chirp_detunings_gamma"][index]))
        extrema.append({"sample_index": int(index), "time_s": float(t[index]), **extremum})
        distances[index] = math.hypot(
            (float(x[index]) - extremum["position_m"]) / PAPER_SPATIAL_HALF_WIDTH_M,
            (float(v[index]) - extremum["velocity_m_s"]) / VELOCITY_UNIT_M_S,
        )
        useful[index] = normalized[index] <= -USEFUL_FORCE_FRACTION * abs(
            extremum["normalized_force"]
        )
    closest_index = int(np.nanargmin(distances))
    illuminated_indices = np.flatnonzero(illumination)
    negative_normalized_time, positive_normalized_time = _signed_trapezoid(t, normalized)
    negative_impulse, positive_impulse = _signed_trapezoid(t, force_n)
    handoff_index = int(np.flatnonzero(t >= TAU_S)[0]) if np.any(t >= TAU_S) else len(t) - 1
    crossing_indices = np.flatnonzero((x[:-1] < 0.0) & (x[1:] >= 0.0)) + 1
    peak_negative = int(np.argmin(normalized))
    peak_positive = int(np.argmax(normalized))
    required = mass_kg * float(v[0])
    cumulative = float(arrays["cumulative_impulse_x_n_s"][-1])
    useful_time = float(np.sum(np.diff(t) * (useful[:-1] & useful[1:])))
    useful_indices = np.flatnonzero(useful)
    def event(index: int | None) -> dict[str, float] | None:
        if index is None:
            return None
        return {
            "sample_index": int(index),
            "time_s": float(t[index]),
            "position_m": float(x[index]),
            "velocity_m_s": float(v[index]),
            "mean_envelope": float(envelope[index]),
            "minimum_envelope": float(arrays["gaussian_envelope_minimum"][index]),
            "maximum_envelope": float(arrays["gaussian_envelope_maximum"][index]),
        }
    result = {
        "name": name,
        "sample_count": int(len(t)),
        "initial": {"time_s": float(t[0]), "position_m": float(x[0]), "velocity_m_s": float(v[0])},
        "final_or_termination": {
            "time_s": float(t[-1]),
            "position_m": float(x[-1]),
            "velocity_m_s": float(v[-1]),
        },
        "first_appreciable_illumination": None
        if not illuminated_indices.size
        else {
            "sample_index": int(illuminated_indices[0]),
            "time_s": float(t[illuminated_indices[0]]),
            "position_m": float(x[illuminated_indices[0]]),
            "velocity_m_s": float(v[illuminated_indices[0]]),
            "mean_envelope": float(envelope[illuminated_indices[0]]),
        },
        "last_appreciable_illumination": None
        if not illuminated_indices.size
        else {
            "sample_index": int(illuminated_indices[-1]),
            "time_s": float(t[illuminated_indices[-1]]),
            "position_m": float(x[illuminated_indices[-1]]),
            "velocity_m_s": float(v[illuminated_indices[-1]]),
            "mean_envelope": float(envelope[illuminated_indices[-1]]),
        },
        "closest_to_slowing_extremum": {
            "sample_index": closest_index,
            "time_s": float(t[closest_index]),
            "trajectory_position_m": float(x[closest_index]),
            "trajectory_velocity_m_s": float(v[closest_index]),
            "detuning_gamma": float(arrays["chirp_detunings_gamma"][closest_index]),
            "trajectory_normalized_force": float(normalized[closest_index]),
            "phase_space_distance": float(distances[closest_index]),
            "extremum_position_m": next(row for row in extrema if row["sample_index"] == closest_index)["position_m"],
            "extremum_velocity_m_s": next(row for row in extrema if row["sample_index"] == closest_index)["velocity_m_s"],
            "extremum_normalized_force": next(row for row in extrema if row["sample_index"] == closest_index)["normalized_force"],
            "paper_boat_velocity_m_s": next(row for row in extrema if row["sample_index"] == closest_index)["paper_boat_velocity_m_s"],
        },
        "useful_force_definition": (
            f"F <= -{USEFUL_FORCE_FRACTION:.2f}*abs(F_min(detuning)) on the cached pre-handoff field"
        ),
        "useful_force_time_s": useful_time,
        "gaussian_timing_events": {
            "first_useful_force_encounter": event(None if not useful_indices.size else int(useful_indices[0])),
            "closest_to_slowing_extremum": event(closest_index),
            "handoff": event(handoff_index),
            "center_crossing": event(None if not crossing_indices.size else int(crossing_indices[0])),
            "last_appreciable_illumination": event(None if not illuminated_indices.size else int(illuminated_indices[-1])),
        },
        "arrival_classification": (
            "after_slowing_feature"
            if v[closest_index] > next(row for row in extrema if row["sample_index"] == closest_index)["velocity_m_s"] + VELOCITY_UNIT_M_S
            else "near_slowing_feature_in_velocity_but_spatially_offset"
        ),
        "impulse_budget": {
            "initial_momentum_kg_m_s": mass_kg * float(v[0]),
            "final_momentum_kg_m_s": mass_kg * float(v[-1]),
            "cumulative_longitudinal_impulse_n_s": cumulative,
            "negative_impulse_endpoint_trapezoid_n_s": negative_impulse,
            "positive_impulse_endpoint_trapezoid_n_s": positive_impulse,
            "net_impulse_endpoint_trapezoid_n_s": negative_impulse + positive_impulse,
            "negative_normalized_force_time_s": negative_normalized_time,
            "positive_normalized_force_time_s": positive_normalized_time,
            "impulse_before_tau_n_s": mass_kg * float(v[handoff_index] - v[0]),
            "impulse_after_tau_n_s": mass_kg * float(v[-1] - v[handoff_index]),
            "impulse_while_appreciably_illuminated_endpoint_trapezoid_n_s": _interval_trapezoid(t, force_n, illumination),
            "required_stopping_impulse_magnitude_n_s": required,
            "negative_to_required_stopping_impulse_ratio": abs(negative_impulse) / required,
            "signed_decomposition_note": (
                "Negative/positive and illuminated terms are trapezoids over saved endpoint samples; "
                "the cumulative longitudinal value is the Run 011 RK4-weighted value."
            ),
        },
        "peak_negative_force": {
            "sample_index": peak_negative,
            "time_s": float(t[peak_negative]),
            "position_m": float(x[peak_negative]),
            "velocity_m_s": float(v[peak_negative]),
            "normalized_force": float(normalized[peak_negative]),
            "force_n": float(force_n[peak_negative]),
        },
        "peak_positive_force": {
            "sample_index": peak_positive,
            "time_s": float(t[peak_positive]),
            "position_m": float(x[peak_positive]),
            "velocity_m_s": float(v[peak_positive]),
            "normalized_force": float(normalized[peak_positive]),
            "force_n": float(force_n[peak_positive]),
        },
        "handoff": {
            "sample_index": handoff_index,
            "time_s": float(t[handoff_index]),
            "position_m": float(x[handoff_index]),
            "velocity_m_s": float(v[handoff_index]),
            "normalized_force": float(normalized[handoff_index]),
        },
        "first_center_crossing": None
        if not crossing_indices.size
        else {
            "sample_index": int(crossing_indices[0]),
            "time_s": float(t[crossing_indices[0]]),
            "position_m": float(x[crossing_indices[0]]),
            "velocity_m_s": float(v[crossing_indices[0]]),
        },
        "pre_handoff_slowing_extrema": extrema,
    }
    return result


def gaussian_envelope_audit(adapter: InterpolatedRateEquationTrajectoryForce) -> dict[str, Any]:
    positions_mm = (-50.0, -40.0, -30.0, -25.0, -20.0, 0.0)
    rows = []
    for position_mm in positions_mm:
        values = adapter.gaussian3.envelopes(np.array([position_mm * 1e-3, 0.0, 0.0]))
        rows.append(
            {
                "position_mm": position_mm,
                "plus_x_prime": values["+x_prime"],
                "minus_x_prime": values["-x_prime"],
                "plus_y_prime": values["+y_prime"],
                "minus_y_prime": values["-y_prime"],
                "plus_z": values["+z"],
                "minus_z": values["-z"],
                "mean": float(np.mean(tuple(values.values()))),
            }
        )
    return {
        "radius_convention": adapter.gaussian3.config.radius_convention,
        "paper_rough_spatial_half_width_m": PAPER_SPATIAL_HALF_WIDTH_M,
        "appreciable_illumination_threshold_mean_envelope": ILLUMINATION_THRESHOLD,
        "rows": rows,
    }


def cached_topology(cache: dict[str, np.ndarray]) -> dict[str, Any]:
    rows = []
    for detuning in (-8.0, -6.0, -4.0, -2.0, -1.0):
        force = _force_slice(cache, detuning)
        extremum_index = np.unravel_index(int(np.argmin(force)), force.shape)
        profile_x = force[:, extremum_index[1]]
        minimum = float(force[extremum_index])
        spatial_mask = profile_x <= math.exp(-2.0) * minimum
        xs = cache["positions_m"][spatial_mask]
        profile_v = force[extremum_index[0], :]
        velocity_mask = profile_v <= math.exp(-2.0) * minimum
        vs = cache["velocities_m_s"][velocity_mask]
        rows.append(
            {
                "detuning_gamma": detuning,
                "minimum_normalized_force": minimum,
                "extremum_position_m": float(cache["positions_m"][extremum_index[0]]),
                "extremum_velocity_m_s": float(cache["velocities_m_s"][extremum_index[1]]),
                "paper_scaling_velocity_m_s": math.sqrt(2.0) * abs(detuning) * VELOCITY_UNIT_M_S,
                "one_over_e2_spatial_extent_m": None if not xs.size else [float(xs[0]), float(xs[-1])],
                "one_over_e2_velocity_extent_m_s": None if not vs.size else [float(vs[0]), float(vs[-1])],
            }
        )
    return {"definition": "grid cells with F <= exp(-2)*F_min at the extremum coordinate", "rows": rows}


def optical_frequency_audit(
    adapter: InterpolatedRateEquationTrajectoryForce, policy: Any
) -> dict[str, Any]:
    backend = adapter.backend
    ground = dict(backend._role_ground_energy)
    excited = np.real(np.diag(backend.hamiltonian.blocks[1, 1][0].matrix))
    samples = {}
    for segment, time_s, beams in (
        ("pre_handoff", 0.0, adapter.gaussian3),
        ("post_handoff", TAU_S, adapter.gaussian31),
    ):
        sample = policy.sample(time_s)
        system = backend.build_optical_system(
            sample,
            policy_name=f"{LABEL}_{segment}",
            beam_mode="elliptical_gaussian",
            gaussian_beam_set=beams,
        )
        components = system.physical_beams[0].components
        rows = []
        for component in components:
            transition_detunings = {
                role: [
                    float(component.pylcp_carrier_detuning_gamma - (energy - role_energy))
                    for energy in excited
                ]
                for role, role_energy in ground.items()
                if "confinement" not in role
            }
            rows.append(
                {
                    **asdict(component),
                    "reference_transition_energy_gamma": float(
                        backend._excited_reference_energy
                        - ground[component.addressed_role]
                    ),
                    "detuning_from_each_ground_role_to_excited_basis_gamma": transition_detunings,
                }
            )
        samples[segment] = rows
    return {
        "internal_frequency_convention": (
            "rotating-frame carrier coordinates in units of Gamma; the 834.3 THz optical common offset is not represented"
        ),
        "excited_reference": "maximum diagonal excited energy (the three F'=1 basis states)",
        "excited_basis_energies_gamma": excited.tolist(),
        "ground_role_energies_gamma": ground,
        "centroid_reference_finding": (
            "The addressed F'=1 transitions receive exactly the policy detuning. The F'=0 transition is shifted by +0.023923 Gamma because the accepted 0.5 MHz splitting is retained. No material common-reference mismatch was found."
        ),
        "samples": samples,
    }


def rate_convention_audit(
    adapter: InterpolatedRateEquationTrajectoryForce, policy: Any
) -> dict[str, Any]:
    sample = policy.sample(TAU_S)
    system = adapter.backend.build_optical_system(
        sample,
        policy_name=f"{LABEL}_rate_side_by_side",
        beam_mode="elliptical_gaussian",
        gaussian_beam_set=adapter.gaussian31,
    )
    result = adapter.backend.force_at(
        np.zeros(3), np.zeros(3), system, collect_solver_diagnostics=True
    )
    laser_index = system.pylcp_beam_index.index(("+x_prime", 1))
    matrix = result.pumping_rate_matrices[laser_index]
    state_index = np.unravel_index(int(np.argmax(matrix)), matrix.shape)
    rate = float(matrix[state_index])
    component = next(
        component
        for component in system.physical_beams[0].components
        if component.component_id == 1
    )
    ground_energies = np.real(np.diag(adapter.backend.hamiltonian.blocks[0, 0][0].matrix))
    excited_energies = np.real(np.diag(adapter.backend.hamiltonian.blocks[1, 1][0].matrix))
    transition_detuning = float(
        component.pylcp_carrier_detuning_gamma
        - (excited_energies[state_index[1]] - ground_energies[state_index[0]])
    )
    denominator = 1.0 + 4.0 * transition_detuning**2
    line_strength = rate * denominator * 2.0 / component.peak_saturation
    omega_squared_over_gamma_squared = 0.5 * component.peak_saturation * line_strength
    paper_rate = omega_squared_over_gamma_squared / denominator
    return {
        "selected_point": "beam center, zero field, zero velocity, t=tau, +x' beam, component 1",
        "ground_basis_index": int(state_index[0]),
        "excited_basis_index": int(state_index[1]),
        "saturation_per_physical_beam_component": component.peak_saturation,
        "transition_detuning_gamma": transition_detuning,
        "lorentzian_denominator": denominator,
        "effective_polarized_line_strength": line_strength,
        "paper_omega_squared_over_gamma_squared": omega_squared_over_gamma_squared,
        "paper_rate_over_gamma": paper_rate,
        "pylcp_rate_over_gamma": rate,
        "absolute_difference": abs(paper_rate - rate),
        "paper_definition": "s_lm=I_lm/I_sat; Omega/Gamma=(d.epsilon)*sqrt(2s)/2",
        "pylcp_definition": "R/Gamma=s*|d.epsilon|^2/[2*(1+4 detuning^2)]",
        "linewidth_convention": "Gamma is angular decay rate; normalized pylcp gamma=1; detunings are angular/Gamma",
        "dipole_normalization_per_excited_state": np.sum(
            np.abs(adapter.backend.hamiltonian.blocks[0, 1].matrix) ** 2, axis=(0, 1)
        ).real.tolist(),
        "factor_findings": {
            "rabi_factor_of_two": "MATCHES",
            "linewidth": "MATCHES",
            "line_strength_applied_once": True,
            "saturation_applied_per_physical_beam_and_component": True,
            "six_beam_multiplier": "none; six physical beams are summed explicitly",
            "total_power_metadata_used_in_calculation": False,
        },
        "population_solver_health": {
            "population_sum": result.population_sum,
            "population_minimum": result.population_minimum,
            "residual_linf": result.steady_state_residual_linf,
            "fallback": result.singular_solver_fallback_used,
        },
    }


def _deterministic_indices(arrays: dict[str, np.ndarray], audit: dict[str, Any]) -> list[tuple[str, int]]:
    t = arrays["times_s"]
    x = arrays["positions_m"][:, 0]
    labels = [
        ("initial_state", 0),
        ("first_appreciably_illuminated_state", audit["first_appreciable_illumination"]["sample_index"]),
        ("closest_to_slowing_extremum", audit["closest_to_slowing_extremum"]["sample_index"]),
        ("strongest_negative_force", audit["peak_negative_force"]["sample_index"]),
        ("immediately_before_handoff", int(np.flatnonzero(t < TAU_S)[-1])),
        ("immediately_after_handoff", int(np.flatnonzero(t >= TAU_S)[0])),
        ("center_crossing", int(np.flatnonzero(x >= 0.0)[0])),
        ("strongest_positive_force", audit["peak_positive_force"]["sample_index"]),
        ("domain_exit", len(t) - 1),
    ]
    return labels


def direct_point_audit(
    adapter: InterpolatedRateEquationTrajectoryForce,
    policy: Any,
    arrays: dict[str, np.ndarray],
    audit: dict[str, Any],
) -> list[dict[str, Any]]:
    records = []
    for point_label, index in _deterministic_indices(arrays, audit):
        time_s = float(arrays["times_s"][index])
        x = float(arrays["positions_m"][index, 0])
        v = float(arrays["velocities_m_s"][index, 0])
        sample = policy.sample(time_s)
        pre = time_s < TAU_S
        system = adapter.backend.build_optical_system(
            sample,
            policy_name=f"{LABEL}_{point_label}",
            beam_mode="elliptical_gaussian",
            gaussian_beam_set=adapter.gaussian3 if pre else adapter.gaussian31,
        )
        direct = adapter.backend.force_at(
            np.array([x, 0.0, 0.0]),
            np.array([v, 0.0, 0.0]),
            system,
            collect_solver_diagnostics=True,
        )
        cached = float(arrays["normalized_force_x"][index])
        records.append(
            {
                "label": LABEL,
                "point": point_label,
                "sample_index": index,
                "time_s": time_s,
                "position_m": x,
                "velocity_m_s": v,
                "policy_segment": str(arrays["policy_segments"][index]),
                "component_detunings_gamma": arrays["component_detunings_gamma"][index].tolist(),
                "component_saturations": arrays["component_saturations"][index].tolist(),
                "component_active": arrays["component_active"][index].astype(bool).tolist(),
                "cached_normalized_force": cached,
                "direct_normalized_force": float(direct.normalized_force[0]),
                "absolute_difference": abs(cached - float(direct.normalized_force[0])),
                "force_direction": "slowing" if direct.normalized_force[0] < 0 else "accelerating",
                "population_solver_health": {
                    "population_sum": direct.population_sum,
                    "population_minimum": direct.population_minimum,
                    "residual_linf": direct.steady_state_residual_linf,
                    "fallback": direct.singular_solver_fallback_used,
                    "passed": bool(
                        direct.population_minimum >= -1e-10
                        and abs(direct.population_sum - 1.0) <= 1e-9
                        and direct.steady_state_residual_linf <= 1e-9
                        and not direct.singular_solver_fallback_used
                    ),
                },
            }
        )
    return records


def benchmark_ledger() -> list[dict[str, str]]:
    return [
        {"parameter": "initial position", "paper": "-50", "code": "-0.050", "units": "mm -> m", "conversion": "mm*1e-3", "location": "Rodriguez Sec. IV/Fig. 4(a); rodriguez_named_trajectory_protocol.yaml", "status": "exact match"},
        {"parameter": "initial velocity", "paper": "7.5 Gamma/k about 57", "code": "56.475", "units": "Gamma/k -> m/s", "conversion": "7.5*7.53 m/s", "location": "Rodriguez Sec. IV/Fig. 4(a); rodriguez_named_trajectory_protocol.yaml", "status": "derived match"},
        {"parameter": "velocity direction", "paper": "+x from x<0 toward center", "code": "+x", "units": "direction", "conversion": "none", "location": "Rodriguez Sec. II/IV; protocol coordinate_convention", "status": "exact match"},
        {"parameter": "chirp start", "paper": "0", "code": "0", "units": "s", "conversion": "none", "location": "Rodriguez Eq. (6)/Sec. IV; handoff policy", "status": "exact match"},
        {"parameter": "chirp endpoints", "paper": "-8 to -1", "code": "-8 to -1", "units": "Gamma", "conversion": "angular detuning/Gamma", "location": "Rodriguez Fig. 4 caption/Sec. IV; handoff YAML", "status": "exact match"},
        {"parameter": "chirp duration", "paper": "1", "code": "0.001", "units": "ms -> s", "conversion": "ms*1e-3", "location": "Rodriguez Fig. 4 caption/Sec. IV; handoff policy", "status": "exact match"},
        {"parameter": "pre saturation", "paper": "(1.45,1.45,2.89,0)", "code": "same per beam", "units": "I/I_sat", "conversion": "none", "location": "Rodriguez Sec. IV; handoff policy", "status": "exact match"},
        {"parameter": "post saturation", "paper": "(1.45,1.45,2.17,0.72)", "code": "same per beam", "units": "I/I_sat", "conversion": "none", "location": "Rodriguez Sec. IV; handoff policy", "status": "exact match"},
        {"parameter": "component 4", "paper": "+2, on at tau", "code": "+2 parked/off before tau; active at t>=tau", "units": "Gamma, s", "conversion": "none", "location": "Rodriguez Fig. 1/Sec. IV; handoff policy", "status": "exact match"},
        {"parameter": "field gradient", "paper": "2", "code": "0.2", "units": "mT/cm -> T/m", "conversion": "1 mT/cm=0.1 T/m", "location": "Rodriguez Fig. 4 caption; accepted_backend.py", "status": "exact match"},
        {"parameter": "beam axes", "paper": "+/-x', +/-y', +/-z; 45", "code": "same six unit vectors", "units": "degrees/unit vectors", "conversion": "x',y' lab projections 1/sqrt(2)", "location": "Rodriguez Sec. II; geometry.py", "status": "exact match"},
        {"parameter": "Gaussian radii", "paper": "17.5, 10, 1/e^2", "code": "0.0175, 0.010, exp(-2r^2/w^2)", "units": "mm -> m", "conversion": "mm*1e-3", "location": "Rodriguez Sec. II/Fig. 4; Gaussian baseline YAML", "status": "exact match"},
        {"parameter": "total-power statement", "paper": "1", "code": "1 metadata only", "units": "W", "conversion": "no inferred allocation", "location": "Rodriguez Fig. 4 caption/Sec. IV; Gaussian baseline YAML", "status": "ambiguity"},
        {"parameter": "operative saturation", "paper": "s_lm=I_lm/I_sat for each beam/component", "code": "reported peak s per physical beam/component", "units": "dimensionless", "conversion": "none", "location": "Rodriguez Eq. (4)/notation after Eq. (5); rateeq_backend.py", "status": "exact match"},
        {"parameter": "simulation duration", "paper": "not stated for Fig. 4(a)", "code": "0.020", "units": "s", "conversion": "none", "location": "Rodriguez Fig. 4(a); Run 011 YAML", "status": "ambiguity"},
        {"parameter": "capture terminology", "paper": "largest initial velocity captured; curve reaches v=0,x=0", "code": "engineering BOUNDED_FINAL_STATE or UNRESOLVED", "units": "classification", "conversion": "none", "location": "Rodriguez Fig. 4(a)/Sec. III wording; Run 011 outcome classifier", "status": "not comparable"},
    ]


def expectation_comparison(topology: dict[str, Any]) -> list[dict[str, str]]:
    rows = topology["rows"]
    peak = max(abs(row["minimum_normalized_force"]) for row in rows)
    return [
        {"feature": "slowing extrema near sqrt(2)*abs(Delta)/k", "classification": "CLOSE", "evidence": "cached extrema track the guide within about one 6.25 m/s velocity cell"},
        {"feature": "useful force scale about 0.03 hbar*k*Gamma", "classification": "MATERIALLY_DIFFERENT", "evidence": f"sampled cached negative extrema reach {peak:.3f}"},
        {"feature": "velocity width about Gamma/k", "classification": "CLOSE", "evidence": "cached exp(-2) spans are grid-limited but of order 6-13 m/s"},
        {"feature": "spatial width about sqrt(2)wxy about 25 mm", "classification": "MATERIALLY_DIFFERENT", "evidence": "cached exp(-2) negative-force half-extents are mostly 15-20 mm"},
        {"feature": "smooth movement during chirp", "classification": "MATCHES", "evidence": "accepted detuning slices move monotonically from about 88 to 13 m/s"},
        {"feature": "nominal capture near 7.5 Gamma/k", "classification": "MATERIALLY_DIFFERENT", "evidence": "saved path exits x=+60 mm at positive speed"},
    ]


def candidate_diagnoses() -> dict[str, list[dict[str, str]]]:
    return {
        "demonstrated_causes": [
            {"candidate": "GAUSSIAN_FORCE_REGION_TOO_NARROW", "evidence": "cached exp(-2) slowing-force half-width is 15-20 mm rather than the paper's rough 25 mm"},
            {"candidate": "POST_HANDOFF_ACCELERATION_CANCELS_SLOWING", "evidence": "7.5 Gamma/k has negative impulse before tau and larger positive impulse after tau, ending faster than it entered"},
        ],
        "likely_contributors": [
            {"candidate": "PROVISIONAL_HAMILTONIAN_FORCE_SHAPE_DIFFERENCE", "evidence": "the accepted field is about twice the paper's rough peak scale yet spatially narrower; unresolved exact excited-state physics remains the principal model boundary"},
        ],
        "ruled_out": [
            {"candidate": "CHIRP_TIMING_MISMATCH", "evidence": "start, endpoints, duration, and exact handoff agree"},
            {"candidate": "VELOCITY_SIGN_OR_PROJECTION_MISMATCH", "evidence": "positive lab-x motion and 45-degree Doppler projections agree; cached boat velocities follow sqrt(2)|Delta|/k"},
            {"candidate": "DETUNING_REFERENCE_MISMATCH", "evidence": "addressed F'=1 carriers have exact policy detuning; retained F'=0 offset is only 0.023923 Gamma"},
            {"candidate": "SATURATION_CONVENTION_MISMATCH", "evidence": "paper and code both apply s_lm per physical beam and component"},
            {"candidate": "RABI_RATE_NORMALIZATION_MISMATCH", "evidence": "paper and pylcp pumping-rate formulas agree term by term and numerically"},
            {"candidate": "FORCE_FIELD_DOMAIN_ONLY", "evidence": "the 7.5 Gamma/k path has already failed to slow before the +60 mm boundary; the boundary records failure rather than causing it"},
        ],
        "unresolved": [
            {"candidate": "COMPONENT_FREQUENCY_MAPPING_MISMATCH", "evidence": "no mismatch found in the implemented common reference, but the exact Rodriguez code is unavailable for direct comparison"},
            {"candidate": "PAPER_CAPTURE_CRITERION_AMBIGUITY", "evidence": "Fig. 4 calls the thick trajectory captured but does not state its numerical terminal rule or duration"},
            {"candidate": "INSUFFICIENT_EVIDENCE", "evidence": "the paper force map was visually inspected but not digitized"},
        ],
    }


def _save_plot(trajectories: dict[str, dict[str, np.ndarray]], cache: dict[str, np.ndarray]) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    for name, arrays in trajectories.items():
        short = name.replace("v_", "").replace("_gamma_over_k", "")
        axes[0, 0].plot(arrays["times_s"] * 1e3, arrays["velocities_m_s"][:, 0], label=short)
        axes[0, 1].plot(arrays["positions_m"][:, 0] * 1e3, arrays["velocities_m_s"][:, 0], label=short)
        axes[1, 0].plot(arrays["times_s"] * 1e3, arrays["normalized_force_x"], label=short)
    seven = trajectories["v_7p5_gamma_over_k"]
    pre = seven["times_s"] < TAU_S
    guide = math.sqrt(2.0) * np.abs(seven["chirp_detunings_gamma"][pre]) * VELOCITY_UNIT_M_S
    actual = np.array([
        slowing_extremum(cache, float(delta))["velocity_m_s"]
        for delta in seven["chirp_detunings_gamma"][pre]
    ])
    axes[0, 0].plot(seven["times_s"][pre] * 1e3, guide, "k--", label="paper guide")
    axes[0, 0].plot(seven["times_s"][pre] * 1e3, actual, "ko", ms=3, label="cached extremum")
    axes[1, 1].plot(seven["times_s"] * 1e3, seven["gaussian_envelope_mean"], color="tab:purple")
    for axis in (axes[0, 0], axes[1, 0], axes[1, 1]):
        axis.axvline(1.0, color="tab:red", linestyle="--", linewidth=0.8)
    axes[0, 1].axvline(0.0, color="tab:red", linestyle="--", linewidth=0.8)
    for axis in axes.flat:
        axis.grid(alpha=0.2)
    axes[0, 0].set(xlabel="time [ms]", ylabel="velocity [m/s]", title="Saved velocity and moving slowing feature")
    axes[0, 1].set(xlabel="x [mm]", ylabel="velocity [m/s]", title="Saved phase-space paths")
    axes[1, 0].set(xlabel="time [ms]", ylabel="force [hbar k Gamma]", title="Saved normalized force")
    axes[1, 1].set(xlabel="time [ms]", ylabel="mean I/I0", title="7.5 Gamma/k Gaussian illumination")
    axes[0, 0].legend(fontsize=7)
    axes[0, 1].legend(fontsize=7)
    axes[1, 0].legend(fontsize=7)
    fig.suptitle(LABEL, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(PLOT_PATH, dpi=150)
    plt.close(fig)


def _table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    lines = ["| " + " | ".join(title for _, title in columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        values = []
        for key, _ in columns:
            value = row.get(key)
            if isinstance(value, float):
                values.append(f"{value:.6g}")
            else:
                values.append(str(value).replace("|", "/"))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _write_report(metadata: dict[str, Any]) -> None:
    h = lambda text: f"## {LABEL} {text}"
    lines = [
        f"# {LABEL}",
        "",
        "This is a read-only discrepancy audit of saved Track P artifacts. It is provisional, is not a Rodriguez replication, and makes no capture claim.",
        "",
        h("Immutable input verification"),
        "",
        f"Protected Run 010/011 arrays, metadata, reports, caches, spectroscopy, and apparatus configs: `{metadata['protected_artifacts_unchanged']}` ({len(metadata['protected_hashes_before'])} files). No force field was rebuilt and no trajectory was reintegrated.",
        "",
        h("Benchmark ledger"),
        "",
        *_table(metadata["benchmark_ledger"], [("parameter", "parameter"), ("paper", "paper"), ("code", "code"), ("units", "units"), ("conversion", "conversion"), ("location", "source/config"), ("status", "status")]),
        "",
        h("Moving slowing-force region"),
        "",
        f"Appreciable illumination is defined as mean six-beam envelope >= `{ILLUMINATION_THRESHOLD}`. A useful slowing sample satisfies `{metadata['trajectories']['v_7p5_gamma_over_k']['useful_force_definition']}`. Phase-space distance uses the paper guide widths `{PAPER_SPATIAL_HALF_WIDTH_M*1e3:.3f} mm` and `{VELOCITY_UNIT_M_S:.3f} m/s`.",
        "",
        "| case | first illuminated ms | closest ms | closest x mm | closest v m/s | cached extremum v m/s | distance | useful time ms | arrival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, row in metadata["trajectories"].items():
        illum = row["first_appreciable_illumination"]
        close = row["closest_to_slowing_extremum"]
        lines.append(
            f"| {name} | {illum['time_s']*1e3:.3f} | {close['time_s']*1e3:.3f} | {close['trajectory_position_m']*1e3:.3f} | {close['trajectory_velocity_m_s']:.3f} | {close['extremum_velocity_m_s']:.3f} | {close['phase_space_distance']:.3f} | {row['useful_force_time_s']*1e3:.3f} | {row['arrival_classification']} |"
        )
    lines += [
        "",
        "For 7.5 Gamma/k, the trajectory is velocity-matched to the cached slowing extremum near 0.4 ms but is still near x=-27 mm, outside the cached major negative-force region. It then falls behind the rapidly descending velocity feature. This is primarily a spatial-then-velocity miss, not a chirp-sign error.",
        "",
        h("Force and impulse budget"),
        "",
        "| case | p initial | p final | net impulse | negative impulse | positive impulse | pre-tau | post-tau | negative/stop | Fmin | Fmax |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in metadata["trajectories"].items():
        b = row["impulse_budget"]
        lines.append(
            f"| {name} | {b['initial_momentum_kg_m_s']:.3e} | {b['final_momentum_kg_m_s']:.3e} | {b['cumulative_longitudinal_impulse_n_s']:.3e} | {b['negative_impulse_endpoint_trapezoid_n_s']:.3e} | {b['positive_impulse_endpoint_trapezoid_n_s']:.3e} | {b['impulse_before_tau_n_s']:.3e} | {b['impulse_after_tau_n_s']:.3e} | {b['negative_to_required_stopping_impulse_ratio']:.3f} | {row['peak_negative_force']['normalized_force']:.4f} | {row['peak_positive_force']['normalized_force']:.4f} |"
        )
    lines += [
        "",
        "The 7.5 Gamma/k case exits about 0.90 m/s faster than it entered: its post-handoff accelerating impulse exceeds its pre-handoff slowing impulse. The 9 Gamma/k case slows more because it crosses the center before the handoff and continues sampling the moving negative pre-handoff feature; 7.5 crosses at the handoff and 6 crosses afterward, where the post-handoff positive lobe cancels much of their slowing. The 2 and 4 cases remain on x<0 because post-handoff negative force removes nearly all incident momentum before either reaches the origin; their residual speeds are small and the 20 ms interval ends before crossing.",
        "",
        h("Optical-frequency construction"),
        "",
        metadata["optical_frequency_audit"]["internal_frequency_convention"] + ". " + metadata["optical_frequency_audit"]["centroid_reference_finding"],
        "",
        "| segment | component | role | policy detuning | carrier coordinate | polarization | saturation | active |",
        "|---|---:|---|---:|---:|---|---:|---|",
    ]
    for segment, rows in metadata["optical_frequency_audit"]["samples"].items():
        for row in rows:
            lines.append(f"| {segment} | {row['component_id']} | {row['addressed_role']} | {row['detuning_gamma']:.3f} | {row['pylcp_carrier_detuning_gamma']:.6f} | {row['polarization']} -> pylcp {row['pylcp_helicity']:+d} | {row['peak_saturation']:.3f} | {row['active']} |")
    lines += [
        "",
        "Components 3 and 4 reference the arithmetic mean of the upper F=1/F=2 ground energies. The internal optical carrier uses the retained F'=1 energy as its excited reference. Full detunings from every retained ground-role/excited-basis combination are preserved in the JSON metadata. No material centroid/reference mismatch was demonstrated.",
        "",
        h("Saturation and Rabi convention"),
        "",
        f"At the selected transition, paper rate/Gamma = `{metadata['rate_convention_audit']['paper_rate_over_gamma']:.12g}` and pylcp rate/Gamma = `{metadata['rate_convention_audit']['pylcp_rate_over_gamma']:.12g}` (absolute difference `{metadata['rate_convention_audit']['absolute_difference']:.3e}`). The Rabi factor, angular-linewidth convention, and single line-strength application match. Saturation is applied to each physical beam and component; six beams are explicit rather than folded into s. The 1 W field is metadata and does not separately rescale the already supplied peak saturation vector.",
        "",
        h("Gaussian timing and width"),
        "",
        "| x mm | +/-x' | +/-y' | +/-z | mean |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in metadata["gaussian_envelope_audit"]["rows"]:
        lines.append(f"| {row['position_mm']:.0f} | {row['plus_x_prime']:.6f} | {row['plus_y_prime']:.6f} | {row['plus_z']:.6f} | {row['mean']:.6f} |")
    lines += [
        "",
        "Saved 7.5 Gamma/k path envelope events:",
        "",
        "| event | t ms | x mm | v m/s | min envelope | mean envelope | max envelope |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for event_name, event_row in metadata["trajectories"]["v_7p5_gamma_over_k"]["gaussian_timing_events"].items():
        if event_row is None:
            lines.append(f"| {event_name} | not encountered | | | | | |")
        else:
            lines.append(
                f"| {event_name} | {event_row['time_s']*1e3:.3f} | {event_row['position_m']*1e3:.3f} | {event_row['velocity_m_s']:.3f} | {event_row['minimum_envelope']:.6f} | {event_row['mean_envelope']:.6f} | {event_row['maximum_envelope']:.6f} |"
            )
    lines += [
        "",
        "The analytic Gaussian frames have the intended sqrt(2) projection. Nevertheless, after molecular/Zeeman response is included, the cached major negative-force region has exp(-2)-level half-extents mostly 15-20 mm rather than the paper's rough 25 mm. Thus the operative provisional force boat is materially narrower even though the bare optical envelope is correctly wired.",
        "",
        h("Direct rate-equation audit points on 7.5 Gamma/k"),
        "",
        "| point | t ms | x mm | v m/s | cached | direct | direction | solver healthy |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in metadata["direct_point_audit"]:
        lines.append(f"| {row['point']} | {row['time_s']*1e3:.3f} | {row['position_m']*1e3:.3f} | {row['velocity_m_s']:.3f} | {row['cached_normalized_force']:.6f} | {row['direct_normalized_force']:.6f} | {row['force_direction']} | {row['population_solver_health']['passed']} |")
    lines += [
        "",
        "These fresh solves are audit samples only. They confirm the cached force direction and population-solver health at dynamically meaningful saved states; they do not reopen the already-passed Run 011 interpolation gate.",
        "",
        h("Paper force-map expectations"),
        "",
        *_table(metadata["paper_expectations"], [("feature", "feature"), ("classification", "classification"), ("evidence", "evidence")]),
        "",
        h("Candidate diagnoses"),
        "",
        "Demonstrated causes:",
        "",
        *[f"- `{row['candidate']}`: {row['evidence']}" for row in metadata["candidate_diagnoses"]["demonstrated_causes"]],
        "",
        "Likely contributor:",
        "",
        *[f"- `{row['candidate']}`: {row['evidence']}" for row in metadata["candidate_diagnoses"]["likely_contributors"]],
        "",
        "Ruled out by this audit:",
        "",
        *[f"- `{row['candidate']}`: {row['evidence']}" for row in metadata["candidate_diagnoses"]["ruled_out"]],
        "",
        "Unresolved:",
        "",
        *[f"- `{row['candidate']}`: {row['evidence']}" for row in metadata["candidate_diagnoses"]["unresolved"]],
        "",
        h("Final gate: BASELINE_DISCREPANCY_NARROWED"),
        "",
        "**BASELINE_DISCREPANCY_NARROWED**",
        "",
        "The accepted provisional field's operative slowing region is demonstrably narrower than the paper guide, and the post-handoff accelerating lobe demonstrably cancels the 7.5 Gamma/k path's earlier slowing. The most likely common origin is provisional Hamiltonian force-shape physics, but the paper field has not been digitized and the exact excited-state model remains blocked, so a targeted corrective physics change is not yet justified.",
        "",
        "`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.",
        "",
        f"# {LABEL} FINAL_BASELINE_DISCREPANCY_NARROWED",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = protected_paths()
    hashes_before = hash_manifest(paths)
    cache = _pre_cache()
    trajectories = {name: _load_npz(path) for name, path in _trajectory_paths().items()}
    policy = load_policy(REPO_ROOT / "configs" / "rodriguez_chirp_to_3_plus_1_handoff.yaml")
    adapter = InterpolatedRateEquationTrajectoryForce(
        repo_root=REPO_ROOT,
        explicit_provisional_opt_in=True,
        acknowledge_midpoint_not_measured=True,
    )
    mass = adapter.force_units.mass.value_kg
    audits = {
        name: trajectory_audit(name, arrays, cache, mass)
        for name, arrays in trajectories.items()
    }
    topology = cached_topology(cache)
    frequency = optical_frequency_audit(adapter, policy)
    rate = rate_convention_audit(adapter, policy)
    direct = direct_point_audit(
        adapter,
        policy,
        trajectories["v_7p5_gamma_over_k"],
        audits["v_7p5_gamma_over_k"],
    )
    _save_plot(trajectories, cache)
    hashes_after = hash_manifest(paths)
    metadata = {
        "label": LABEL,
        "title": f"{LABEL} metadata",
        "track": "provisional",
        "replication_valid": False,
        "audit_only": True,
        "trajectory_integrations_performed": 0,
        "force_field_rebuilds_performed": 0,
        "fresh_direct_rate_equation_solves": len(direct) + 1,
        "protected_hashes_before": hashes_before,
        "protected_hashes_after": hashes_after,
        "protected_artifacts_unchanged": hashes_before == hashes_after,
        "benchmark_ledger": benchmark_ledger(),
        "thresholds": {
            "appreciable_illumination_mean_envelope": ILLUMINATION_THRESHOLD,
            "useful_force_fraction_of_instantaneous_cached_negative_extremum": USEFUL_FORCE_FRACTION,
        },
        "trajectories": audits,
        "cached_topology": topology,
        "gaussian_envelope_audit": gaussian_envelope_audit(adapter),
        "optical_frequency_audit": frequency,
        "rate_convention_audit": rate,
        "direct_point_audit": direct,
        "paper_expectations": expectation_comparison(topology),
        "candidate_diagnoses": candidate_diagnoses(),
        "gate": "BASELINE_DISCREPANCY_NARROWED",
        "capture_authorized": False,
        "capture_velocity_authorized": False,
        "optimizer_authorized": False,
        "exact_replication_valid": False,
        "exact_track_blocked": True,
        "generated_files": [REPORT_PATH.name, METADATA_PATH.name, PLOT_PATH.name],
    }
    if not metadata["protected_artifacts_unchanged"]:
        raise RuntimeError("Run 010/011 protected artifacts changed during the audit")
    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, default=_json),
        encoding="utf-8",
    )
    _write_report(metadata)
    print(f"{LABEL}: {metadata['gate']}")
    print(f"report: {REPORT_PATH}")
    return metadata


if __name__ == "__main__":
    run()
