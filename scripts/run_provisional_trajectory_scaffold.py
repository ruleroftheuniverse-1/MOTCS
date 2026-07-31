"""Run Track P Run 004 trajectory-scaffold validation.

The analytic checks validate only the RK4 implementation. The single policy
run validates provisional schedule-to-force-to-state plumbing and has no
capture, loading, or replication interpretation.
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
    LinearChirpPolicy,
    load_policy_config,
    policy_from_config,
)
from mgf_mot.provisional_force import ProvisionalForceMapConfig
from mgf_mot.trajectory import (
    TRAJECTORY_SCAFFOLD_LABEL,
    TrajectoryConfig,
    TrajectoryInitialState,
    integrate_analytic_test_trajectory,
    integrate_policy_trajectory,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
POLICY_CONFIG_PATH = REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml"


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


def _run_analytic_checks() -> dict[str, Any]:
    config = TrajectoryConfig(
        t_start_s=0.0,
        t_end_s=0.1,
        time_step_s=0.005,
    )

    zero_initial = TrajectoryInitialState(
        position=(1.0, -2.0, 0.5),
        velocity=(0.25, -0.5, 1.0),
    )
    zero = integrate_analytic_test_trajectory(
        zero_initial,
        config,
        lambda _t, _r, _v: np.zeros(3),
        model_name="zero_acceleration",
    )
    zero_expected_position = (
        np.asarray(zero_initial.position)
        + zero.times_s[:, None] * np.asarray(zero_initial.velocity)
    )

    constant_acceleration = np.asarray((0.5, -1.0, 2.0))
    constant_initial = TrajectoryInitialState(
        position=(0.1, 0.2, -0.3),
        velocity=(0.4, -0.2, 0.1),
    )
    constant = integrate_analytic_test_trajectory(
        constant_initial,
        config,
        lambda _t, _r, _v: constant_acceleration,
        model_name="constant_acceleration",
    )
    constant_expected_position = (
        np.asarray(constant_initial.position)
        + constant.times_s[:, None] * np.asarray(constant_initial.velocity)
        + 0.5 * constant.times_s[:, None] ** 2 * constant_acceleration
    )
    constant_expected_velocity = (
        np.asarray(constant_initial.velocity)
        + constant.times_s[:, None] * constant_acceleration
    )

    damping_rate = 4.0
    damping = integrate_analytic_test_trajectory(
        TrajectoryInitialState(position=(0.0, 0.0, 0.0), velocity=(0.0, 0.0, 1.0)),
        config,
        lambda _t, _r, velocity: -damping_rate * velocity,
        model_name="linear_damping",
    )

    return {
        "label": TRAJECTORY_SCAFFOLD_LABEL,
        "zero_force_check": {
            "model_label": zero.label,
            "uses_mgf_backend": zero.uses_mgf_backend,
            "max_position_error": float(
                np.max(np.abs(zero.positions - zero_expected_position))
            ),
            "max_velocity_error": float(
                np.max(
                    np.abs(zero.velocities - np.asarray(zero_initial.velocity))
                )
            ),
        },
        "constant_force_check": {
            "model_label": constant.label,
            "uses_mgf_backend": constant.uses_mgf_backend,
            "max_position_error": float(
                np.max(np.abs(constant.positions - constant_expected_position))
            ),
            "max_velocity_error": float(
                np.max(np.abs(constant.velocities - constant_expected_velocity))
            ),
        },
        "linear_damping_check": {
            "model_label": damping.label,
            "uses_mgf_backend": damping.uses_mgf_backend,
            "initial_speed": float(np.linalg.norm(damping.velocities[0])),
            "final_speed": float(np.linalg.norm(damping.velocities[-1])),
        },
    }


def _save_plot(result: Any, output_dir: Path) -> tuple[Path | None, str | None]:
    try:
        import matplotlib.pyplot as plt

        plot_path = output_dir / f"{TRAJECTORY_SCAFFOLD_LABEL}_run_004_z_state.png"
        fig, axes = plt.subplots(2, 1, sharex=True)
        axes[0].plot(result.times_s, result.positions[:, 2])
        axes[0].set_ylabel(f"z [{result.metadata.position_unit}]")
        axes[1].plot(result.times_s, result.velocities[:, 2])
        axes[1].set_xlabel("time [s]")
        axes[1].set_ylabel(f"v_z [{result.metadata.velocity_unit}]")
        fig.suptitle(f"{TRAJECTORY_SCAFFOLD_LABEL} Run 004 z-state")
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
    analytic_checks = _run_analytic_checks()

    source_policy_config = load_policy_config(POLICY_CONFIG_PATH)
    if source_policy_config.get("beam_model") != "infinite_plane_wave":
        raise ValueError("Run 004 supports only the infinite_plane_wave beam model")
    policy = policy_from_config(source_policy_config)
    if not isinstance(policy, LinearChirpPolicy):
        raise TypeError("Run 004 expects the baseline linear chirp policy")
    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    provenance = backend.provenance
    force_config = ProvisionalForceMapConfig(explicit_provisional_opt_in=True)
    trajectory_config = TrajectoryConfig(
        t_start_s=0.0,
        t_end_s=0.0002,
        time_step_s=0.00002,
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
        force_config,
        trajectory_config,
    )

    print(TRAJECTORY_SCAFFOLD_LABEL)
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

    arrays_path = output_dir / f"{TRAJECTORY_SCAFFOLD_LABEL}_run_004_arrays.npz"
    metadata_path = output_dir / f"{TRAJECTORY_SCAFFOLD_LABEL}_run_004_metadata.json"
    np.savez_compressed(
        arrays_path,
        times_s=result.times_s,
        positions=result.positions,
        velocities=result.velocities,
        forces=result.forces,
        component_detunings_gamma=result.component_detunings_gamma,
        component_saturations=result.component_saturations,
        component_active=result.component_active,
    )
    plot_path: Path | None = None
    plot_error: str | None = None
    if save_plot:
        plot_path, plot_error = _save_plot(result, output_dir)

    metadata = {
        "label": TRAJECTORY_SCAFFOLD_LABEL,
        "title": f"{TRAJECTORY_SCAFFOLD_LABEL} Run 004 metadata",
        "run_type": "trajectory_scaffold_only",
        "policy_config_path": str(POLICY_CONFIG_PATH.relative_to(REPO_ROOT)),
        "beam_model": source_policy_config["beam_model"],
        "initial_state": _json_safe(initial_state),
        "trajectory_config": _json_safe(trajectory_config),
        "trajectory_metadata": _json_safe(result.metadata),
        "backend_provenance": _json_safe(provenance),
        "analytic_integrator_checks": analytic_checks,
        "times_shape": list(result.times_s.shape),
        "positions_shape": list(result.positions.shape),
        "velocities_shape": list(result.velocities.shape),
        "forces_shape": list(result.forces.shape),
        "arrays_finite": bool(
            np.isfinite(result.positions).all()
            and np.isfinite(result.velocities).all()
            and np.isfinite(result.forces).all()
        ),
        "component_4_active_any": bool(result.component_active[:, 3].any()),
        "component_4_saturation_max": float(
            np.max(result.component_saturations[:, 3])
        ),
        "arrays_path": arrays_path.name,
        "plot_path": None if plot_path is None else plot_path.name,
        "plot_error": plot_error,
        "replication_valid": False,
        "force_ready": False,
        "disclaimer": (
            f"{TRAJECTORY_SCAFFOLD_LABEL}: trajectory plumbing only; "
            "no capture, loading, source distribution, Gaussian beam, or physical claim."
        ),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = output_dir / f"{TRAJECTORY_SCAFFOLD_LABEL}_run_004.md"
    report_lines = [
        f"# {TRAJECTORY_SCAFFOLD_LABEL} Run 004",
        "",
        "This validates trajectory plumbing only.",
        "",
        "Exact MgF force readiness remains blocked.",
        "The provisional backend is approximate and not replication-valid.",
        "No capture velocity or capture/loss classification was computed.",
        "No molecular-beam source distribution was used.",
        "No Gaussian beams were used.",
        "No physical conclusions should be drawn from this trajectory.",
        "",
        f"## {TRAJECTORY_SCAFFOLD_LABEL} Analytic integrator checks",
        "",
        f"- zero-force maximum position error: `{analytic_checks['zero_force_check']['max_position_error']}`",
        f"- zero-force maximum velocity error: `{analytic_checks['zero_force_check']['max_velocity_error']}`",
        f"- constant-force maximum position error: `{analytic_checks['constant_force_check']['max_position_error']}`",
        f"- constant-force maximum velocity error: `{analytic_checks['constant_force_check']['max_velocity_error']}`",
        f"- damping initial speed: `{analytic_checks['linear_damping_check']['initial_speed']}`",
        f"- damping final speed: `{analytic_checks['linear_damping_check']['final_speed']}`",
        "",
        f"## {TRAJECTORY_SCAFFOLD_LABEL} Provisional policy smoke run",
        "",
        f"- track: `{provenance.track.value}`",
        f"- backend mode: `{provenance.backend_mode}`",
        f"- replication_valid: `{provenance.replication_valid}`",
        f"- force_ready: `{provenance.force_ready}`",
        f"- policy: `{policy.name}`",
        f"- beam model: `{source_policy_config['beam_model']}`",
        f"- one initial state: `{initial_state}`",
        f"- samples: `{result.times_s.size}`",
        f"- position shape: `{result.positions.shape}`",
        f"- velocity shape: `{result.velocities.shape}`",
        f"- force shape: `{result.forces.shape}`",
        f"- component 4 active at any sample: `{result.component_active[:, 3].any()}`",
        f"- component 4 maximum saturation: `{np.max(result.component_saturations[:, 3])}`",
        f"- arrays: `{arrays_path.name}`",
        f"- metadata: `{metadata_path.name}`",
        f"- plot: `{None if plot_path is None else plot_path.name}`",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote report: {report_path}")
    return {
        "result": result,
        "analytic_checks": analytic_checks,
        "arrays_path": arrays_path,
        "metadata_path": metadata_path,
        "plot_path": plot_path,
        "report_path": report_path,
    }


def main() -> None:
    run()


if __name__ == "__main__":
    main()
