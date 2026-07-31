"""Run Track P Run 006 ordered ensemble and outcome-classification checks.

The reported labels are provisional engineering categories. This script does
not search a velocity threshold or make a physical MOT claim.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from mgf_mot.mgf_backend import (
    ApproximationMode,
    build_mgf_hamiltonian_from_sources,
)
from mgf_mot.outcomes import (
    OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
    OutcomeCriteria,
    classify_trajectory,
    run_trajectory_ensemble,
)
from mgf_mot.policies import (
    ChirpToTrapHandoffPolicy,
    load_policy_config,
    policy_from_config,
)
from mgf_mot.provisional_force import ProvisionalForceMapConfig
from mgf_mot.trajectory import (
    TrajectoryConfig,
    TrajectoryInitialState,
    integrate_analytic_test_trajectory,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
POLICY_CONFIG_PATH = (
    REPO_ROOT / "configs" / "rodriguez_chirp_to_3_plus_1_handoff.yaml"
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


def _analytic_examples() -> list[dict[str, Any]]:
    criteria = OutcomeCriteria(
        max_position=0.05,
        max_speed=0.05,
        final_dwell_window_s=1.0,
        min_dwell_samples=50,
        required_dwell_fraction=1.0,
        hard_escape_position=2.0,
        hard_speed=6.0,
    )
    damped = integrate_analytic_test_trajectory(
        TrajectoryInitialState((1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        TrajectoryConfig(0.0, 5.0, 0.01),
        lambda _t, position, velocity: -4.0 * position - 3.0 * velocity,
        model_name="damped_harmonic_motion",
    )
    fast = integrate_analytic_test_trajectory(
        TrajectoryInitialState((0.0, 0.0, 0.0), (5.0, 0.0, 0.0)),
        TrajectoryConfig(0.0, 1.0, 0.01),
        lambda _t, _position, _velocity: np.zeros(3),
        model_name="fast_zero_force_motion",
    )
    short = integrate_analytic_test_trajectory(
        TrajectoryInitialState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        TrajectoryConfig(0.0, 0.5, 0.01),
        lambda _t, _position, _velocity: np.zeros(3),
        model_name="short_zero_force_motion",
    )
    center_crossing = integrate_analytic_test_trajectory(
        TrajectoryInitialState((1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        TrajectoryConfig(0.0, float(np.pi), 0.01),
        lambda _t, position, _velocity: -position,
        model_name="undamped_center_crossing",
    )
    invalid = SimpleNamespace(
        times_s=np.asarray((0.0, 1.0)),
        positions=np.asarray(((0.0, 0.0, 0.0), (np.nan, 0.0, 0.0))),
        velocities=np.zeros((2, 3)),
    )
    cases = (
        ("damped_bounded", damped),
        ("fast_escaped", fast),
        ("short_unresolved", short),
        ("nonfinite_invalid", invalid),
        ("center_crossing_not_bounded", center_crossing),
    )
    return [
        {
            "label": OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
            "title": f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} analytic {name}",
            "case": name,
            "outcome": _json_safe(classify_trajectory(trajectory, criteria)),
            "criteria": _json_safe(criteria),
            "uses_provisional_backend": False,
        }
        for name, trajectory in cases
    ]


def _save_plot(
    ensemble: Any, output_dir: Path
) -> tuple[Path | None, str | None]:
    try:
        import matplotlib.pyplot as plt

        plot_path = (
            output_dir
            / f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL}_run_006_z_trajectories.png"
        )
        fig, ax = plt.subplots()
        for index, member in enumerate(ensemble.members):
            if member.trajectory is None:
                continue
            initial_vz = member.initial_state.velocity[2]
            ax.plot(
                member.trajectory.times_s,
                member.trajectory.positions[:, 2],
                label=f"member {index}, initial v_z={initial_vz:g}",
            )
        ax.set_title(
            f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} Run 006 trajectories"
        )
        ax.set_xlabel("time [s]")
        ax.set_ylabel("z [normalized_position]")
        ax.legend()
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
    analytic_examples = _analytic_examples()

    source_config = load_policy_config(POLICY_CONFIG_PATH)
    if source_config.get("beam_model") != "infinite_plane_wave":
        raise ValueError("Run 006 supports only the infinite_plane_wave beam model")
    policy = policy_from_config(source_config)
    if not isinstance(policy, ChirpToTrapHandoffPolicy):
        raise TypeError("Run 006 requires ChirpToTrapHandoffPolicy")
    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    force_config = ProvisionalForceMapConfig(explicit_provisional_opt_in=True)
    trajectory_config = TrajectoryConfig(
        t_start_s=0.0,
        t_end_s=0.0014,
        time_step_s=0.0003,
        normalized_force_to_acceleration=1.0,
    )
    criteria = OutcomeCriteria(
        max_position=0.1,
        max_speed=0.1,
        final_dwell_window_s=0.0002,
        min_dwell_samples=2,
        required_dwell_fraction=1.0,
        hard_escape_position=0.5,
        hard_speed=0.5,
    )
    common_position = (0.0, 0.0, 0.05)
    initial_velocities = (
        (0.0, 0.0, -0.05),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.05),
    )
    initial_states = tuple(
        TrajectoryInitialState(common_position, velocity)
        for velocity in initial_velocities
    )
    ensemble = run_trajectory_ensemble(
        initial_states,
        policy,
        backend,
        force_config,
        trajectory_config,
        criteria,
    )
    provenance = backend.provenance

    print(OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL)
    print(f"track: {provenance.track.value}")
    print(f"backend_mode: {provenance.backend_mode}")
    print(f"replication_valid: {provenance.replication_valid}")
    print(f"force_ready: {provenance.force_ready}")
    print("warnings:")
    for warning in provenance.warnings:
        print(f"  - {warning}")
    print("omitted_terms:")
    for term in provenance.omitted_terms:
        print(f"  - {term}")
    print("collapsed_terms:")
    for term in provenance.collapsed_terms:
        print(f"  - {term}")
    print("analytic examples:")
    for example in analytic_examples:
        print(f"  - {example['case']}: {example['outcome']['label']}")
    print("provisional ordered ensemble:")
    for index, member in enumerate(ensemble.members):
        print(
            f"  - member {index}, initial v={member.initial_state.velocity}: "
            f"{member.outcome.label.value}; {member.outcome.numerical_reason}"
        )

    completed = tuple(
        member for member in ensemble.members if member.trajectory is not None
    )
    if len(completed) != len(ensemble.members):
        raise RuntimeError("Run 006 expected all provisional integrations to complete")
    reference_times = completed[0].trajectory.times_s
    if not all(
        np.array_equal(member.trajectory.times_s, reference_times)
        for member in completed
    ):
        raise RuntimeError("Run 006 ensemble members must share one time grid")
    positions = np.stack([member.trajectory.positions for member in completed])
    velocities = np.stack([member.trajectory.velocities for member in completed])
    forces = np.stack([member.trajectory.forces for member in completed])
    component_active = np.stack(
        [member.trajectory.component_active for member in completed]
    )

    arrays_path = (
        output_dir
        / f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL}_run_006_arrays.npz"
    )
    metadata_path = (
        output_dir
        / f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL}_run_006_metadata.json"
    )
    np.savez_compressed(
        arrays_path,
        times_s=reference_times,
        positions=positions,
        velocities=velocities,
        forces=forces,
        component_active=component_active,
        initial_positions=np.asarray(
            [member.initial_state.position for member in ensemble.members]
        ),
        initial_velocities=np.asarray(
            [member.initial_state.velocity for member in ensemble.members]
        ),
        outcome_labels=np.asarray(
            [member.outcome.label.value for member in ensemble.members]
        ),
    )
    plot_path: Path | None = None
    plot_error: str | None = None
    if save_plot:
        plot_path, plot_error = _save_plot(ensemble, output_dir)

    member_records = []
    for index, member in enumerate(ensemble.members):
        trajectory = member.trajectory
        member_records.append(
            {
                "label": OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
                "title": (
                    f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} ensemble member "
                    f"{index}"
                ),
                "index": index,
                "initial_state": _json_safe(member.initial_state),
                "integration_status": member.integration_status,
                "outcome": _json_safe(member.outcome),
                "provenance": _json_safe(member.provenance),
                "time_shape": (
                    None if trajectory is None else list(trajectory.times_s.shape)
                ),
                "position_shape": (
                    None if trajectory is None else list(trajectory.positions.shape)
                ),
                "event_times_s": (
                    None
                    if trajectory is None
                    else list(trajectory.metadata.encountered_event_times_s)
                ),
                "component_4_active_before_handoff": (
                    None
                    if trajectory is None
                    else bool(
                        trajectory.component_active[
                            trajectory.times_s < policy.handoff_time_s, 3
                        ].any()
                    )
                ),
                "component_4_active_at_and_after_handoff": (
                    None
                    if trajectory is None
                    else bool(
                        trajectory.component_active[
                            trajectory.times_s >= policy.handoff_time_s, 3
                        ].all()
                    )
                ),
            }
        )
    backend_record = _json_safe(provenance)
    backend_record.update(
        {
            "label": OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
            "title": (
                f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} backend provenance"
            ),
        }
    )
    metadata = {
        "label": OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
        "title": f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} Run 006 metadata",
        "run_type": "outcome_classification_scaffold_only",
        "replication_valid": False,
        "force_ready": False,
        "beam_model": source_config["beam_model"],
        "policy_config_path": str(POLICY_CONFIG_PATH.relative_to(REPO_ROOT)),
        "criteria_status": "provisional_engineering_defined",
        "criteria": _json_safe(criteria),
        "analytic_examples": analytic_examples,
        "ensemble_metadata": _json_safe(ensemble.metadata),
        "backend_provenance": backend_record,
        "members": member_records,
        "initial_state_order_preserved": True,
        "event_time_exact_in_all_members": bool(
            all(
                np.any(member.trajectory.times_s == policy.handoff_time_s)
                for member in completed
            )
        ),
        "arrays_finite": bool(
            np.isfinite(positions).all()
            and np.isfinite(velocities).all()
            and np.isfinite(forces).all()
        ),
        "arrays_path": arrays_path.name,
        "plot_path": None if plot_path is None else plot_path.name,
        "plot_error": plot_error,
        "disclaimer": (
            f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL}: engineering-defined "
            "outcomes only; no velocity-threshold search, source distribution, "
            "Gaussian beam, optimization, exact force, or physical conclusion."
        ),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = (
        output_dir
        / f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL}_run_006.md"
    )
    report_lines = [
        f"# {OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} Run 006",
        "",
        "The outcome criteria are provisional and engineering-defined.",
        "`BOUNDED_FINAL_STATE` is not equivalent to physical MOT capture.",
        "Exact MgF force readiness remains blocked.",
        "Infinite plane waves were used.",
        "No Gaussian beam envelope or molecular source distribution was included.",
        "No capture velocity was calculated and no threshold search was performed.",
        "No physical conclusions should be drawn.",
        "",
        f"## {OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} Criteria",
        "",
        f"- position measure: `{criteria.position_measure}`",
        f"- final position bound: `{criteria.max_position}`",
        f"- final speed bound: `{criteria.max_speed}`",
        f"- final dwell window: `{criteria.final_dwell_window_s}` s",
        f"- minimum dwell samples: `{criteria.min_dwell_samples}`",
        f"- required dwell fraction: `{criteria.required_dwell_fraction}`",
        f"- hard escape-position bound: `{criteria.hard_escape_position}`",
        f"- hard speed bound: `{criteria.hard_speed}`",
        "",
        f"## {OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} Analytic classifier examples",
        "",
    ]
    report_lines.extend(
        f"- `{example['case']}`: `{example['outcome']['label']}` — "
        f"{example['outcome']['numerical_reason']}"
        for example in analytic_examples
    )
    report_lines.extend(
        [
            "",
            f"## {OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} Ordered provisional ensemble",
            "",
        ]
    )
    for index, member in enumerate(ensemble.members):
        report_lines.extend(
            [
                f"### {OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} Member {index}",
                "",
                f"- initial position: `{member.initial_state.position}`",
                f"- initial velocity: `{member.initial_state.velocity}`",
                f"- integration status: `{member.integration_status}`",
                f"- outcome: `{member.outcome.label.value}`",
                f"- numerical reason: {member.outcome.numerical_reason}",
                (
                    "- event-aware handoff time encountered: "
                    f"`{member.trajectory.metadata.encountered_event_times_s}`"
                ),
                "",
            ]
        )
    report_lines.extend(
        [
            f"## {OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} Quarantined artifacts",
            "",
            f"- arrays: `{arrays_path.name}`",
            f"- metadata: `{metadata_path.name}`",
            f"- plot: `{None if plot_path is None else plot_path.name}`",
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote report: {report_path}")
    return {
        "analytic_examples": analytic_examples,
        "ensemble": ensemble,
        "arrays_path": arrays_path,
        "metadata_path": metadata_path,
        "plot_path": plot_path,
        "report_path": report_path,
    }


def main() -> None:
    run()


if __name__ == "__main__":
    main()
