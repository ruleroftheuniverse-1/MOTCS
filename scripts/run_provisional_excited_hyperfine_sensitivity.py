"""Run 009D: static-only excited-hyperfine and d-term sensitivity audit."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_provisional_excited_zeeman_sensitivity as run009c
import run_provisional_rateeq_static_acceptance_audit_r1 as r1

from mgf_mot.conventions import GroundZeemanConvention
from mgf_mot.excited_hyperfine import (
    ExcitedHyperfineModel,
    SourceAlignedSplittingCase,
    build_excited_f_projectors,
    build_excited_hyperfine_operator,
    validate_excited_f_projectors,
    validate_excited_hyperfine_operator,
)
from mgf_mot.excited_zeeman import ExcitedZeemanModel
from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.rateeq_backend import ProvisionalPylcpRateEquationBackend, RateEquationBackendConfig
from mgf_mot.spectroscopy import (
    EXCITED_HYPERFINE_D_MHZ,
    EXCITED_HYPERFINE_D_UNCERTAINTY_MHZ,
    EXCITED_POSITIVE_PARITY_HFS_UPPER_BOUND_MHZ,
)
from mgf_mot.static_acceptance import flip_policy_polarizations


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
RUN009D_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_"
    "EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY"
)
THRESHOLDS = {
    "insensitive_relative_max": 0.01,
    "weakly_sensitive_relative_max": 0.05,
    "relative_force_mask_fraction_of_reference_max": 1.0e-3,
    "topology_changing": "restoring/damping/reversal sign or zero-contour branch count changes",
}
FULL_CASES = (
    ("pylcp_collapsed", ExcitedHyperfineModel.PYLCP_COLLAPSED_ASTATE, None),
    ("zero_splitting_stress", ExcitedHyperfineModel.NO_EXCITED_HYPERFINE_SPLITTING, None),
    (
        "source_mid_range_0p5_mhz",
        ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING,
        SourceAlignedSplittingCase.MID_RANGE_0P5_MHZ,
    ),
    (
        "source_upper_boundary_stress_1_mhz",
        ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING,
        SourceAlignedSplittingCase.UPPER_BOUND_STRESS_1_MHZ,
    ),
)


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
        if np.iscomplexobj(value):
            return {"real": value.real.tolist(), "imag": value.imag.tolist()}
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _stamp(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _stamp(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stamp(item) for item in value]
    if isinstance(value, str):
        return value.replace(run009c.RUN009C_LABEL, RUN009D_LABEL).replace(r1.R1_LABEL, RUN009D_LABEL)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _backend(
    model: ExcitedHyperfineModel,
    splitting_case: SourceAlignedSplittingCase | None,
    *,
    gradient_t_m: float = 0.2,
) -> ProvisionalPylcpRateEquationBackend:
    backend = ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            magnetic_gradient_t_m=gradient_t_m,
            ground_zeeman_convention=GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED,
            excited_zeeman_model=ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001,
            excited_hyperfine_model=model,
            excited_hyperfine_splitting_case=splitting_case,
        )
    )
    status = backend.status
    if status.ground_magnetic_moment_correction_count != 1:
        raise RuntimeError("Run 009D requires exactly one corrected ground-Zeeman mapping")
    if status.excited_zeeman_model != ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001.value:
        raise RuntimeError("Run 009D freezes excited Zeeman to Rodriguez effective g'=0.001")
    if status.excited_hyperfine_model_application_count != 1:
        raise RuntimeError("excited hyperfine model must be applied exactly once")
    return backend


def _current_h0_audit(backend: ProvisionalPylcpRateEquationBackend) -> dict[str, Any]:
    source = backend.source_backend
    h0 = np.asarray(source.hamiltonian.blocks[1, 1][0].matrix, dtype=complex)
    basis = source.validation_model.excited_basis
    vals, vecs = np.linalg.eigh(h0)
    projectors = build_excited_f_projectors(basis)
    split = float(np.trace(projectors.f1 @ h0).real / 3 - np.trace(projectors.f0 @ h0).real)
    return {
        "label": RUN009D_LABEL,
        "basis_order": [
            {"index": i, "F_prime": int(s["F"]), "mF": int(s["mF"])}
            for i, s in enumerate(basis)
        ],
        "matrix_shape": list(h0.shape),
        "matrix_mhz": h0.real.tolist(),
        "eigenvalues_mhz": vals.tolist(),
        "eigenvectors_columns": vecs.real.tolist(),
        "F_prime_character": ["F'=0,mF=0", "F'=1,mF=-1", "F'=1,mF=0", "F'=1,mF=+1"],
        "F0_to_F1_splitting_mhz": split,
        "center_of_gravity_mhz": float(np.trace(h0).real / 4),
        "source_supported": False,
        "astate_inputs": {
            "J": 0.5, "I": 0.5, "P": 1, "B_MHz": 15788.2, "D_MHz": 0.0,
            "H_MHz": 0.0, "a_MHz": 109.0, "b_MHz": -52.0, "c_MHz": 0.0,
            "eQq0_MHz": 0.0, "p_MHz": 15.0, "q_MHz": 0.0,
            "gS": "source-tagged project value", "gL": 0.0, "gl": 0.0,
            "glprime": 0.0, "gr": 0.0, "greprime": 0.0, "gN": 0.0,
        },
        "term_mapping": {
            "direct": ["a=109 MHz", "B=15788.2 MHz"],
            "collapsed": ["b_F+2c/3=-52 MHz -> pylcp b=-52,c=0", "p+2q=15 MHz -> pylcp p=15,q=0"],
            "absent": ["independent Doppelbauer d=135(7) MHz"],
            "common_or_unused_in_single_J_parity_block": ["B", "p", "D=H=0"],
        },
    }


def _reversal(model, splitting_case, backend, resources) -> dict[str, Any]:
    sample = resources["static31"].sample(0.0)
    flipped = flip_policy_polarizations(sample)
    negative = _backend(model, splitting_case, gradient_t_m=-0.2)
    definitions = {
        "nominal": (backend, sample),
        "polarization_flipped": (backend, flipped),
        "gradient_flipped": (negative, sample),
        "both_flipped": (negative, flipped),
    }
    cases = {}
    for name, (case_backend, case_sample) in definitions.items():
        system = case_backend.build_optical_system(case_sample, policy_name=f"run009d_{name}", beam_mode="plane_wave")
        cases[name] = _stamp(r1._local_slope_record(case_backend, system))
    passed = bool(
        cases["nominal"]["dFdx_normalized_per_m"] < 0
        and cases["nominal"]["dFdv_normalized_per_m_s"] < 0
        and cases["polarization_flipped"]["dFdx_normalized_per_m"] > 0
        and cases["gradient_flipped"]["dFdx_normalized_per_m"] > 0
        and cases["both_flipped"]["dFdx_normalized_per_m"] < 0
    )
    return {"label": RUN009D_LABEL, "cases": cases, "passed": passed}


def _observables(key, model, splitting_case):
    print(f"{RUN009D_LABEL}: evaluating {key}")
    backend = _backend(model, splitting_case)
    resources = r1.prior_audit._resources(backend)
    arrays, health = run009c._evaluate_grids(backend, resources)
    local = _stamp(r1._local_slope_audit(backend, resources))
    component4 = _stamp(r1._component4_audit(backend, resources, arrays))
    chirp = _stamp(r1._chirp_audit(backend, resources, np.linspace(0.0, 110.0, 111)))
    gaussian = _stamp(r1.prior_audit._gaussian_audit(backend, resources))
    convergence = _stamp(r1.prior_audit._grid_convergence(backend, resources, arrays, refinement_factor=2))
    convergence["topology_preserved"] = bool(
        all(row["checks"]["local_topology_signs_unchanged"] for row in convergence["cases"].values())
    )
    record = {
        "label": RUN009D_LABEL,
        "title": f"{RUN009D_LABEL} {key}",
        "key": key,
        "model": model.value,
        "splitting_case": None if splitting_case is None else splitting_case.value,
        "splitting_mhz": backend.excited_hyperfine_operator.splitting_mhz,
        "backend_status": _json_safe(backend.status),
        "hyperfine_operator": _json_safe(backend.excited_hyperfine_operator),
        "hamiltonian_validation": validate_excited_hyperfine_operator(backend.excited_hyperfine_operator),
        "non_hyperfine_input_fingerprint": {
            "ground_zeeman": backend.config.ground_zeeman_convention.value,
            "excited_zeeman": backend.config.excited_zeeman_model.value,
            "gradient_t_m": 0.2,
            "paper_helicity_translation": backend.config.paper_helicity_translation.value,
            "position_axis_m": run009c.POSITIONS_M.tolist(),
            "velocity_axis_m_s": run009c.VELOCITIES_M_S.tolist(),
            "policy_names": [resources["static3"].name, resources["static31"].name, resources["chirp"].name],
            "geometry": "unchanged six-beam x_prime/y_prime/z plus Rodriguez Gaussian baseline",
        },
        "local_slopes": local,
        "component_4": component4,
        "reversal": _reversal(model, splitting_case, backend, resources),
        "extrema": run009c._extrema(arrays),
        "chirp": chirp,
        "force_scale": _stamp(r1._force_scale_audit(arrays, backend)),
        "gaussian": gaussian,
        "population_health": _stamp(health),
        "grid_refinement": convergence,
    }
    return record, arrays


def _zero_crossings(axis: np.ndarray, values: np.ndarray) -> list[float]:
    result = []
    for i in range(len(axis) - 1):
        y0, y1 = values[i], values[i + 1]
        if y0 == 0:
            result.append(float(axis[i]))
        elif y0 * y1 < 0:
            result.append(float(axis[i] - y0 * (axis[i + 1] - axis[i]) / (y1 - y0)))
    return result


def _surface_comparison(reference_arrays, candidate_arrays) -> dict[str, Any]:
    result = {}
    for name, reference in reference_arrays.items():
        if not name.startswith("force_"):
            continue
        candidate = candidate_arrays[name]
        diff = candidate - reference
        scale = max(float(np.max(np.abs(reference))), 1e-15)
        mask = np.abs(reference) > THRESHOLDS["relative_force_mask_fraction_of_reference_max"] * scale
        relative = np.abs(diff[mask] / reference[mask]) if np.any(mask) else np.array([])
        ref_crossings = [_zero_crossings(run009c.POSITIONS_M, reference[:, j]) for j in range(reference.shape[1])]
        can_crossings = [_zero_crossings(run009c.POSITIONS_M, candidate[:, j]) for j in range(candidate.shape[1])]
        paired = [abs(a[0] - b[0]) for a, b in zip(ref_crossings, can_crossings) if a and b]
        ref_ext = np.unravel_index(int(np.argmax(np.abs(reference))), reference.shape)
        can_ext = np.unravel_index(int(np.argmax(np.abs(candidate))), candidate.shape)
        result[name] = {
            "maximum_absolute_difference": float(np.max(np.abs(diff))),
            "normalized_rms_difference": float(np.sqrt(np.mean(diff**2)) / scale),
            "maximum_relative_difference_away_from_zero": None if relative.size == 0 else float(np.max(relative)),
            "median_relative_difference_away_from_zero": None if relative.size == 0 else float(np.median(relative)),
            "zero_contour_max_displacement_m": None if not paired else float(max(paired)),
            "zero_contour_branch_count_changed": any(len(a) != len(b) for a, b in zip(ref_crossings, can_crossings)),
            "absolute_extremum_displacement": {
                "x_m": float(run009c.POSITIONS_M[can_ext[0]] - run009c.POSITIONS_M[ref_ext[0]]),
                "vx_m_s": float(run009c.VELOCITIES_M_S[can_ext[1]] - run009c.VELOCITIES_M_S[ref_ext[1]]),
            },
        }
    return result


def _classification(comparison: dict[str, Any]) -> str:
    if any(row["zero_contour_branch_count_changed"] for row in comparison.values()):
        return "TOPOLOGY_CHANGING"
    worst = max(row["normalized_rms_difference"] for row in comparison.values())
    if worst <= THRESHOLDS["insensitive_relative_max"]:
        return "INSENSITIVE"
    if worst <= THRESHOLDS["weakly_sensitive_relative_max"]:
        return "WEAKLY_SENSITIVE"
    return "MATERIALLY_SENSITIVE"


def _local_range_sweep() -> list[dict[str, Any]]:
    rows = []
    for case in SourceAlignedSplittingCase:
        backend = _backend(ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING, case)
        resources = r1.prior_audit._resources(backend)
        slopes = _stamp(r1._local_slope_audit(backend, resources))["cases"]
        rows.append({
            "case": case.value,
            "splitting_mhz": case.splitting_mhz,
            "boundary_stress_not_physical_candidate": case is SourceAlignedSplittingCase.UPPER_BOUND_STRESS_1_MHZ,
            "plane_wave_3_dFdx": slopes["plane_wave_3"]["dFdx_normalized_per_m"],
            "plane_wave_3_dFdv": slopes["plane_wave_3"]["dFdv_normalized_per_m_s"],
            "plane_wave_3_plus_1_dFdx": slopes["plane_wave_3_plus_1"]["dFdx_normalized_per_m"],
            "plane_wave_3_plus_1_dFdv": slopes["plane_wave_3_plus_1"]["dFdv_normalized_per_m_s"],
        })
    return rows


def _save_plot(records, arrays_by_key, output_dir):
    import matplotlib.pyplot as plt

    path = output_dir / f"{RUN009D_LABEL}_run_009D_comparison.png"
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    for key, record in records.items():
        slopes = record["local_slopes"]["cases"]["plane_wave_3"]
        axes[0].scatter(slopes["dFdx_normalized_per_m"], slopes["dFdv_normalized_per_m_s"], label=key)
        grid = arrays_by_key[key]["force_plane_wave_3_plus_1"]
        axes[1].plot(run009c.POSITIONS_M * 1e3, grid[:, 8], label=key)
        axes[2].plot(run009c.VELOCITIES_M_S, grid[8, :], label=key)
    axes[0].set(xlabel="dF_x/dx", ylabel="dF_x/dv_x", title="Refined [3] slopes")
    axes[1].set(xlabel="x [mm]", ylabel="F/(hbar k Gamma)", title="[3+1] position slice at v=0")
    axes[2].set(xlabel="v_x [m/s]", ylabel="F/(hbar k Gamma)", title="[3+1] velocity slice at x=0")
    for axis in axes:
        axis.legend(fontsize=6)
    fig.suptitle(
        "PROVISIONAL / NOT_RODRIGUEZ_REPLICATION\n"
        "EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY - Run 009D",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(path)
    plt.close(fig)
    return path


def run(output_dir: Path = DEFAULT_OUTPUT_DIR, *, save_plot: bool = True) -> dict[str, Any]:
    """Execute static diagnostics only; this function never integrates motion."""

    output_dir.mkdir(parents=True, exist_ok=True)
    yaml_paths = tuple(sorted((REPO_ROOT / "configs").glob("rodriguez*.yaml")))
    yaml_before = {str(p.relative_to(REPO_ROOT)): _sha256(p) for p in yaml_paths}
    collapsed_backend = _backend(ExcitedHyperfineModel.PYLCP_COLLAPSED_ASTATE, None)
    current_audit = _current_h0_audit(collapsed_backend)
    basis = collapsed_backend.source_backend.validation_model.excited_basis
    projector_validation = validate_excited_f_projectors(build_excited_f_projectors(basis))
    full_d_failure = None
    try:
        build_excited_hyperfine_operator(
            ExcitedHyperfineModel.FULL_DOPPELBAUER_D_OPERATOR,
            basis=basis,
            pylcp_collapsed_h0_mhz=collapsed_backend.source_backend.hamiltonian.blocks[1, 1][0].matrix,
        )
    except ValueError as exc:
        full_d_failure = str(exc)

    records, arrays_by_key = {}, {}
    for key, model, splitting_case in FULL_CASES:
        records[key], arrays_by_key[key] = _observables(key, model, splitting_case)
    reference_key = "source_mid_range_0p5_mhz"
    comparisons = {}
    for key in records:
        if key == reference_key:
            continue
        surfaces = _surface_comparison(arrays_by_key[reference_key], arrays_by_key[key])
        comparisons[f"{key}_vs_{reference_key}"] = {
            "whole_surfaces": surfaces,
            "classification": _classification(surfaces),
            "scalar_observables": _stamp(run009c._compare_models(records[reference_key], records[key])),
        }
    source_range = comparisons[f"source_upper_boundary_stress_1_mhz_vs_{reference_key}"]
    source_range_robust = source_range["classification"] in {"INSENSITIVE", "WEAKLY_SENSITIVE"}
    preferred = records[reference_key]
    acceptance = {
        "projectors_valid": all(projector_validation[k] for k in ("hermitian", "idempotent", "orthogonal", "complete")) and projector_validation["dimensions"] == [1, 3],
        "fixed_zeeman_conventions": all(
            r["backend_status"]["ground_magnetic_moment_correction_count"] == 1
            and r["backend_status"]["excited_zeeman_model"] == "rodriguez_effective_g_0p001"
            for r in records.values()
        ),
        "source_range_static_robust": source_range_robust,
        "restoring_and_damping": preferred["local_slopes"]["passed"],
        "component_4_improves_confinement": preferred["component_4"]["passed"],
        "reversal_pattern": preferred["reversal"]["passed"],
        "chirp_feature_motion": preferred["chirp"]["passed"],
        "force_scale": preferred["force_scale"]["passed"],
        "population_health": preferred["population_health"]["passed"],
        "refined_topology": preferred["grid_refinement"]["topology_preserved"],
        "gaussian_application": preferred["gaussian"]["passed"],
        "full_d_not_invented": full_d_failure is not None,
    }
    gate = "PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO" if all(acceptance.values()) else "STATIC_ONLY_CONTINUE"
    trajectory_authorized = gate == "PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO"
    arrays_path = output_dir / f"{RUN009D_LABEL}_run_009D_arrays.npz"
    np.savez_compressed(arrays_path, **{
        f"{key}__{name}": array
        for key, arrays in arrays_by_key.items()
        for name, array in arrays.items()
    })
    plot_path = _save_plot(records, arrays_by_key, output_dir) if save_plot else None
    yaml_after = {str(p.relative_to(REPO_ROOT)): _sha256(p) for p in yaml_paths}
    if yaml_before != yaml_after:
        raise RuntimeError("Rodriguez YAML changed during Run 009D")
    metadata = {
        "label": RUN009D_LABEL,
        "title": f"{RUN009D_LABEL} Run 009D metadata",
        "gate": gate,
        "provisional_static_authorized": True,
        "provisional_trajectory_authorized": trajectory_authorized,
        "capture_authorized": False,
        "exact_replication_valid": False,
        "exact_track_blocked": True,
        "trajectory_integrations_performed": 0,
        "capture_calculations_performed": 0,
        "selected_excited_zeeman_model": ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001.value,
        "selected_excited_hyperfine_model": ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING.value,
        "selected_splitting_case": SourceAlignedSplittingCase.MID_RANGE_0P5_MHZ.value,
        "selected_splitting_caveat": "0.5 MHz is the deterministic midpoint of a reported <1 MHz interval, not a measured central value",
        "unresolved_terms": ["full d-dependent J'=1/2 <-> J'=3/2 mixing", "exact positive-parity line splitting", "d-dependent transition-strength corrections"],
        "source_constraints": {
            "d_value_mhz": EXCITED_HYPERFINE_D_MHZ.require(),
            "d_uncertainty_mhz": EXCITED_HYPERFINE_D_UNCERTAINTY_MHZ.require(),
            "positive_parity_splitting_upper_bound_mhz": EXCITED_POSITIVE_PARITY_HFS_UPPER_BOUND_MHZ.require(),
            "d_operator": "a Lz Iz + b_F S.I + c/3(3 Sz Iz-S.I) - d/2(S+ I+ + S- I-)",
            "source": "Doppelbauer et al., JCP 156, 134301 (2022), Eq. (1), Table III, Conclusion, Appendix A",
            "constraint_types": {"d": "direct fit", "operator": "direct equation", "positive_parity_split": "direct reported upper bound", "0.5_mhz": "inferred interval midpoint"},
        },
        "current_collapsed_h0_audit": current_audit,
        "projector_validation": projector_validation,
        "full_d_operator_implementation": {"implemented": False, "fail_closed_message": full_d_failure},
        "candidate_models": records,
        "comparisons": comparisons,
        "controlled_source_range_local_sweep": _local_range_sweep(),
        "sensitivity_thresholds": THRESHOLDS,
        "acceptance_checks": acceptance,
        "non_hyperfine_inputs_identical": len({json.dumps(r["non_hyperfine_input_fingerprint"], sort_keys=True) for r in records.values()}) == 1,
        "source_yaml_unchanged": True,
        "source_yaml_hashes": yaml_after,
        "arrays": arrays_path.name,
        "plot": None if plot_path is None else plot_path.name,
    }
    metadata_path = output_dir / f"{RUN009D_LABEL}_run_009D_metadata.json"
    metadata_path.write_text(json.dumps(_json_safe(metadata), indent=2, sort_keys=True), encoding="utf-8")
    report_path = output_dir / f"{RUN009D_LABEL}_run_009D.md"
    h = lambda text: f"## {RUN009D_LABEL} {text}"
    lines = [
        f"# {RUN009D_LABEL} Run 009D",
        "",
        "This is a static-only provisional sensitivity audit. It runs no trajectory or capture calculation and is not an exact MgF/Rodriguez reproduction.",
        "",
        h("Current collapsed Astate audit"), "",
        f"Basis: `{[(r['F_prime'], r['mF']) for r in current_audit['basis_order']]}`. Matrix shape: `{current_audit['matrix_shape']}`. Eigenvalues: `{current_audit['eigenvalues_mhz']}` MHz. Eigenvectors are the corresponding basis unit vectors (up to degenerate-subspace rotations).",
        f"The collapsed splitting is `{current_audit['F0_to_F1_splitting_mhz']:.9f} MHz`; it is not source-supported for the positive-parity cooling state. The independent `d=135(7) MHz` term is absent.",
        "",
        h("Source boundary"), "",
        "Doppelbauer Eq. (1) defines the independent `d` operator and Table III reports `135 +/- 7 MHz`. The conclusion reports the positive-parity `J'=1/2` hyperfine splitting as less than 1 MHz. Appendix A shows `d`-dependent coupling to `J'=3/2`; therefore the projector model changes energies only and omits eigenvector/transition-strength corrections.",
        "",
        h("Projectors and candidate Hamiltonians"), "",
        f"Projector validation: `{projector_validation}`. The F'=0 and F'=1 dimensions are 1 and 3 and are compatible with the direct-sum `g'=0.001` operator.",
        "| candidate | splitting MHz | source family | stress | Hermitian | changes eigenvectors |",
        "|---|---:|---|---|---|---|",
    ]
    for key, record in records.items():
        op, val = record["hyperfine_operator"], record["hamiltonian_validation"]
        lines.append(f"| {key} | {record['splitting_mhz']:.9g} | {op['source_supported_family']} | {op['engineering_stress_test']} | {val['hermitian']} | {val['changes_eigenvectors']} |")
    lines += ["", h("Static observables"), "", "| candidate | [3] dF/dx | [3] dF/dv | [3+1] dF/dx | [3+1] dF/dv | c4 | reversal | health |", "|---|---:|---:|---:|---:|---|---|---|"]
    for key, record in records.items():
        c = record["local_slopes"]["cases"]
        lines.append(f"| {key} | {c['plane_wave_3']['dFdx_normalized_per_m']:.6g} | {c['plane_wave_3']['dFdv_normalized_per_m_s']:.6g} | {c['plane_wave_3_plus_1']['dFdx_normalized_per_m']:.6g} | {c['plane_wave_3_plus_1']['dFdv_normalized_per_m_s']:.6g} | {record['component_4']['passed']} | {record['reversal']['passed']} | {record['population_health']['passed']} |")
    lines += ["", h("Whole-surface sensitivity"), ""]
    for name, comparison in comparisons.items():
        lines.append(f"- `{name}`: **{comparison['classification']}**; per-surface maximum absolute, normalized RMS, masked relative, zero-contour, and extremum displacements are recorded in metadata.")
    lines += [
        "", h("Answers and authorization"), "",
        "1. The collapsed model produces 55.333335977 MHz and is not supported by the positive-parity spectroscopy constraint.",
        "2. A center-of-gravity-preserving F'-projector model over the reported 0 to <1 MHz interval is defensible as an effective diagonal family, not as a full `d` operator.",
        "3. The sourced `d` term requires J'=3/2 mixing beyond diagonal splitting; a full retained-basis operator was not invented.",
        f"4. Source-range sensitivity is `{source_range['classification']}`. The collapsed-model comparison is `{comparisons[f'pylcp_collapsed_vs_{reference_key}']['classification']}` and may contaminate provisional motion if retained.",
        "5. The preferred Track P family is `SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING`; the 0.5 MHz midpoint is merely a reproducible interval representative.",
        "", h(f"Final gate: {gate}"), "", f"**{gate}**", "",
        f"`provisional_static_authorized = true`; `provisional_trajectory_authorized = {str(trajectory_authorized).lower()}`; `capture_authorized = false`; `exact_replication_valid = false`; `exact_track_blocked = true`.",
        "This gate, if GO, authorizes reconnecting only the named provisional rate-equation backend to non-capture trajectory plumbing. It does not authorize capture thresholds or replication claims.",
        "", f"# {RUN009D_LABEL} FINAL_{gate}",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{RUN009D_LABEL}: {gate}")
    print(f"metadata: {metadata_path}")
    print(f"report: {report_path}")
    return {"gate": gate, "metadata": metadata, "metadata_path": metadata_path, "report_path": report_path, "arrays_path": arrays_path, "plot_path": plot_path}


if __name__ == "__main__":
    run()
