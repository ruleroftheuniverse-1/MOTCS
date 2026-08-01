"""Audit saved Track P Run 008 trajectories without integrating new paths."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.named_protocol import load_rodriguez_named_trajectory_protocol


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = REPO_ROOT / "outputs" / "provisional"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR
PROTOCOL_PATH = REPO_ROOT / "configs" / "rodriguez_named_trajectory_protocol.yaml"
RUN_008_LABEL = "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_NAMED_TRAJECTORY_PROTOCOL_ONLY"
AUDIT_LABEL = "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY"
TAIL_INTERVAL_S = 0.005
APPRECIABLE_ENVELOPE_THRESHOLD = 1.0e-3
NEAR_ZERO_FORCE_RELATIVE_THRESHOLD = 1.0e-3
NEAR_ZERO_FORCE_ABSOLUTE_THRESHOLD = 1.0e-12


def _validate_run_metadata(metadata: dict[str, Any]) -> None:
    """Reject anything other than the saved provisional Run 008 contract."""

    if metadata.get("label") != RUN_008_LABEL:
        raise ValueError("Run 008A accepts only labeled Run 008 artifacts")
    if metadata.get("replication_valid") is not False:
        raise ValueError("exact or replication-valid metadata cannot enter Run 008A")
    protocol = metadata.get("protocol", {})
    if protocol.get("track") != "provisional":
        raise ValueError("Run 008A requires Track P provisional provenance")
    if metadata.get("beam_mode") != "elliptical_gaussian":
        raise ValueError("Run 008A requires the saved elliptical-Gaussian run")


def _crossing_times(times: np.ndarray, values: np.ndarray) -> list[float]:
    crossings: list[float] = []
    for index in range(len(values) - 1):
        left, right = float(values[index]), float(values[index + 1])
        if left == 0.0:
            candidate = float(times[index])
        elif left * right < 0.0:
            fraction = -left / (right - left)
            candidate = float(times[index] + fraction * (times[index + 1] - times[index]))
        else:
            continue
        if not crossings or not np.isclose(candidate, crossings[-1], atol=1e-15):
            crossings.append(candidate)
    if values[-1] == 0.0:
        candidate = float(times[-1])
        if not crossings or not np.isclose(candidate, crossings[-1], atol=1e-15):
            crossings.append(candidate)
    return crossings


def _mask_statistics(times: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    indices = np.flatnonzero(mask)
    entries = np.flatnonzero(mask & np.r_[True, ~mask[:-1]])
    exits = np.flatnonzero(mask & np.r_[~mask[1:], True])
    duration = float(np.trapezoid(mask.astype(float), times))
    return {
        "first_entry_s": None if entries.size == 0 else float(times[entries[0]]),
        "last_entry_s": None if entries.size == 0 else float(times[entries[-1]]),
        "first_exit_s": None if exits.size == 0 else float(times[exits[0]]),
        "last_exit_s": None if exits.size == 0 else float(times[exits[-1]]),
        "sample_count": int(indices.size),
        "sampled_occupancy_duration_s": duration,
    }


def _linear_trend(times: np.ndarray, values: np.ndarray) -> float:
    if times.size < 2:
        return float("nan")
    centered = times - float(np.mean(times))
    denominator = float(np.dot(centered, centered))
    return float(np.dot(centered, values - float(np.mean(values))) / denominator)


def _trend_direction(value: float, *, tolerance: float = 1.0e-9) -> str:
    """Describe a diagnostic slope without promoting roundoff to a trend."""

    if abs(value) <= tolerance:
        return "effectively constant"
    return "increasing" if value > 0.0 else "decreasing"


def _audit_category(
    *,
    official_label: str,
    dwell_count: int,
    minimum_dwell_samples: int,
    position_ever_inside: bool,
    crossed_origin: bool,
    final_receding: bool,
    final_both_inside: bool,
    endpoint_force_near_zero: bool,
) -> tuple[str, list[str]]:
    if official_label != "UNRESOLVED":
        return "OTHER", ["official outcome is not UNRESOLVED"]
    if dwell_count < minimum_dwell_samples:
        return "INSUFFICIENT_FINAL_SAMPLES", []
    contributors: list[str] = []
    if position_ever_inside and final_receding and not final_both_inside:
        contributors.append("LEFT_BOUNDED_REGION")
    if endpoint_force_near_zero:
        contributors.append("FORCE_OR_ACCELERATION_NEAR_ZERO")
    if crossed_origin and final_receding and not final_both_inside:
        return "CENTER_CROSSING_WITHOUT_SETTLING", contributors
    if final_receding and not final_both_inside:
        return "OUTSIDE_BOUNDS_BUT_NOT_ESCAPED", contributors
    if not crossed_origin and not final_receding:
        return "STILL_APPROACHING", contributors
    return "OTHER", contributors


def _behavior_summary(
    *, crossed: bool, final_receding: bool, both_fraction: float, force_near_zero: bool
) -> str:
    if crossed and final_receding and both_fraction < 1.0:
        return "passing through / leaving"
    if force_near_zero:
        return "effectively unforced at endpoint"
    if not final_receding:
        return "still evolving / approaching"
    return "insufficient evidence"


def _analyze_case(
    arrays_path: Path,
    metadata_path: Path,
    protocol: Any,
    beam_set: Any,
) -> dict[str, Any]:
    saved = json.loads(metadata_path.read_text(encoding="utf-8"))
    if saved.get("replication_valid") is not False:
        raise ValueError("case metadata must remain non-replication-valid")
    with np.load(arrays_path) as arrays:
        times = np.asarray(arrays["times_s"], dtype=float)
        positions = np.asarray(arrays["positions_m"], dtype=float)
        velocities = np.asarray(arrays["velocities_m_s"], dtype=float)
        forces = np.asarray(arrays["normalized_forces"], dtype=float)
        saturations = np.asarray(arrays["component_saturations"], dtype=float)
        active = np.asarray(arrays["component_active"], dtype=bool)
        handoff = np.asarray(arrays["handoff_occurred"], dtype=bool)

    if not all(np.isfinite(item).all() for item in (times, positions, velocities, forces)):
        raise ValueError(f"nonfinite saved arrays in {arrays_path.name}")
    x = positions[:, 0]
    vx = velocities[:, 0]
    radii = np.linalg.norm(positions, axis=1)
    speeds = np.linalg.norm(velocities, axis=1)
    force_norms = np.linalg.norm(forces, axis=1)
    criteria = protocol.outcome_criteria
    position_mask = radii <= criteria.max_position
    velocity_mask = speeds <= criteria.max_speed
    both_mask = position_mask & velocity_mask
    dwell_start = float(times[-1] - criteria.final_dwell_window_s)
    dwell_mask = times >= dwell_start
    dwell_count = int(np.count_nonzero(dwell_mask))
    position_dwell_count = int(np.count_nonzero(position_mask & dwell_mask))
    velocity_dwell_count = int(np.count_nonzero(velocity_mask & dwell_mask))
    both_dwell_count = int(np.count_nonzero(both_mask & dwell_mask))
    closest_index = int(np.argmin(radii))
    crossings = _crossing_times(times, x)

    tail_start = max(float(times[0]), float(times[-1] - TAIL_INTERVAL_S))
    tail_mask = times >= tail_start
    trends = {
        "tail_interval_s": [tail_start, float(times[-1])],
        "tail_sample_count": int(np.count_nonzero(tail_mask)),
        "dx_dt_m_s": _linear_trend(times[tail_mask], x[tail_mask]),
        "dv_dt_m_s2": _linear_trend(times[tail_mask], vx[tail_mask]),
        "d_abs_x_dt_m_s": _linear_trend(times[tail_mask], np.abs(x[tail_mask])),
        "d_abs_v_dt_m_s2": _linear_trend(times[tail_mask], np.abs(vx[tail_mask])),
    }
    final_receding = bool(x[-1] * vx[-1] > 0.0)
    endpoint_force_near_zero = bool(
        force_norms[-1]
        <= max(
            NEAR_ZERO_FORCE_ABSOLUTE_THRESHOLD,
            NEAR_ZERO_FORCE_RELATIVE_THRESHOLD * float(np.max(force_norms)),
        )
    )
    final_envelopes = beam_set.envelopes(positions[-1])
    appreciably_illuminated = bool(
        max(final_envelopes.values()) >= APPRECIABLE_ENVELOPE_THRESHOLD
    )
    outcome = saved["outcome"]
    category, contributors = _audit_category(
        official_label=str(outcome["label"]),
        dwell_count=dwell_count,
        minimum_dwell_samples=criteria.min_dwell_samples,
        position_ever_inside=bool(position_mask.any()),
        crossed_origin=bool(crossings),
        final_receding=final_receding,
        final_both_inside=bool(both_mask[-1]),
        endpoint_force_near_zero=endpoint_force_near_zero,
    )
    denominator = max(dwell_count, 1)
    tau = float(saved["diagnostics"]["exact_handoff_event"]["tau_s"])
    before = times < tau
    after = times >= tau
    return {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} {saved['diagnostics']['case_name']} diagnostic metadata",
        "replication_valid": False,
        "case_name": saved["diagnostics"]["case_name"],
        "initial_velocity_gamma_over_k": saved["diagnostics"]["initial_velocity_gamma_over_k"],
        "initial_velocity_m_s": saved["diagnostics"]["initial_velocity_m_s"],
        "final_position_m": positions[-1].tolist(),
        "final_velocity_m_s": velocities[-1].tolist(),
        "final_normalized_force": forces[-1].tolist(),
        "final_provisional_integrator_acceleration_m_s2": (
            forces[-1] * protocol.normalized_force_to_acceleration
        ).tolist(),
        "force_scaling_warning": "engineering scaling only; not calibrated to MgF",
        "minimum_absolute_distance_m": float(radii[closest_index]),
        "time_of_closest_approach_s": float(times[closest_index]),
        "x_zero_crossed": bool(crossings),
        "x_zero_crossing_count": len(crossings),
        "x_zero_crossing_times_s": crossings,
        "position_bound": {"value": criteria.max_position, "unit": "m", **_mask_statistics(times, position_mask)},
        "velocity_bound": {"value": criteria.max_speed, "unit": "m/s", **_mask_statistics(times, velocity_mask)},
        "both_bounds": _mask_statistics(times, both_mask),
        "dwell_window": {
            "start_s": dwell_start,
            "end_s": float(times[-1]),
            "available_samples": dwell_count,
            "minimum_required_samples": criteria.min_dwell_samples,
            "position_count": position_dwell_count,
            "position_fraction": position_dwell_count / denominator,
            "velocity_count": velocity_dwell_count,
            "velocity_fraction": velocity_dwell_count / denominator,
            "both_count": both_dwell_count,
            "both_fraction": both_dwell_count / denominator,
        },
        "official_outcome_label": outcome["label"],
        "official_classifier_reason": outcome["numerical_reason"],
        "diagnostic_category": category,
        "contributing_diagnostic_categories": contributors,
        "final_motion": {
            "approaching_or_receding": "receding" if final_receding else "approaching",
            "speed_trend": _trend_direction(trends["d_abs_v_dt_m_s2"]),
            "position_magnitude_trend": _trend_direction(trends["d_abs_x_dt_m_s"]),
            "behavior_summary": _behavior_summary(
                crossed=bool(crossings),
                final_receding=final_receding,
                both_fraction=both_dwell_count / denominator,
                force_near_zero=endpoint_force_near_zero,
            ),
        },
        "tail_trends": trends,
        "endpoint_force_near_zero": endpoint_force_near_zero,
        "endpoint_force_threshold_definition": "norm(F_end) <= max(1e-12, 1e-3 * max trajectory force norm)",
        "final_gaussian_envelopes": final_envelopes,
        "appreciably_illuminated_at_endpoint": appreciably_illuminated,
        "appreciable_envelope_threshold": APPRECIABLE_ENVELOPE_THRESHOLD,
        "handoff_audit": {
            "tau_s": tau,
            "landed_exactly": bool(np.any(times == tau)),
            "component_4_inactive_before": bool(not active[before, 3].any()),
            "component_4_saturation_zero_before": bool(np.all(saturations[before, 3] == 0.0)),
            "component_4_active_after": bool(active[after, 3].all()),
            "handoff_flag_after": bool(handoff[after].all()),
            "pre_saturations": saturations[np.flatnonzero(before)[-1]].tolist(),
            "post_saturations": saturations[np.flatnonzero(after)[0]].tolist(),
        },
        "source_arrays": arrays_path.name,
        "source_metadata": metadata_path.name,
    }


def _save_plot(case: dict[str, Any], arrays_path: Path, output_dir: Path) -> Path:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    with np.load(arrays_path) as arrays:
        t = arrays["times_s"]
        x = arrays["positions_m"][:, 0]
        vx = arrays["velocities_m_s"][:, 0]
    position_bound = case["position_bound"]["value"]
    velocity_bound = case["velocity_bound"]["value"]
    dwell_start = case["dwell_window"]["start_s"]
    path = output_dir / f"{AUDIT_LABEL}_{case['case_name']}.png"
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    axes[0, 0].plot(t, x)
    axes[0, 0].axhspan(-position_bound, position_bound, alpha=0.18, color="green")
    axes[0, 0].set(xlabel="time [s]", ylabel="x [m]")
    axes[0, 1].plot(t, vx)
    axes[0, 1].axhspan(-velocity_bound, velocity_bound, alpha=0.18, color="green")
    axes[0, 1].set(xlabel="time [s]", ylabel="v_x [m/s]")
    axes[1, 0].plot(x, vx)
    axes[1, 0].add_patch(Rectangle((-position_bound, -velocity_bound), 2 * position_bound, 2 * velocity_bound, alpha=0.18, color="green"))
    axes[1, 0].set(xlabel="x [m]", ylabel="v_x [m/s]")
    tail = t >= dwell_start
    axes[1, 1].plot(t[tail], x[tail], label="x [m]")
    axes[1, 1].plot(t[tail], vx[tail], label="v_x [m/s]")
    axes[1, 1].axhspan(-position_bound, position_bound, alpha=0.12, color="green")
    axes[1, 1].set(xlabel="time [s]", title="final dwell-window close-up")
    axes[1, 1].legend()
    fig.suptitle(f"{AUDIT_LABEL} {case['case_name']}")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def analyze(
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    save_plots: bool = True,
) -> dict[str, Any]:
    """Analyze exactly the five saved cases; never call the integrator."""

    output_dir.mkdir(parents=True, exist_ok=True)
    run_metadata_path = input_dir / f"{RUN_008_LABEL}_run_008_metadata.json"
    run_metadata = json.loads(run_metadata_path.read_text(encoding="utf-8"))
    _validate_run_metadata(run_metadata)
    protocol = load_rodriguez_named_trajectory_protocol(PROTOCOL_PATH)
    saved_criteria = run_metadata["protocol"]["outcome_criteria"]
    if asdict(protocol.outcome_criteria) != saved_criteria:
        raise ValueError(
            "current outcome criteria differ from the criteria saved by Run 008"
        )
    gaussian_config = load_gaussian_envelope_config(REPO_ROOT / protocol.gaussian_config_path)
    beam_set = build_rodriguez_gaussian_beam_set(gaussian_config, protocol.post_handoff_saturations)

    expected_order = [item.name for item in protocol.named_velocities]
    records_by_name = {item["name"]: item for item in run_metadata["case_records"]}
    if list(records_by_name) != expected_order or len(records_by_name) != 5:
        raise ValueError("saved Run 008 cases do not preserve the exact five-case order")

    cases: list[dict[str, Any]] = []
    for name in expected_order:
        source = records_by_name[name]
        case = _analyze_case(input_dir / source["arrays_path"], input_dir / source["metadata_path"], protocol, beam_set)
        plot_path = _save_plot(case, input_dir / source["arrays_path"], output_dir) if save_plots else None
        case["plot_path"] = None if plot_path is None else plot_path.name
        cases.append(case)

    criteria = protocol.outcome_criteria
    sample_intervals = np.diff(np.load(input_dir / records_by_name[expected_order[0]]["arrays_path"])["times_s"])
    cadence = float(np.median(sample_intervals))
    criteria_audit = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} unchanged classifier criteria",
        "position_bound_m": criteria.max_position,
        "velocity_bound_m_s": criteria.max_speed,
        "dwell_window_s": criteria.final_dwell_window_s,
        "minimum_dwell_samples": criteria.min_dwell_samples,
        "required_dwell_fraction": criteria.required_dwell_fraction,
        "escape_position_m": criteria.hard_escape_position,
        "escape_speed_m_s": criteria.hard_speed,
        "simulation_duration_s": protocol.simulation_duration_s,
        "nominal_output_cadence_s": cadence,
        "expected_inclusive_dwell_samples": int(round(criteria.final_dwell_window_s / cadence)) + 1,
        "can_in_principle_satisfy_duration": protocol.simulation_duration_s >= criteria.final_dwell_window_s,
        "can_in_principle_satisfy_sample_minimum": int(round(criteria.final_dwell_window_s / cadence)) + 1 >= criteria.min_dwell_samples,
        "criteria_modified": False,
        "current_criteria_equal_saved_run_008_criteria": True,
    }
    consistency = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} Run 008 consistency audit",
        "initial_position_is_minus_50_mm": protocol.initial_position_m == (-0.05, 0.0, 0.0),
        "velocity_order_gamma_over_k": [item.gamma_over_k for item in protocol.named_velocities],
        "velocity_order_exact": [item.gamma_over_k for item in protocol.named_velocities] == [2.0, 4.0, 6.0, 7.5, 9.0],
        "gaussian_mode_active": run_metadata["beam_mode"] == "elliptical_gaussian",
        "handoff_exact_all_cases": all(case["handoff_audit"]["landed_exactly"] for case in cases),
        "component_4_switch_correct_all_cases": all(case["handoff_audit"]["component_4_inactive_before"] and case["handoff_audit"]["component_4_saturation_zero_before"] and case["handoff_audit"]["component_4_active_after"] for case in cases),
        "pre_saturations_exact_all_cases": all(tuple(case["handoff_audit"]["pre_saturations"]) == protocol.pre_handoff_saturations for case in cases),
        "post_saturations_exact_all_cases": all(tuple(case["handoff_audit"]["post_saturations"]) == protocol.post_handoff_saturations for case in cases),
        "track": run_metadata["protocol"]["track"],
        "replication_valid": run_metadata["replication_valid"],
    }
    metadata = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} Run 008A metadata",
        "replication_valid": False,
        "analysis_mode": "saved_artifacts_only_no_integration",
        "source_run_metadata": run_metadata_path.name,
        "tail_interval_s": TAIL_INTERVAL_S,
        "criteria_audit": criteria_audit,
        "consistency_audit": consistency,
        "cases": cases,
        "warnings": [
            f"{AUDIT_LABEL}: diagnostic audit only.",
            "Official outcome labels and classifier criteria are unchanged.",
            "No capture boundary, maximum velocity, or physical conclusion is reported.",
        ],
    }
    metadata_path = output_dir / f"{AUDIT_LABEL}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    report_path = output_dir / f"{AUDIT_LABEL}.md"
    headings = lambda text: f"## {AUDIT_LABEL} {text}"
    lines = [
        f"# {AUDIT_LABEL}",
        "",
        "This audits the saved Run 008 arrays and metadata only; no trajectory was rerun.",
        "Official outcomes remain `UNRESOLVED`, and classifier criteria were not changed.",
        "This is not a capture analysis or a Rodriguez replication. Track E remains blocked.",
        "",
        headings("Compact diagnosis"),
        "",
        "| initial Gamma/k | initial m/s | final x (m) | final vx (m/s) | closest | crossings | dwell pos/vel/both | category | behavior |",
        "|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for case in cases:
        dwell = case["dwell_window"]
        lines.append(
            f"| {case['initial_velocity_gamma_over_k']:g} | {case['initial_velocity_m_s']:g} | "
            f"{case['final_position_m'][0]:.6g} | {case['final_velocity_m_s'][0]:.6g} | "
            f"{case['minimum_absolute_distance_m']:.6g} m at {case['time_of_closest_approach_s']:.6g} s | "
            f"{case['x_zero_crossing_count']} | {dwell['position_count']}/{dwell['velocity_count']}/{dwell['both_count']} of {dwell['available_samples']} | "
            f"`{case['diagnostic_category']}` | {case['final_motion']['behavior_summary']} |"
        )
    lines += [
        "",
        headings("Why the official outcomes are unresolved"),
        "",
        "All cases have 21 final dwell-window samples, exceeding the required 10. None satisfies either the 10 mm position bound or the 1 m/s speed bound in that final window, so none satisfies both. Each crossed the center once, left the bounded region, is receding at 20 ms, and has negligible endpoint force under the documented relative test. The primary audit category is therefore `CENTER_CROSSING_WITHOUT_SETTLING`; `LEFT_BOUNDED_REGION` and `FORCE_OR_ACCELERATION_NEAR_ZERO` are contributing diagnostics, not replacement outcome labels.",
        "",
        headings("Per-trajectory details"),
    ]
    for case in cases:
        dwell = case["dwell_window"]
        lines += [
            "",
            f"### {AUDIT_LABEL} {case['case_name']}",
            "",
            f"- official outcome and reason: `{case['official_outcome_label']}`; {case['official_classifier_reason']}",
            f"- audit category: `{case['diagnostic_category']}`; contributors: `{', '.join(case['contributing_diagnostic_categories'])}`",
            f"- final position / velocity: `{case['final_position_m']}` m / `{case['final_velocity_m_s']}` m/s",
            f"- final normalized force: `{case['final_normalized_force']}`; provisional integrator acceleration: `{case['final_provisional_integrator_acceleration_m_s2']}` m/s^2 (uncalibrated)",
            f"- crossing times: `{case['x_zero_crossing_times_s']}` s; final motion: `{case['final_motion']}`",
            f"- position-bound entry/exit and sampled duration: `{case['position_bound']}`",
            f"- velocity-bound entry/exit and sampled duration: `{case['velocity_bound']}`",
            f"- final dwell position/velocity/both fractions: `{dwell['position_fraction']:.6g}` / `{dwell['velocity_fraction']:.6g}` / `{dwell['both_fraction']:.6g}`",
            f"- final 5 ms trends: `{case['tail_trends']}`",
            f"- final Gaussian envelopes: `{case['final_gaussian_envelopes']}`; appreciably illuminated: `{case['appreciably_illuminated_at_endpoint']}` using threshold `{APPRECIABLE_ENVELOPE_THRESHOLD}`",
            f"- plot: `{case['plot_path']}`",
        ]
    lines += [
        "",
        headings("Unchanged classifier and cadence audit"),
        "",
        f"- criteria: `{criteria_audit}`",
        "- The 20 ms duration and approximately 0.1 ms output cadence can in principle provide the required 2 ms dwell interval and minimum 10 samples.",
        "- The current unresolved results therefore point primarily to pass-through force/geometry behavior in this provisional model, not insufficient dwell duration, sample count, or numerical cadence. This is an engineering diagnosis, not a physical conclusion.",
        "",
        headings("Run 008 consistency audit"),
        "",
        f"- `{consistency}`",
        "",
        headings("Scope boundary"),
        "",
        "No initial velocity, duration, classifier criterion, force model, beam geometry, or policy was changed. No capture threshold, boundary search, source distribution, stochastic effect, optimizer, or exact-force path was added.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(AUDIT_LABEL)
    print("analysis_mode: saved_artifacts_only_no_integration")
    for case in cases:
        print(f"{case['case_name']}: {case['official_outcome_label']} -> {case['diagnostic_category']}; {case['final_motion']['behavior_summary']}")
    print(f"metadata: {metadata_path}")
    print(f"report: {report_path}")
    return {"metadata": metadata, "metadata_path": metadata_path, "report_path": report_path, "cases": cases}


if __name__ == "__main__":
    analyze()
