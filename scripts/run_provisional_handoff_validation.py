"""Run Track P Run 005 chirp-to-[3+1] handoff validation.

This script inspects the instantaneous policy boundary and one event-split RK4
trajectory. It does not define capture, loss, loading, or physical validity.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.mgf_backend import (
    ApproximationMode,
    build_mgf_hamiltonian_from_sources,
)
from mgf_mot.policies import (
    ChirpToTrapHandoffPolicy,
    PolicySample,
    load_policy_config,
    policy_from_config,
)
from mgf_mot.provisional_force import FULL_WARNING_LABEL, ProvisionalForceMapConfig
from mgf_mot.trajectory import (
    TrajectoryConfig,
    TrajectoryInitialState,
    integrate_policy_trajectory,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
POLICY_CONFIG_PATH = (
    REPO_ROOT / "configs" / "rodriguez_chirp_to_3_plus_1_handoff.yaml"
)
HANDOFF_VALIDATION_LABEL = f"{FULL_WARNING_LABEL}_HANDOFF_VALIDATION_ONLY"
BOUNDARY_EPSILON_S = 1.0e-9


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


def _snapshot_record(
    policy: ChirpToTrapHandoffPolicy,
    label: str,
    time_s: float,
) -> dict[str, Any]:
    sample = policy.sample(time_s)
    return {
        "label": HANDOFF_VALIDATION_LABEL,
        "title": f"{HANDOFF_VALIDATION_LABEL} {label}",
        "sample_label": label,
        "time_s": sample.time_s,
        "current_policy_segment": sample.segment,
        "handoff_occurred": sample.handoff_occurred,
        "component_order": list(sample.component_order),
        "detuning_unit": sample.detuning_unit,
        "saturation_unit": sample.saturation_unit,
        "components": [
            {
                "component_id": component.component_id,
                "detuning_gamma": component.detuning_gamma,
                "saturation": component.saturation,
                "enabled": component.enabled,
                "active": component.active,
                "role": component.role,
                "off_reason": component.off_reason,
            }
            for component in sample.components
        ],
    }


def _save_plot(
    result: Any, tau_s: float, output_dir: Path
) -> tuple[Path | None, str | None]:
    try:
        import matplotlib.pyplot as plt

        plot_path = (
            output_dir / f"{HANDOFF_VALIDATION_LABEL}_run_005_z_state.png"
        )
        fig, axes = plt.subplots(2, 1, sharex=True)
        axes[0].plot(result.times_s, result.positions[:, 2], marker="o")
        axes[0].axvline(tau_s, color="black", linestyle="--", label="handoff")
        axes[0].set_ylabel(f"z [{result.metadata.position_unit}]")
        axes[0].legend()
        axes[1].plot(result.times_s, result.velocities[:, 2], marker="o")
        axes[1].axvline(tau_s, color="black", linestyle="--")
        axes[1].set_xlabel("time [s]")
        axes[1].set_ylabel(f"v_z [{result.metadata.velocity_unit}]")
        fig.suptitle(f"{HANDOFF_VALIDATION_LABEL} Run 005 event split")
        fig.tight_layout()
        fig.savefig(plot_path)
        plt.close(fig)
        return plot_path, None
    except Exception as exc:  # pragma: no cover - optional plotting stack
        return None, repr(exc)


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    save_plot: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_config = load_policy_config(POLICY_CONFIG_PATH)
    if source_config.get("beam_model") != "infinite_plane_wave":
        raise ValueError("Run 005 supports only the infinite_plane_wave beam model")
    policy = policy_from_config(source_config)
    if not isinstance(policy, ChirpToTrapHandoffPolicy):
        raise TypeError("Run 005 requires ChirpToTrapHandoffPolicy")

    tau_s = policy.handoff_time_s
    sample_spec = (
        ("t_0", 0.0),
        ("t_tau_over_2", tau_s / 2.0),
        ("t_tau_minus_epsilon", tau_s - BOUNDARY_EPSILON_S),
        ("t_tau", tau_s),
        ("t_tau_plus_epsilon", tau_s + BOUNDARY_EPSILON_S),
        ("t_2tau", 2.0 * tau_s),
    )
    snapshots = [
        _snapshot_record(policy, label, time_s)
        for label, time_s in sample_spec
    ]

    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    provenance = backend.provenance
    requested_time_step_s = 0.0005
    trajectory_config = TrajectoryConfig(
        t_start_s=0.0007,
        t_end_s=0.0013,
        time_step_s=requested_time_step_s,
        normalized_force_to_acceleration=1.0,
    )
    initial_state = TrajectoryInitialState(
        position=(0.0, 0.0, 0.05),
        velocity=(0.0, 0.0, 0.0),
    )
    result = integrate_policy_trajectory(
        policy,
        initial_state,
        backend,
        ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
        trajectory_config,
    )

    event_indices = np.flatnonzero(result.times_s == tau_s)
    if event_indices.size != 1:
        raise RuntimeError("event-aware integration did not contain tau exactly once")
    event_index = int(event_indices[0])
    if event_index == 0 or event_index >= result.times_s.size - 1:
        raise RuntimeError("Run 005 trajectory must straddle the handoff")

    checks = {
        "label": HANDOFF_VALIDATION_LABEL,
        "title": f"{HANDOFF_VALIDATION_LABEL} deterministic event checks",
        "tau_s": tau_s,
        "requested_time_step_s": requested_time_step_s,
        "tau_exact_in_time_array": bool(np.any(result.times_s == tau_s)),
        "step_ends_exactly_at_tau": bool(result.times_s[event_index] == tau_s),
        "next_step_starts_at_tau_with_post_handoff_state": bool(
            result.policy_segments[event_index] == "trap_3_plus_1"
            and result.handoff_occurred[event_index]
        ),
        "component_4_inactive_before_tau": bool(
            not result.component_active[event_index - 1, 3]
        ),
        "component_4_active_at_tau": bool(result.component_active[event_index, 3]),
        "component_4_active_after_tau": bool(
            result.component_active[event_index + 1, 3]
        ),
        "component_3_saturation_before_tau": float(
            result.component_saturations[event_index - 1, 2]
        ),
        "component_3_saturation_at_tau": float(
            result.component_saturations[event_index, 2]
        ),
        "known_event_times_s": list(result.metadata.known_event_times_s),
        "encountered_event_times_s": list(
            result.metadata.encountered_event_times_s
        ),
        "event_index": event_index,
    }

    print(HANDOFF_VALIDATION_LABEL)
    print(f"track: {provenance.track.value}")
    print(f"backend_mode: {provenance.backend_mode}")
    print(f"replication_valid: {provenance.replication_valid}")
    print(f"force_ready: {provenance.force_ready}")
    print(f"event_times_s: {policy.event_times_s}")
    print("warnings:")
    for warning in provenance.warnings:
        print(f"  - {warning}")
    print("omitted_terms:")
    for term in provenance.omitted_terms:
        print(f"  - {term}")
    print("collapsed_terms:")
    for term in provenance.collapsed_terms:
        print(f"  - {term}")
    for snapshot in snapshots:
        print(
            f"{snapshot['sample_label']}: t={snapshot['time_s']:.9g}s "
            f"segment={snapshot['current_policy_segment']} "
            f"handoff={snapshot['handoff_occurred']} "
            f"saturations={tuple(item['saturation'] for item in snapshot['components'])}"
        )
    print(f"trajectory times: {result.times_s}")

    arrays_path = output_dir / f"{HANDOFF_VALIDATION_LABEL}_run_005_arrays.npz"
    metadata_path = output_dir / f"{HANDOFF_VALIDATION_LABEL}_run_005_metadata.json"
    np.savez_compressed(
        arrays_path,
        times_s=result.times_s,
        positions=result.positions,
        velocities=result.velocities,
        forces=result.forces,
        component_detunings_gamma=result.component_detunings_gamma,
        component_saturations=result.component_saturations,
        component_enabled=result.component_enabled,
        component_active=result.component_active,
        policy_segments=np.asarray(result.policy_segments),
        handoff_occurred=result.handoff_occurred,
    )
    plot_path: Path | None = None
    plot_error: str | None = None
    if save_plot:
        plot_path, plot_error = _save_plot(result, tau_s, output_dir)

    trajectory_metadata_record = _json_safe(result.metadata)
    trajectory_metadata_record.update(
        {
            "base_scaffold_label": trajectory_metadata_record["label"],
            "label": HANDOFF_VALIDATION_LABEL,
            "title": f"{HANDOFF_VALIDATION_LABEL} trajectory metadata",
        }
    )
    backend_provenance_record = _json_safe(provenance)
    backend_provenance_record.update(
        {
            "label": HANDOFF_VALIDATION_LABEL,
            "title": f"{HANDOFF_VALIDATION_LABEL} backend provenance",
        }
    )
    metadata = {
        "label": HANDOFF_VALIDATION_LABEL,
        "title": f"{HANDOFF_VALIDATION_LABEL} Run 005 metadata",
        "run_type": "handoff_validation_only",
        "replication_valid": False,
        "force_ready": False,
        "beam_model": source_config["beam_model"],
        "policy_config_path": str(POLICY_CONFIG_PATH.relative_to(REPO_ROOT)),
        "boundary_epsilon_s": BOUNDARY_EPSILON_S,
        "boundary_epsilon_purpose": (
            "policy-boundary inspection only; it is not an integration or apparatus timescale"
        ),
        "boundary_convention": "t < tau uses chirp/[3]; t >= tau uses final [3+1]",
        "snapshots": snapshots,
        "trajectory_checks": checks,
        "trajectory_metadata": trajectory_metadata_record,
        "backend_provenance": backend_provenance_record,
        "initial_state": _json_safe(initial_state),
        "trajectory_config": _json_safe(trajectory_config),
        "times_shape": list(result.times_s.shape),
        "positions_shape": list(result.positions.shape),
        "velocities_shape": list(result.velocities.shape),
        "forces_shape": list(result.forces.shape),
        "arrays_finite": bool(
            np.isfinite(result.positions).all()
            and np.isfinite(result.velocities).all()
            and np.isfinite(result.forces).all()
        ),
        "arrays_path": arrays_path.name,
        "plot_path": None if plot_path is None else plot_path.name,
        "plot_error": plot_error,
        "disclaimer": (
            f"{HANDOFF_VALIDATION_LABEL}: event and trajectory plumbing only; "
            "no capture/loss classification, source distribution, Gaussian beam, "
            "optimization, exact force map, or physical conclusion."
        ),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = output_dir / f"{HANDOFF_VALIDATION_LABEL}_run_005.md"
    report_lines = [
        f"# {HANDOFF_VALIDATION_LABEL} Run 005",
        "",
        "This validates an instantaneous chirp-to-[3+1] policy handoff and event-aware trajectory plumbing only.",
        "",
        "Exact MgF force readiness remains blocked.",
        "The provisional backend is approximate and not replication-valid.",
        "No capture velocity or capture/loss classification was computed.",
        "No molecular-beam source distribution was used.",
        "No Gaussian beams or optimizer were used.",
        "No physical conclusions should be drawn from this trajectory.",
        "",
        f"## {HANDOFF_VALIDATION_LABEL} Boundary convention",
        "",
        "- `t < tau`: chirped `[3]` state.",
        "- `t >= tau`: final static `[3+1]` state.",
        "- The handoff is instantaneous; no smoothing or interpolation is applied.",
        f"- `tau = {tau_s}` s.",
        f"- `epsilon = {BOUNDARY_EPSILON_S}` s, used only to inspect either side of the policy boundary.",
        "",
        f"## {HANDOFF_VALIDATION_LABEL} Policy-state snapshots",
        "",
    ]
    for snapshot in snapshots:
        report_lines.extend(
            [
                f"### {HANDOFF_VALIDATION_LABEL} {snapshot['sample_label']}",
                "",
                f"- time: `{snapshot['time_s']}` s",
                f"- current policy segment: `{snapshot['current_policy_segment']}`",
                f"- handoff occurred: `{snapshot['handoff_occurred']}`",
                "",
                "| component | detuning [Gamma] | saturation | enabled | active | role | off reason |",
                "|---:|---:|---:|:---:|:---:|---|---|",
                *[
                    (
                        f"| {item['component_id']} | {item['detuning_gamma']} | "
                        f"{item['saturation']} | {item['enabled']} | {item['active']} | "
                        f"{item['role']} | {item['off_reason']} |"
                    )
                    for item in snapshot["components"]
                ],
                "",
            ]
        )
    report_lines.extend(
        [
            f"## {HANDOFF_VALIDATION_LABEL} Event-aware trajectory checks",
            "",
            f"- requested timestep: `{requested_time_step_s}` s",
            f"- trajectory times: `{result.times_s.tolist()}`",
            f"- time array contains tau exactly: `{checks['tau_exact_in_time_array']}`",
            f"- a step ends exactly at tau: `{checks['step_ends_exactly_at_tau']}`",
            f"- next step starts at tau with post-handoff state: `{checks['next_step_starts_at_tau_with_post_handoff_state']}`",
            f"- component 4 inactive before tau: `{checks['component_4_inactive_before_tau']}`",
            f"- component 4 active at tau: `{checks['component_4_active_at_tau']}`",
            f"- component 4 active after tau: `{checks['component_4_active_after_tau']}`",
            f"- component 3 saturation before/at tau: `{checks['component_3_saturation_before_tau']}` / `{checks['component_3_saturation_at_tau']}`",
            f"- encountered event times: `{checks['encountered_event_times_s']}`",
            f"- arrays: `{arrays_path.name}`",
            f"- metadata: `{metadata_path.name}`",
            f"- plot: `{None if plot_path is None else plot_path.name}`",
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote report: {report_path}")
    return {
        "policy": policy,
        "snapshots": snapshots,
        "result": result,
        "checks": checks,
        "arrays_path": arrays_path,
        "metadata_path": metadata_path,
        "plot_path": plot_path,
        "report_path": report_path,
    }


def main() -> None:
    run()


if __name__ == "__main__":
    main()
