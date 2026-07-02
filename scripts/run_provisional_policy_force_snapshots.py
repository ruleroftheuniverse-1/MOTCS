"""Run Track P policy-conditioned frozen-time force snapshots.

This is a static snapshot bridge from policy schedules to provisional force
grids. It does not integrate molecule motion or compute capture behavior.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.mgf_backend import ApproximationMode, build_mgf_hamiltonian_from_sources
from mgf_mot.policies import LinearChirpPolicy, load_policy
from mgf_mot.policy_force import (
    POLICY_FORCE_SNAPSHOT_LABEL,
    PolicyForceGridConfig,
    force_grid_for_policy_snapshot,
)
from mgf_mot.provisional_force import ProvisionalForceMapConfig, save_normalized_force_plot

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


def _snapshot_times(policy: LinearChirpPolicy) -> tuple[float, float, float, float]:
    tau = policy.duration_s
    return (0.0, tau / 2.0, tau, 2.0 * tau)


def run(output_dir: Path = DEFAULT_OUTPUT_DIR, *, save_plots: bool = True) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = load_policy(POLICY_CONFIG_PATH)
    if not isinstance(policy, LinearChirpPolicy):
        raise TypeError("Run 003 expects the baseline linear chirp policy")

    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    provenance = backend.provenance
    force_config = ProvisionalForceMapConfig(explicit_provisional_opt_in=True)
    grid_config = PolicyForceGridConfig(
        axis="z",
        positions=(-0.4, -0.2, 0.0, 0.2, 0.4),
        velocities=(-0.2, 0.0, 0.2),
    )

    print(POLICY_FORCE_SNAPSHOT_LABEL)
    print(f"track: {provenance.track.value}")
    print(f"backend_mode: {provenance.backend_mode}")
    print(f"replication_valid: {provenance.replication_valid}")
    print(f"force_ready: {provenance.force_ready}")
    print(f"policy: {policy.name}")

    records: list[dict[str, Any]] = []
    for time_s in _snapshot_times(policy):
        snapshot = force_grid_for_policy_snapshot(
            policy,
            time_s,
            backend,
            force_config,
            grid_config,
        )
        stem = snapshot.metadata.filename_stem
        arrays_path = output_dir / f"{stem}_grid.npz"
        metadata_path = output_dir / f"{stem}_metadata.json"
        plot_path: Path | None = None
        plot_error: str | None = None

        np.savez_compressed(
            arrays_path,
            positions=snapshot.grid.positions,
            velocities=snapshot.grid.velocities,
            forces=snapshot.grid.forces,
            component_detunings_gamma=np.asarray(snapshot.metadata.component_detunings_gamma),
            component_saturations=np.asarray(snapshot.metadata.component_saturations),
            component_enabled=np.asarray(snapshot.metadata.component_enabled),
        )

        if save_plots:
            try:
                plot_path = save_normalized_force_plot(snapshot.grid, output_dir)
            except Exception as exc:  # pragma: no cover - optional plotting stack
                plot_error = repr(exc)

        metadata = {
            "label": POLICY_FORCE_SNAPSHOT_LABEL,
            "title": snapshot.metadata.title,
            "run_type": "policy_force_snapshot_only",
            "policy_config_path": str(POLICY_CONFIG_PATH.relative_to(REPO_ROOT)),
            "snapshot_metadata": _json_safe(snapshot.metadata),
            "policy_sample": _json_safe(snapshot.policy_sample),
            "derived_force_config": _json_safe(snapshot.derived_force_config),
            "backend_provenance": _json_safe(provenance),
            "grid_metadata": _json_safe(snapshot.grid.metadata),
            "axis": snapshot.grid.axis,
            "positions_shape": list(snapshot.grid.positions.shape),
            "velocities_shape": list(snapshot.grid.velocities.shape),
            "forces_shape": list(snapshot.grid.forces.shape),
            "forces_finite": bool(np.isfinite(snapshot.grid.forces).all()),
            "arrays_path": arrays_path.name,
            "plot_path": None if plot_path is None else plot_path.name,
            "plot_error": plot_error,
            "replication_valid": False,
            "force_ready": False,
            "disclaimer": (
                "PROVISIONAL NOT_RODRIGUEZ_REPLICATION POLICY_FORCE_SNAPSHOT_ONLY; "
                "frozen-time static force snapshot only; no trajectory or capture calculation."
            ),
        }
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(
            f"snapshot t={time_s:g}s detunings="
            f"{snapshot.metadata.component_detunings_gamma} shape={snapshot.grid.forces.shape}"
        )
        records.append(
            {
                "time_s": time_s,
                "metadata_path": metadata_path,
                "arrays_path": arrays_path,
                "plot_path": plot_path,
                "forces_shape": snapshot.grid.forces.shape,
                "forces_finite": bool(np.isfinite(snapshot.grid.forces).all()),
                "component_detunings_gamma": snapshot.metadata.component_detunings_gamma,
            }
        )

    report_path = output_dir / f"{POLICY_FORCE_SNAPSHOT_LABEL}_run_003.md"
    report_lines = [
        f"# {POLICY_FORCE_SNAPSHOT_LABEL} run 003",
        "",
        "This is a frozen-time static force snapshot bridge from policy schedules to Track P force grids.",
        "",
        "No molecule trajectory was integrated.",
        "No capture velocity was computed.",
        "Exact MgF force readiness remains blocked.",
        "No physical conclusions should be drawn from provisional force magnitudes or topology.",
        "",
        "No Gaussian beams, optimizers, exact force maps, or Rodriguez replication claims are used.",
        "",
        "## Backend and policy",
        "",
        f"- track: `{provenance.track.value}`",
        f"- backend mode: `{provenance.backend_mode}`",
        f"- replication_valid: `{provenance.replication_valid}`",
        f"- force_ready: `{provenance.force_ready}`",
        f"- policy: `{policy.name}`",
        f"- tau: `{policy.duration_s}` s",
        "",
        "## Snapshots",
        "",
    ]
    for record in records:
        report_lines.extend(
            [
                f"### {POLICY_FORCE_SNAPSHOT_LABEL} t={record['time_s']:.6g}s",
                "",
                f"- metadata: `{record['metadata_path'].name}`",
                f"- arrays: `{record['arrays_path'].name}`",
                f"- plot: `{None if record['plot_path'] is None else record['plot_path'].name}`",
                f"- force grid shape: `{tuple(record['forces_shape'])}`",
                f"- finite: `{record['forces_finite']}`",
                f"- detunings Gamma: `{record['component_detunings_gamma']}`",
                "",
            ]
        )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote report: {report_path}")
    return records


def main() -> None:
    run()


if __name__ == "__main__":
    main()
