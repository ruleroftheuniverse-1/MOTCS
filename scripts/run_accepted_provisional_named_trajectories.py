"""Run 011: accepted force-field named trajectories, without capture inference."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from mgf_mot.accepted_trajectory import (
    RUN011_LABEL,
    AcceptedTrajectoryResult,
    IntegrationTerminationStatus,
    InterpolatedRateEquationTrajectoryForce,
    integrate_accepted_force_field_trajectory,
)
from mgf_mot.gaussian_beams import build_rodriguez_gaussian_beam_set, load_gaussian_envelope_config
from mgf_mot.named_protocol import load_rodriguez_named_trajectory_protocol
from mgf_mot.outcomes import OutcomeLabel, classify_trajectory
from mgf_mot.policies import load_policy


CONFIG_PATH = REPO_ROOT / "configs" / "provisional_named_trajectory_run_011.yaml"
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
REPORT_PATH = OUTPUT_DIR / "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_run_011.md"
METADATA_PATH = OUTPUT_DIR / f"{RUN011_LABEL}_metadata.json"
COMBINED_PLOT_PATH = OUTPUT_DIR / f"{RUN011_LABEL}_combined_comparison.png"
PATHWISE_PATH = OUTPUT_DIR / f"{RUN011_LABEL}_pathwise_interpolation_validation.json"


def _json(value):
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_config():
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if data["name"] != RUN011_LABEL:
        raise ValueError("Run 011 config label mismatch")
    return data


def _historical_hashes(config) -> dict[str, str]:
    result = {}
    for pattern in config["historical_artifacts"]["preserve_globs"]:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file():
                result[str(path.relative_to(REPO_ROOT))] = _hash(path)
    return result


def _crossings(result: AcceptedTrajectoryResult) -> list[float]:
    x, t = result.positions[:, 0], result.times_s
    rows = []
    for i in range(len(x) - 1):
        if x[i] == 0:
            rows.append(float(t[i]))
        elif x[i] * x[i + 1] < 0:
            rows.append(float(t[i] - x[i] * (t[i + 1] - t[i]) / (x[i + 1] - x[i])))
    return rows


def _closest(result):
    crossings = _crossings(result)
    if crossings:
        time = crossings[0]
        return 0.0, time, int(np.argmin(abs(result.times_s - time)))
    index = int(np.argmin(np.abs(result.positions[:, 0])))
    return float(abs(result.positions[index, 0])), float(result.times_s[index]), index


def _trapezoid_boolean_time(times, mask) -> float:
    if len(times) < 2:
        return 0.0
    return float(np.trapezoid(mask.astype(float), times))


def _qualitative(result, crossings, closest) -> str:
    if result.termination_status is IntegrationTerminationStatus.FORCE_FIELD_DOMAIN_EXIT:
        return "FORCE_FIELD_DOMAIN_EXIT"
    x, v = result.positions[:, 0], result.velocities[:, 0]
    if len(crossings) >= 2:
        return "CROSSED_AND_RETURNED"
    if len(crossings) == 1:
        if abs(x[-1]) <= 0.01 and abs(v[-1]) <= 1.0:
            return "REMAINED_NEAR_CENTER"
        return "CROSSED_WITHOUT_SETTLING"
    if np.any(v <= 0) and np.all(x < 0):
        return "TURNED_AROUND_BEFORE_CENTER"
    if v[-1] < v[0] and closest < abs(x[0]):
        return "SLOWED_BEFORE_CENTER"
    return "OTHER"


def _unit_consistency(result, adapter, config):
    if len(result.times_s) < 2:
        return {"passed": False, "reason": "fewer than two samples"}
    integrated_acceleration = float(result.cumulative_integrated_acceleration_x_m_s[-1])
    delta_v = float(result.velocities[-1, 0] - result.velocities[0, 0])
    impulse = float(result.cumulative_impulse_x_n_s[-1])
    momentum_change = float(adapter.force_units.mass.value_kg * delta_v)
    floor = float(config["unit_consistency"]["absolute_floor"])
    dv_rel = abs(delta_v - integrated_acceleration) / max(abs(delta_v), abs(integrated_acceleration), floor)
    momentum_rel = abs(momentum_change - impulse) / max(abs(momentum_change), abs(impulse), floor * adapter.force_units.mass.value_kg)
    passed = bool(
        dv_rel <= float(config["unit_consistency"]["velocity_change_vs_integrated_acceleration_relative_max"])
        and momentum_rel <= float(config["unit_consistency"]["momentum_change_vs_integrated_force_relative_max"])
        and result.metadata.force_conversion_count == 1
    )
    return {
        "delta_v_m_s": delta_v,
        "integrated_acceleration_m_s": integrated_acceleration,
        "relative_difference_delta_v": dv_rel,
        "momentum_change_kg_m_s": momentum_change,
        "integrated_force_impulse_n_s": impulse,
        "relative_difference_momentum": momentum_rel,
        "force_conversion_count": result.metadata.force_conversion_count,
        "passed": passed,
    }


def _diagnostics(name, gamma_over_k, result, outcome, adapter, protocol, config):
    crossings = _crossings(result)
    closest, closest_time, _ = _closest(result)
    tau = 0.001
    before = result.times_s <= tau
    impulse_before = float(result.cumulative_impulse_x_n_s[np.flatnonzero(before)[-1]])
    impulse_total = float(result.cumulative_impulse_x_n_s[-1])
    pos_bound = np.abs(result.positions[:, 0]) <= protocol.outcome_criteria.max_position
    vel_bound = np.abs(result.velocities[:, 0]) <= protocol.outcome_criteria.max_speed
    return {
        "label": RUN011_LABEL,
        "title": f"{RUN011_LABEL} {name} diagnostics",
        "name": name,
        "initial_velocity_gamma_over_k": gamma_over_k,
        "initial_velocity_m_s": float(result.velocities[0, 0]),
        "final_or_termination_time_s": float(result.times_s[-1]),
        "final_position_m": float(result.positions[-1, 0]),
        "final_velocity_m_s": float(result.velocities[-1, 0]),
        "minimum_absolute_distance_m": closest,
        "time_of_closest_approach_s": closest_time,
        "center_crossing_count": len(crossings),
        "center_crossing_times_s": crossings,
        "minimum_velocity_m_s": float(np.min(result.velocities[:, 0])),
        "maximum_velocity_m_s": float(np.max(result.velocities[:, 0])),
        "total_impulse_n_s": impulse_total,
        "impulse_before_handoff_n_s": impulse_before,
        "impulse_after_handoff_n_s": impulse_total - impulse_before,
        "force_field_domain_status": "inside_for_all_saved_queries" if result.domain_exit is None else "domain_exit_recorded",
        "domain_exit": None if result.domain_exit is None else asdict(result.domain_exit),
        "time_inside_position_bound_s": _trapezoid_boolean_time(result.times_s, pos_bound),
        "time_inside_velocity_bound_s": _trapezoid_boolean_time(result.times_s, vel_bound),
        "time_inside_both_bounds_s": _trapezoid_boolean_time(result.times_s, pos_bound & vel_bound),
        "final_dwell_window": {
            "start_s": outcome.dwell_start_s,
            "end_s": outcome.dwell_end_s,
            "sample_count": outcome.dwell_sample_count,
            "in_bounds_count": outcome.dwell_in_bounds_count,
            "in_bounds_fraction": outcome.dwell_in_bounds_fraction,
            "max_position_m": outcome.max_position_dwell,
            "max_speed_m_s": outcome.max_speed_dwell,
        },
        "official_provisional_outcome": outcome.label.value,
        "numerical_reason": outcome.numerical_reason,
        "integration_termination_status": result.termination_status.value,
        "qualitative_motion": _qualitative(result, crossings, closest),
        "unit_consistency": _unit_consistency(result, adapter, config),
    }


def _summary_for_convergence(result, outcome):
    closest, _, _ = _closest(result)
    crossings = _crossings(result)
    return {
        "final_position_m": float(result.positions[-1, 0]),
        "final_velocity_m_s": float(result.velocities[-1, 0]),
        "closest_approach_m": closest,
        "first_center_crossing_s": None if not crossings else crossings[0],
        "cumulative_impulse_n_s": float(result.cumulative_impulse_x_n_s[-1]),
        "outcome_label": outcome.label.value,
        "termination_status": result.termination_status.value,
    }


def _convergence_pair(baseline, refined, baseline_outcome, refined_outcome, thresholds):
    a, b = _summary_for_convergence(baseline, baseline_outcome), _summary_for_convergence(refined, refined_outcome)
    crossing_pass = (
        a["first_center_crossing_s"] is None and b["first_center_crossing_s"] is None
    ) or (
        a["first_center_crossing_s"] is not None and b["first_center_crossing_s"] is not None
        and abs(a["first_center_crossing_s"] - b["first_center_crossing_s"]) <= float(thresholds["center_crossing_time_difference_max_s"])
    )
    impulse_diff = abs(a["cumulative_impulse_n_s"] - b["cumulative_impulse_n_s"])
    impulse_rel = impulse_diff / max(abs(a["cumulative_impulse_n_s"]), abs(b["cumulative_impulse_n_s"]), float(thresholds["cumulative_impulse_absolute_floor_n_s"]))
    checks = {
        "final_position": abs(a["final_position_m"] - b["final_position_m"]) <= float(thresholds["final_position_difference_max_m"]),
        "final_velocity": abs(a["final_velocity_m_s"] - b["final_velocity_m_s"]) <= float(thresholds["final_velocity_difference_max_m_s"]),
        "closest_approach": abs(a["closest_approach_m"] - b["closest_approach_m"]) <= float(thresholds["closest_approach_difference_max_m"]),
        "center_crossing_time": crossing_pass,
        "cumulative_impulse": impulse_rel <= float(thresholds["cumulative_impulse_relative_difference_max"]),
        "outcome_label": a["outcome_label"] == b["outcome_label"],
        "termination_status": a["termination_status"] == b["termination_status"],
    }
    return {"baseline": a, "refined": b, "impulse_relative_difference": impulse_rel, "checks": checks, "passed": all(checks.values())}


def _direct_resources(adapter):
    gaussian_config = load_gaussian_envelope_config(REPO_ROOT / "configs" / "rodriguez_gaussian_baseline.yaml")
    gaussian3 = build_rodriguez_gaussian_beam_set(gaussian_config, (1.45, 1.45, 2.89, 0.0))
    gaussian31 = build_rodriguez_gaussian_beam_set(gaussian_config, (1.45, 1.45, 2.17, 0.72))
    return gaussian3, gaussian31


def _selected_indices(result):
    indices = {0, len(result.times_s) - 1, int(np.argmin(np.abs(result.positions[:, 0]))), int(0.75 * (len(result.times_s) - 1))}
    illuminated = np.flatnonzero(result.gaussian_envelope_mean >= 0.01)
    if illuminated.size:
        indices.add(int(illuminated[0]))
    pre = np.flatnonzero(result.times_s < 0.001)
    if pre.size:
        indices.add(int(pre[np.argmax(np.abs(result.normalized_forces_x[pre]))]))
        indices.add(int(pre[-1]))
    post = np.flatnonzero(result.times_s >= 0.001)
    if post.size:
        indices.add(int(post[0]))
    crossings = _crossings(result)
    if crossings:
        indices.add(int(np.argmin(abs(result.times_s - crossings[0]))))
    return sorted(indices)


def _pathwise(name, result, adapter, policy, gaussian3, gaussian31, config):
    before_hash = sha256(result.positions.tobytes() + result.velocities.tobytes()).hexdigest()
    force_range = max(np.ptp(adapter.pre.grid.normalized_force_x), np.ptp(adapter.post.grid.normalized_force_x), 1e-15)
    floor = float(config["pathwise_interpolation"]["relative_error_floor_fraction_of_force_range"]) * force_range
    rows = []
    for index in _selected_indices(result):
        t, x, v = float(result.times_s[index]), float(result.positions[index, 0]), float(result.velocities[index, 0])
        sample = policy.sample(t)
        if t < policy.handoff_time_s:
            system = adapter.backend.build_optical_system(sample, policy_name=f"run011_direct_{name}_{index}_pre", beam_mode="elliptical_gaussian", gaussian_beam_set=gaussian3)
        else:
            system = adapter.backend.build_optical_system(sample, policy_name=f"run011_direct_{name}_{index}_post", beam_mode="elliptical_gaussian", gaussian_beam_set=gaussian31)
        direct_result = adapter.backend.force_at(np.array([x, 0, 0]), np.array([v, 0, 0]), system, collect_solver_diagnostics=True)
        direct = float(direct_result.normalized_force[0])
        interpolated = float(result.normalized_forces_x[index])
        error = abs(interpolated - direct)
        rows.append({
            "label": RUN011_LABEL, "title": f"{RUN011_LABEL} {name} path state {index}",
            "sample_index": index, "time_s": t, "position_m": x, "velocity_m_s": v,
            "segment": result.policy_segments[index], "detuning_gamma": float(result.chirp_detunings_gamma[index]),
            "direct_normalized_force": direct, "interpolated_normalized_force": interpolated,
            "absolute_error": error, "error_over_force_range": error / force_range,
            "relative_error": None if abs(direct) <= floor else error / abs(direct),
            "population_health": {
                "minimum_population": direct_result.population_minimum,
                "normalization_error": abs(direct_result.population_sum - 1),
                "residual_linf": direct_result.steady_state_residual_linf,
                "fallback": direct_result.singular_solver_fallback_used,
                "passed": direct_result.population_minimum >= -1e-10 and abs(direct_result.population_sum - 1) <= 1e-9 and direct_result.steady_state_residual_linf <= 1e-9 and not direct_result.singular_solver_fallback_used,
            },
        })
    after_hash = sha256(result.positions.tobytes() + result.velocities.tobytes()).hexdigest()
    errors = np.array([r["absolute_error"] for r in rows])
    rms = float(np.sqrt(np.mean(errors**2)) / force_range)
    maximum = float(np.max(errors) / force_range)
    thresholds = config["pathwise_interpolation"]
    if rms <= float(thresholds["pass_rms_error_over_force_range_max"]) and maximum <= float(thresholds["pass_maximum_error_over_force_range_max"]) and all(r["population_health"]["passed"] for r in rows):
        gate = "PATHWISE_INTERPOLATION_PASS"
    elif rms <= float(thresholds["warning_rms_error_over_force_range_max"]) and maximum <= float(thresholds["warning_maximum_error_over_force_range_max"]):
        gate = "PATHWISE_INTERPOLATION_WARNING"
    else:
        gate = "PATHWISE_INTERPOLATION_FAIL"
    return {"label": RUN011_LABEL, "title": f"{RUN011_LABEL} {name} pathwise validation", "gate": gate, "force_range_normalized": float(force_range), "relative_error_floor": floor, "normalized_rms_error_over_range": rms, "maximum_error_over_range": maximum, "direct_validation_did_not_alter_trajectory": before_hash == after_hash, "records": rows}


def _save_trajectory(name, result, diagnostics, outcome, pathwise):
    stem = f"{RUN011_LABEL}_{name}"
    npz_path = OUTPUT_DIR / f"{stem}.npz"
    np.savez_compressed(
        npz_path, times_s=result.times_s, positions_m=result.positions,
        velocities_m_s=result.velocities, normalized_force_x=result.normalized_forces_x,
        force_x_n=result.forces_x_n, acceleration_x_m_s2=result.accelerations_x_m_s2,
        cumulative_impulse_x_n_s=result.cumulative_impulse_x_n_s,
        cumulative_integrated_acceleration_x_m_s=result.cumulative_integrated_acceleration_x_m_s,
        chirp_detunings_gamma=result.chirp_detunings_gamma,
        component_detunings_gamma=result.component_detunings_gamma,
        component_saturations=result.component_saturations,
        component_active=result.component_active,
        policy_segments=np.asarray(result.policy_segments), field_selections=np.asarray(result.field_selections),
        gaussian_envelope_mean=result.gaussian_envelope_mean,
        gaussian_envelope_minimum=result.gaussian_envelope_minimum,
        gaussian_envelope_maximum=result.gaussian_envelope_maximum,
    )
    metadata = {
        "label": RUN011_LABEL, "title": f"{RUN011_LABEL} {name} metadata",
        "trajectory_metadata": asdict(result.metadata), "diagnostics": diagnostics,
        "outcome": asdict(outcome), "termination_status": result.termination_status.value,
        "domain_exit": None if result.domain_exit is None else asdict(result.domain_exit),
        "pathwise_interpolation": pathwise, "array_file": npz_path.name,
        "array_sha256": _hash(npz_path), "replication_valid": False,
    }
    meta_path = OUTPUT_DIR / f"{stem}_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True, default=_json), encoding="utf-8")
    return npz_path, meta_path


def _save_plot(name, result, diagnostics, protocol):
    import matplotlib.pyplot as plt
    path = OUTPUT_DIR / f"{RUN011_LABEL}_{name}_diagnostics.png"
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    t_ms = result.times_s * 1e3
    axes[0,0].plot(t_ms, result.positions[:,0] * 1e3); axes[0,0].axhline(0,color="k",lw=.8); axes[0,0].axhline(10,color="gray",ls=":"); axes[0,0].axhline(-10,color="gray",ls=":"); axes[0,0].set(xlabel="t [ms]",ylabel="x [mm]",title="Position")
    axes[0,1].plot(t_ms, result.velocities[:,0]); axes[0,1].axhline(1,color="gray",ls=":"); axes[0,1].axhline(-1,color="gray",ls=":"); axes[0,1].set(xlabel="t [ms]",ylabel="v_x [m/s]",title="Velocity")
    axes[1,0].plot(result.positions[:,0]*1e3,result.velocities[:,0]); axes[1,0].axvline(0,color="k",lw=.8); axes[1,0].set(xlabel="x [mm]",ylabel="v_x [m/s]",title="Phase space")
    axes[1,1].plot(t_ms,result.cumulative_impulse_x_n_s); axes[1,1].set(xlabel="t [ms]",ylabel="impulse [N s]",title="Cumulative impulse")
    for axis in axes.flat: axis.axvline(1.0,color="tab:red",ls="--",lw=.8)
    if result.domain_exit is not None:
        for axis in axes.flat[:2]: axis.axvline(result.domain_exit.time_s*1e3,color="purple",ls=":")
    fig.suptitle(f"{RUN011_LABEL}\n{name}: {diagnostics['official_provisional_outcome']} / {result.termination_status.value}",fontsize=10)
    fig.tight_layout(rect=(0,0,1,.92)); fig.savefig(path); plt.close(fig)
    return path


def _save_combined(results, diagnostics):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1,2,figsize=(14,5))
    for name, result in results.items():
        label=f"{name}: {diagnostics[name]['qualitative_motion']}"
        axes[0].plot(result.times_s*1e3,result.positions[:,0]*1e3,label=label)
        axes[1].plot(result.times_s*1e3,result.velocities[:,0],label=label)
        if result.domain_exit is not None:
            axes[0].scatter(result.times_s[-1]*1e3,result.positions[-1,0]*1e3,marker="x",s=45)
            axes[1].scatter(result.times_s[-1]*1e3,result.velocities[-1,0],marker="x",s=45)
    axes[0].axhline(0,color="k",lw=.8); axes[0].axhline(10,color="gray",ls=":"); axes[0].axhline(-10,color="gray",ls=":")
    axes[1].axhline(1,color="gray",ls=":"); axes[1].axhline(-1,color="gray",ls=":")
    for axis in axes: axis.axvline(1,color="tab:red",ls="--"); axis.legend(fontsize=6)
    axes[0].set(xlabel="t [ms]",ylabel="x [mm]",title="Named positions"); axes[1].set(xlabel="t [ms]",ylabel="v_x [m/s]",title="Named velocities")
    fig.suptitle(f"{RUN011_LABEL}\ncombined named-trajectory comparison",fontsize=10)
    fig.tight_layout(rect=(0,0,1,.91)); fig.savefig(COMBINED_PLOT_PATH); plt.close(fig)


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    historical_before = _historical_hashes(config)
    protocol = load_rodriguez_named_trajectory_protocol(REPO_ROOT / config["protocol_config"])
    policy = load_policy(REPO_ROOT / config["handoff_policy_config"])
    expected_velocities = (2.0, 4.0, 6.0, 7.5, 9.0)
    if tuple(v.gamma_over_k for v in protocol.named_velocities) != expected_velocities:
        raise RuntimeError("named velocity set changed")
    adapter = InterpolatedRateEquationTrajectoryForce(
        repo_root=REPO_ROOT, explicit_provisional_opt_in=True,
        acknowledge_midpoint_not_measured=True,
    )
    baseline_dt = float(config["integration"]["baseline_time_step_s"])
    refined_dt = float(config["integration"]["refined_time_step_s"])
    duration = float(config["integration"]["duration_s"])
    convergence = {}
    cached_runs = {}
    for named, initial in zip(protocol.named_velocities, protocol.initial_states()):
        if named.gamma_over_k not in config["convergence"]["named_velocities_gamma_over_k"]:
            continue
        baseline = integrate_accepted_force_field_trajectory(adapter=adapter,policy=policy,initial_state=initial,duration_s=duration,timestep_s=baseline_dt)
        refined = integrate_accepted_force_field_trajectory(adapter=adapter,policy=policy,initial_state=initial,duration_s=duration,timestep_s=refined_dt)
        bo, ro = classify_trajectory(baseline, protocol.outcome_criteria), classify_trajectory(refined, protocol.outcome_criteria)
        convergence[named.name] = _convergence_pair(baseline,refined,bo,ro,config["convergence"])
        cached_runs[(named.name,"baseline")], cached_runs[(named.name,"refined")] = baseline, refined
    convergence_passed = all(row["passed"] for row in convergence.values())
    selected_dt = baseline_dt if convergence_passed else refined_dt
    results, outcomes, diagnostics = {}, {}, {}
    for named, initial in zip(protocol.named_velocities, protocol.initial_states()):
        result = cached_runs.get((named.name,"baseline" if selected_dt == baseline_dt else "refined"))
        if result is None:
            result = integrate_accepted_force_field_trajectory(adapter=adapter,policy=policy,initial_state=initial,duration_s=duration,timestep_s=selected_dt)
        outcome = classify_trajectory(result, protocol.outcome_criteria)
        results[named.name], outcomes[named.name] = result, outcome
        diagnostics[named.name] = _diagnostics(named.name,named.gamma_over_k,result,outcome,adapter,protocol,config)
    gaussian3, gaussian31 = _direct_resources(adapter)
    pathwise = {name:_pathwise(name,result,adapter,policy,gaussian3,gaussian31,config) for name,result in results.items()}
    path_gates = [row["gate"] for row in pathwise.values()]
    overall_path_gate = "PATHWISE_INTERPOLATION_FAIL" if "PATHWISE_INTERPOLATION_FAIL" in path_gates else "PATHWISE_INTERPOLATION_WARNING" if "PATHWISE_INTERPOLATION_WARNING" in path_gates else "PATHWISE_INTERPOLATION_PASS"
    PATHWISE_PATH.write_text(json.dumps({"label":RUN011_LABEL,"title":f"{RUN011_LABEL} pathwise validation","overall_gate":overall_path_gate,"trajectories":pathwise},indent=2,sort_keys=True,default=_json),encoding="utf-8")
    files={}
    for name,result in results.items():
        arrays,meta=_save_trajectory(name,result,diagnostics[name],outcomes[name],pathwise[name])
        plot=_save_plot(name,result,diagnostics[name],protocol)
        files[name]={"arrays":arrays.name,"metadata":meta.name,"plot":plot.name}
    _save_combined(results,diagnostics)
    historical_after = _historical_hashes(config)
    historical_unchanged = historical_before == historical_after
    all_finite = all(np.isfinite(r.positions).all() and np.isfinite(r.velocities).all() and np.isfinite(r.normalized_forces_x).all() for r in results.values())
    units_pass = all(d["unit_consistency"]["passed"] for d in diagnostics.values())
    event_pass = all((r.termination_status is not IntegrationTerminationStatus.COMPLETED_TIME_INTERVAL) or r.handoff_event_times_s == (0.001,) for r in results.values())
    no_silent_domain = all(r.termination_status is not IntegrationTerminationStatus.FORCE_FIELD_DOMAIN_EXIT or r.domain_exit is not None for r in results.values())
    checks={
        "accepted_cache_and_backend_provenance": adapter.backend.status.excited_zeeman_model=="rodriguez_effective_g_0p001" and adapter.backend.status.excited_hyperfine_splitting_mhz==0.5,
        "si_conversion_exactly_once": units_pass,
        "event_aware_handoff_exact": event_pass,
        "timestep_convergence": convergence_passed,
        "pathwise_interpolation": overall_path_gate in ("PATHWISE_INTERPOLATION_PASS","PATHWISE_INTERPOLATION_WARNING"),
        "no_silent_domain_extrapolation": no_silent_domain,
        "finite_saved_arrays": all_finite,
        "explicit_non_capture_outcomes": all(o.label in set(OutcomeLabel) for o in outcomes.values()),
        "historical_run008_unchanged": historical_unchanged,
    }
    if all(checks.values()): gate="PROVISIONAL_NAMED_TRAJECTORY_GO"
    elif checks["accepted_cache_and_backend_provenance"] and checks["si_conversion_exactly_once"] and checks["no_silent_domain_extrapolation"]:
        gate="PROVISIONAL_NAMED_TRAJECTORY_REFINEMENT_REQUIRED"
    else: gate="PROVISIONAL_NAMED_TRAJECTORY_NO_GO"
    metadata={
        "label":RUN011_LABEL,"title":f"{RUN011_LABEL} metadata","gate":gate,
        "provisional_static_authorized":True,"provisional_force_field_authorized":True,
        "provisional_named_trajectory_authorized":gate=="PROVISIONAL_NAMED_TRAJECTORY_GO",
        "capture_authorized":False,"capture_velocity_authorized":False,"optimizer_authorized":False,
        "exact_replication_valid":False,"exact_track_blocked":True,
        "named_velocity_order_gamma_over_k":list(expected_velocities),"selected_timestep_s":selected_dt,
        "baseline_timestep_s":baseline_dt,"refined_timestep_s":refined_dt,
        "convergence":convergence,"pathwise_interpolation_gate":overall_path_gate,
        "pathwise_validation_file":PATHWISE_PATH.name,"diagnostics":diagnostics,
        "termination_statuses":{k:r.termination_status.value for k,r in results.items()},
        "outcomes":{k:o.label.value for k,o in outcomes.items()},"acceptance_checks":checks,
        "historical_run008_hashes_before":historical_before,"historical_run008_hashes_after":historical_after,
        "historical_run008_unchanged":historical_unchanged,"files":files,"combined_plot":COMBINED_PLOT_PATH.name,
        "trajectory_integrations_are_named_only":True,"capture_calculations_performed":0,
        "source_distributions_used":0,"stochastic_models_used":0,"optimizer_runs":0,
    }
    METADATA_PATH.write_text(json.dumps(metadata,indent=2,sort_keys=True,default=_json),encoding="utf-8")
    h=lambda x:f"## {RUN011_LABEL} {x}"
    lines=[f"# {RUN011_LABEL}","","This is the first named-trajectory run using the accepted provisional physics-bearing rate-equation force fields. It is not a capture study and not a Rodriguez replication.","",h("Historical separation"),"","Run 008 validated plumbing only. Its toy-force outcomes omitted the physical acceleration conversion, are physically uninterpretable, and are superseded for force-dependent discussion. Numerical comparison to Run 008 is not scientifically meaningful. All Run 008 artifacts were preserved unchanged.","",h("Backend and numerics"),"",f"The adapter used the accepted `g'=0.001`, source-aligned 0.5 MHz interval-midpoint model, provenance-matched Run 010 caches, and one `hbar*k*Gamma/m` conversion. Baseline dt=`{baseline_dt}` s, refined dt=`{refined_dt}` s, selected dt=`{selected_dt}` s. Convergence passed: `{convergence_passed}`. Pathwise gate: `{overall_path_gate}`.","",h("Named trajectory diagnostics"),"","| name | Gamma/k | termination | outcome | qualitative motion | final x m | final v m/s | closest m | crossings |", "|---|---:|---|---|---|---:|---:|---:|---:|"]
    for name,d in diagnostics.items(): lines.append(f"| {name} | {d['initial_velocity_gamma_over_k']} | {d['integration_termination_status']} | {d['official_provisional_outcome']} | {d['qualitative_motion']} | {d['final_position_m']:.6g} | {d['final_velocity_m_s']:.6g} | {d['minimum_absolute_distance_m']:.6g} | {d['center_crossing_count']} |")
    lines += ["",h("Acceptance checks"),"",*[f"- `{k}`: `{v}`" for k,v in checks.items()],"",h(f"Final gate: {gate}"),"",f"**{gate}**","",f"`provisional_static_authorized = true`; `provisional_force_field_authorized = true`; `provisional_named_trajectory_authorized = {str(gate=='PROVISIONAL_NAMED_TRAJECTORY_GO').lower()}`; `capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; `exact_track_blocked = true`.","A GO authorizes further provisional named-trajectory analysis and design of a later paper-grounded capture protocol. It does not authorize capture thresholds, source distributions, optimization, or exact-replication claims.","",f"# {RUN011_LABEL} FINAL_{gate}"]
    REPORT_PATH.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"{RUN011_LABEL}: {gate}"); print(f"report: {REPORT_PATH}")
    return metadata


if __name__=="__main__": run()
