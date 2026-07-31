"""Run Track P Run 007 elliptical-Gaussian geometry validation.

The force comparison is a normalized plumbing diagnostic. It does not perform
a velocity-threshold search or support a physical conclusion.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.gaussian_beams import (
    GaussianBeamSet,
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.mgf_backend import (
    ApproximationMode,
    build_mgf_hamiltonian_from_sources,
)
from mgf_mot.policies import StaticPolicy, load_policy
from mgf_mot.policy_force import (
    PolicyForceGridConfig,
    force_grid_for_policy_snapshot,
)
from mgf_mot.provisional_force import FULL_WARNING_LABEL, ProvisionalForceMapConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
GAUSSIAN_CONFIG_PATH = REPO_ROOT / "configs" / "rodriguez_gaussian_baseline.yaml"
POLICY_CONFIG_PATH = REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml"
GAUSSIAN_GEOMETRY_VALIDATION_LABEL = (
    f"{FULL_WARNING_LABEL}_GAUSSIAN_GEOMETRY_VALIDATION_ONLY"
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


def _analytic_beam_checks(beam_set: GaussianBeamSet) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for beam in beam_set.beams:
        center = np.asarray(beam.center_m)
        u_point = center + beam.radius_u_m * np.asarray(beam.transverse_u)
        v_point = center + beam.radius_v_m * np.asarray(beam.transverse_v)
        longitudinal_point = center + 0.123 * np.asarray(beam.propagation_direction)
        sample_points = (
            center,
            u_point,
            v_point,
            longitudinal_point,
            np.asarray((-0.05, 0.0, 0.0)),
            np.asarray((0.0, 0.02, 0.0)),
            np.asarray((0.0, 0.0, 0.02)),
        )
        values = tuple(beam.envelope(point) for point in sample_points)
        checks.append(
            {
                "label": GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
                "title": (
                    f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} analytic beam "
                    f"{beam.name}"
                ),
                "beam_name": beam.name,
                "center_envelope": values[0],
                "u_radius_envelope": values[1],
                "v_radius_envelope": values[2],
                "longitudinal_displacement_envelope": values[3],
                "expected_one_radius_envelope": float(np.exp(-2.0)),
                "all_samples_finite": bool(np.isfinite(values).all()),
                "all_samples_in_unit_interval": bool(
                    np.all(np.asarray(values) >= 0.0)
                    and np.all(np.asarray(values) <= 1.0)
                ),
                "right_handed_u_cross_v_equals_k": bool(
                    np.allclose(
                        np.cross(beam.transverse_u, beam.transverse_v),
                        beam.propagation_direction,
                        atol=1e-12,
                        rtol=0.0,
                    )
                ),
            }
        )
    return checks


def _diagnostic_points() -> tuple[tuple[str, tuple[float, float, float]], ...]:
    return (
        ("origin", (0.0, 0.0, 0.0)),
        ("x_minus_50_mm", (-0.050, 0.0, 0.0)),
        ("x_minus_25_mm", (-0.025, 0.0, 0.0)),
        ("x_plus_25_mm", (0.025, 0.0, 0.0)),
        ("x_plus_50_mm", (0.050, 0.0, 0.0)),
        ("y_plus_10_mm", (0.0, 0.010, 0.0)),
        ("z_plus_10_mm", (0.0, 0.0, 0.010)),
    )


def _lab_diagnostics(beam_set: GaussianBeamSet) -> list[dict[str, Any]]:
    return [
        {
            "label": GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
            "title": f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} lab point {name}",
            "point_name": name,
            "position_m": list(position),
            "envelopes": beam_set.envelopes(position),
        }
        for name, position in _diagnostic_points()
    ]


def _save_plot(
    positions_m: np.ndarray,
    plane_forces: np.ndarray,
    gaussian_forces: np.ndarray,
    output_dir: Path,
) -> tuple[Path | None, str | None]:
    try:
        import matplotlib.pyplot as plt

        path = (
            output_dir
            / f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL}_run_007_force_comparison.png"
        )
        fig, ax = plt.subplots()
        ax.plot(positions_m * 1e3, plane_forces, marker="o", label="plane wave")
        ax.plot(
            positions_m * 1e3,
            gaussian_forces,
            marker="s",
            label="elliptical Gaussian",
        )
        ax.set_title(
            f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Run 007 static force"
        )
        ax.set_xlabel("lab x [mm]")
        ax.set_ylabel("normalized provisional F_x")
        ax.legend()
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path, None
    except Exception as exc:  # pragma: no cover - optional plotting stack
        return None, repr(exc)


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    save_plot: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    envelope_config = load_gaussian_envelope_config(GAUSSIAN_CONFIG_PATH)
    policy = load_policy(POLICY_CONFIG_PATH)
    if not isinstance(policy, StaticPolicy):
        raise TypeError("Run 007 expects the static [3+1] policy")
    policy_sample = policy.sample(0.0)
    component_saturations = tuple(
        component.saturation for component in policy_sample.components
    )
    beam_set = build_rodriguez_gaussian_beam_set(
        envelope_config,
        component_saturations,  # type: ignore[arg-type]
    )
    analytic_checks = _analytic_beam_checks(beam_set)
    lab_diagnostics = _lab_diagnostics(beam_set)

    pair_checks = []
    for pair_name in ("x_prime", "y_prime", "z"):
        forward, backward = beam_set.pair(pair_name)
        differences = [
            abs(forward.envelope(position) - backward.envelope(position))
            for _, position in _diagnostic_points()
        ]
        pair_checks.append(
            {
                "label": GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
                "title": (
                    f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} pair {pair_name}"
                ),
                "pair_name": pair_name,
                "max_envelope_difference": max(differences),
                "identical_envelopes": bool(max(differences) <= 1e-15),
            }
        )

    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    positions_m = (-0.050, -0.025, 0.0, 0.025, 0.050)
    grid_config = PolicyForceGridConfig(
        axis="x",
        positions=positions_m,
        velocities=(0.0,),
    )
    plane_snapshot = force_grid_for_policy_snapshot(
        policy,
        0.0,
        backend,
        ProvisionalForceMapConfig(
            explicit_provisional_opt_in=True,
            beam_mode="plane_wave",
            position_unit="m",
        ),
        grid_config,
    )
    gaussian_snapshot = force_grid_for_policy_snapshot(
        policy,
        0.0,
        backend,
        ProvisionalForceMapConfig(
            explicit_provisional_opt_in=True,
            beam_mode="elliptical_gaussian",
            gaussian_beam_set=beam_set,
            position_unit="m",
        ),
        grid_config,
    )
    plane_forces = plane_snapshot.grid.forces[:, 0]
    gaussian_forces = gaussian_snapshot.grid.forces[:, 0]

    print(GAUSSIAN_GEOMETRY_VALIDATION_LABEL)
    print(f"track: {backend.provenance.track.value}")
    print(f"backend_mode: {backend.provenance.backend_mode}")
    print(f"replication_valid: {backend.provenance.replication_valid}")
    print(f"wxy: {envelope_config.wxy_m * 1e3:g} mm")
    print(f"wz: {envelope_config.wz_m * 1e3:g} mm")
    print(f"total power metadata: {envelope_config.total_power_w:g} W")
    print(f"power allocation: {envelope_config.power_allocation_status}")
    for check in analytic_checks:
        print(
            f"{check['beam_name']}: center={check['center_envelope']:.9g}, "
            f"u-radius={check['u_radius_envelope']:.9g}, "
            f"v-radius={check['v_radius_envelope']:.9g}"
        )
    print("lab x-axis envelopes:")
    for record in lab_diagnostics:
        if record["point_name"].startswith("x_") or record["point_name"] == "origin":
            print(f"  {record['point_name']}: {record['envelopes']}")

    arrays_path = (
        output_dir
        / f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL}_run_007_arrays.npz"
    )
    metadata_path = (
        output_dir
        / f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL}_run_007_metadata.json"
    )
    np.savez_compressed(
        arrays_path,
        positions_m=np.asarray(positions_m),
        plane_wave_forces=plane_snapshot.grid.forces,
        elliptical_gaussian_forces=gaussian_snapshot.grid.forces,
        diagnostic_positions_m=np.asarray(
            [position for _, position in _diagnostic_points()]
        ),
        diagnostic_envelopes=np.asarray(
            [
                tuple(record["envelopes"].values())
                for record in lab_diagnostics
            ]
        ),
    )
    plot_path: Path | None = None
    plot_error: str | None = None
    if save_plot:
        plot_path, plot_error = _save_plot(
            np.asarray(positions_m),
            plane_forces,
            gaussian_forces,
            output_dir,
        )

    geometry_provenance = _json_safe(beam_set.provenance)
    geometry_provenance.update(
        {
            "label": GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
            "title": (
                f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} geometry provenance"
            ),
        }
    )
    backend_provenance = _json_safe(backend.provenance)
    backend_provenance.update(
        {
            "label": GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
            "title": (
                f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} backend provenance"
            ),
        }
    )
    snapshot_records = (
        {
            "label": GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
            "title": (
                f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} plane-wave snapshot"
            ),
            "beam_mode": "plane_wave",
            "forces": plane_forces.tolist(),
            "grid_shape": list(plane_snapshot.grid.forces.shape),
            "replication_valid": False,
        },
        {
            "label": GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
            "title": (
                f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Gaussian snapshot"
            ),
            "beam_mode": "elliptical_gaussian",
            "forces": gaussian_forces.tolist(),
            "grid_shape": list(gaussian_snapshot.grid.forces.shape),
            "replication_valid": False,
        },
    )
    metadata = {
        "label": GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
        "title": f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Run 007 metadata",
        "run_type": "gaussian_geometry_validation_only",
        "replication_valid": False,
        "force_ready": False,
        "gaussian_config_path": str(
            GAUSSIAN_CONFIG_PATH.relative_to(REPO_ROOT)
        ),
        "policy_config_path": str(POLICY_CONFIG_PATH.relative_to(REPO_ROOT)),
        "geometry_config": _json_safe(envelope_config),
        "geometry_provenance": geometry_provenance,
        "backend_provenance": backend_provenance,
        "analytic_beam_checks": analytic_checks,
        "counterpropagating_pair_checks": pair_checks,
        "lab_frame_diagnostics": lab_diagnostics,
        "force_snapshots": snapshot_records,
        "plane_wave_behavior_retained": True,
        "peak_saturation_vector_used_directly": list(component_saturations),
        "total_power_conversion_performed": False,
        "arrays_finite": bool(
            np.isfinite(plane_snapshot.grid.forces).all()
            and np.isfinite(gaussian_snapshot.grid.forces).all()
        ),
        "arrays_path": arrays_path.name,
        "plot_path": None if plot_path is None else plot_path.name,
        "plot_error": plot_error,
        "disclaimer": (
            f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL}: geometry and force "
            "plumbing only; no threshold search, source distribution, "
            "stochastic diffusion, optimization, exact force, or physical conclusion."
        ),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = (
        output_dir
        / f"{GAUSSIAN_GEOMETRY_VALIDATION_LABEL}_run_007.md"
    )
    report_lines = [
        f"# {GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Run 007",
        "",
        "The Gaussian geometry follows the paper's stated radii and beam axes.",
        "The exact MgF Hamiltonian remains blocked.",
        "Reported peak saturation vectors are used directly.",
        "The reported total laser power is retained as metadata rather than converted through an assumed allocation.",
        "No capture velocity or threshold search was performed.",
        "No physical conclusions should be drawn from provisional force differences.",
        "",
        f"## {GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Geometry",
        "",
        f"- `wxy = {envelope_config.wxy_m * 1e3:g} mm`",
        f"- `wz = {envelope_config.wz_m * 1e3:g} mm`",
        f"- radius convention: `{envelope_config.radius_convention}`",
        f"- longitudinal model: `{envelope_config.longitudinal_model}`",
        f"- total power metadata: `{envelope_config.total_power_w:g} W`",
        f"- power allocation status: `{envelope_config.power_allocation_status}`",
        f"- operative peak saturation vector: `{component_saturations}`",
        "",
        f"## {GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Analytic checks",
        "",
    ]
    for check in analytic_checks:
        report_lines.extend(
            [
                f"### {GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Beam {check['beam_name']}",
                "",
                f"- center envelope: `{check['center_envelope']}`",
                f"- one `wxy` radius: `{check['u_radius_envelope']}`",
                f"- one `wz` radius: `{check['v_radius_envelope']}`",
                f"- longitudinal displacement: `{check['longitudinal_displacement_envelope']}`",
                f"- right-handed frame: `{check['right_handed_u_cross_v_equals_k']}`",
                "",
            ]
        )
    report_lines.extend(
        [
            f"## {GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Lab x-axis projection",
            "",
            "| point | +x' | -x' | +y' | -y' | +z | -z |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for record in lab_diagnostics:
        if record["point_name"].startswith("x_") or record["point_name"] == "origin":
            values = record["envelopes"]
            report_lines.append(
                f"| {record['point_name']} | {values['+x_prime']:.9g} | "
                f"{values['-x_prime']:.9g} | {values['+y_prime']:.9g} | "
                f"{values['-y_prime']:.9g} | {values['+z']:.9g} | "
                f"{values['-z']:.9g} |"
            )
    report_lines.extend(
        [
            "",
            f"## {GAUSSIAN_GEOMETRY_VALIDATION_LABEL} Static force plumbing",
            "",
            "The same frozen static `[3+1]` policy state and grid were used for both modes.",
            "",
            f"- plane-wave force values: `{plane_forces.tolist()}`",
            f"- elliptical-Gaussian force values: `{gaussian_forces.tolist()}`",
            f"- arrays: `{arrays_path.name}`",
            f"- metadata: `{metadata_path.name}`",
            f"- plot: `{None if plot_path is None else plot_path.name}`",
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote report: {report_path}")
    return {
        "beam_set": beam_set,
        "analytic_checks": analytic_checks,
        "lab_diagnostics": lab_diagnostics,
        "plane_snapshot": plane_snapshot,
        "gaussian_snapshot": gaussian_snapshot,
        "arrays_path": arrays_path,
        "metadata_path": metadata_path,
        "plot_path": plot_path,
        "report_path": report_path,
    }


def main() -> None:
    run()


if __name__ == "__main__":
    main()
