"""Run Track P Run 008 named finite-beam trajectories.

This executes five explicit diagnostic cases. It does not insert velocities,
search a boundary, or report a maximum successful velocity.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.mgf_backend import (
    ApproximationMode,
    build_mgf_hamiltonian_from_sources,
)
from mgf_mot.named_protocol import (
    NamedInitialVelocity,
    RodriguezTrajectoryProtocol,
    load_rodriguez_named_trajectory_protocol,
)
from mgf_mot.outcomes import OutcomeLabel, run_trajectory_ensemble
from mgf_mot.policies import ChirpToTrapHandoffPolicy, load_policy
from mgf_mot.provisional_force import ProvisionalForceMapConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
PROTOCOL_CONFIG_PATH = (
    REPO_ROOT / "configs" / "rodriguez_named_trajectory_protocol.yaml"
)
NAMED_TRAJECTORY_PROTOCOL_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_NAMED_TRAJECTORY_PROTOCOL_ONLY"
)


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _inside_bound_times(
    times_s: np.ndarray,
    positions_m: np.ndarray,
    bound_m: float,
) -> dict[str, Any]:
    inside = np.linalg.norm(positions_m, axis=1) <= bound_m
    indices = np.flatnonzero(inside)
    return {
        "bound_m": bound_m,
        "first_time_s": None if indices.size == 0 else float(times_s[indices[0]]),
        "last_time_s": None if indices.size == 0 else float(times_s[indices[-1]]),
        "sample_count": int(indices.size),
    }


def _crossed_zero(x_positions_m: np.ndarray) -> bool:
    if np.any(x_positions_m == 0.0):
        return True
    return bool(np.any(x_positions_m[:-1] * x_positions_m[1:] < 0.0))


def _case_diagnostics(
    protocol: RodriguezTrajectoryProtocol,
    named_velocity: NamedInitialVelocity,
    member: Any,
) -> dict[str, Any]:
    trajectory = member.trajectory
    if trajectory is None:
        raise RuntimeError(f"named trajectory {named_velocity.name} did not complete")
    times = trajectory.times_s
    positions = trajectory.positions
    velocities = trajectory.velocities
    x = positions[:, 0]
    vx = velocities[:, 0]
    distances = np.linalg.norm(positions, axis=1)
    closest_index = int(np.argmin(distances))
    crossed = _crossed_zero(x)
    primary_bound = protocol.outcome_criteria.max_position
    near_origin = distances <= primary_bound
    minimum_abs_vx_near_origin = (
        None if not near_origin.any() else float(np.min(np.abs(vx[near_origin])))
    )
    approached = bool(float(np.min(distances)) < abs(protocol.initial_position_m[0]))
    slowed_near_origin = bool(
        minimum_abs_vx_near_origin is not None
        and minimum_abs_vx_near_origin < named_velocity.velocity_m_s
    )
    remained_in_final_bounds = (
        member.outcome.label is OutcomeLabel.BOUNDED_FINAL_STATE
    )
    tau_s = trajectory.metadata.known_event_times_s[0]
    return {
        "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
        "title": (
            f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} diagnostics "
            f"{named_velocity.name}"
        ),
        "case_name": named_velocity.name,
        "initial_velocity_gamma_over_k": named_velocity.gamma_over_k,
        "initial_velocity_m_s": named_velocity.velocity_m_s,
        "final_position_m": positions[-1].tolist(),
        "final_velocity_m_s": velocities[-1].tolist(),
        "minimum_distance_from_origin_m": float(distances[closest_index]),
        "time_of_closest_approach_s": float(times[closest_index]),
        "maximum_vx_m_s": float(np.max(vx)),
        "minimum_vx_m_s": float(np.min(vx)),
        "crossed_x_zero": crossed,
        "inside_position_bounds": [
            _inside_bound_times(times, positions, bound)
            for bound in protocol.diagnostic_position_bounds_m
        ],
        "approached_origin": approached,
        "slowed_near_origin": slowed_near_origin,
        "minimum_abs_vx_near_origin_m_s": minimum_abs_vx_near_origin,
        "remained_within_provisional_final_bounds": remained_in_final_bounds,
        "center_crossing_without_bounded_final_state": bool(
            crossed and not remained_in_final_bounds
        ),
        "final_dwell_statistics": {
            "dwell_start_s": member.outcome.dwell_start_s,
            "dwell_end_s": member.outcome.dwell_end_s,
            "dwell_sample_count": member.outcome.dwell_sample_count,
            "dwell_in_bounds_count": member.outcome.dwell_in_bounds_count,
            "dwell_in_bounds_fraction": member.outcome.dwell_in_bounds_fraction,
            "max_position_dwell": member.outcome.max_position_dwell,
            "max_speed_dwell": member.outcome.max_speed_dwell,
        },
        "outcome_label": member.outcome.label.value,
        "numerical_reason": member.outcome.numerical_reason,
        "integration_status": member.integration_status,
        "exact_handoff_event": {
            "tau_s": tau_s,
            "landed_exactly": bool(np.any(times == tau_s)),
            "known_event_times_s": list(trajectory.metadata.known_event_times_s),
            "encountered_event_times_s": list(
                trajectory.metadata.encountered_event_times_s
            ),
        },
        "component_4_inactive_before_tau": bool(
            not trajectory.component_active[times < tau_s, 3].any()
        ),
        "component_4_active_at_and_after_tau": bool(
            trajectory.component_active[times >= tau_s, 3].all()
        ),
        "trajectory_arrays_finite": bool(
            np.isfinite(times).all()
            and np.isfinite(positions).all()
            and np.isfinite(velocities).all()
            and np.isfinite(trajectory.forces).all()
        ),
    }


def _save_case_plot(
    case_name: str,
    member: Any,
    tau_s: float,
    position_bound_m: float,
    output_dir: Path,
) -> tuple[Path | None, str | None]:
    try:
        import matplotlib.pyplot as plt

        trajectory = member.trajectory
        path = (
            output_dir
            / f"{NAMED_TRAJECTORY_PROTOCOL_LABEL}_{case_name}_run_008.png"
        )
        fig, axes = plt.subplots(3, 1)
        axes[0].plot(trajectory.times_s, trajectory.positions[:, 0])
        axes[0].axhline(0.0, color="black", linewidth=0.8)
        axes[0].axhline(position_bound_m, color="gray", linestyle=":")
        axes[0].axhline(-position_bound_m, color="gray", linestyle=":")
        axes[0].axvline(tau_s, color="red", linestyle="--")
        axes[0].set_ylabel("x [m]")
        axes[1].plot(trajectory.times_s, trajectory.velocities[:, 0])
        axes[1].axvline(tau_s, color="red", linestyle="--")
        axes[1].set_ylabel("v_x [m/s]")
        axes[1].set_xlabel("time [s]")
        axes[2].plot(trajectory.positions[:, 0], trajectory.velocities[:, 0])
        axes[2].axvline(0.0, color="black", linewidth=0.8)
        axes[2].axvline(position_bound_m, color="gray", linestyle=":")
        axes[2].axvline(-position_bound_m, color="gray", linestyle=":")
        axes[2].set_xlabel("x [m]")
        axes[2].set_ylabel("v_x [m/s]")
        fig.suptitle(
            f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} {case_name} Run 008"
        )
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path, None
    except Exception as exc:  # pragma: no cover - optional plotting stack
        return None, repr(exc)


def _save_combined_plot(
    protocol: RodriguezTrajectoryProtocol,
    ensemble: Any,
    tau_s: float,
    output_dir: Path,
) -> tuple[Path | None, str | None]:
    try:
        import matplotlib.pyplot as plt

        path = (
            output_dir
            / f"{NAMED_TRAJECTORY_PROTOCOL_LABEL}_run_008_combined.png"
        )
        fig, axes = plt.subplots(2, 1, sharex=True)
        for named_velocity, member in zip(
            protocol.named_velocities, ensemble.members
        ):
            trajectory = member.trajectory
            label = f"{named_velocity.gamma_over_k:g} Gamma/k"
            axes[0].plot(
                trajectory.times_s, trajectory.positions[:, 0], label=label
            )
            axes[1].plot(
                trajectory.times_s, trajectory.velocities[:, 0], label=label
            )
        axes[0].axhline(0.0, color="black", linewidth=0.8)
        axes[0].axhline(
            protocol.outcome_criteria.max_position, color="gray", linestyle=":"
        )
        axes[0].axhline(
            -protocol.outcome_criteria.max_position, color="gray", linestyle=":"
        )
        axes[0].axvline(tau_s, color="red", linestyle="--")
        axes[1].axvline(tau_s, color="red", linestyle="--")
        axes[0].set_ylabel("x [m]")
        axes[1].set_ylabel("v_x [m/s]")
        axes[1].set_xlabel("time [s]")
        axes[0].legend()
        fig.suptitle(
            f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} Run 008 combined comparison"
        )
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path, None
    except Exception as exc:  # pragma: no cover - optional plotting stack
        return None, repr(exc)


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    save_plots: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    protocol = load_rodriguez_named_trajectory_protocol(PROTOCOL_CONFIG_PATH)
    gaussian_config = load_gaussian_envelope_config(
        REPO_ROOT / protocol.gaussian_config_path
    )
    policy = load_policy(REPO_ROOT / protocol.handoff_policy_config_path)
    if not isinstance(policy, ChirpToTrapHandoffPolicy):
        raise TypeError("Run 008 requires the chirp-to-[3+1] handoff policy")
    if tuple(
        component.saturation for component in policy.sample(0.0).components
    ) != protocol.pre_handoff_saturations:
        raise ValueError("policy pre-handoff saturations do not match protocol")
    if tuple(
        component.saturation
        for component in policy.sample(policy.handoff_time_s).components
    ) != protocol.post_handoff_saturations:
        raise ValueError("policy post-handoff saturations do not match protocol")
    beam_set = build_rodriguez_gaussian_beam_set(
        gaussian_config,
        protocol.post_handoff_saturations,
    )
    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    force_config = ProvisionalForceMapConfig(
        explicit_provisional_opt_in=True,
        beam_mode="elliptical_gaussian",
        gaussian_beam_set=beam_set,
        position_unit="m",
        magnetic_gradient_t_m=protocol.magnetic_gradient_t_m,
        normalized_gradient_scale=protocol.normalized_gradient_scale,
    )
    ensemble = run_trajectory_ensemble(
        protocol.initial_states(),
        policy,
        backend,
        force_config,
        protocol.trajectory_config(),
        protocol.outcome_criteria,
    )

    print(NAMED_TRAJECTORY_PROTOCOL_LABEL)
    print(f"track: {backend.provenance.track.value}")
    print(f"backend_mode: {backend.provenance.backend_mode}")
    print(f"replication_valid: {backend.provenance.replication_valid}")
    print(f"beam_mode: {force_config.beam_mode}")
    print(f"initial_position_m: {protocol.initial_position_m}")
    print(f"simulation_duration_s: {protocol.simulation_duration_s}")
    print(f"magnetic_gradient_t_m: {protocol.magnetic_gradient_t_m}")
    print("warnings:")
    for warning in protocol.warnings + backend.provenance.warnings:
        print(f"  - {warning}")

    case_records: list[dict[str, Any]] = []
    for named_velocity, member in zip(
        protocol.named_velocities, ensemble.members
    ):
        diagnostics = _case_diagnostics(protocol, named_velocity, member)
        trajectory = member.trajectory
        arrays_path = (
            output_dir
            / f"{NAMED_TRAJECTORY_PROTOCOL_LABEL}_{named_velocity.name}_run_008_arrays.npz"
        )
        metadata_path = (
            output_dir
            / f"{NAMED_TRAJECTORY_PROTOCOL_LABEL}_{named_velocity.name}_run_008_metadata.json"
        )
        np.savez_compressed(
            arrays_path,
            times_s=trajectory.times_s,
            positions_m=trajectory.positions,
            velocities_m_s=trajectory.velocities,
            normalized_forces=trajectory.forces,
            component_detunings_gamma=trajectory.component_detunings_gamma,
            component_saturations=trajectory.component_saturations,
            component_active=trajectory.component_active,
            handoff_occurred=trajectory.handoff_occurred,
        )
        plot_path: Path | None = None
        plot_error: str | None = None
        if save_plots:
            plot_path, plot_error = _save_case_plot(
                named_velocity.name,
                member,
                policy.handoff_time_s,
                protocol.outcome_criteria.max_position,
                output_dir,
            )
        backend_record = _json_safe(backend.provenance)
        backend_record.update(
            {
                "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
                "title": (
                    f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} backend provenance "
                    f"{named_velocity.name}"
                ),
            }
        )
        outcome_record = _json_safe(member.outcome)
        outcome_record.update(
            {
                "artifact_label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
                "artifact_title": (
                    f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} outcome "
                    f"{named_velocity.name}"
                ),
            }
        )
        member_provenance_record = _json_safe(member.provenance)
        member_provenance_record.update(
            {
                "base_scaffold_label": member_provenance_record["label"],
                "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
                "title": (
                    f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} member provenance "
                    f"{named_velocity.name}"
                ),
            }
        )
        trajectory_metadata_record = _json_safe(trajectory.metadata)
        trajectory_metadata_record.update(
            {
                "base_scaffold_label": trajectory_metadata_record["label"],
                "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
                "title": (
                    f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} trajectory metadata "
                    f"{named_velocity.name}"
                ),
            }
        )
        case_metadata = {
            "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
            "title": (
                f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} {named_velocity.name} "
                "metadata"
            ),
            "replication_valid": False,
            "force_ready": False,
            "protocol_name": protocol.name,
            "beam_mode": force_config.beam_mode,
            "diagnostics": diagnostics,
            "outcome": outcome_record,
            "member_provenance": member_provenance_record,
            "backend_provenance": backend_record,
            "trajectory_metadata": trajectory_metadata_record,
            "arrays_path": arrays_path.name,
            "plot_path": None if plot_path is None else plot_path.name,
            "plot_error": plot_error,
            "disclaimer": (
                f"{NAMED_TRAJECTORY_PROTOCOL_LABEL}: one named case only; "
                "not a boundary search or physical capture claim."
            ),
        }
        metadata_path.write_text(
            json.dumps(case_metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        case_records.append(
            {
                "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
                "title": (
                    f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} case record "
                    f"{named_velocity.name}"
                ),
                "named_velocity": named_velocity,
                "member": member,
                "diagnostics": diagnostics,
                "arrays_path": arrays_path,
                "metadata_path": metadata_path,
                "plot_path": plot_path,
            }
        )
        print(
            f"{named_velocity.name}: {named_velocity.gamma_over_k:g} Gamma/k, "
            f"{named_velocity.velocity_m_s:g} m/s, "
            f"outcome={member.outcome.label.value}, "
            f"crossed={diagnostics['crossed_x_zero']}"
        )

    combined_plot_path: Path | None = None
    combined_plot_error: str | None = None
    if save_plots:
        combined_plot_path, combined_plot_error = _save_combined_plot(
            protocol, ensemble, policy.handoff_time_s, output_dir
        )

    metadata_path = (
        output_dir
        / f"{NAMED_TRAJECTORY_PROTOCOL_LABEL}_run_008_metadata.json"
    )
    protocol_record = _json_safe(protocol)
    protocol_record.update(
        {
            "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
            "title": f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} protocol provenance",
        }
    )
    metadata = {
        "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
        "title": f"{NAMED_TRAJECTORY_PROTOCOL_LABEL} Run 008 metadata",
        "run_type": "named_trajectory_protocol_only",
        "replication_valid": False,
        "force_ready": False,
        "protocol_config_path": str(
            PROTOCOL_CONFIG_PATH.relative_to(REPO_ROOT)
        ),
        "protocol": protocol_record,
        "beam_mode": force_config.beam_mode,
        "gaussian_geometry": _json_safe(gaussian_config),
        "total_power_conversion_performed": False,
        "initial_state_order_preserved": bool(
            tuple(member.initial_state for member in ensemble.members)
            == protocol.initial_states()
        ),
        "case_records": [
            {
                "label": NAMED_TRAJECTORY_PROTOCOL_LABEL,
                "title": record["title"],
                "name": record["named_velocity"].name,
                "gamma_over_k": record["named_velocity"].gamma_over_k,
                "velocity_m_s": record["named_velocity"].velocity_m_s,
                "diagnostics": record["diagnostics"],
                "arrays_path": record["arrays_path"].name,
                "metadata_path": record["metadata_path"].name,
                "plot_path": (
                    None
                    if record["plot_path"] is None
                    else record["plot_path"].name
                ),
            }
            for record in case_records
        ],
        "combined_plot_path": (
            None if combined_plot_path is None else combined_plot_path.name
        ),
        "combined_plot_error": combined_plot_error,
        "disclaimer": (
            f"{NAMED_TRAJECTORY_PROTOCOL_LABEL}: deterministic named cases "
            "only; no maximum-velocity interpolation, source distribution, "
            "stochastic recoil, optimization, exact force, or agreement claim."
        ),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = (
        output_dir / f"{NAMED_TRAJECTORY_PROTOCOL_LABEL}_run_008.md"
    )
    report_lines = [
        f"# {NAMED_TRAJECTORY_PROTOCOL_LABEL} Run 008",
        "",
        "This is an end-to-end provisional apparatus/plumbing test.",
        "The exact excited-state Hamiltonian remains unresolved.",
        "Outcomes are not physical capture claims.",
        "No capture boundary or maximum capture velocity was calculated.",
        "No molecular source distribution was used.",
        "No stochastic recoil or diffusion was included.",
        "Reported total power was not converted through a guessed allocation.",
        "No conclusion should be drawn about agreement with Rodriguez.",
        "",
        f"## {NAMED_TRAJECTORY_PROTOCOL_LABEL} Baseline protocol",
        "",
        f"- initial position: `{protocol.initial_position_m}` m",
        f"- motion direction: positive lab `x`, toward the origin",
        f"- duration: `{protocol.simulation_duration_s}` s",
        f"- timestep: `{protocol.time_step_s}` s",
        f"- magnetic gradient: `{protocol.magnetic_gradient_t_m}` T/m",
        f"- beam mode: `{force_config.beam_mode}`",
        f"- Gaussian radii: `{gaussian_config.wxy_m}` m, `{gaussian_config.wz_m}` m",
        f"- handoff time: `{policy.handoff_time_s}` s",
        f"- total power metadata: `{protocol.total_laser_power_w}` W",
        f"- power allocation: `{protocol.power_allocation_status}`",
        "",
        f"## {NAMED_TRAJECTORY_PROTOCOL_LABEL} Named trajectories",
        "",
    ]
    for record in case_records:
        named_velocity = record["named_velocity"]
        diagnostics = record["diagnostics"]
        report_lines.extend(
            [
                f"### {NAMED_TRAJECTORY_PROTOCOL_LABEL} {named_velocity.name}",
                "",
                f"- initial velocity: `{named_velocity.gamma_over_k}` Gamma/k = `{named_velocity.velocity_m_s}` m/s",
                f"- final position: `{diagnostics['final_position_m']}` m",
                f"- final velocity: `{diagnostics['final_velocity_m_s']}` m/s",
                f"- minimum distance from origin: `{diagnostics['minimum_distance_from_origin_m']}` m",
                f"- time of closest approach: `{diagnostics['time_of_closest_approach_s']}` s",
                f"- min/max v_x: `{diagnostics['minimum_vx_m_s']}` / `{diagnostics['maximum_vx_m_s']}` m/s",
                f"- approached origin: `{diagnostics['approached_origin']}`",
                f"- crossed x=0: `{diagnostics['crossed_x_zero']}`",
                f"- slowed near origin: `{diagnostics['slowed_near_origin']}`",
                f"- remained within final bounds: `{diagnostics['remained_within_provisional_final_bounds']}`",
                f"- center crossing without bounded final state: `{diagnostics['center_crossing_without_bounded_final_state']}`",
                f"- outcome: `{diagnostics['outcome_label']}`",
                f"- numerical reason: {diagnostics['numerical_reason']}",
                f"- handoff event: `{diagnostics['exact_handoff_event']}`",
                f"- component 4 inactive before handoff: `{diagnostics['component_4_inactive_before_tau']}`",
                f"- component 4 active at/after handoff: `{diagnostics['component_4_active_at_and_after_tau']}`",
                f"- arrays: `{record['arrays_path'].name}`",
                f"- metadata: `{record['metadata_path'].name}`",
                f"- plot: `{None if record['plot_path'] is None else record['plot_path'].name}`",
                "",
            ]
        )
    report_lines.extend(
        [
            f"## {NAMED_TRAJECTORY_PROTOCOL_LABEL} Combined comparison",
            "",
            f"- combined plot: `{None if combined_plot_path is None else combined_plot_path.name}`",
            f"- run metadata: `{metadata_path.name}`",
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote report: {report_path}")
    return {
        "protocol": protocol,
        "policy": policy,
        "beam_set": beam_set,
        "force_config": force_config,
        "ensemble": ensemble,
        "case_records": case_records,
        "metadata_path": metadata_path,
        "combined_plot_path": combined_plot_path,
        "report_path": report_path,
    }


def main() -> None:
    run()


if __name__ == "__main__":
    main()
