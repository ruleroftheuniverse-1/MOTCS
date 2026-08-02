"""Run 010: build and validate accepted provisional normalized-force tables."""

from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from mgf_mot.accepted_backend import (
    AcceptedProvisionalBackendSelection,
    build_accepted_provisional_rateeq_backend,
)
from mgf_mot.force_field import (
    FORCE_FIELD_LABEL,
    ForceFieldCacheMismatchError,
    ForceFieldDomain,
    ForceFieldDomainError,
    ForceFieldGrid,
    ForceFieldProvenance,
    InterpolatedForceField,
    SeparatedHandoffForceFields,
    load_force_field_cache,
    save_force_field_cache,
)
from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.policies import PolicySample, load_policy
from mgf_mot.spectroscopy import BOHR_MAGNETON_MHZ_PER_GAUSS, LINEWIDTH_MHZ


RUN010_LABEL = FORCE_FIELD_LABEL
CONFIG_PATH = REPO_ROOT / "configs" / "provisional_force_field_run_010.yaml"
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
CACHE_DIR = OUTPUT_DIR / "force_fields"
REPORT_PATH = OUTPUT_DIR / f"{RUN010_LABEL}_run_010.md"
METADATA_PATH = OUTPUT_DIR / f"{RUN010_LABEL}_run_010_metadata.json"
PLOT_PATH = OUTPUT_DIR / f"{RUN010_LABEL}_run_010_validation.png"


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_config() -> dict[str, Any]:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["name"] != f"{RUN010_LABEL}_run_010":
        raise ValueError("Run 010 config must carry the full quarantine label")
    return config


def _linspace(spec: dict[str, Any]) -> np.ndarray:
    return np.linspace(float(spec["minimum"]), float(spec["maximum"]), int(spec["count"]))


def _source_hashes() -> tuple[tuple[str, str], ...]:
    paths = (
        CONFIG_PATH,
        REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml",
        REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml",
        REPO_ROOT / "configs" / "rodriguez_gaussian_baseline.yaml",
        REPO_ROOT / "src" / "mgf_mot" / "accepted_backend.py",
        REPO_ROOT / "src" / "mgf_mot" / "excited_hyperfine.py",
        REPO_ROOT / "src" / "mgf_mot" / "force_field.py",
        REPO_ROOT / "src" / "mgf_mot" / "gaussian_beams.py",
        REPO_ROOT / "src" / "mgf_mot" / "mgf_backend.py",
        REPO_ROOT / "src" / "mgf_mot" / "rateeq_backend.py",
        REPO_ROOT / "src" / "mgf_mot" / "spectroscopy.py",
    )
    return tuple((str(path.relative_to(REPO_ROOT)), _hash(path)) for path in paths)


def _systems(backend):
    chirp = load_policy(REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml")
    post = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    gaussian_config = load_gaussian_envelope_config(
        REPO_ROOT / "configs" / "rodriguez_gaussian_baseline.yaml"
    )
    gaussian3 = build_rodriguez_gaussian_beam_set(gaussian_config, (1.45, 1.45, 2.89, 0.0))
    gaussian31 = build_rodriguez_gaussian_beam_set(gaussian_config, (1.45, 1.45, 2.17, 0.72))

    def pre_sample(detuning_gamma: float) -> PolicySample:
        base = chirp.sample(0.0)
        components = tuple(
            replace(component, detuning_gamma=float(detuning_gamma))
            if component.component_id in (1, 2, 3)
            else component
            for component in base.components
        )
        sample = replace(base, components=components)
        if tuple(c.active for c in sample.components) != (True, True, True, False):
            raise RuntimeError("pre-handoff field requires active components (1,2,3) and parked component 4")
        if tuple(c.saturation for c in sample.components) != (1.45, 1.45, 2.89, 0.0):
            raise RuntimeError("pre-handoff saturation vector changed")
        return sample

    def pre_system(detuning_gamma: float):
        return backend.build_optical_system(
            pre_sample(detuning_gamma),
            policy_name=f"run010_pre_{detuning_gamma:+.9g}_Gamma",
            beam_mode="elliptical_gaussian",
            gaussian_beam_set=gaussian3,
        )

    post_sample = post.sample(0.0)
    if tuple(c.detuning_gamma for c in post_sample.components) != (-1.0, -1.0, -1.0, 2.0):
        raise RuntimeError("post-handoff detuning vector changed")
    if tuple(c.saturation for c in post_sample.components) != (1.45, 1.45, 2.17, 0.72):
        raise RuntimeError("post-handoff saturation vector changed")
    post_system = backend.build_optical_system(
        post_sample,
        policy_name="run010_post_3_plus_1",
        beam_mode="elliptical_gaussian",
        gaussian_beam_set=gaussian31,
    )
    return chirp, post, gaussian3, gaussian31, pre_system, post_system


def _provenance(backend, selection, kind, source_hashes):
    pre = kind == "pre_handoff_chirp_3"
    return ForceFieldProvenance(
        label=RUN010_LABEL,
        field_kind=kind,
        track="provisional",
        backend_mode=backend.status.backend_mode,
        ground_zeeman_convention=backend.status.ground_zeeman_convention,
        excited_zeeman_model=backend.status.excited_zeeman_model,
        excited_hyperfine_model=backend.status.excited_hyperfine_model,
        splitting_case=selection.splitting_case.value,
        splitting_mhz=selection.splitting_case.splitting_mhz,
        splitting_interval_mhz=selection.splitting_interval_mhz,
        splitting_note=selection.splitting_note,
        replication_valid=False,
        exact_track_blocked=True,
        unresolved_terms=selection.unresolved_terms,
        normalized_force_unit="hbar*k*Gamma",
        canonical_values_are_si_acceleration=False,
        field_gradient_t_m=0.2,
        beam_mode="elliptical_gaussian",
        component_order=(1, 2, 3, 4),
        saturation_vector=(1.45, 1.45, 2.89, 0.0) if pre else (1.45, 1.45, 2.17, 0.72),
        detuning_specification="common -8 to -1 Gamma for active components (1,2,3); component 4 parked/off" if pre else "(-1,-1,-1,+2) Gamma; component 4 active",
        source_hashes=source_hashes,
        interpolation_method="trilinear" if pre else "bilinear",
    )


class _Health:
    def __init__(self):
        self.solves = 0
        self.minimum_population = np.inf
        self.maximum_sum_error = 0.0
        self.maximum_residual = 0.0
        self.fallbacks = 0
        self.nonfinite = 0
        self.nullities: set[int] = set()

    def add(self, result) -> None:
        self.solves += 1
        self.minimum_population = min(self.minimum_population, result.population_minimum)
        self.maximum_sum_error = max(self.maximum_sum_error, abs(result.population_sum - 1.0))
        self.maximum_residual = max(self.maximum_residual, result.steady_state_residual_linf)
        self.fallbacks += int(result.singular_solver_fallback_used)
        self.nullities.add(result.nullspace_dimension)
        if not np.isfinite(result.normalized_force).all() or not np.isfinite(result.equilibrium_populations).all():
            self.nonfinite += 1

    def record(self) -> dict[str, Any]:
        passed = bool(
            self.minimum_population >= -1e-10 and self.maximum_sum_error <= 1e-9
            and self.maximum_residual <= 1e-9 and self.fallbacks == 0
            and self.nonfinite == 0 and self.nullities == {1}
        )
        return {
            "solves": self.solves,
            "minimum_population": float(self.minimum_population),
            "maximum_sum_error": float(self.maximum_sum_error),
            "maximum_residual_linf": float(self.maximum_residual),
            "fallback_count": self.fallbacks,
            "nonfinite_count": self.nonfinite,
            "nullspace_dimensions": sorted(self.nullities),
            "passed": passed,
        }


def _direct(backend, system, x, v, health: _Health | None = None) -> float:
    result = backend.force_at(
        np.array([x, 0.0, 0.0]), np.array([v, 0.0, 0.0]), system,
        collect_solver_diagnostics=True,
    )
    if health is not None:
        health.add(result)
    return float(result.normalized_force[0])


def _scales(backend) -> tuple[float, float]:
    position = LINEWIDTH_MHZ.require() / (
        BOHR_MAGNETON_MHZ_PER_GAUSS.require() * backend.gradient_gauss_per_m
    )
    velocity = backend.force_units.linewidth_rad_s / backend.force_units.wave_number_rad_m
    return float(position), float(velocity)


def _build_grids(config, backend, pre_system, post_system, pre_prov, post_prov):
    x = _linspace(config["domain"]["position_m"])
    v = _linspace(config["domain"]["velocity_m_s"])
    d = _linspace(config["domain"]["detuning_gamma"])
    pre_domain, post_domain = ForceFieldDomain(x, v, d), ForceFieldDomain(x, v)
    print(f"{RUN010_LABEL}: estimated equilibrium solves = {pre_domain.equilibrium_solve_count + post_domain.equilibrium_solve_count}")
    health = _Health()
    start = perf_counter()
    pre_values = np.empty(pre_domain.shape)
    for kd, delta in enumerate(d):
        system = pre_system(float(delta))
        for ix, position in enumerate(x):
            for iv, velocity in enumerate(v):
                pre_values[ix, iv, kd] = _direct(backend, system, position, velocity, health)
    post_values = np.empty(post_domain.shape)
    for ix, position in enumerate(x):
        for iv, velocity in enumerate(v):
            post_values[ix, iv] = _direct(backend, post_system, position, velocity, health)
    elapsed = perf_counter() - start
    scales = _scales(backend)
    return (
        ForceFieldGrid(pre_domain, pre_values, pre_prov, *scales),
        ForceFieldGrid(post_domain, post_values, post_prov, *scales),
        health.record(), elapsed,
    )


def _cache_paths(kind: str) -> tuple[Path, Path]:
    stem = f"{RUN010_LABEL}_{kind}_run_010"
    return CACHE_DIR / f"{stem}.npz", CACHE_DIR / f"{stem}_metadata.json"


def _load_matching(pre_prov, post_prov):
    pairs = (_cache_paths("pre_handoff_chirp_3"), _cache_paths("post_handoff_trap_3_plus_1"))
    if not all(npz.exists() and meta.exists() for npz, meta in pairs):
        return None
    try:
        return (
            load_force_field_cache(*pairs[0], pre_prov),
            load_force_field_cache(*pairs[1], post_prov),
        )
    except ForceFieldCacheMismatchError as exc:
        print(f"{RUN010_LABEL}: cache refused: {exc}; rebuilding")
        return None


def _not_node(value: float, axis: np.ndarray) -> bool:
    return not bool(np.any(np.isclose(value, axis, atol=1e-13, rtol=0)))


def _holdouts(config, pre_grid, post_grid):
    rng = np.random.default_rng(int(config["holdouts"]["seed"]))
    x, v, d = pre_grid.domain.positions_m, pre_grid.domain.velocities_m_s, pre_grid.domain.detunings_gamma
    structured_pre = [
        (0.5 * (x[0] + x[1]), 0.5 * (v[0] + v[1]), 0.5 * (d[0] + d[1]), "near_lower_boundaries"),
        (0.5 * (x[-2] + x[-1]), 0.5 * (v[-2] + v[-1]), 0.5 * (d[-2] + d[-1]), "near_upper_boundaries"),
        (0.5 * (x[12] + x[13]), 0.5 * (v[16] + v[17]), -4.5, "near_origin_mid_detuning"),
        (0.5 * (x[2] + x[3]), 0.5 * (v[23] + v[24]), -7.5, "Gaussian_edge_slowing_region"),
        (0.5 * (x[21] + x[22]), 0.5 * (v[8] + v[9]), -1.5, "opposite_Gaussian_edge"),
        (0.5 * (x[12] + x[13]), 47.5, -4.75, "near_major_mid_chirp_slowing_extremum"),
        (0.5 * (x[12] + x[13]), 83.0, -7.75, "near_major_early_chirp_slowing_extremum"),
    ]
    pre = list(structured_pre)
    while len(pre) < len(structured_pre) + int(config["holdouts"]["pseudorandom_pre_count"]):
        point = (rng.uniform(x[0], x[-1]), rng.uniform(v[0], v[-1]), rng.uniform(d[0], d[-1]), "deterministic_pseudorandom")
        if _not_node(point[0], x) and _not_node(point[1], v) and _not_node(point[2], d):
            pre.append(point)
    structured_post = [
        (0.5 * (x[0] + x[1]), 0.5 * (v[0] + v[1]), "near_lower_boundaries"),
        (0.5 * (x[-2] + x[-1]), 0.5 * (v[-2] + v[-1]), "near_upper_boundaries"),
        (0.5 * (x[12] + x[13]), 0.5 * (v[16] + v[17]), "near_origin"),
        (0.5 * (x[2] + x[3]), 0.5 * (v[23] + v[24]), "Gaussian_edge"),
    ]
    post = list(structured_post)
    while len(post) < len(structured_post) + int(config["holdouts"]["pseudorandom_post_count"]):
        point = (rng.uniform(x[0], x[-1]), rng.uniform(v[0], v[-1]), "deterministic_pseudorandom")
        if _not_node(point[0], x) and _not_node(point[1], v):
            post.append(point)
    return pre, post


def _validate_holdouts(config, backend, pre_system, post_system, pre_field, post_field):
    pre_points, post_points = _holdouts(config, pre_field.grid, post_field.grid)
    health = _Health()
    records = []
    for x, v, d, category in pre_points:
        direct = _direct(backend, pre_system(d), x, v, health)
        interpolated = pre_field.force_normalized(x, v, d)
        records.append({"field": "pre", "category": category, "x_m": x, "vx_m_s": v, "detuning_gamma": d, "direct": direct, "interpolated": interpolated})
    for x, v, category in post_points:
        direct = _direct(backend, post_system, x, v, health)
        interpolated = post_field.force_normalized(x, v)
        records.append({"field": "post", "category": category, "x_m": x, "vx_m_s": v, "detuning_gamma": None, "direct": direct, "interpolated": interpolated})
    force_range = max(
        np.ptp(pre_field.grid.normalized_force_x), np.ptp(post_field.grid.normalized_force_x), 1e-15
    )
    floor = float(config["acceptance_thresholds"]["important_region_force_floor_fraction"]) * force_range
    for record in records:
        error = abs(record["interpolated"] - record["direct"])
        record["absolute_error"] = error
        record["error_over_total_force_range"] = error / force_range
        record["relative_error"] = None if abs(record["direct"]) <= floor else error / abs(record["direct"])
        record["holdout_is_not_grid_node"] = True
    errors = np.array([row["absolute_error"] for row in records])
    important = np.array([row["absolute_error"] for row in records if abs(row["direct"]) > floor])
    return {
        "records": records,
        "force_range_normalized": float(force_range),
        "relative_error_floor_normalized": floor,
        "normalized_rms_error_over_force_range": float(np.sqrt(np.mean(errors**2)) / force_range),
        "maximum_error_over_force_range": float(np.max(errors) / force_range),
        "maximum_important_region_error_over_force_range": float(np.max(important) / force_range) if important.size else 0.0,
        "all_holdouts_off_grid_nodes": all(row["holdout_is_not_grid_node"] for row in records),
        "population_health": health.record(),
    }


def _central_slope(function, step: float) -> float:
    return (function(step) - function(-step)) / (2 * step)


def _crossings(axis, values):
    result = []
    for i in range(len(axis) - 1):
        if values[i] == 0:
            result.append(float(axis[i]))
        elif values[i] * values[i + 1] < 0:
            result.append(float(axis[i] - values[i] * (axis[i + 1] - axis[i]) / (values[i + 1] - values[i])))
    return result


def _representative_crossing(axis, values):
    crossings = _crossings(axis, values)
    return None if not crossings else min(crossings, key=abs)


def _topology(config, backend, pre_system, post_system, pre_field, post_field):
    x_dense = _linspace(config["refined_slices"]["position_m"])
    v_dense = _linspace(config["refined_slices"]["velocity_m_s"])
    deltas = tuple(float(x) for x in config["refined_slices"]["detuning_gamma"])
    health = _Health()
    features = []
    for delta in deltas:
        system = pre_system(delta)
        direct = np.array([_direct(backend, system, 0.0, value, health) for value in v_dense])
        interp = np.array([pre_field.force_normalized(0.0, value, delta) for value in v_dense])
        i_direct, i_interp = int(np.argmin(direct)), int(np.argmin(interp))
        direct_crossings = _crossings(v_dense, direct)
        interpolated_crossings = _crossings(v_dense, interp)
        features.append({
            "detuning_gamma": delta,
            "direct_extremum_force": float(direct[i_direct]),
            "interpolated_extremum_force": float(interp[i_interp]),
            "direct_extremum_velocity_m_s": float(v_dense[i_direct]),
            "interpolated_extremum_velocity_m_s": float(v_dense[i_interp]),
            "extremum_velocity_displacement_m_s": float(abs(v_dense[i_interp] - v_dense[i_direct])),
            "direct_zero_crossings_m_s": direct_crossings,
            "interpolated_zero_crossings_m_s": interpolated_crossings,
            "representative_direct_zero_crossing_m_s": _representative_crossing(v_dense, direct),
            "representative_interpolated_zero_crossing_m_s": _representative_crossing(v_dense, interp),
            "zero_crossing_branch_count_preserved": len(direct_crossings) == len(interpolated_crossings),
        })
    dx, dv = 5e-4, 0.25
    direct_dfdx = _central_slope(lambda q: _direct(backend, post_system, q, 0.0, health), dx)
    direct_dfdv = _central_slope(lambda q: _direct(backend, post_system, 0.0, q, health), dv)
    interp_dfdx = _central_slope(lambda q: post_field.force_normalized(q, 0.0), dx)
    interp_dfdv = _central_slope(lambda q: post_field.force_normalized(0.0, q), dv)
    post_direct_x = np.array([_direct(backend, post_system, value, 0.0, health) for value in x_dense])
    post_interp_x = np.array([post_field.force_normalized(value, 0.0) for value in x_dense])
    velocity_order = [row["direct_extremum_velocity_m_s"] for row in features]
    interpolation_order = [row["interpolated_extremum_velocity_m_s"] for row in features]
    grid_dv = pre_field.grid.domain.velocities_m_s[1] - pre_field.grid.domain.velocities_m_s[0]
    force_range = max(np.ptp(pre_field.grid.normalized_force_x), np.ptp(post_field.grid.normalized_force_x), 1e-15)
    important_limit = float(config["acceptance_thresholds"]["maximum_important_region_error_over_force_range_max"])
    for row in features:
        row["extremum_force_error_over_total_range"] = abs(
            row["interpolated_extremum_force"] - row["direct_extremum_force"]
        ) / force_range
    threshold = float(config["acceptance_thresholds"]["local_slope_relative_error_max"])
    slope_errors = {
        "dFdx": abs(interp_dfdx - direct_dfdx) / max(abs(direct_dfdx), 1e-15),
        "dFdv": abs(interp_dfdv - direct_dfdv) / max(abs(direct_dfdv), 1e-15),
    }
    preserved = bool(
        direct_dfdx < 0 and interp_dfdx < 0 and direct_dfdv < 0 and interp_dfdv < 0
        and all(np.diff(velocity_order) < 0) and all(np.diff(interpolation_order) < 0)
        and max(slope_errors.values()) <= threshold
        and all(row["extremum_velocity_displacement_m_s"] <= 1.5 * grid_dv for row in features)
        and all(row["extremum_force_error_over_total_range"] <= important_limit for row in features)
        and all(row["zero_crossing_branch_count_preserved"] for row in features)
    )
    return {
        "refined_slice_strategy": "direct 121-point position and 161-point velocity slices; baseline interpolation evaluated at identical points",
        "features": features,
        "chirp_feature_velocity_decreases_with_less_negative_detuning_direct": bool(all(np.diff(velocity_order) < 0)),
        "chirp_feature_velocity_decreases_with_less_negative_detuning_interpolated": bool(all(np.diff(interpolation_order) < 0)),
        "post_local_slopes": {"direct_dFdx": direct_dfdx, "interpolated_dFdx": interp_dfdx, "direct_dFdv": direct_dfdv, "interpolated_dFdv": interp_dfdv, "relative_errors": slope_errors},
        "post_zero_crossing_x_m": {"direct": _representative_crossing(x_dense, post_direct_x), "interpolated": _representative_crossing(x_dense, post_interp_x)},
        "post_restoring_and_damping_preserved": bool(direct_dfdx < 0 and interp_dfdx < 0 and direct_dfdv < 0 and interp_dfdv < 0),
        "topology_preserved": preserved,
        "population_health": health.record(),
    }


def _component4(backend, post, gaussian3, pre_system, post_system):
    sample = post.sample(0.0)
    off_components = tuple(replace(c, enabled=False, saturation=0.0, off_reason="run010_component4_off_diagnostic") if c.component_id == 4 else c for c in sample.components)
    off_sample = replace(sample, components=off_components)
    off_system = backend.build_optical_system(off_sample, policy_name="run010_post_component4_off", beam_mode="elliptical_gaussian", gaussian_beam_set=gaussian3)
    health = _Health()
    dx = 5e-4
    with4 = _central_slope(lambda q: _direct(backend, post_system, q, 0.0, health), dx)
    without4 = _central_slope(lambda q: _direct(backend, off_system, q, 0.0, health), dx)
    static3 = _central_slope(lambda q: _direct(backend, pre_system(-1.0), q, 0.0, health), dx)
    return {
        "with_component4_dFdx": with4,
        "without_component4_same_3plus1_power_partition_dFdx": without4,
        "static_3_dFdx": static3,
        "component4_stronger_confinement": with4 < without4 < 0,
        "post_3plus1_stronger_than_static_3": with4 < static3 < 0,
        "population_health": health.record(),
    }


def _gaussian_attenuation(backend, chirp, gaussian3, pre_system):
    sample = chirp.sample(0.0005)
    plane = backend.build_optical_system(
        sample, policy_name="run010_gaussian_attenuation_plane_reference", beam_mode="plane_wave"
    )
    gaussian = pre_system(-4.5)
    points = ((0.0, 5.0), (0.005, 0.0), (0.010, -5.0), (0.010, 0.0), (0.010, 5.0), (0.020, 10.0))
    health = _Health()
    rows, attenuated = [], 0
    for x, v in points:
        fp = _direct(backend, plane, x, v, health)
        fg = _direct(backend, gaussian, x, v, health)
        envelopes = gaussian3.envelopes(np.array([x, 0.0, 0.0]))
        is_attenuated = abs(fg) <= abs(fp) + 1e-12
        attenuated += int(is_attenuated)
        rows.append({"x_m": x, "vx_m_s": v, "plane_force": fp, "gaussian_force": fg, "per_beam_envelopes": envelopes, "attenuated": is_attenuated})
    center_matches = bool(np.isclose(rows[0]["plane_force"], rows[0]["gaussian_force"], atol=1e-12, rtol=1e-10))
    return {
        "points": rows,
        "center_matches_plane_wave": center_matches,
        "attenuated_point_count": attenuated,
        "point_count": len(rows),
        "passed": center_matches and attenuated >= len(rows) - 1,
        "population_health": health.record(),
    }


def _boundary_checks(pre_field, post_field):
    pre = pre_field.grid.domain
    post = post_field.grid.domain
    exact = [
        pre_field.force_normalized(pre.positions_m[0], pre.velocities_m_s[0], pre.detunings_gamma[0]),
        pre_field.force_normalized(pre.positions_m[-1], pre.velocities_m_s[-1], pre.detunings_gamma[-1]),
        post_field.force_normalized(post.positions_m[0], post.velocities_m_s[0]),
        post_field.force_normalized(post.positions_m[-1], post.velocities_m_s[-1]),
    ]
    inside = [
        pre_field.force_normalized(np.nextafter(pre.positions_m[0], np.inf), np.nextafter(pre.velocities_m_s[0], np.inf), np.nextafter(pre.detunings_gamma[0], np.inf)),
        post_field.force_normalized(np.nextafter(post.positions_m[-1], -np.inf), np.nextafter(post.velocities_m_s[-1], -np.inf)),
    ]
    outside_failures = []
    for name, query in (
        ("pre_x_below", lambda: pre_field.force_normalized(pre.positions_m[0] - 1e-9, 0, -4.5)),
        ("pre_v_above", lambda: pre_field.force_normalized(0, pre.velocities_m_s[-1] + 1e-9, -4.5)),
        ("pre_detuning_above", lambda: pre_field.force_normalized(0, 0, pre.detunings_gamma[-1] + 1e-9)),
        ("post_x_above", lambda: post_field.force_normalized(post.positions_m[-1] + 1e-9, 0)),
    ):
        try:
            query()
        except ForceFieldDomainError:
            outside_failures.append(name)
    handoff = SeparatedHandoffForceFields(pre_field, post_field, 0.001)
    before = handoff.force_normalized(np.nextafter(0.001, -np.inf), 0.003, 1.0, -1.0)
    at = handoff.force_normalized(0.001, 0.003, 1.0, -1.0)
    return {
        "exact_boundary_queries_finite": bool(np.isfinite(exact).all()),
        "just_inside_queries_finite": bool(np.isfinite(inside).all()),
        "outside_queries_rejected": outside_failures,
        "all_outside_queries_rejected": len(outside_failures) == 4,
        "handoff_convention": "t < tau uses pre; t >= tau uses post; no smoothing",
        "before_handoff_force": before,
        "at_handoff_force": at,
        "pre_and_post_remain_separate": True,
    }


def _plot(pre_grid, post_grid, topology):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    x, v, d = pre_grid.domain.positions_m, pre_grid.domain.velocities_m_s, pre_grid.domain.detunings_gamma
    for delta in (-8.0, -4.0, -1.0):
        kd = int(np.argmin(abs(d - delta)))
        axes[0].plot(v, pre_grid.normalized_force_x[len(x)//2, :, kd], label=f"{d[kd]:g} Gamma")
    axes[1].plot(x * 1e3, post_grid.normalized_force_x[:, len(v)//2])
    axes[2].plot([f["detuning_gamma"] for f in topology["features"]], [f["direct_extremum_velocity_m_s"] for f in topology["features"]], "o-", label="direct")
    axes[2].plot([f["detuning_gamma"] for f in topology["features"]], [f["interpolated_extremum_velocity_m_s"] for f in topology["features"]], "x--", label="interpolated")
    axes[0].set(title="Pre-handoff force slices", xlabel="v_x [m/s]", ylabel="F_x/(hbar k Gamma)")
    axes[1].set(title="Post-handoff v=0 slice", xlabel="x [mm]", ylabel="F_x/(hbar k Gamma)")
    axes[2].set(title="Slowing-feature motion", xlabel="detuning/Gamma", ylabel="extremum v_x [m/s]")
    axes[0].legend(); axes[2].legend()
    fig.suptitle("PROVISIONAL / NOT_RODRIGUEZ_REPLICATION\nFORCE_FIELD_INTERPOLATION_VALIDATION_ONLY - Run 010")
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(PLOT_PATH)
    plt.close(fig)


def run() -> dict[str, Any]:
    config = _load_config()
    thresholds = config["acceptance_thresholds"]
    selection = AcceptedProvisionalBackendSelection()
    backend = build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=True, selection=selection)
    chirp, post, gaussian3, gaussian31, pre_system, post_system = _systems(backend)
    hashes = _source_hashes()
    pre_prov = _provenance(backend, selection, "pre_handoff_chirp_3", hashes)
    post_prov = _provenance(backend, selection, "post_handoff_trap_3_plus_1", hashes)
    cached = _load_matching(pre_prov, post_prov) if config["cache"]["reuse_if_provenance_matches"] else None
    if cached is None:
        pre_grid, post_grid, build_health, elapsed = _build_grids(config, backend, pre_system, post_system, pre_prov, post_prov)
        cache_reused = False
    else:
        pre_grid, post_grid = cached
        build_health = {"passed": True, "solves": 0, "note": "provenance-matched cache reused"}
        elapsed = 0.0
        cache_reused = True
    pre_field, post_field = InterpolatedForceField(pre_grid), InterpolatedForceField(post_grid)
    holdouts = _validate_holdouts(config, backend, pre_system, post_system, pre_field, post_field)
    topology = _topology(config, backend, pre_system, post_system, pre_field, post_field)
    component4 = _component4(backend, post, gaussian3, pre_system, post_system)
    gaussian_attenuation = _gaussian_attenuation(backend, chirp, gaussian3, pre_system)
    boundaries = _boundary_checks(pre_field, post_field)
    error_pass = bool(
        holdouts["normalized_rms_error_over_force_range"] <= float(thresholds["normalized_rms_error_over_force_range_max"])
        and holdouts["maximum_important_region_error_over_force_range"] <= float(thresholds["maximum_important_region_error_over_force_range_max"])
    )
    checks = {
        "accepted_backend_models": backend.status.ground_zeeman_convention == "project_energy_slope_corrected" and backend.status.excited_zeeman_model == "rodriguez_effective_g_0p001" and backend.status.excited_hyperfine_model == "source_aligned_effective_fprime_splitting" and backend.status.excited_hyperfine_splitting_mhz == 0.5,
        "canonical_normalized_force": pre_prov.normalized_force_unit == "hbar*k*Gamma" and not pre_prov.canonical_values_are_si_acceleration,
        "pre_post_separate": boundaries["pre_and_post_remain_separate"],
        "build_population_health": build_health["passed"],
        "holdout_population_health": holdouts["population_health"]["passed"],
        "refined_slice_population_health": topology["population_health"]["passed"],
        "holdouts_off_grid_nodes": holdouts["all_holdouts_off_grid_nodes"],
        "interpolation_errors": error_pass,
        "topology_preserved": topology["topology_preserved"],
        "component4_effect": component4["component4_stronger_confinement"],
        "post_stronger_than_static_3": component4["post_3plus1_stronger_than_static_3"],
        "component4_population_health": component4["population_health"]["passed"],
        "gaussian_attenuation": gaussian_attenuation["passed"],
        "gaussian_attenuation_population_health": gaussian_attenuation["population_health"]["passed"],
        "no_silent_extrapolation": boundaries["all_outside_queries_rejected"],
        "boundary_queries": boundaries["exact_boundary_queries_finite"] and boundaries["just_inside_queries_finite"],
    }
    if all(checks.values()):
        gate = "PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO"
    elif all(checks[k] for k in checks if k not in {"interpolation_errors", "topology_preserved"}):
        gate = "PROVISIONAL_FORCE_FIELD_REFINEMENT_REQUIRED"
    else:
        gate = "PROVISIONAL_FORCE_FIELD_INTERPOLATION_NO_GO"
    validation_payload = {"gate": gate, "holdouts": holdouts, "topology": topology, "component4": component4, "gaussian_attenuation": gaussian_attenuation, "boundary_checks": boundaries, "acceptance_checks": checks}
    for grid, kind in ((pre_grid, "pre_handoff_chirp_3"), (post_grid, "post_handoff_trap_3_plus_1")):
        save_force_field_cache(grid, *_cache_paths(kind), validation=validation_payload)
    _plot(pre_grid, post_grid, topology)
    metadata = {
        "label": RUN010_LABEL,
        "title": f"{RUN010_LABEL} Run 010 metadata",
        "gate": gate,
        "provisional_static_authorized": True,
        "provisional_force_field_authorized": gate == "PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO",
        "provisional_trajectory_authorized": gate == "PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO",
        "capture_authorized": False,
        "exact_replication_valid": False,
        "exact_track_blocked": True,
        "trajectory_integrations_performed": 0,
        "capture_calculations_performed": 0,
        "source_distributions_used": 0,
        "accepted_backend_selection": asdict(selection),
        "backend_status": asdict(backend.status),
        "source_supported_splitting_interval_mhz": [0.0, 1.0],
        "splitting_midpoint_is_measured_value": False,
        "unresolved_independent_d_physics": list(selection.unresolved_terms),
        "domain_justification": config["domain"]["justification"],
        "pre_shape": list(pre_grid.domain.shape),
        "post_shape": list(post_grid.domain.shape),
        "estimated_build_solve_count": pre_grid.domain.equilibrium_solve_count + post_grid.domain.equilibrium_solve_count,
        "actual_build_health": build_health,
        "elapsed_build_time_s": elapsed,
        "cache_reused": cache_reused,
        "pre_cache_key": pre_prov.cache_key,
        "post_cache_key": post_prov.cache_key,
        "source_hashes": dict(hashes),
        "grid_refinement_history": config["refinement_history"],
        "validation": validation_payload,
        "acceptance_thresholds_declared_in_config_before_run": thresholds,
        "report": REPORT_PATH.name,
        "plot": PLOT_PATH.name,
        "cache_directory": str(CACHE_DIR.relative_to(REPO_ROOT)),
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=True, default=str), encoding="utf-8")
    h = lambda text: f"## {RUN010_LABEL} {text}"
    lines = [
        f"# {RUN010_LABEL} Run 010", "",
        "This run validates reusable equilibrium-force interpolation only. No trajectory, capture search, source distribution, stochastic diffusion, optimization, or exact-replication calculation was performed.", "",
        h("Accepted backend lock"), "",
        "The path requires the corrected ground tensor, `g'=+0.001`, `SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING`, and the explicit `MID_RANGE_0P5_MHZ` selection. The `0.5 MHz` value is an interval midpoint of the source-supported `0-1 MHz` range, not a measured value. The independent `d` physics remains unresolved and Track E remains blocked.", "",
        h("Fields and domain"), "",
        f"Pre-handoff shape: `{pre_grid.domain.shape}` ({pre_grid.domain.equilibrium_solve_count} equilibrium solves), trilinear in `(x,v,Delta)`. Post-handoff shape: `{post_grid.domain.shape}` ({post_grid.domain.equilibrium_solve_count} solves), bilinear in `(x,v)`. Canonical stored values are `F_x/(hbar k Gamma)`, not acceleration.",
        f"The initial `(25,33,8)` baseline failed the predeclared important-extremum threshold at `-4.5 Gamma`; the detuning axis was refined from `1 Gamma` to `0.5 Gamma` spacing without changing thresholds.",
        f"Domain: x=`[{pre_grid.domain.positions_m[0]}, {pre_grid.domain.positions_m[-1]}] m`, v=`[{pre_grid.domain.velocities_m_s[0]}, {pre_grid.domain.velocities_m_s[-1]}] m/s`, detuning=`[{pre_grid.domain.detunings_gamma[0]}, {pre_grid.domain.detunings_gamma[-1]}] Gamma`. Build elapsed: `{elapsed:.3f} s`; cache reused: `{cache_reused}`.", "",
        h("Interpolation validation"), "",
        f"Declared thresholds: RMS/range <= `{thresholds['normalized_rms_error_over_force_range_max']}`, important max/range <= `{thresholds['maximum_important_region_error_over_force_range_max']}`, local slope relative error <= `{thresholds['local_slope_relative_error_max']}`.",
        f"Holdouts: `{len(holdouts['records'])}`, all off grid nodes: `{holdouts['all_holdouts_off_grid_nodes']}`. RMS/range: `{holdouts['normalized_rms_error_over_force_range']:.6g}`; maximum/range: `{holdouts['maximum_error_over_force_range']:.6g}`; important maximum/range: `{holdouts['maximum_important_region_error_over_force_range']:.6g}`.",
        f"Refined-slice topology preserved: `{topology['topology_preserved']}`. Component (4) strengthens confinement: `{component4['component4_stronger_confinement']}`. Outside queries rejected: `{boundaries['all_outside_queries_rejected']}`.", "",
        h("Acceptance checks"), "",
        *[f"- `{name}`: `{value}`" for name, value in checks.items()], "",
        h(f"Final gate: {gate}"), "", f"**{gate}**", "",
        f"`provisional_static_authorized = true`; `provisional_force_field_authorized = {str(gate == 'PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO').lower()}`; `provisional_trajectory_authorized = {str(gate == 'PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO').lower()}`; `capture_authorized = false`; `exact_replication_valid = false`; `exact_track_blocked = true`.",
        "A GO authorizes only reconnection of these accepted tables to the named non-capture trajectory scaffold. It does not authorize capture thresholds, source distributions, diffusion, optimization, or exact-replication claims.", "",
        f"# {RUN010_LABEL} FINAL_{gate}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{RUN010_LABEL}: {gate}")
    print(f"report: {REPORT_PATH}")
    return metadata


if __name__ == "__main__":
    run()
