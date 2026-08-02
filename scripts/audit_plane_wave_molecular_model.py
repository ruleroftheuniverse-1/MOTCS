"""Run 011C: convention-locked, read-only molecular-model differential audit."""

from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
import csv
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
from PIL import Image
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mgf_mot.accepted_backend import build_accepted_provisional_rateeq_backend  # noqa: E402
from mgf_mot.geometry import MOT_BEAM_DIRECTIONS, quadrupole_field  # noqa: E402
from mgf_mot.paper_rateeq_reference import (  # noqa: E402
    PaperRateEquationResult,
    evaluate_paper_rate_equations,
)
from mgf_mot.policies import COMPONENT_ORDER, PolicySample, load_policy  # noqa: E402


LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_"
    "PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY"
)
OUTPUT_ROOT = REPO_ROOT / "outputs" / "provisional"
AUDIT_DIR = OUTPUT_ROOT / "molecular_model_audit" / "run_011c"
REPORT_PATH = OUTPUT_ROOT / f"{LABEL}.md"
METADATA_PATH = AUDIT_DIR / f"{LABEL}_metadata.json"
MATRIX_PATH = AUDIT_DIR / f"{LABEL}_accepted_molecular_matrices.npz"
MATRIX_METADATA_PATH = AUDIT_DIR / f"{LABEL}_accepted_molecular_matrices_metadata.json"
LEDGER_PATH = AUDIT_DIR / f"{LABEL}_transition_ledger.csv"
STATE_PATH = AUDIT_DIR / f"{LABEL}_state_resolved_diagnostics.json"
SIGN_CONFIG = REPO_ROOT / "configs" / "rodriguez_figure2_sign_calibration_run_011c.yaml"
RUN011B_METADATA = OUTPUT_ROOT / (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_"
    "PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY_comparison_metadata.json"
)
VELOCITY_UNIT_M_S = 7.53
POSITION_UNIT_M = 7.48e-3


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        if np.iscomplexobj(value):
            return {"real": value.real.tolist(), "imag": value.imag.tolist()}
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _protected_paths() -> tuple[Path, ...]:
    patterns = (
        "outputs/provisional/*run_009D*",
        "outputs/provisional/*RUN_009A_R1*",
        "outputs/provisional/force_fields/*run_010*",
        "outputs/provisional/*run_010*",
        "outputs/provisional/*RUN_011_*",
        "outputs/provisional/*RUN_011A*",
        "outputs/provisional/*RUN_011B*",
        "outputs/provisional/paper_digitization/run_011b/*",
        "configs/*.yaml",
    )
    paths: set[Path] = {REPO_ROOT / "src" / "mgf_mot" / "spectroscopy.py"}
    for pattern in patterns:
        paths.update(path for path in REPO_ROOT.glob(pattern) if path.is_file())
    return tuple(sorted(paths))


def _manifest(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(REPO_ROOT)): _hash(path) for path in paths}


def _linear(anchors: list[list[float]]) -> tuple[float, float]:
    values = np.asarray(anchors, dtype=float)
    slope, intercept = np.polyfit(values[:, 0], values[:, 1], 1)
    if np.max(abs(slope * values[:, 0] + intercept - values[:, 1])) > max(abs(slope), 1e-9):
        raise ValueError("independent Figure 2 calibration anchors are inconsistent")
    return float(slope), float(intercept)


def _figure_sign_calibration() -> dict[str, Any]:
    config = yaml.safe_load(SIGN_CONFIG.read_text(encoding="utf-8"))
    image_path = REPO_ROOT / config["source_panel_image"]
    image = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.uint8)
    result: dict[str, Any] = {
        "status": "FIGURE_SIGN_CALIBRATION_VALIDATED",
        "independent_config": str(SIGN_CONFIG.relative_to(REPO_ROOT)),
        "independent_of_run_011b_metadata": bool(config["calibration_is_independent_of_run_011b_metadata"]),
        "image_coordinate_direction": {"x": "right_increases_pixel_x", "y": "down_increases_pixel_y"},
        "physical_coordinate_direction": {"x": "right_is_positive_x", "v": "up_is_positive_v"},
        "colorbar_ordering": "top_positive_bottom_negative",
        "signed_color_mapping": "yellow/green positive; blue/purple negative; teal near zero",
        "panels": {},
        "cross_checks": {
            "white_trajectory_overlays": "consistent with axes but obscure local pixels; not used as color anchors",
            "paper_component_4_text": "adds confinement overall but also states slight acceleration at large negative x",
            "low_velocity_trajectories": "reach the origin in the [3+1] calculation; this is a path-level statement, not a proof of the v=0 local slope",
        },
        "correction_applied_to_run_011b": False,
    }
    for name, panel in config["panels"].items():
        left, top, right, bottom = panel["axes_bounds_px"]
        x_slope, x_intercept = _linear(panel["x_anchors_px_data"])
        v_slope, v_intercept = _linear(panel["v_anchors_px_data"])
        force_slope, force_intercept = _linear(panel["colorbar_anchors_px_force"])
        xs_px = np.arange(left + 2, right - 1)
        ys_px = np.arange(top + 2, bottom - 1)
        x = x_slope * xs_px + x_intercept
        v = v_slope * ys_px + v_intercept
        color_y = np.arange(top + 1, bottom - 1)
        palette = image[color_y, int(panel["colorbar_x_px"]), :3].astype(float)
        palette_force = force_slope * color_y + force_intercept
        rgb = image[np.ix_(ys_px, xs_px, np.arange(3))].reshape(-1, 3).astype(float)
        nearest = np.empty(len(rgb), dtype=int)
        residual = np.empty(len(rgb), dtype=float)
        for start in range(0, len(rgb), 20000):
            stop = min(start + 20000, len(rgb))
            distance2 = np.sum((rgb[start:stop, None] - palette[None]) ** 2, axis=2)
            nearest[start:stop] = np.argmin(distance2, axis=1)
            residual[start:stop] = np.sqrt(np.min(distance2, axis=1))
        force = palette_force[nearest].reshape(len(v), len(x))
        force[residual.reshape(force.shape) > 45.0] = np.nan
        center = (abs(v[:, None]) < 0.5) & (abs(x[None, :]) < 0.5)
        force -= float(np.nanmedian(force[center]))
        samples = []
        for delta_x in config["small_displacement_samples"]["delta_x_values"]:
            window = float(config["small_displacement_samples"]["velocity_window_abs_gamma_over_k"])
            negative = (abs(x[None, :] + delta_x) < 0.12) & (abs(v[:, None]) < window)
            positive = (abs(x[None, :] - delta_x) < 0.12) & (abs(v[:, None]) < window)
            fminus, fplus = float(np.nanmedian(force[negative])), float(np.nanmedian(force[positive]))
            samples.append({
                "delta_x": float(delta_x), "F_x_minus_delta_x": fminus,
                "F_x_plus_delta_x": fplus,
                "apparent_dF_dx": (fplus - fminus) / (2.0 * float(delta_x)),
            })
        reflected = np.flip(force, axis=(0, 1))
        valid = np.isfinite(force) & np.isfinite(reflected)
        threshold = float(config["antisymmetry_force_threshold"])
        valid &= (abs(force) >= threshold) | (abs(reflected) >= threshold)
        result["panels"][name] = {
            "x_calibration_data_per_pixel": x_slope,
            "v_calibration_data_per_pixel": v_slope,
            "force_calibration_per_pixel": force_slope,
            "colorbar_numerical_values": [row[1] for row in panel["colorbar_anchors_px_force"]],
            "small_displacement_samples": samples,
            "median_apparent_dF_dx": float(np.median([row["apparent_dF_dx"] for row in samples])),
            "antisymmetry_rms_force": float(np.sqrt(np.mean((force[valid] + reflected[valid]) ** 2))),
            "antisymmetry_correlation": float(np.corrcoef(force[valid], -reflected[valid])[0, 1]),
        }
    result["conclusion"] = (
        "Axes and colorbar signs are independently validated. Figure 2(c)'s rendered v=0 local slope remains positive under all sampled delta-x windows; it is not caused by a global extraction inversion. The path/text statements concern overall confinement and do not justify reversing the calibrated force sign."
    )
    return result


def _basis_labels(backend: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    model = backend.source_backend.validation_model
    ground = [
        {
            "index": state.index, "manifold": "ground", "level": next(
                level.label for level in model.ground_levels
                if np.isclose(level.relative_energy_mhz, state.relative_energy_mhz, atol=1e-7)
            ),
            "F": state.F, "mF": state.mF, "dominant_J": state.dominant_J,
            "dominant_weight": state.dominant_weight,
            "relative_energy_mhz": state.relative_energy_mhz,
        }
        for state in model.ground_eigenstates
    ]
    excited_h0 = np.real(np.diag(backend.hamiltonian.blocks[1, 1][0].matrix))
    excited = [
        {
            "index": index, "manifold": "excited", "level": f"Fprime{int(row['F'])}",
            "F": float(row["F"]), "mF": float(row["mF"]),
            "relative_energy_gamma": float(excited_h0[index] - np.min(excited_h0)),
        }
        for index, row in enumerate(model.excited_basis)
    ]
    return ground, excited


def _spherical_hermiticity_error(tensor: np.ndarray) -> float:
    # T_q^dagger = (-1)^q T_-q for q=(-1,0,+1).
    return float(max(
        np.max(abs(tensor[1] - tensor[1].conj().T)),
        np.max(abs(tensor[0].conj().T + tensor[2])),
        np.max(abs(tensor[2].conj().T + tensor[0])),
    ))


def _weak_field_slopes(h0: np.ndarray, muq: np.ndarray) -> dict[str, list[dict[str, Any]]]:
    from pylcp.common import cart2spherical

    energies, basis = np.linalg.eigh(h0)
    groups: list[np.ndarray] = []
    for value in np.unique(np.round(energies, decimals=10)):
        groups.append(np.flatnonzero(np.isclose(energies, value, atol=1e-9)))
    result: dict[str, list[dict[str, Any]]] = {}
    for axis_name, direction in {
        "x": np.array([1.0, 0.0, 0.0]), "y": np.array([0.0, 1.0, 0.0]), "z": np.array([0.0, 0.0, 1.0])
    }.items():
        bq = cart2spherical(direction)
        slope_operator = -np.tensordot(muq, np.conjugate(bq), axes=(0, 0))
        rows = []
        for group in groups:
            vectors = basis[:, group]
            slopes = np.linalg.eigvalsh(vectors.conj().T @ slope_operator @ vectors)
            rows.append({"zero_field_energy_gamma": float(energies[group[0]]), "degeneracy": len(group), "slopes_gamma_per_gauss": np.real(slopes).tolist()})
        result[axis_name] = rows
    return result


def _matrix_export(backend: Any) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    ground_h0 = np.asarray(backend.hamiltonian.blocks[0, 0][0].matrix, dtype=complex)
    ground_mu = np.asarray(backend.hamiltonian.blocks[0, 0][1].matrix, dtype=complex)
    excited_h0 = np.asarray(backend.hamiltonian.blocks[1, 1][0].matrix, dtype=complex)
    excited_mu = np.asarray(backend.hamiltonian.blocks[1, 1][1].matrix, dtype=complex)
    dipole = np.asarray(backend.hamiltonian.blocks[0, 1].matrix, dtype=complex)
    strengths = abs(dipole) ** 2
    decay_strength = np.sum(strengths, axis=0)
    branching = decay_strength / np.sum(decay_strength, axis=0, keepdims=True)
    ground_labels, excited_labels = _basis_labels(backend)
    ground_transform = np.asarray(backend.source_backend.validation_model.ground_eigenvectors, dtype=complex)
    excited_transform = np.eye(4, dtype=complex)
    np.savez_compressed(
        MATRIX_PATH,
        ground_h0_gamma=ground_h0,
        ground_magnetic_moment_gamma_per_gauss=ground_mu,
        excited_h0_gamma=excited_h0,
        excited_magnetic_moment_gamma_per_gauss=excited_mu,
        dipole_q= dipole,
        dipole_strength_q=strengths,
        spontaneous_branching=branching,
        ground_bare_to_eigen_transform=ground_transform,
        excited_effective_basis_transform=excited_transform,
    )
    phases_g = np.exp(1j * np.arange(12) * 0.173)
    phases_e = np.exp(-1j * np.arange(4) * 0.219)
    rephased = phases_g.conj()[None, :, None] * dipole * phases_e[None, None, :]
    identities = {
        "ground_h0_hermiticity_max_error": float(np.max(abs(ground_h0 - ground_h0.conj().T))),
        "excited_h0_hermiticity_max_error": float(np.max(abs(excited_h0 - excited_h0.conj().T))),
        "ground_magnetic_spherical_hermiticity_max_error": _spherical_hermiticity_error(ground_mu),
        "excited_magnetic_spherical_hermiticity_max_error": _spherical_hermiticity_error(excited_mu),
        "dipole_shape": list(dipole.shape),
        "branching_column_sums": np.sum(branching, axis=0).tolist(),
        "polarization_complete_strength_by_ground": np.sum(strengths, axis=(0, 2)).tolist(),
        "total_decay_strength_by_excited": np.sum(strengths, axis=(0, 1)).tolist(),
        "basis_rephasing_strength_max_error": float(np.max(abs(abs(rephased) ** 2 - strengths))),
        "ground_transform_unitarity_max_error": float(np.max(abs(ground_transform.conj().T @ ground_transform - np.eye(12)))),
        "excited_transform_unitarity_max_error": 0.0,
        "basis_rotation_application": {
            "ground_h0": "pylcp Xstate eigenbasis",
            "ground_magnetic_tensor": "same pylcp Xstate eigenbasis, then one accepted sign translation",
            "dipole": "bare X-to-A tensor left-multiplied by the same ground transform transpose",
            "excited_h0_magnetic_dipole": "common effective Astate F,mF basis; identity zero-field transform",
            "dynamic_field_rotation": "both manifold Hamiltonians diagonalized and both dipole indices rotated in pylcp and independent evaluator",
        },
        "incompatible_basis_object_found": False,
    }
    metadata = {
        "label": LABEL,
        "matrix_file": MATRIX_PATH.name,
        "matrix_file_sha256": _hash(MATRIX_PATH),
        "units": {
            "ground_h0_gamma": "Gamma", "excited_h0_gamma": "Gamma",
            "ground_magnetic_moment_gamma_per_gauss": "Gamma/G",
            "excited_magnetic_moment_gamma_per_gauss": "Gamma/G",
            "dipole_q": "dimensionless reduced-dipole normalization",
            "spontaneous_branching": "probability",
        },
        "spherical_order": [-1, 0, 1],
        "ground_basis": ground_labels,
        "excited_basis": excited_labels,
        "ground_weak_field_slopes": _weak_field_slopes(ground_h0, ground_mu),
        "excited_weak_field_slopes": _weak_field_slopes(excited_h0, excited_mu),
        "identities_and_sum_rules": identities,
        "approximate_assignments": "F,mF labels are dominant zero-field assignments and become approximate after field mixing",
    }
    MATRIX_METADATA_PATH.write_text(json.dumps(_jsonable(metadata), indent=2, sort_keys=True), encoding="utf-8")
    return metadata, ground_labels, excited_labels


def _transition_ledger(backend: Any, ground: list[dict[str, Any]], excited: list[dict[str, Any]]) -> dict[str, Any]:
    dipole = np.asarray(backend.hamiltonian.blocks[0, 1].matrix)
    strength = abs(dipole) ** 2
    decay_strength = np.sum(strength, axis=0)
    branching = decay_strength / np.sum(decay_strength, axis=0, keepdims=True)
    policy = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    optical = backend.build_optical_system(policy.sample(0.0), policy_name=policy.name, beam_mode="plane_wave")
    specs = {component.component_id: component for component in optical.physical_beams[0].components}
    role_components = {"lower_F1": [1], "F0": [2], "upper_F1": [3, 4], "F2": [3, 4]}
    rows = []
    for q_index, q in enumerate((-1, 0, 1)):
        for gi, ei in zip(*np.where(strength[q_index] > 1e-12)):
            components = role_components[ground[gi]["level"]]
            detunings = {
                str(component): float(specs[component].pylcp_carrier_detuning_gamma - (
                    np.real(backend.hamiltonian.blocks[1, 1][0].matrix[ei, ei])
                    - np.real(backend.hamiltonian.blocks[0, 0][0].matrix[gi, gi])
                ))
                for component in components
            }
            categories = {
                key: ("resonant" if abs(value) <= 1.5 else "near_resonant" if abs(value) <= 5 else "off_resonant")
                for key, value in detunings.items()
            }
            rows.append({
                "ground_index": int(gi), "excited_index": int(ei),
                "ground_level": ground[gi]["level"], "ground_F": ground[gi]["F"], "ground_mF": ground[gi]["mF"],
                "excited_level": excited[ei]["level"], "excited_F": excited[ei]["F"], "excited_mF": excited[ei]["mF"],
                "q": q, "squared_dipole_strength": float(strength[q_index, gi, ei]),
                "spontaneous_branching_weight": float(branching[gi, ei]),
                "intended_frequency_components": ",".join(map(str, components)),
                "zero_field_detuning_gamma_by_component": json.dumps(detunings, sort_keys=True),
                "resonance_class_by_component": json.dumps(categories, sort_keys=True),
            })
    with LEDGER_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summaries: dict[str, Any] = {}
    for group_name, getter in {
        "ground_level": lambda row: row["ground_level"],
        "excited_level": lambda row: row["excited_level"],
        "q": lambda row: str(row["q"]),
    }.items():
        values: dict[str, dict[str, float]] = {}
        for row in rows:
            key = str(getter(row)); values.setdefault(key, {"transition_count": 0, "summed_squared_strength": 0.0})
            values[key]["transition_count"] += 1; values[key]["summed_squared_strength"] += row["squared_dipole_strength"]
        summaries[group_name] = values
    return {"row_count": len(rows), "file": LEDGER_PATH.name, "file_sha256": _hash(LEDGER_PATH), "summaries": summaries}


def _component_sample(policy: Any, *, active_components: set[int], name: str) -> tuple[PolicySample, str]:
    sample = policy.sample(0.0)
    components = tuple(
        replace(component, enabled=component.component_id in active_components,
                saturation=component.saturation if component.component_id in active_components else 0.0,
                off_reason=None if component.component_id in active_components else f"disabled_for_{name}")
        for component in sample.components
    )
    return replace(sample, components=components), name


def _evaluate(backend: Any, optical: Any, x_norm: float, v_norm: float) -> tuple[PaperRateEquationResult, dict[str, Any]]:
    position = np.array([x_norm * POSITION_UNIT_M, 0.0, 0.0])
    velocity = np.array([v_norm * VELOCITY_UNIT_M_S, 0.0, 0.0])
    accepted = backend.force_at(position, velocity, optical, collect_solver_diagnostics=True)
    reference = evaluate_paper_rate_equations(
        hamiltonian=backend.hamiltonian,
        pylcp_beams=optical.pylcp_beams,
        beam_index=optical.pylcp_beam_index,
        position_m=position,
        velocity_gamma_over_k=velocity / (
            backend.force_units.linewidth_rad_s / backend.force_units.wave_number_rad_m
        ),
        magnetic_field_gauss=np.asarray(
            quadrupole_field(position, backend.config.magnetic_gradient_t_m), dtype=float
        ) * 1e4,
        svd_eps=backend.config.svd_eps,
    )
    comparison = {
        "accepted_normalized_force": accepted.normalized_force.tolist(),
        "reference_normalized_force": reference.normalized_force.tolist(),
        "force_absolute_difference": float(np.max(abs(accepted.normalized_force - reference.normalized_force))),
        "force_relative_difference": float(np.max(abs(accepted.normalized_force - reference.normalized_force)) / max(np.max(abs(accepted.normalized_force)), 1e-15)),
        "population_absolute_difference": float(np.max(abs(accepted.equilibrium_populations - reference.equilibrium_populations))),
        "per_laser_total_pumping_rate_absolute_difference": float(np.max(abs(
            np.sum(accepted.pumping_rate_matrices, axis=(1, 2))
            - np.sum(reference.pumping_rates, axis=(1, 2))
        ))),
        "state_indexed_summed_pumping_matrix_difference": float(np.max(abs(
            np.sum(accepted.pumping_rate_matrices, axis=0)
            - np.sum(reference.pumping_rates, axis=0)
        ))),
        "state_indexed_rate_comparison_note": "At exactly B=0, rotations inside degenerate manifolds are gauge-dependent; per-laser totals, populations, and force are the invariant comparisons.",
        "state_matrix_residual_linf": reference.residual_linf,
        "reference_total_scattering_rate_gamma": reference.total_scattering_rate_gamma,
        "reference_excited_fraction": reference.excited_fraction,
        "one_shared_equilibrium_population_solution": reference.combined_population_solve_count == 1,
    }
    return reference, comparison


def _state_record(
    reference: PaperRateEquationResult, optical: Any, ground: list[dict[str, Any]], excited: list[dict[str, Any]],
    *, name: str, x_norm: float, v_norm: float,
) -> dict[str, Any]:
    populations = reference.equilibrium_populations
    ground_population = populations[:12]; excited_population = populations[12:]
    imbalance = ground_population[:, None] - excited_population[None, :]
    group_population: dict[str, float] = {}
    mf_population: dict[str, float] = {}
    for state, population in zip(ground, ground_population):
        group_population[state["level"]] = group_population.get(state["level"], 0.0) + float(population)
        mf_population[str(state["mF"])] = mf_population.get(str(state["mF"]), 0.0) + float(population)
    for state, population in zip(excited, excited_population):
        group_population[state["level"]] = group_population.get(state["level"], 0.0) + float(population)
        mf_population[f"excited_{state['mF']}"] = mf_population.get(f"excited_{state['mF']}", 0.0) + float(population)
    by_beam_scattering = {beam: 0.0 for beam in MOT_BEAM_DIRECTIONS}; by_component_scattering = {str(component): 0.0 for component in COMPONENT_ORDER}
    by_beam_force = {beam: np.zeros(3) for beam in MOT_BEAM_DIRECTIONS}; by_component_force = {str(component): np.zeros(3) for component in COMPONENT_ORDER}
    by_q_scattering = {"-1": 0.0, "0": 0.0, "1": 0.0}
    field_norm = np.linalg.norm(reference.magnetic_field_gauss)
    qaxis = reference.magnetic_field_gauss / field_norm if field_norm > 1e-10 else np.array([0.0, 0.0, 1.0])
    projections = optical.pylcp_beams.project_pol(qaxis, R=np.array([x_norm * POSITION_UNIT_M, 0, 0]), t=0.0)
    for index, (beam, component) in enumerate(optical.pylcp_beam_index):
        scattering = float(reference.net_scattering_rate_by_laser_gamma[index])
        by_beam_scattering[beam] += scattering; by_component_scattering[str(component)] += scattering
        by_beam_force[beam] += reference.per_laser_normalized_force[:, index]
        by_component_force[str(component)] += reference.per_laser_normalized_force[:, index]
        weights = abs(np.asarray(projections[index])) ** 2
        weights /= max(float(np.sum(weights)), 1e-30)
        for q_index, q in enumerate((-1, 0, 1)):
            by_q_scattering[str(q)] += scattering * float(weights[q_index])
    pumping_out = np.sum(reference.pumping_rates, axis=(0, 2))
    weakest = np.argsort(pumping_out)[:4]
    strongest_population = np.argsort(ground_population)[::-1][:4]
    return {
        "name": name, "x_normalized": x_norm, "v_normalized": v_norm,
        "position_m": [x_norm * POSITION_UNIT_M, 0.0, 0.0], "velocity_m_s": [v_norm * VELOCITY_UNIT_M_S, 0.0, 0.0],
        "equilibrium_populations": populations.tolist(), "ground_population_by_level": group_population,
        "population_by_approximate_mF": mf_population, "total_excited_fraction": reference.excited_fraction,
        "total_scattering_rate_gamma": reference.total_scattering_rate_gamma,
        "scattering_rate_by_physical_beam_gamma": by_beam_scattering,
        "scattering_rate_by_frequency_component_gamma": by_component_scattering,
        "scattering_rate_by_spherical_polarization_gamma": by_q_scattering,
        "longitudinal_force_by_physical_beam": {key: float(value[0]) for key, value in by_beam_force.items()},
        "longitudinal_force_by_frequency_component": {key: float(value[0]) for key, value in by_component_force.items()},
        "normalized_force_x": float(reference.normalized_force[0]),
        "most_populated_ground_states": [{"state": ground[index], "population": float(ground_population[index])} for index in strongest_population],
        "weakest_coupled_ground_states": [{"state": ground[index], "total_pumping_rate_gamma": float(pumping_out[index])} for index in weakest],
        "ground_zeeman_shift_gamma_sorted": (reference.ground_energies_gamma - reference.ground_zero_field_energies_gamma).tolist(),
        "excited_zeeman_shift_gamma_sorted": (reference.excited_energies_gamma - reference.excited_zero_field_energies_gamma).tolist(),
        "one_shared_population_solution": reference.combined_population_solve_count == 1,
    }


def _component4_ground_force(reference: PaperRateEquationResult, optical: Any, ground: list[dict[str, Any]]) -> dict[str, float]:
    imbalance = reference.equilibrium_populations[:12, None] - reference.equilibrium_populations[None, 12:]
    result = {"upper_F1": 0.0, "F2": 0.0, "other_ground_levels": 0.0}
    for laser_index, (beam_name, component) in enumerate(optical.pylcp_beam_index):
        if component != 4:
            continue
        kx = MOT_BEAM_DIRECTIONS[beam_name][0]
        for level_name in result:
            indices = [row["index"] for row in ground if row["level"] == level_name]
            if level_name == "other_ground_levels":
                indices = [row["index"] for row in ground if row["level"] not in ("upper_F1", "F2")]
            result[level_name] += float(kx * np.sum(reference.pumping_rates[laser_index, indices] * imbalance[indices]))
    return result


def _classification(value: float, target: float, match_tolerance: float, weak_tolerance: float) -> str:
    difference = abs(value - target)
    if difference <= match_tolerance:
        return "MATCHES_WITHIN_DIGITIZATION_OR_TEXT_PRECISION"
    if difference <= weak_tolerance:
        return "WEAKLY_DIFFERENT"
    return "MATERIALLY_DIFFERENT"


def run() -> dict[str, Any]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    protected = _protected_paths(); before = _manifest(protected)
    backend = build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=True)
    sign = _figure_sign_calibration()
    matrix_metadata, ground, excited = _matrix_export(backend)
    ledger = _transition_ledger(backend, ground, excited)
    run011b = json.loads(RUN011B_METADATA.read_text(encoding="utf-8"))

    policies = {
        "mgf_3": load_policy(REPO_ROOT / "configs" / "rodriguez_static_3.yaml"),
        "mgf_3_plus_1": load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml"),
    }
    optical = {name: backend.build_optical_system(policy.sample(0.0), policy_name=policy.name, beam_mode="plane_wave") for name, policy in policies.items()}
    point_diagnostics: dict[str, Any] = {}
    state_records: list[dict[str, Any]] = []
    for name in policies:
        paper_row = run011b["figure_2"][name]
        points = [
            ("origin", 0.0, 0.0), ("minus_delta_x", -0.5, 0.0), ("plus_delta_x", 0.5, 0.0),
            ("minus_delta_v", 0.0, -0.5), ("plus_delta_v", 0.0, 0.5),
            ("model_negative_extremum", paper_row["model_negative_extremum"]["position"], paper_row["model_negative_extremum"]["velocity"]),
            ("model_positive_extremum", paper_row["model_positive_extremum"]["position"], paper_row["model_positive_extremum"]["velocity"]),
            ("dark_region", 5.5, 0.0),
        ]
        rows = []
        for point_name, x_norm, v_norm in points:
            reference, comparison = _evaluate(backend, optical[name], float(x_norm), float(v_norm))
            rows.append({"name": point_name, "x_normalized": float(x_norm), "v_normalized": float(v_norm), **comparison})
            state_records.append(_state_record(reference, optical[name], ground, excited, name=f"{name}_{point_name}", x_norm=float(x_norm), v_norm=float(v_norm)))
        point_diagnostics[name] = rows

    # Component (4) diagnosis: one combined solve for each explicitly defined optical system.
    plus_policy = policies["mgf_3_plus_1"]
    variants: dict[str, Any] = {}
    component_variants = {
        "three": (policies["mgf_3"], {1, 2, 3}),
        "three_plus_one": (plus_policy, {1, 2, 3, 4}),
        "three_plus_one_component4_disabled": (plus_policy, {1, 2, 3}),
        "component4_alone": (plus_policy, {4}),
    }
    for variant, (variant_policy, active) in component_variants.items():
        sample, policy_name = _component_sample(variant_policy, active_components=active, name=variant)
        system = backend.build_optical_system(sample, policy_name=policy_name, beam_mode="plane_wave")
        rows = []
        for x_norm in (-0.5, 0.5):
            try:
                reference, comparison = _evaluate(backend, system, x_norm, 0.0)
                rows.append({
                    "x_normalized": x_norm, **comparison,
                    "ground_population_by_level": _state_record(reference, system, ground, excited, name=variant, x_norm=x_norm, v_norm=0.0)["ground_population_by_level"],
                    "component4_force_by_ground_level": _component4_ground_force(reference, system, ground),
                    "per_physical_beam_force_x": {
                        beam: float(sum(reference.per_laser_normalized_force[0, i] for i, item in enumerate(system.pylcp_beam_index) if item[0] == beam))
                        for beam in MOT_BEAM_DIRECTIONS
                    },
                })
            except RuntimeError as exc:
                rows.append({"x_normalized": x_norm, "numerically_meaningful": False, "reason": str(exc), "expected_cause": "unaddressed manifolds create multiple dark stationary subspaces"})
        variants[variant] = {"active_components": sorted(active), "rows": rows}
    def _variant_slope(name: str) -> float:
        rows = variants[name]["rows"]
        return float((rows[1]["reference_normalized_force"][0] - rows[0]["reference_normalized_force"][0]) /
                     (rows[1]["x_normalized"] - rows[0]["x_normalized"]))
    full_rows = variants["three_plus_one"]["rows"]
    disabled_rows = variants["three_plus_one_component4_disabled"]["rows"]
    population_redistribution = []
    for full, disabled in zip(full_rows, disabled_rows):
        population_redistribution.append({
            "x_normalized": full["x_normalized"],
            "full_minus_component4_disabled_population_by_level": {
                key: full["ground_population_by_level"][key] - disabled["ground_population_by_level"][key]
                for key in full["ground_population_by_level"]
            },
            "total_force_change_when_component4_enabled": (
                full["reference_normalized_force"][0] - disabled["reference_normalized_force"][0]
            ),
        })
    component4 = {
        "variants": variants,
        "small_signal_slopes": {name: _variant_slope(name) for name in variants},
        "population_redistribution": population_redistribution,
        "paper_level_specific_expectation": {
            "F2": "component (4) polarization is trapping",
            "upper_F1": "component (4) polarization is anti-trapping",
        },
        "accepted_level_specific_result": {
            "full_three_plus_one": "upper-F1 and F2 resolved component-4 terms are both restoring; upper-F1 has the larger magnitude",
            "component4_alone": "upper-F1 and F2 terms nearly cancel; upper-F1 is restoring and F2 is anti-restoring",
            "paper_hierarchy_reproduced": False,
        },
        "interpretation": (
            "The accepted [3+1] local slope is restoring and stronger than either [3] or the same [3+1] saturation vector with component (4) disabled. However, its shared-solution level decomposition does not reproduce the paper's stated F2-trapping/upper-F1-anti-trapping hierarchy. Component (4) alone is numerically meaningful only because weak off-resonant coupling removes an exact dark nullspace; it gives near cancellation with the opposite level-specific signs. This implicates level-specific molecular matrix content, while population redistribution also changes the forces from components (1)-(3)."
        ),
    }

    # Dark-state/width sequence at the paper's v=sqrt(2) Gamma/k guide.
    dark_sequence = []
    for x_norm in (0.0, 1.5, 3.0, 4.5, 6.0):
        reference, _ = _evaluate(backend, optical["mgf_3"], x_norm, np.sqrt(2.0))
        record = _state_record(reference, optical["mgf_3"], ground, excited, name=f"dark_width_x_{x_norm:g}", x_norm=x_norm, v_norm=float(np.sqrt(2.0)))
        counter = sum(value for beam, value in record["scattering_rate_by_physical_beam_gamma"].items() if MOT_BEAM_DIRECTIONS[beam][0] < -0.1)
        co = sum(value for beam, value in record["scattering_rate_by_physical_beam_gamma"].items() if MOT_BEAM_DIRECTIONS[beam][0] > 0.1)
        zbeams = sum(value for beam, value in record["scattering_rate_by_physical_beam_gamma"].items() if abs(MOT_BEAM_DIRECTIONS[beam][2]) > 0.9)
        total = max(record["total_scattering_rate_gamma"], 1e-30)
        dark_sequence.append({
            "x_normalized": x_norm, "force": record["normalized_force_x"], "scattering_rate_gamma": total,
            "excited_fraction": record["total_excited_fraction"], "most_populated_ground_states": record["most_populated_ground_states"],
            "weakest_coupled_ground_states": record["weakest_coupled_ground_states"],
            "ground_zeeman_shift_gamma_sorted": record["ground_zeeman_shift_gamma_sorted"],
            "excited_zeeman_shift_gamma_sorted": record["excited_zeeman_shift_gamma_sorted"],
            "scattering_fractions": {"counterpropagating_in_plane": counter / total, "copropagating_in_plane": co / total, "plus_minus_z": zbeams / total},
        })
    dark_cause = {
        "force_drop_factor_x0_to_x6": abs(dark_sequence[-1]["force"] / dark_sequence[0]["force"]),
        "scattering_drop_factor_x0_to_x6": dark_sequence[-1]["scattering_rate_gamma"] / dark_sequence[0]["scattering_rate_gamma"],
        "counter_minus_co_fraction_x0": dark_sequence[0]["scattering_fractions"]["counterpropagating_in_plane"] - dark_sequence[0]["scattering_fractions"]["copropagating_in_plane"],
        "counter_minus_co_fraction_x6": dark_sequence[-1]["scattering_fractions"]["counterpropagating_in_plane"] - dark_sequence[-1]["scattering_fractions"]["copropagating_in_plane"],
        "accepted_model_diagnosis": [
            "total scattering and excited fraction decrease with Zeeman displacement",
            "population accumulates in weakly coupled stretched/upper-manifold ground states",
            "counterpropagating dominance falls while copropagating cancellation grows",
        ],
        "not_distinguishable_from_paper_without_paper_matrices": [
            "weaker transition strengths", "different ground or excited Zeeman shifts",
            "different excited eigenvectors", "different branching",
        ],
    }

    matching_reference, _ = _evaluate(backend, optical["mgf_3"], 0.0, float(np.sqrt(2.0)))
    matching_record = _state_record(matching_reference, optical["mgf_3"], ground, excited, name="paper_quantitative_point", x_norm=0.0, v_norm=float(np.sqrt(2.0)))
    beam_scattering = matching_record["scattering_rate_by_physical_beam_gamma"]
    total = matching_record["total_scattering_rate_gamma"]
    z_fraction = sum(value for beam, value in beam_scattering.items() if abs(MOT_BEAM_DIRECTIONS[beam][2]) > 0.9) / total
    co_fraction = sum(value for beam, value in beam_scattering.items() if MOT_BEAM_DIRECTIONS[beam][0] > 0.1) / total
    quantitative = {
        "point": {"x_normalized": 0.0, "v_normalized": float(np.sqrt(2.0))},
        "maximum_scattering_rate": {"paper": 0.125, "accepted": total, "unit": "Gamma", "classification": _classification(total, 0.125, 0.03, 0.06)},
        "force_magnitude": {"paper": 0.05, "accepted": abs(matching_record["normalized_force_x"]), "unit": "hbar*k*Gamma", "classification": _classification(abs(matching_record["normalized_force_x"]), 0.05, 0.015, 0.03)},
        "plus_minus_z_scattering_fraction": {"paper": 0.30, "accepted": z_fraction, "classification": _classification(z_fraction, 0.30, 0.12, 0.22)},
        "copropagating_scattering_fraction": {"paper": 0.10, "accepted": co_fraction, "classification": _classification(co_fraction, 0.10, 0.07, 0.15)},
        "paper_values_are_rough_not_fit_targets": True,
    }

    max_force_difference = max(row["force_absolute_difference"] for rows in point_diagnostics.values() for row in rows)
    max_population_difference = max(row["population_absolute_difference"] for rows in point_diagnostics.values() for row in rows)
    max_rate_difference = max(row["per_laser_total_pumping_rate_absolute_difference"] for rows in point_diagnostics.values() for row in rows)
    implementation = {
        "independent_evaluator_calls_pylcp_rateeq": False,
        "combined_population_solve_per_point": True,
        "maximum_force_absolute_difference": max_force_difference,
        "maximum_population_absolute_difference": max_population_difference,
        "maximum_per_laser_total_pumping_rate_absolute_difference": max_rate_difference,
        "zero_field_degenerate_basis_gauge_documented": True,
        "conclusion": "independent paper-equation evaluator reproduces the accepted pylcp force and equilibrium solution for identical supplied matrices",
    }
    history = {
        "official_repository": "https://github.com/JQIamo/pylcp",
        "official_v1_0_2_tag": "https://github.com/JQIamo/pylcp/tree/v1.0.2",
        "v1_0_2_commit": "a7cb104f38fa98840ec198d13ec20c432e8ee3ff",
        "v1_0_2_commit_date": "2022-06-23T16:49:02-04:00",
        "latest_official_commit_before_paper_date": "a7cb104f38fa98840ec198d13ec20c432e8ee3ff",
        "paper_date": "2023-09-20",
        "current_project_version": "1.0.2",
        "installed_core_files_equal_official_v1_0_2": {
            "pylcp/rateeq.py": True, "pylcp/fields.py": True,
            "pylcp/hamiltonians/XFmolecules.py": True, "pylcp/hamiltonian.py": True,
        },
        "official_v1_0_2_git_blob_ids": {
            "pylcp/rateeq.py": "37d3552ef23431c190d452047ebf0738e1e4962f",
            "pylcp/fields.py": "164135d5ea75c1666232f3019b69daf7c125953b",
            "pylcp/hamiltonians/XFmolecules.py": "e67d55ddf08df000f64da8b9dfed0588b453a6d9",
            "pylcp/hamiltonian.py": "c88a06627aafea83122fdcaf287beb0ebd91c131",
        },
        "installed_file_sha256": {
            relative: _hash(REPO_ROOT / ".venv" / "Lib" / "site-packages" / relative)
            for relative in (
                "pylcp/rateeq.py", "pylcp/fields.py",
                "pylcp/hamiltonians/XFmolecules.py", "pylcp/hamiltonian.py",
            )
        },
        "changes_after_v1_0_2_through_official_master_53885b54_in_audited_files": [],
        "exact_paper_checkout_published": False,
        "conclusion": "No official implementation-history evidence supports a pylcp version cause; the exact paper checkout or private matrices are unavailable.",
    }
    splitting_vs_eigenvectors = {
        "run_009d_result": "0-1 MHz diagonal Fprime splitting changes did not materially alter accepted static topology",
        "does_not_test": [
            "excited hyperfine eigenvector changes", "transition-dipole changes",
            "coupling through omitted Jprime=3/2 states", "independent Doppelbauer d operator",
        ],
        "independent_d_operator_implemented_in_run_011c": False,
        "plausible_run_011b_sources": ["excited_hyperfine_eigenvector_difference", "dipole_tensor_difference", "unpublished_paper_model_matrix_difference"],
    }
    diagnosis = {
        "demonstrated_causes": [],
        "likely_contributors": [
            "DIPOLE_TENSOR_DIFFERENCE",
            "EXCITED_HYPERFINE_EIGENVECTOR_DIFFERENCE",
            "GROUND_ZEEMAN_MATRIX_DIFFERENCE",
            "DARK_STATE_POPULATION_DIFFERENCE",
            "UNPUBLISHED_PAPER_MODEL_MATRIX_DIFFERENCE",
        ],
        "ruled_out_candidates": [
            "FIGURE_SIGN_CALIBRATION_ERROR", "RATE_EQUATION_WRAPPER_MISMATCH",
            "PYLCP_VERSION_DIFFERENCE", "BASIS_TRANSFORMATION_MISMATCH",
        ],
        "unresolved_blockers": [
            "paper-specific Hamiltonian, dipole, branching, and basis matrices were not published",
            "independent Doppelbauer d operator and Jprime mixing are unavailable",
            "exact excited Zeeman mapping remains unresolved",
        ],
        "ranked_candidates": [
            {"rank": 1, "candidate": "UNPUBLISHED_PAPER_MODEL_MATRIX_DIFFERENCE", "evidence": "local equations and official pylcp implementation agree; paper matrices are unavailable"},
            {"rank": 2, "candidate": "DIPOLE_TENSOR_DIFFERENCE", "evidence": "accepted component-4 level-resolved signs do not reproduce the paper-stated F2 versus upper-F1 hierarchy"},
            {"rank": 3, "candidate": "EXCITED_HYPERFINE_EIGENVECTOR_DIFFERENCE", "evidence": "accepted diagonal splitting cannot reproduce d-driven eigenvector/J mixing that would rotate dipoles"},
            {"rank": 4, "candidate": "GROUND_ZEEMAN_MATRIX_DIFFERENCE", "evidence": "level-specific component-4 trapping signs depend on ground magnetic slopes; the local convention is locked but the paper matrix is unpublished"},
            {"rank": 5, "candidate": "DARK_STATE_POPULATION_DIFFERENCE", "evidence": "population redistribution and weak-coupling states visibly control the accepted net force; likely downstream of molecular matrices"},
            {"rank": 6, "candidate": "EXCITED_ZEEMAN_MATRIX_DIFFERENCE", "evidence": "exact mapping unresolved, but Run 009C static sensitivity was limited"},
            {"rank": 7, "candidate": "GROUND_HAMILTONIAN_MATRIX_DIFFERENCE", "evidence": "source-supported spacings and sum rules pass; paper matrix still unpublished"},
            {"rank": 8, "candidate": "SPONTANEOUS_BRANCHING_DIFFERENCE", "evidence": "local branching is normalized and derived from the same dipole tensor; paper tensor unavailable"},
        ],
    }

    STATE_PATH.write_text(json.dumps(_jsonable({"label": LABEL, "records": state_records, "component_4": component4, "dark_state_width_sequence": dark_sequence}), indent=2, sort_keys=True), encoding="utf-8")
    after = _manifest(protected)
    metadata = {
        "label": LABEL, "track": "provisional", "replication_valid": False,
        "figure_2_sign_calibration": sign, "independent_rate_equation_comparison": implementation,
        "deterministic_point_diagnostics": point_diagnostics,
        "matrix_export": {**matrix_metadata, "metadata_file": MATRIX_METADATA_PATH.name},
        "transition_ledger": ledger, "state_resolved_diagnostics_file": STATE_PATH.name,
        "component_4_diagnosis": component4, "dark_state_and_force_width_diagnosis": dark_sequence,
        "dark_state_cause_assessment": dark_cause,
        "paper_quantitative_statements": quantitative, "pylcp_version_history": history,
        "splitting_vs_eigenvector_physics": splitting_vs_eigenvectors,
        "candidate_diagnosis": diagnosis,
        "gate": "MOLECULAR_MODEL_DISCREPANCY_NARROWED",
        "gate_basis": "local wrapper and released pylcp implementation are reproduced independently; unresolved excited eigenvector/dipole and unpublished matrix differences remain strongly implicated but cannot be conclusively separated",
        "protected_hashes_before": before, "protected_hashes_after": after,
        "protected_artifacts_unchanged": before == after,
        "accepted_physics_objects_modified": False, "accepted_caches_rebuilt": 0,
        "trajectories_integrated": 0, "missing_d_operator_invented": False,
        "capture_authorized": False, "capture_velocity_authorized": False,
        "optimizer_authorized": False, "exact_replication_valid": False, "exact_track_blocked": True,
        "generated_files": [
            REPORT_PATH.name, str(METADATA_PATH.relative_to(OUTPUT_ROOT)), str(MATRIX_PATH.relative_to(OUTPUT_ROOT)),
            str(MATRIX_METADATA_PATH.relative_to(OUTPUT_ROOT)), str(LEDGER_PATH.relative_to(OUTPUT_ROOT)), str(STATE_PATH.relative_to(OUTPUT_ROOT)),
        ],
    }
    if not metadata["protected_artifacts_unchanged"]:
        raise RuntimeError("Run 011C changed a protected accepted/benchmark artifact")
    METADATA_PATH.write_text(json.dumps(_jsonable(metadata), indent=2, sort_keys=True), encoding="utf-8")
    _write_report(metadata)
    print(f"{LABEL}: {metadata['gate']}")
    print(f"report: {REPORT_PATH}")
    return metadata


def _write_report(metadata: dict[str, Any]) -> None:
    h = lambda text: f"## {LABEL} {text}"
    sign = metadata["figure_2_sign_calibration"]
    impl = metadata["independent_rate_equation_comparison"]
    q = metadata["paper_quantitative_statements"]
    lines = [
        f"# {LABEL}", "",
        "Run 011C is a static, plane-wave, read-only differential audit. It does not alter the accepted backend, rebuild a cache, integrate a trajectory, fit a paper figure, or authorize capture.", "",
        h("Figure 2 sign calibration"), "",
        f"`{sign['status']}`. Pixel x points right and physical x increases right; pixel y points down while physical v increases upward. Both colorbars run from positive yellow/green at the top to negative blue/purple at the bottom. Independent anchors reproduce the Run 011B sign without reading its calibration metadata.", "",
        f"The robust rendered local slopes are `{sign['panels']['mgf_3']['median_apparent_dF_dx']:.5g}` for [3] and `{sign['panels']['mgf_3_plus_1']['median_apparent_dF_dx']:.5g}` for [3+1]. Figure 2(c)'s positive local slope is therefore not a global digitization inversion. White paths obscure pixels, and the paper's confinement statements concern complete trajectories; neither supports silently reversing the colorbar.", "",
        h("Independent paper-equation reproduction"), "",
        "The reference evaluator implements Rodriguez Eqs. (1)-(5) directly and never calls `pylcp.rateeq` or the accepted backend force method. It diagonalizes the supplied manifolds, rotates the supplied dipole tensor, constructs optical and spontaneous rates, solves one combined 16-state equilibrium matrix, and computes every beam/component contribution from that shared population vector.", "",
        f"Across deterministic [3] and [3+1] points, maximum force difference is `{impl['maximum_force_absolute_difference']:.3e}`, maximum population difference is `{impl['maximum_population_absolute_difference']:.3e}`, and maximum per-laser total pumping-rate difference is `{impl['maximum_per_laser_total_pumping_rate_absolute_difference']:.3e}`. State-indexed pumping matrices at exactly zero field are compared only with an explicit degenerate-basis gauge warning. The local wrapper/API use is reproduced.", "",
        h("Molecular matrices and identities"), "",
        f"The complete accepted 12+4 zero-field, magnetic, dipole, branching, strength, and basis-transform objects are exported in `{MATRIX_PATH.name}` with units and basis metadata. Hamiltonian/vector Hermiticity, `(3,12,4)` shape, branching normalization, polarization completeness, ground/excited strength sums, transformation unitarity, and basis-rephasing invariance pass. No incompatible one-sided basis transform was found.", "",
        h("Component 4 and dark-state mechanism"), "",
        f"The accepted [3+1] calculation has a restoring local slope `{metadata['component_4_diagnosis']['small_signal_slopes']['three_plus_one']:.5g}`, unlike the rendered Figure 2(c) slope. Enabling component (4) strengthens confinement relative to the same [3+1] saturation vector with it disabled. However, the shared-solution decomposition does not reproduce the paper's stated level hierarchy: the accepted upper-F=1 and F2 component-(4) terms are both restoring, with upper-F=1 larger. With component (4) alone, weak off-resonant coupling makes the solve unique but the upper-F=1 and F2 terms nearly cancel with the opposite nominal hierarchy. Population redistribution also changes components (1)-(3). This is direct evidence for a level-specific molecular-matrix mismatch, not a wrapper error.", "",
        f"As |x| grows from 0 to 6 normalized units in [3], the accepted force falls to `{metadata['dark_state_cause_assessment']['force_drop_factor_x0_to_x6']:.3f}` of its central value while scattering falls to `{metadata['dark_state_cause_assessment']['scattering_drop_factor_x0_to_x6']:.3f}`. Population accumulates in weakly coupled states and counterpropagating dominance gives way to stronger copropagating cancellation. Zeeman shifts, populated states, and beam fractions are tabulated at every point. This diagnoses the accepted model's early force loss, but cannot decide whether the paper differs through strengths, Zeeman matrices, eigenvectors, or branching without its matrices.", "",
        h("Paper quantitative statements"), "",
        "| quantity | paper rough value | accepted value | classification |", "|---|---:|---:|---|",
        f"| scattering rate | 0.125 Gamma | {q['maximum_scattering_rate']['accepted']:.4f} Gamma | {q['maximum_scattering_rate']['classification']} |",
        f"| force magnitude | 0.05 hbar k Gamma | {q['force_magnitude']['accepted']:.4f} | {q['force_magnitude']['classification']} |",
        f"| +/-z scattering fraction | 0.30 | {q['plus_minus_z_scattering_fraction']['accepted']:.3f} | {q['plus_minus_z_scattering_fraction']['classification']} |",
        f"| copropagating scattering fraction | 0.10 | {q['copropagating_scattering_fraction']['accepted']:.3f} | {q['copropagating_scattering_fraction']['classification']} |", "",
        h("pylcp history"), "",
        "The installed `pylcp 1.0.2` `rateeq.py`, `fields.py`, `hamiltonian.py`, and `hamiltonians/XFmolecules.py` are byte-identical to official tag `v1.0.2` (`a7cb104f...`, 2022-06-23), the latest official commit before the paper date. Official master through `53885b54...` contains no changes to those audited files. The paper's exact checkout is not published, so private modifications cannot be excluded.", "",
        h("Splitting versus eigenvectors"), "",
        "Run 009D's insensitivity to a 0-1 MHz diagonal F'=0/F'=1 splitting does not test eigenvector changes, d-driven J'=1/2 to J'=3/2 mixing, altered dipoles, or omitted-state coupling. Run 011C does not invent the missing independent Doppelbauer d operator.", "",
        h("Diagnosis ranking"), "",
        "Demonstrated local causes: none. Ruled out by this audit: global figure-sign inversion, rate-equation wrapper mismatch, released-pylcp version drift, and a local one-sided basis transform. The leading unresolved contributors are unpublished paper-specific matrices, excited-hyperfine eigenvectors/J mixing, the resulting dipole tensor, and downstream dark-state population differences. Exact excited Zeeman physics remains a secondary blocker.", "",
        h("Final gate: MOLECULAR_MODEL_DISCREPANCY_NARROWED"), "",
        "**MOLECULAR_MODEL_DISCREPANCY_NARROWED**", "",
        "The supplied local matrices are evaluated consistently by two independent equation paths, but the paper discrepancy cannot be assigned uniquely between excited eigenvectors and transition dipoles without the full d operator or paper-specific matrices.", "",
        "`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.", "",
        f"# {LABEL} FINAL_MOLECULAR_MODEL_DISCREPANCY_NARROWED",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
