"""Run 009: static pylcp rate-equation validation for provisional Track P."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.force_units import (
    acceleration_m_s2_to_normalized_force,
    normalized_force_to_acceleration_m_s2,
    normalized_force_to_newtons,
)
from mgf_mot.conventions import GroundZeemanConvention
from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.policies import load_policy
from mgf_mot.rateeq_backend import (
    RATEEQ_STATIC_LABEL,
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
POSITION_AXIS_M = np.linspace(-0.02, 0.02, 17)
VELOCITY_AXIS_M_S = np.linspace(-15.06, 15.06, 17)


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
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


def _order_description(value: float, reference: float) -> str:
    ratio = abs(value) / reference
    if ratio < 0.1:
        return "substantially smaller"
    if ratio > 10.0:
        return "substantially larger"
    return "comparable order"


def _evaluate_case(
    backend: ProvisionalPylcpRateEquationBackend,
    name: str,
    optical_system: Any,
    positions_m: np.ndarray,
    velocities_m_s: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray]:
    forces = np.empty((positions_m.size, velocities_m_s.size), dtype=float)
    for i, x in enumerate(positions_m):
        for j, velocity in enumerate(velocities_m_s):
            result = backend.force_at(
                np.array([x, 0.0, 0.0]),
                np.array([velocity, 0.0, 0.0]),
                optical_system,
            )
            forces[i, j] = result.normalized_force[0]
    if not np.isfinite(forces).all():
        raise RuntimeError(f"nonfinite force grid for {name}")
    i0 = int(np.argmin(abs(positions_m)))
    j0 = int(np.argmin(abs(velocities_m_s)))
    dfdx = (forces[i0 + 1, j0] - forces[i0 - 1, j0]) / (
        positions_m[i0 + 1] - positions_m[i0 - 1]
    )
    dfdv = (forces[i0, j0 + 1] - forces[i0, j0 - 1]) / (
        velocities_m_s[j0 + 1] - velocities_m_s[j0 - 1]
    )
    max_index = np.unravel_index(int(np.argmax(forces)), forces.shape)
    min_index = np.unravel_index(int(np.argmin(forces)), forces.shape)
    contribution_point = backend.force_at(
        np.zeros(3), np.array([1.0, 0.0, 0.0]), optical_system
    )
    record = {
        "label": RATEEQ_STATIC_LABEL,
        "title": f"{RATEEQ_STATIC_LABEL} {name} topology metadata",
        "name": name,
        "beam_mode": optical_system.beam_mode,
        "policy_name": optical_system.policy_name,
        "policy_time_s": optical_system.policy_time_s,
        "active_laser_count": optical_system.active_component_count,
        "combined_population_solve": optical_system.combined_solve,
        "per_beam_envelope_before_solve": optical_system.per_beam_envelope_before_solve,
        "post_sum_envelope_used": optical_system.post_sum_envelope_used,
        "force_at_origin": float(forces[i0, j0]),
        "dFdx_normalized_per_m": float(dfdx),
        "dFdv_normalized_per_m_s": float(dfdv),
        "position_topology": "restoring" if dfdx < 0 else "anti-restoring" if dfdx > 0 else "flat",
        "velocity_topology": "damping" if dfdv < 0 else "anti-damping" if dfdv > 0 else "flat",
        "maximum_normalized_force": float(forces[max_index]),
        "maximum_location": {
            "x_m": float(positions_m[max_index[0]]),
            "vx_m_s": float(velocities_m_s[max_index[1]]),
        },
        "minimum_normalized_force": float(forces[min_index]),
        "minimum_location": {
            "x_m": float(positions_m[min_index[0]]),
            "vx_m_s": float(velocities_m_s[min_index[1]]),
        },
        "maximum_absolute_normalized_force": float(np.max(np.abs(forces))),
        "versus_reference_0p03": _order_description(float(np.max(np.abs(forces))), 0.03),
        "versus_reference_0p015": _order_description(float(np.max(np.abs(forces))), 0.015),
        "per_physical_beam_force_at_origin_vx_1": _json_safe(
            contribution_point.per_physical_beam_normalized_force
        ),
        "per_component_force_at_origin_vx_1": _json_safe(
            contribution_point.per_component_normalized_force
        ),
        "population_sum_at_contribution_point": float(
            np.sum(contribution_point.equilibrium_populations)
        ),
        "population_min_at_contribution_point": float(
            np.min(contribution_point.equilibrium_populations)
        ),
        "arrays_finite": True,
    }
    return record, forces


def _save_case_plot(
    record: dict[str, Any],
    forces: np.ndarray,
    positions_m: np.ndarray,
    velocities_m_s: np.ndarray,
    output_dir: Path,
) -> Path:
    import matplotlib.pyplot as plt

    path = output_dir / f"{RATEEQ_STATIC_LABEL}_{record['name']}.png"
    i0 = int(np.argmin(abs(positions_m)))
    j0 = int(np.argmin(abs(velocities_m_s)))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    mesh = axes[0].pcolormesh(
        positions_m * 1e3, velocities_m_s, forces.T, shading="auto"
    )
    fig.colorbar(mesh, ax=axes[0], label="F_x / (hbar k Gamma)")
    axes[0].set(xlabel="x [mm]", ylabel="v_x [m/s]", title="force grid")
    axes[1].plot(positions_m * 1e3, forces[:, j0])
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set(xlabel="x [mm]", ylabel="F_x / (hbar k Gamma)", title="v_x = 0")
    axes[2].plot(velocities_m_s, forces[i0, :])
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set(xlabel="v_x [m/s]", ylabel="F_x / (hbar k Gamma)", title="x = 0")
    fig.suptitle(f"{RATEEQ_STATIC_LABEL} {record['name']}")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    save_plots: bool = True,
    positions_m: np.ndarray = POSITION_AXIS_M,
    velocities_m_s: np.ndarray = VELOCITY_AXIS_M_S,
) -> dict[str, Any]:
    """Perform static grids only; this function never calls trajectory APIs."""

    output_dir.mkdir(parents=True, exist_ok=True)
    backend = ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            magnetic_gradient_t_m=0.2,
            ground_zeeman_convention=GroundZeemanConvention.RAW_XFMOLECULES,
        )
    )
    gaussian_config = load_gaussian_envelope_config(
        REPO_ROOT / "configs" / "rodriguez_gaussian_baseline.yaml"
    )
    static3 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3.yaml")
    static31 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    chirp = load_policy(REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml")
    gaussian3 = build_rodriguez_gaussian_beam_set(
        gaussian_config, (1.45, 1.45, 2.89, 0.0)
    )
    gaussian31 = build_rodriguez_gaussian_beam_set(
        gaussian_config, (1.45, 1.45, 2.17, 0.72)
    )

    case_inputs = [
        (
            "plane_wave_3",
            backend.build_optical_system(
                static3.sample(0.0), policy_name=static3.name, beam_mode="plane_wave"
            ),
        ),
        (
            "plane_wave_3_plus_1",
            backend.build_optical_system(
                static31.sample(0.0), policy_name=static31.name, beam_mode="plane_wave"
            ),
        ),
        (
            "gaussian_3",
            backend.build_optical_system(
                static3.sample(0.0),
                policy_name=static3.name,
                beam_mode="elliptical_gaussian",
                gaussian_beam_set=gaussian3,
            ),
        ),
        (
            "gaussian_3_plus_1",
            backend.build_optical_system(
                static31.sample(0.0),
                policy_name=static31.name,
                beam_mode="elliptical_gaussian",
                gaussian_beam_set=gaussian31,
            ),
        ),
        (
            "gaussian_chirp_minus_8_gamma",
            backend.build_optical_system(
                chirp.sample(0.0),
                policy_name=chirp.name,
                beam_mode="elliptical_gaussian",
                gaussian_beam_set=gaussian3,
            ),
        ),
        (
            "gaussian_chirp_minus_4p5_gamma",
            backend.build_optical_system(
                chirp.sample(0.0005),
                policy_name=chirp.name,
                beam_mode="elliptical_gaussian",
                gaussian_beam_set=gaussian3,
            ),
        ),
        (
            "gaussian_chirp_minus_1_gamma",
            backend.build_optical_system(
                chirp.sample(0.001),
                policy_name=chirp.name,
                beam_mode="elliptical_gaussian",
                gaussian_beam_set=gaussian3,
            ),
        ),
    ]

    case_records: list[dict[str, Any]] = []
    force_arrays: dict[str, np.ndarray] = {
        "positions_m": np.asarray(positions_m),
        "velocities_m_s": np.asarray(velocities_m_s),
    }
    for name, optical_system in case_inputs:
        print(f"evaluating {name} ({optical_system.active_component_count} lasers)")
        record, forces = _evaluate_case(
            backend,
            name,
            optical_system,
            np.asarray(positions_m),
            np.asarray(velocities_m_s),
        )
        plot_path = (
            _save_case_plot(record, forces, positions_m, velocities_m_s, output_dir)
            if save_plots
            else None
        )
        record["plot_path"] = None if plot_path is None else plot_path.name
        case_records.append(record)
        force_arrays[f"force_{name}"] = forces

    by_name = {record["name"]: record for record in case_records}
    grid_by_name = {
        name: force_arrays[f"force_{name}"] for name, _ in case_inputs
    }
    comparisons = {
        "label": RATEEQ_STATIC_LABEL,
        "title": f"{RATEEQ_STATIC_LABEL} required behavior comparisons",
        "three_vs_three_plus_one_different": bool(
            not np.allclose(
                grid_by_name["plane_wave_3"], grid_by_name["plane_wave_3_plus_1"]
            )
        ),
        "component_4_changes_optical_system": bool(
            by_name["plane_wave_3"]["active_laser_count"]
            != by_name["plane_wave_3_plus_1"]["active_laser_count"]
        ),
        "chirp_minus_8_vs_minus_4p5_different": bool(
            not np.allclose(
                grid_by_name["gaussian_chirp_minus_8_gamma"],
                grid_by_name["gaussian_chirp_minus_4p5_gamma"],
            )
        ),
        "chirp_minus_4p5_vs_minus_1_different": bool(
            not np.allclose(
                grid_by_name["gaussian_chirp_minus_4p5_gamma"],
                grid_by_name["gaussian_chirp_minus_1_gamma"],
            )
        ),
        "plane_gaussian_three_agree_at_origin": bool(
            np.isclose(
                by_name["plane_wave_3"]["force_at_origin"],
                by_name["gaussian_3"]["force_at_origin"],
                atol=1e-12,
            )
        ),
        "plane_gaussian_three_differ_away": bool(
            not np.allclose(grid_by_name["plane_wave_3"], grid_by_name["gaussian_3"])
        ),
        "origin_symmetry_all_cases": bool(
            all(abs(record["force_at_origin"]) < 1e-12 for record in case_records)
        ),
        "chirp_extrema_locations": {
            record["name"]: {
                "maximum": record["maximum_location"],
                "minimum": record["minimum_location"],
            }
            for record in case_records
            if "chirp" in record["name"]
        },
        "chirp_topology_changed": bool(
            not np.allclose(
                grid_by_name["gaussian_chirp_minus_8_gamma"],
                grid_by_name["gaussian_chirp_minus_1_gamma"],
            )
        ),
    }
    sample_normalized_force = np.array([0.01, 0.015, 0.03, 1.0])
    accelerations = normalized_force_to_acceleration_m_s2(
        sample_normalized_force, backend.force_units
    )
    units = {
        "label": RATEEQ_STATIC_LABEL,
        "title": f"{RATEEQ_STATIC_LABEL} explicit force-unit conversions",
        "force_unit": "hbar*k*Gamma",
        "normalized_examples": sample_normalized_force.tolist(),
        "newtons": normalized_force_to_newtons(
            sample_normalized_force, backend.force_units
        ).tolist(),
        "accelerations_m_s2": accelerations.tolist(),
        "round_trip_normalized": acceleration_m_s2_to_normalized_force(
            accelerations, backend.force_units
        ).tolist(),
        "normalized_force_conversion_count": 0,
        "si_acceleration_conversion_count": 1,
    }
    metadata = {
        "label": RATEEQ_STATIC_LABEL,
        "title": f"{RATEEQ_STATIC_LABEL} Run 009 metadata",
        "replication_valid": False,
        "trajectory_integrations_performed": 0,
        "capture_results_calculated": 0,
        "backend_status": _json_safe(backend.status),
        "hamiltonian_structure": {
            "label": RATEEQ_STATIC_LABEL,
            "title": f"{RATEEQ_STATIC_LABEL} Hamiltonian structure",
            "ground_states": backend.source_backend.validation_model.ground_state_count,
            "excited_states": backend.source_backend.validation_model.excited_state_count,
            "dipole_shape": list(
                backend.source_backend.validation_model.transition_dipole_q.shape
            ),
        },
        "grid_definition": {
            "label": RATEEQ_STATIC_LABEL,
            "title": f"{RATEEQ_STATIC_LABEL} static grid definition",
            "positions_m": positions_m.tolist(),
            "velocities_m_s": velocities_m_s.tolist(),
        },
        "case_records": case_records,
        "comparisons": comparisons,
        "force_units": units,
        "contribution_diagnostics": {
            "label": RATEEQ_STATIC_LABEL,
            "title": f"{RATEEQ_STATIC_LABEL} contribution diagnostics",
            "available": True,
            "method": "pylcp per-laser forces grouped after one combined equilibrium-population solve",
            "independent_component_solves_used": False,
        },
        "historical_output_status": (
            "Force-dependent Runs 001-008 remain plumbing artifacts and are physically "
            "uninterpretable as established by Run 008B; no historical output was rewritten."
        ),
    }
    arrays_path = output_dir / f"{RATEEQ_STATIC_LABEL}_run_009_arrays.npz"
    np.savez_compressed(arrays_path, **force_arrays)
    metadata_path = output_dir / f"{RATEEQ_STATIC_LABEL}_run_009_metadata.json"
    metadata_path.write_text(
        json.dumps(_json_safe(metadata), indent=2, sort_keys=True), encoding="utf-8"
    )

    report_path = output_dir / f"{RATEEQ_STATIC_LABEL}_run_009.md"
    heading = lambda value: f"## {RATEEQ_STATIC_LABEL} {value}"
    lines = [
        f"# {RATEEQ_STATIC_LABEL} Run 009",
        "",
        "This static validation uses pylcp rate equations with the explicitly requested collapsed excited-state approximation. It is not exact and is not Rodriguez-valid.",
        "The force calculation now uses one combined equilibrium-population rate-equation solve rather than the toy heuristic.",
        "Exact Track E remains blocked. No trajectory was rerun, no capture result was calculated, and no agreement with Rodriguez is claimed.",
        "All force-dependent Run 001-008 outcomes remain physically uninterpretable; their historical files were not changed.",
        "",
        heading("Backend and units"),
        "",
        f"- backend: `{_json_safe(backend.status)}`",
        f"- force conversions: `{units}`",
        "",
        heading("Static topology and scale"),
        "",
        "| case | lasers | dF/dx | dF/dv | position | velocity | min | max | scale vs 0.03 / 0.015 |",
        "|---|---:|---:|---:|---|---|---:|---:|---|",
    ]
    for record in case_records:
        lines.append(
            f"| {record['name']} | {record['active_laser_count']} | "
            f"{record['dFdx_normalized_per_m']:.6g} | {record['dFdv_normalized_per_m_s']:.6g} | "
            f"{record['position_topology']} | {record['velocity_topology']} | "
            f"{record['minimum_normalized_force']:.6g} | {record['maximum_normalized_force']:.6g} | "
            f"{record['versus_reference_0p03']} / {record['versus_reference_0p015']} |"
        )
    lines += [
        "",
        "Force-scale comparisons are descriptive order-of-magnitude labels only; they do not assert reproduction, validation, or disagreement.",
        "",
        heading("Required behavior checks"),
        "",
        f"- `{comparisons}`",
        "- Frozen chirp topology is labeled changed when its force arrays differ; extrema locations are reported above without physical interpretation.",
        "",
        heading("Combined populations and contributions"),
        "",
        "All active lasers enter one pylcp evolution matrix. The SVD equilibrium population is then used for total and per-laser forces. Per-beam and per-component entries in metadata are groupings of those contributions, not sums of independently solved systems.",
        "",
        heading("Gaussian application"),
        "",
        "Each physical beam supplies its own elliptical envelope callable. That envelope multiplies each of the beam's active component saturations before pylcp constructs and sums pumping rates. No mean, weakest-beam, post-summation, or squared-saturation adapter is used.",
        "",
        heading("Scope boundary"),
        "",
        "No trajectory integration, capture result, source distribution, stochastic recoil, optimizer, or exact-force path was added. The collapsed d-term and Zeeman limitations remain explicit.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RATEEQ_STATIC_LABEL)
    print(json.dumps(comparisons, indent=2))
    print(f"arrays: {arrays_path}")
    print(f"metadata: {metadata_path}")
    print(f"report: {report_path}")
    return {
        "backend": backend,
        "metadata": metadata,
        "case_records": case_records,
        "force_arrays": force_arrays,
        "arrays_path": arrays_path,
        "metadata_path": metadata_path,
        "report_path": report_path,
    }


if __name__ == "__main__":
    run()
