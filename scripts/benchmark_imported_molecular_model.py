"""Compact pre-dynamics paper benchmark for any validated Run 012 package."""

from __future__ import annotations

import argparse
from dataclasses import replace
import glob
import json
from pathlib import Path
import sys
import warnings
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
from mgf_mot.molecular_model_package import RUN012_LABEL, build_backend_from_package, load_package, validate_package  # noqa: E402
from mgf_mot.policies import load_policy  # noqa: E402

DEFAULT = ROOT / "outputs/provisional/molecular_model_packages/run_012" / f"{RUN012_LABEL}_ACCEPTED_PROVISIONAL_REFERENCE_PACKAGE"
OUTPUT = DEFAULT.parent / f"{RUN012_LABEL}_paper_benchmark.json"
REPORT = ROOT / "outputs/provisional" / f"{RUN012_LABEL}.md"


def _force(backend: Any, optical: Any, x: float, v: float) -> Any:
    context = backend.force_units
    position_unit = float(backend.package_metadata["force_context"]["figure_position_unit_m"])
    position = np.array([x * position_unit, 0.0, 0.0]); velocity = np.array([v * context.linewidth_rad_s / context.wave_number_rad_m, 0.0, 0.0])
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always", np.exceptions.ComplexWarning)
        return backend.force_at(position, velocity, optical, collect_solver_diagnostics=True)


def _paper_sample(name: str, xs: np.ndarray, vs: np.ndarray) -> dict[str, Any]:
    matches = glob.glob(str(ROOT / "outputs/provisional/paper_digitization/run_011b" / f"*figure_2_{name}_digitized.npz"))
    if len(matches) != 1: return {"available": False, "reason": "Run 011B digitized panel not found uniquely"}
    with np.load(matches[0]) as data:
        px, pv, force, valid = data["x"], data["y"], data["force_hbar_k_gamma"], data["valid_mask"]
        sampled = np.full((len(vs), len(xs)), np.nan)
        mask = np.zeros_like(sampled, dtype=bool)
        for j, v in enumerate(vs):
            for i, x in enumerate(xs):
                ix, iv = int(np.argmin(abs(px - x))), int(np.argmin(abs(pv - v)))
                sampled[j, i] = force[iv, ix]; mask[j, i] = bool(valid[iv, ix])
    return {"available": True, "force": sampled.tolist(), "valid": mask.tolist(), "source": str(Path(matches[0]).relative_to(ROOT))}


def _level_component4(backend: Any, result: Any) -> dict[str, float]:
    populations = result.equilibrium_populations; rates = result.pumping_rate_matrices
    imbalance = populations[:12, None] - populations[None, 12:]
    labels = backend.package_metadata["basis"]["ground"] if hasattr(backend, "package_metadata") else []
    groups = {name: [] for name in ("lower_F1", "F0", "upper_F1", "F2")}
    for row in labels: groups.setdefault(row["label"], []).append(int(row["index"]))
    output = {name: 0.0 for name in groups}
    for laser, (_, component) in enumerate(result.optical_system.pylcp_beam_index):
        if component != 4: continue
        collection = result.optical_system.pylcp_beams
        if not hasattr(collection, "beam_vector"):
            collection = collection["g->e"]
        beam = collection.beam_vector[laser]
        kx = float(np.asarray(beam.kvec(np.zeros(3), 0.0))[0])
        for name, indices in groups.items():
            output[name] += kx * float(np.sum(rates[laser, indices, :] * imbalance[indices, :]))
    return output


def run(path: Path = DEFAULT) -> dict[str, Any]:
    package = load_package(path, validate=False); validation = validate_package(package)
    if not validation.valid: raise ValueError("invalid molecular-model package cannot be benchmarked")
    backend = build_backend_from_package(package); backend.package_metadata = package.metadata
    xs = np.linspace(-6.0, 6.0, 9); vs = np.linspace(-8.0, 8.0, 9)
    surfaces: dict[str, Any] = {}; local: dict[str, Any] = {}; quantitative: dict[str, Any] = {}
    for key, config in (("mgf_3", "rodriguez_static_3.yaml"), ("mgf_3_plus_1", "rodriguez_static_3_plus_1.yaml")):
        policy = load_policy(ROOT / "configs" / config); optical = backend.build_optical_system(policy.sample(0), policy_name=policy.name, beam_mode="plane_wave")
        force = np.empty((len(vs), len(xs))); excited = np.empty_like(force); saved: dict[tuple[int, int], Any] = {}
        for j, v in enumerate(vs):
            for i, x in enumerate(xs):
                result = _force(backend, optical, float(x), float(v)); force[j, i] = result.normalized_force[0]; excited[j, i] = np.sum(result.equilibrium_populations[12:]); saved[(j, i)] = result
        paper = _paper_sample(key, xs, vs); valid = np.asarray(paper.get("valid", np.zeros_like(force)), dtype=bool); paper_force = np.asarray(paper.get("force", np.zeros_like(force)), dtype=float)
        rmse = float(np.sqrt(np.mean((force[valid] - paper_force[valid]) ** 2))) if valid.any() else None
        dx = 0.25; dv = 0.25
        dfdx = (_force(backend, optical, dx, 0).normalized_force[0] - _force(backend, optical, -dx, 0).normalized_force[0]) / (2 * dx)
        dfdv = (_force(backend, optical, 0, dv).normalized_force[0] - _force(backend, optical, 0, -dv).normalized_force[0]) / (2 * dv)
        max_index = np.unravel_index(int(np.argmax(abs(force))), force.shape); atmax = saved[max_index]
        pop = atmax.equilibrium_populations; imbalance = pop[:12, None] - pop[None, 12:]
        scattering = np.sum(atmax.pumping_rate_matrices * imbalance[None], axis=(1, 2))
        directions = [name for name, _ in atmax.optical_system.pylcp_beam_index]
        total = float(np.sum(scattering)); z = float(sum(value for value, name in zip(scattering, directions) if name in {"+z", "-z"}))
        surfaces[key] = {"x_Gamma_over_muB_gradient": xs.tolist(), "v_Gamma_over_k": vs.tolist(), "force_hbar_k_Gamma": force.tolist(), "paper_sample": paper, "sampled_rmse": rmse}
        local[key] = {"dF_dx_normalized": float(dfdx), "dF_dv_normalized": float(dfdv)}
        quantitative[key] = {"maximum_sampled_scattering_Gamma": float(np.max(excited)), "paper_maximum_scattering_Gamma": 0.125, "plus_minus_z_scattering_fraction_at_force_extremum": z / total if total else None, "paper_plus_minus_z_fraction": 0.30}
    policy31 = load_policy(ROOT / "configs/rodriguez_static_3_plus_1.yaml"); optical31 = backend.build_optical_system(policy31.sample(0), policy_name=policy31.name, beam_mode="plane_wave")
    plus = _force(backend, optical31, 0.5, 0); minus = _force(backend, optical31, -0.5, 0)
    hierarchy_plus, hierarchy_minus = _level_component4(backend, plus), _level_component4(backend, minus)
    component4 = {"level_resolved_spatial_slope": {name: (hierarchy_plus[name] - hierarchy_minus[name]) for name in hierarchy_plus}, "paper_expectation": {"F2": "trapping", "upper_F1": "anti-trapping"}}
    figure3 = {}
    base_policy = load_policy(ROOT / "configs/rodriguez_static_3.yaml")
    for detuning in (-2.0, -4.0, -6.0, -8.0):
        sample = base_policy.sample(0); sample = replace(sample, components=tuple(replace(component, detuning_gamma=detuning) if component.active else component for component in sample.components))
        optical = backend.build_optical_system(sample, policy_name=f"figure3_{detuning:g}Gamma", beam_mode="plane_wave")
        figure3[str(detuning)] = {"force_at_x0_v0": float(_force(backend, optical, 0, 0).normalized_force[0]), "dF_dv_at_origin": float((_force(backend, optical, 0, 0.25).normalized_force[0] - _force(backend, optical, 0, -0.25).normalized_force[0]) / 0.5)}
    rmse_values = [row["sampled_rmse"] for row in surfaces.values() if row["sampled_rmse"] is not None]
    reproduces = bool(rmse_values and max(rmse_values) < 0.01 and component4["level_resolved_spatial_slope"].get("F2", 0) < 0 < component4["level_resolved_spatial_slope"].get("upper_F1", 0))
    payload = {
        "label": RUN012_LABEL, "package_hash": package.hashes().full_package, "import_gate": validation.gate.value,
        "benchmark_scope": "compact plane-wave pre-dynamics diagnostic only", "figure_2": surfaces,
        "local_slopes": local, "component_4_hierarchy": component4, "paper_quantitative_scattering": quantitative,
        "selected_figure_3_detunings": figure3, "reproduces_paper_force_structure": reproduces,
        "benchmark_interpretation": "This compact result answers the pre-dynamics force-structure question; it does not authorize caches or trajectories.",
        "accepted_artifacts_modified": False, "cache_rebuild_authorized": False, "trajectory_reintegration_authorized": False,
        "capture_authorized": False, "optimizer_authorized": False, "replication_valid": False,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if REPORT.exists():
        lines = REPORT.read_text(encoding="utf-8").rstrip().splitlines()
        if lines and lines[-1] in {"MOLECULAR_MODEL_INTERCHANGE_READY", "MOLECULAR_MODEL_INTERCHANGE_REFINEMENT_REQUIRED", "MOLECULAR_MODEL_INTERCHANGE_NO_GO"}:
            lines.pop()
        rmses = {name: row["sampled_rmse"] for name, row in surfaces.items()}
        lines.extend([
            "", f"## {RUN012_LABEL} Import validation and paper benchmark", "",
            f"The serialized package passes `{validation.gate.value}` and carries full hash `{package.hashes().full_package}` into the packaged backend. The compact sampled Figure 2 RMSE values are `{rmses}`. Reproduces the paper force structure: `{reproduces}`. The accepted provisional reference is expected to remain discrepant; this establishes the baseline an author package must improve.", "",
            f"## {RUN012_LABEL} Author handoff", "",
            "The low-burden request is documented in `docs/author-request-molecular-model-package.md`; a matrix-free synthetic schema template is under `examples/molecular_model_package_template/`. A construction script is acceptable in place of serialized matrices, and no trajectory code is requested.", "",
            "`molecular_model_interchange_authorized=true`; `imported_model_force_authorized=false`; `cache_rebuild_authorized=false`; `trajectory_reintegration_authorized=false`; `capture_authorized=false`; `optimizer_authorized=false`; `exact_replication_valid=false`. Track E remains blocked pending the actual paper model.", "",
            "MOLECULAR_MODEL_INTERCHANGE_READY",
        ])
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{RUN012_LABEL}: package reproduces paper force structure={reproduces}"); return payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("package", nargs="?", type=Path, default=DEFAULT); args = parser.parse_args(); run(args.package)
