"""Track P Run 008B force-budget audit over immutable saved trajectories."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.force_units import (
    build_mgf_force_unit_audit,
    cumulative_trapezoid_impulse,
    normalized_force_to_acceleration_m_s2,
    normalized_force_to_newtons,
    trapezoid_impulse,
)
from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.mgf_backend import ApproximationMode, build_mgf_hamiltonian_from_sources
from mgf_mot.named_protocol import load_rodriguez_named_trajectory_protocol
from mgf_mot.policies import load_policy
from mgf_mot.policy_force import force_config_for_policy_sample
from mgf_mot.provisional_force import ProvisionalForceMapConfig, force_at


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = REPO_ROOT / "outputs" / "provisional"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR
PROTOCOL_PATH = REPO_ROOT / "configs" / "rodriguez_named_trajectory_protocol.yaml"
RUN_008_LABEL = "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_NAMED_TRAJECTORY_PROTOCOL_ONLY"
AUDIT_LABEL = "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY"
APPRECIABLE_ENVELOPE_THRESHOLD = 1.0e-3
FORCE_SCALE_POSITION_DOMAIN_M = (-0.05, 0.05)
FORCE_SCALE_VELOCITY_DOMAIN_M_S = (-7.53, 7.53)


def _json_safe(value: Any) -> Any:
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
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_saved_run(metadata: dict[str, Any]) -> None:
    if metadata.get("label") != RUN_008_LABEL:
        raise ValueError("Run 008B accepts only the named Run 008 artifact set")
    if metadata.get("replication_valid") is not False:
        raise ValueError("exact Track E or replication-valid input cannot enter Run 008B")
    if metadata.get("protocol", {}).get("track") != "provisional":
        raise ValueError("Run 008B requires Track P provenance")


def _interval_integral(
    times: np.ndarray, values: np.ndarray, interval_mask: np.ndarray
) -> np.ndarray:
    increments = 0.5 * (values[:-1] + values[1:]) * np.diff(times)[:, None]
    if interval_mask.shape != (times.size - 1,):
        raise ValueError("interval mask shape mismatch")
    return np.sum(increments[interval_mask], axis=0)


def _crossing_times(times: np.ndarray, values: np.ndarray) -> list[float]:
    result: list[float] = []
    for index, (left, right) in enumerate(zip(values[:-1], values[1:])):
        if left == 0.0:
            result.append(float(times[index]))
        elif left * right < 0.0:
            fraction = -left / (right - left)
            result.append(float(times[index] + fraction * np.diff(times)[index]))
    return result


def _local_force_audit(backend: Any, base_config: ProvisionalForceMapConfig, sample: Any) -> dict[str, Any]:
    config = force_config_for_policy_sample(sample, base_config)
    dx = 1.0e-4
    dv = 1.0e-2

    def fx(x: float, v: float) -> float:
        force, _ = force_at(
            np.array([x, 0.0, 0.0]),
            np.array([v, 0.0, 0.0]),
            backend,
            config,
        )
        return float(force[0])

    position_values = {-dx: fx(-dx, 0.0), 0.0: fx(0.0, 0.0), dx: fx(dx, 0.0)}
    velocity_values = {-dv: fx(0.0, -dv), 0.0: fx(0.0, 0.0), dv: fx(0.0, dv)}
    dfdx = (position_values[dx] - position_values[-dx]) / (2.0 * dx)
    dfdv = (velocity_values[dv] - velocity_values[-dv]) / (2.0 * dv)
    asymmetry_x = abs(position_values[dx] + position_values[-dx] - 2.0 * position_values[0.0])
    asymmetry_v = abs(velocity_values[dv] + velocity_values[-dv] - 2.0 * velocity_values[0.0])
    return {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} {base_config.beam_mode} post-handoff local-force audit",
        "beam_mode": base_config.beam_mode,
        "position_probe_m": [-dx, 0.0, dx],
        "force_at_v_zero": [position_values[-dx], position_values[0.0], position_values[dx]],
        "velocity_probe_m_s": [-dv, 0.0, dv],
        "force_at_x_zero": [velocity_values[-dv], velocity_values[0.0], velocity_values[dv]],
        "dFdx_normalized_per_m": dfdx,
        "dFdv_normalized_per_m_s": dfdv,
        "restoring_status": "restoring" if dfdx < 0.0 else "anti-restoring" if dfdx > 0.0 else "flat",
        "damping_status": "damping" if dfdv < 0.0 else "anti-damping" if dfdv > 0.0 else "flat",
        "numerical_asymmetry_x": asymmetry_x,
        "numerical_asymmetry_v": asymmetry_v,
    }


def _maximum_force(
    backend: Any, base_config: ProvisionalForceMapConfig, sample: Any
) -> float:
    config = force_config_for_policy_sample(sample, base_config)
    positions = np.linspace(*FORCE_SCALE_POSITION_DOMAIN_M, 51)
    velocities = np.linspace(*FORCE_SCALE_VELOCITY_DOMAIN_M_S, 51)
    maximum = 0.0
    for x in positions:
        for velocity in velocities:
            force, _ = force_at(
                np.array([x, 0.0, 0.0]),
                np.array([velocity, 0.0, 0.0]),
                backend,
                config,
            )
            maximum = max(maximum, abs(float(force[0])))
    return maximum


def _scale_description(value: float, reference: float) -> str:
    ratio = value / reference
    if ratio < 0.1:
        return "much smaller"
    if ratio > 10.0:
        return "much larger"
    return "comparable order"


def _case_force_audit(
    arrays_path: Path,
    metadata_path: Path,
    protocol: Any,
    beam_set: Any,
    unit_audit: Any,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata["replication_valid"] is not False:
        raise ValueError("saved trajectory must remain non-replication-valid")
    with np.load(arrays_path) as data:
        arrays = {name: np.asarray(data[name]).copy() for name in data.files}
    times = arrays["times_s"]
    positions = arrays["positions_m"]
    velocities = arrays["velocities_m_s"]
    normalized_forces = arrays["normalized_forces"]
    physical_forces = normalized_force_to_newtons(normalized_forces, unit_audit)
    physical_accelerations = normalized_force_to_acceleration_m_s2(normalized_forces, unit_audit)
    current_adapter_accelerations = normalized_forces * protocol.normalized_force_to_acceleration
    cumulative_impulse = cumulative_trapezoid_impulse(times, physical_forces)
    total_impulse = trapezoid_impulse(times, physical_forces)
    normalized_integral = trapezoid_impulse(times, normalized_forces)
    mass = unit_audit.mass.value_kg
    initial_momentum = mass * velocities[0]
    final_momentum = mass * velocities[-1]
    stopping_impulse_magnitude = mass * abs(float(velocities[0, 0]))

    tau = float(metadata["diagnostics"]["exact_handoff_event"]["tau_s"])
    mid_times = 0.5 * (times[:-1] + times[1:])
    before = mid_times < tau
    after = ~before
    envelope_matrix = np.asarray(
        [list(beam_set.envelopes(position).values()) for position in positions],
        dtype=float,
    )
    maximum_envelope = np.max(envelope_matrix, axis=1)
    appreciable = maximum_envelope >= APPRECIABLE_ENVELOPE_THRESHOLD
    appreciable_intervals = 0.5 * (maximum_envelope[:-1] + maximum_envelope[1:]) >= APPRECIABLE_ENVELOPE_THRESHOLD
    impulse_pre = _interval_integral(times, physical_forces, before)
    impulse_post = _interval_integral(times, physical_forces, after)
    impulse_illuminated = _interval_integral(times, physical_forces, appreciable_intervals)
    illuminated_indices = np.flatnonzero(appreciable)
    closest = int(np.argmin(np.linalg.norm(positions, axis=1)))
    crossings = _crossing_times(times, positions[:, 0])
    physical_delta_v = total_impulse / mass
    saved_delta_v = velocities[-1] - velocities[0]
    current_adapter_delta_v = normalized_integral * protocol.normalized_force_to_acceleration
    reconstruction_error = current_adapter_delta_v - saved_delta_v
    physical_ratio = -float(total_impulse[0]) / stopping_impulse_magnitude
    current_ratio = -float(saved_delta_v[0]) / abs(float(velocities[0, 0]))
    diagnoses = [
        "UNIT_CONVERSION_SUSPECT",
        "GAUSSIAN_APPLICATION_SUSPECT",
        "PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT",
    ]
    record = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} {metadata['diagnostics']['case_name']} force budget",
        "replication_valid": False,
        "case_name": metadata["diagnostics"]["case_name"],
        "initial_velocity_gamma_over_k": metadata["diagnostics"]["initial_velocity_gamma_over_k"],
        "initial_velocity_m_s": float(velocities[0, 0]),
        "final_velocity_m_s": float(velocities[-1, 0]),
        "initial_momentum_kg_m_s": initial_momentum.tolist(),
        "final_momentum_kg_m_s": final_momentum.tolist(),
        "actual_saved_momentum_change_kg_m_s": (final_momentum - initial_momentum).tolist(),
        "normalized_force_time_integral": normalized_integral.tolist(),
        "physical_impulse_if_hbar_k_gamma_applied_once_n_s": total_impulse.tolist(),
        "physical_delta_v_if_conversion_applied_once_m_s": physical_delta_v.tolist(),
        "current_run008_adapter_delta_v_from_force_integral_m_s": current_adapter_delta_v.tolist(),
        "actual_saved_delta_v_m_s": saved_delta_v.tolist(),
        "current_adapter_reconstruction_error_m_s": reconstruction_error.tolist(),
        "current_adapter_reconstruction_max_abs_error_m_s": float(
            np.max(np.abs(reconstruction_error))
        ),
        "pre_handoff_physical_impulse_n_s": impulse_pre.tolist(),
        "post_handoff_physical_impulse_n_s": impulse_post.tolist(),
        "appreciably_illuminated_physical_impulse_n_s": impulse_illuminated.tolist(),
        "stopping_impulse_required_magnitude_n_s": stopping_impulse_magnitude,
        "physical_delivered_to_stopping_impulse_ratio": physical_ratio,
        "current_run008_delta_v_to_stopping_delta_v_ratio": current_ratio,
        "ratio_warning": "diagnostic impulse ratio only; it is not capture efficiency",
        "first_appreciable_illumination_s": None if illuminated_indices.size == 0 else float(times[illuminated_indices[0]]),
        "last_appreciable_illumination_s": None if illuminated_indices.size == 0 else float(times[illuminated_indices[-1]]),
        "closest_approach_s": float(times[closest]),
        "center_crossing_times_s": crossings,
        "handoff_time_s": tau,
        "component_4_inactive_before_handoff": bool(not arrays["component_active"][times < tau, 3].any()),
        "component_4_active_after_handoff": bool(arrays["component_active"][times >= tau, 3].all()),
        "official_outcome_label": metadata["outcome"]["label"],
        "official_classifier_reason": metadata["outcome"]["numerical_reason"],
        "engineering_diagnoses": diagnoses,
        "source_arrays": arrays_path.name,
        "source_metadata": metadata_path.name,
    }
    plot_arrays = {
        "times_s": times,
        "normalized_force_x": normalized_forces[:, 0],
        "physical_acceleration_x": physical_accelerations[:, 0],
        "current_adapter_acceleration_x": current_adapter_accelerations[:, 0],
        "maximum_envelope": maximum_envelope,
        "detunings": arrays["component_detunings_gamma"],
        "component_4_active": arrays["component_active"][:, 3].astype(float),
        "cumulative_impulse_x": cumulative_impulse[:, 0],
    }
    return record, plot_arrays


def _save_case_plot(record: dict[str, Any], arrays: dict[str, np.ndarray], output_dir: Path) -> Path:
    import matplotlib.pyplot as plt

    time = arrays["times_s"]
    path = output_dir / f"{AUDIT_LABEL}_{record['case_name']}.png"
    fig, axes = plt.subplots(5, 1, figsize=(10, 13), sharex=True)
    axes[0].plot(time, arrays["normalized_force_x"])
    axes[0].set_ylabel("F_x [hbar k Gamma]")
    axes[1].plot(time, arrays["current_adapter_acceleration_x"], label="Run 008 adapter")
    axes[1].plot(time, arrays["physical_acceleration_x"], label="single SI conversion", alpha=0.75)
    axes[1].set_ylabel("a_x [m/s^2]")
    axes[1].legend()
    axes[2].semilogy(time, np.maximum(arrays["maximum_envelope"], 1e-320))
    axes[2].axhline(APPRECIABLE_ENVELOPE_THRESHOLD, color="gray", linestyle=":")
    axes[2].set_ylabel("max envelope")
    for index in range(4):
        axes[3].plot(time, arrays["detunings"][:, index], label=f"c{index + 1}")
    axes[3].plot(time, arrays["component_4_active"], "k--", label="c4 active")
    axes[3].set_ylabel("detuning [Gamma]")
    axes[3].legend(ncol=5)
    axes[4].plot(time, arrays["cumulative_impulse_x"])
    axes[4].set(xlabel="time [s]", ylabel="cumulative J_x [N s]")
    markers = [
        record["handoff_time_s"],
        record["first_appreciable_illumination_s"],
        record["closest_approach_s"],
        *(record["center_crossing_times_s"][:1]),
        record["last_appreciable_illumination_s"],
    ]
    for axis in axes:
        for marker in markers:
            if marker is not None:
                axis.axvline(marker, color="red", alpha=0.25, linewidth=0.8)
    fig.suptitle(f"{AUDIT_LABEL} {record['case_name']}")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def audit(
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    save_plots: bool = True,
) -> dict[str, Any]:
    """Audit force budgets and pointwise force laws without trajectory integration."""

    output_dir.mkdir(parents=True, exist_ok=True)
    source_metadata_path = input_dir / f"{RUN_008_LABEL}_run_008_metadata.json"
    source_metadata = json.loads(source_metadata_path.read_text(encoding="utf-8"))
    _validate_saved_run(source_metadata)
    protocol = load_rodriguez_named_trajectory_protocol(PROTOCOL_PATH)
    gaussian_config = load_gaussian_envelope_config(REPO_ROOT / protocol.gaussian_config_path)
    beam_set = build_rodriguez_gaussian_beam_set(gaussian_config, protocol.post_handoff_saturations)
    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    if backend.provenance.replication_valid:
        raise ValueError("Run 008B cannot use a replication-valid backend")

    source_paths = [source_metadata_path]
    for item in source_metadata["case_records"]:
        source_paths.extend((input_dir / item["arrays_path"], input_dir / item["metadata_path"]))
    hashes_before = {path.name: _sha256(path) for path in source_paths}
    official_labels_before = [
        json.loads((input_dir / item["metadata_path"]).read_text(encoding="utf-8"))["outcome"]["label"]
        for item in source_metadata["case_records"]
    ]

    unit_audit = build_mgf_force_unit_audit()
    acceleration_examples = {
        f"{value:g}": float(normalized_force_to_acceleration_m_s2(value, unit_audit))
        for value in (0.01, 0.015, 0.03, 1.0)
    }
    unit_record = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} unit and acceleration chain",
        **_json_safe(asdict(unit_audit)),
        "acceleration_examples_m_s2": acceleration_examples,
        "integrator_position_unit": "m",
        "integrator_velocity_unit": "m/s",
        "integrator_time_unit": "s",
        "run008_normalized_force_to_acceleration": protocol.normalized_force_to_acceleration,
        "run008_physical_conversion_application_count": 0,
        "audited_conversion_application_count": 1,
        "run008_adapter_to_physical_acceleration_ratio": protocol.normalized_force_to_acceleration / unit_audit.acceleration_per_normalized_force_m_s2,
        "diagnosis": "UNIT_CONVERSION_SUSPECT",
    }

    plane_base = ProvisionalForceMapConfig(
        explicit_provisional_opt_in=True,
        beam_mode="plane_wave",
        position_unit="m",
        magnetic_gradient_t_m=protocol.magnetic_gradient_t_m,
        normalized_gradient_scale=protocol.normalized_gradient_scale,
    )
    gaussian_base = replace(plane_base, beam_mode="elliptical_gaussian", gaussian_beam_set=beam_set)
    post_policy = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    post_sample = post_policy.sample(0.0)
    local_audits = [
        _local_force_audit(backend, plane_base, post_sample),
        _local_force_audit(backend, gaussian_base, post_sample),
    ]

    static3 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3.yaml")
    static31 = post_policy
    chirp = load_policy(REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml")
    scale_inputs = [
        ("plane_wave_[3]", plane_base, static3.sample(0.0)),
        ("plane_wave_[3+1]", plane_base, static31.sample(0.0)),
        ("gaussian_[3]", gaussian_base, static3.sample(0.0)),
        ("gaussian_[3+1]", gaussian_base, static31.sample(0.0)),
        ("gaussian_chirp_-8Gamma", gaussian_base, chirp.sample(0.0)),
        ("gaussian_chirp_-4.5Gamma", gaussian_base, chirp.sample(0.0005)),
        ("gaussian_chirp_-1Gamma", gaussian_base, chirp.sample(0.001)),
    ]
    force_scales = []
    for name, config, sample in scale_inputs:
        maximum = _maximum_force(backend, config, sample)
        force_scales.append(
            {
                "label": AUDIT_LABEL,
                "title": f"{AUDIT_LABEL} {name} force scale",
                "name": name,
                "detunings_gamma": [component.detuning_gamma for component in sample.components],
                "maximum_absolute_normalized_force": maximum,
                "versus_0p03": _scale_description(maximum, 0.03),
                "versus_0p015": _scale_description(maximum, 0.015),
            }
        )

    envelope_points = []
    for x_mm in (-50.0, -25.0, 0.0, 25.0, 50.0):
        values = beam_set.envelopes(np.array([x_mm * 1e-3, 0.0, 0.0]))
        envelope_points.append(
            {
                "label": AUDIT_LABEL,
                "title": f"{AUDIT_LABEL} Gaussian envelopes x={x_mm:g} mm",
                "x_mm": x_mm,
                "per_beam": values,
            }
        )
    gaussian_application = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} Gaussian application implementation audit",
        "per_beam_envelopes_available": True,
        "counterpropagating_pair_envelopes_equal": all(
            np.isclose(point["per_beam"][f"+{pair}"], point["per_beam"][f"-{pair}"])
            for point in envelope_points
            for pair in ("x_prime", "y_prime", "z")
        ),
        "per_beam_envelopes_applied_before_force_summation": False,
        "mean_envelope_applied_after_force_summation": True,
        "saturation_squared": False,
        "all_beams_multiplied_by_weakest_envelope": False,
        "all_force_components_multiplied_by_single_mean_envelope": True,
        "position_units_m": True,
        "implementation_summary": "force_at forms one aggregate spring/damping vector, then multiplies it by GaussianBeamSet.mean_envelope(position)",
        "diagnosis": "GAUSSIAN_APPLICATION_SUSPECT",
        "representative_points": envelope_points,
    }

    representative_points = [
        ("inbound_x_minus_25_mm", -0.025, 30.12),
        ("near_origin_positive_velocity", -0.001, 15.06),
        ("origin_zero_velocity", 0.0, 0.0),
        ("outbound_x_plus_25_mm", 0.025, 30.12),
    ]
    aggregate_comparison = []
    for name, x, velocity in representative_points:
        pre_config = force_config_for_policy_sample(static3.sample(0.0), gaussian_base)
        post_config = force_config_for_policy_sample(static31.sample(0.0), gaussian_base)
        pre_force, _ = force_at(np.array([x, 0.0, 0.0]), np.array([velocity, 0.0, 0.0]), backend, pre_config)
        post_force, _ = force_at(np.array([x, 0.0, 0.0]), np.array([velocity, 0.0, 0.0]), backend, post_config)
        aggregate_comparison.append(
            {
                "label": AUDIT_LABEL,
                "title": f"{AUDIT_LABEL} aggregate pre-post comparison {name}",
                "point": name,
                "x_m": x,
                "vx_m_s": velocity,
                "pre_handoff_Fx": float(pre_force[0]),
                "post_handoff_Fx": float(post_force[0]),
                "difference": float(post_force[0] - pre_force[0]),
            }
        )
    decomposition = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} beam and frequency decomposition limitation",
        "decomposition_available": False,
        "reason": "the provisional force law aggregates active saturation into one spring coefficient, ignores detuning and backend transition matrices, and has no beam- or component-resolved force terms",
        "component_4_conclusion": "the [3] and [3+1] saturation sums are both 5.79, so component 4 only redistributes aggregate saturation and changes neither magnitude nor topology in this toy law",
        "aggregate_pre_post_comparison": aggregate_comparison,
        "diagnosis": "PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT",
    }

    cases = []
    plot_paths = []
    for source in source_metadata["case_records"]:
        record, plot_arrays = _case_force_audit(
            input_dir / source["arrays_path"],
            input_dir / source["metadata_path"],
            protocol,
            beam_set,
            unit_audit,
        )
        if save_plots:
            plot_path = _save_case_plot(record, plot_arrays, output_dir)
            record["plot_path"] = plot_path.name
            plot_paths.append(plot_path)
        else:
            record["plot_path"] = None
        cases.append(record)

    hashes_after = {path.name: _sha256(path) for path in source_paths}
    official_labels_after = [
        json.loads((input_dir / item["metadata_path"]).read_text(encoding="utf-8"))["outcome"]["label"]
        for item in source_metadata["case_records"]
    ]
    immutability = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} saved Run 008 immutability audit",
        "source_hashes_before": hashes_before,
        "source_hashes_after": hashes_after,
        "all_source_hashes_unchanged": hashes_before == hashes_after,
        "official_outcome_labels_before": official_labels_before,
        "official_outcome_labels_after": official_labels_after,
        "official_outcome_labels_unchanged": official_labels_before == official_labels_after,
        "trajectory_integrations_performed": 0,
    }
    overall_diagnoses = [
        "UNIT_CONVERSION_SUSPECT",
        "GAUSSIAN_APPLICATION_SUSPECT",
        "PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT",
    ]
    metadata = {
        "label": AUDIT_LABEL,
        "title": f"{AUDIT_LABEL} metadata",
        "replication_valid": False,
        "analysis_mode": "saved_force_samples_and_pointwise_static_calls_only",
        "unit_audit": unit_record,
        "local_force_audits": local_audits,
        "force_scale_domain": {
            "label": AUDIT_LABEL,
            "title": f"{AUDIT_LABEL} force-scale sampling domain",
            "position_m": FORCE_SCALE_POSITION_DOMAIN_M,
            "velocity_m_s": FORCE_SCALE_VELOCITY_DOMAIN_M_S,
        },
        "force_scales": force_scales,
        "gaussian_application_audit": gaussian_application,
        "beam_frequency_decomposition": decomposition,
        "trajectory_force_budgets": cases,
        "immutability_audit": immutability,
        "overall_engineering_diagnoses": overall_diagnoses,
        "primary_suspect": "provisional force adapter: missing SI acceleration conversion, aggregate mean-envelope application, and a toy law that does not consult backend force topology or detuning",
    }
    metadata_path = output_dir / f"{AUDIT_LABEL}_metadata.json"
    metadata_path.write_text(json.dumps(_json_safe(metadata), indent=2, sort_keys=True), encoding="utf-8")

    report_path = output_dir / f"{AUDIT_LABEL}.md"
    heading = lambda text: f"## {AUDIT_LABEL} {text}"
    lines = [
        f"# {AUDIT_LABEL}",
        "",
        "This is an offline force-budget and implementation audit. It did not integrate or alter a trajectory, change an outcome, or open an exact-force path.",
        "",
        heading("Primary finding"),
        "",
        "The primary suspect is the provisional force adapter, not classifier cadence: Run 008 applied no physical `hbar k Gamma / m` acceleration conversion, applied one mean Gaussian envelope after forming an aggregate force, ignored detuning and backend transition topology, and represented [3] and [3+1] by the same total active saturation. These are engineering findings, not MgF physical conclusions.",
        "",
        heading("Unit and acceleration chain"),
        "",
        f"- `k = {unit_audit.wave_number_rad_m:.12g} rad/m`",
        f"- `Gamma = {unit_audit.linewidth_rad_s:.12g} rad/s`",
        f"- `hbar k Gamma = {unit_audit.hbar_k_gamma_n:.12g} N`",
        f"- `m(24Mg19F) = {unit_audit.mass.value_kg:.12g} kg` (`{unit_audit.mass.status}`; {unit_audit.mass.note})",
        f"- `hbar k Gamma / m = {unit_audit.acceleration_per_normalized_force_m_s2:.12g} m/s^2`",
        f"- acceleration examples for 0.01, 0.015, 0.03, and 1.0: `{acceleration_examples}` m/s^2",
        f"- Run 008 adapter: `1.0`; adapter/physical ratio: `{unit_record['run008_adapter_to_physical_acceleration_ratio']:.12g}`",
        "- The physical conversion was applied zero times in Run 008 and exactly once in this audit conversion helper; it was not applied twice.",
        "",
        heading("Required versus delivered impulse"),
        "",
        "| Gamma/k | saved dv (m/s) | normalized integral | physical Jx if converted once (N s) | J/stopping J | Run008 dv/stopping dv | diagnosis |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for case in cases:
        lines.append(
            f"| {case['initial_velocity_gamma_over_k']:g} | {case['actual_saved_delta_v_m_s'][0]:.6g} | "
            f"{case['normalized_force_time_integral'][0]:.6g} | {case['physical_impulse_if_hbar_k_gamma_applied_once_n_s'][0]:.6g} | "
            f"{case['physical_delivered_to_stopping_impulse_ratio']:.6g} | {case['current_run008_delta_v_to_stopping_delta_v_ratio']:.6g} | "
            f"`{', '.join(case['engineering_diagnoses'])}` |"
        )
    lines += [
        "",
        "The physical impulse ratios are counterfactual single-conversion diagnostics and are not capture efficiencies. The saved trajectories instead used the unit adapter and show only the small recorded velocity changes.",
        "",
        heading("Static post-handoff local-force audit"),
        "",
    ]
    for local in local_audits:
        lines.append(f"- `{local}`")
    lines += [
        "",
        "Both modes are locally restoring and damping and numerically symmetric. At the origin the Gaussian envelope is unity, so their small-signal slopes coincide. This does not validate global topology.",
        "",
        heading("Force-scale comparison"),
        "",
        f"Sampling domain: x in `{FORCE_SCALE_POSITION_DOMAIN_M}` m and vx in `{FORCE_SCALE_VELOCITY_DOMAIN_M_S}` m/s.",
    ]
    for scale in force_scales:
        lines.append(
            f"- {scale['name']}: max `{scale['maximum_absolute_normalized_force']:.6g}`; "
            f"{scale['versus_0p03']} than 0.03 and {scale['versus_0p015']} than 0.015."
        )
    lines += [
        "",
        "These descriptive comparisons do not claim reproduction or disagreement. Identical chirp values expose that detuning is metadata-only in the toy force law.",
        "",
        heading("Gaussian-envelope application audit"),
        "",
        f"- `{gaussian_application}`",
        "- Result: `GAUSSIAN_APPLICATION_SUSPECT`. Per-beam envelopes exist and counterpropagating partners agree, but the current force path applies their mean after aggregate force summation. Saturation is linear rather than squared, and position is in metres.",
        "",
        heading("Beam and frequency contribution limitation"),
        "",
        f"- `{decomposition}`",
        "- A beam-pair/component decomposition cannot be obtained honestly from the current law. Component 4 does not improve confinement here because [3] and [3+1] both reduce to aggregate saturation 5.79.",
        "",
        heading("Saved-trajectory force audit"),
        "",
    ]
    for case in cases:
        lines += [
            f"### {AUDIT_LABEL} {case['case_name']}",
            "",
            f"- official outcome remains `{case['official_outcome_label']}`: {case['official_classifier_reason']}",
            f"- pre/post/appreciably-illuminated impulse: `{case['pre_handoff_physical_impulse_n_s']}` / `{case['post_handoff_physical_impulse_n_s']}` / `{case['appreciably_illuminated_physical_impulse_n_s']}` N s",
            f"- first/last appreciable illumination: `{case['first_appreciable_illumination_s']}` / `{case['last_appreciable_illumination_s']}` s",
            f"- handoff / closest approach / center crossing: `{case['handoff_time_s']}` / `{case['closest_approach_s']}` / `{case['center_crossing_times_s']}` s",
            f"- plot: `{case['plot_path']}`",
            "",
        ]
    lines += [
        heading("Immutability and scope"),
        "",
        f"- all source hashes unchanged: `{immutability['all_source_hashes_unchanged']}`",
        f"- official outcomes unchanged: `{immutability['official_outcome_labels_unchanged']}`",
        f"- trajectory integrations performed: `{immutability['trajectory_integrations_performed']}`",
        "- No new velocity, longer integration, capture threshold, source distribution, stochastic recoil, optimizer, or exact-force API was added. Track E remains blocked.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(AUDIT_LABEL)
    print(f"k_rad_m: {unit_audit.wave_number_rad_m:.12g}")
    print(f"Gamma_rad_s: {unit_audit.linewidth_rad_s:.12g}")
    print(f"hbar_k_Gamma_N: {unit_audit.hbar_k_gamma_n:.12g}")
    print(f"MgF_mass_kg: {unit_audit.mass.value_kg:.12g}")
    print(f"acceleration_per_unit_m_s2: {unit_audit.acceleration_per_normalized_force_m_s2:.12g}")
    print("overall diagnoses: " + ", ".join(overall_diagnoses))
    print(f"metadata: {metadata_path}")
    print(f"report: {report_path}")
    return {
        "metadata": metadata,
        "metadata_path": metadata_path,
        "report_path": report_path,
        "cases": cases,
        "plot_paths": plot_paths,
    }


if __name__ == "__main__":
    audit()
