"""Run 012: export and strictly round-trip the accepted Track P model."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any
import warnings

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mgf_mot.accepted_backend import build_accepted_provisional_rateeq_backend  # noqa: E402
from mgf_mot.molecular_model_package import (  # noqa: E402
    RUN012_LABEL, build_backend_from_package, compare_packages, load_package,
    package_from_accepted_backend, validate_package, write_package,
)
from mgf_mot.policies import load_policy  # noqa: E402


OUTPUT = ROOT / "outputs" / "provisional"
PACKAGE_DIR = OUTPUT / "molecular_model_packages" / "run_012"
BASE = PACKAGE_DIR / f"{RUN012_LABEL}_ACCEPTED_PROVISIONAL_REFERENCE_PACKAGE"
ROUNDTRIP = PACKAGE_DIR / f"{RUN012_LABEL}_roundtrip_validation.json"
REPORT = OUTPUT / f"{RUN012_LABEL}.md"


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _protected() -> tuple[Path, ...]:
    patterns = (
        "outputs/provisional/*RUN_009*", "outputs/provisional/*RUN_010*",
        "outputs/provisional/*RUN_011*", "outputs/provisional/force_fields/*",
        "outputs/provisional/molecular_model_audit/run_011*/*",
        "outputs/provisional/paper_digitization/run_011b/*", "configs/*.yaml",
    )
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update(path for path in ROOT.glob(pattern) if path.is_file())
    paths.update({ROOT / "src/mgf_mot/accepted_backend.py", ROOT / "src/mgf_mot/spectroscopy.py"})
    return tuple(sorted(paths))


def _manifest(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): _hash(path) for path in paths}


def _force_comparison(original: Any, loaded: Any) -> dict[str, Any]:
    rows = []
    maximum = {"force": 0.0, "population": 0.0, "scattering": 0.0}
    for config in ("rodriguez_static_3.yaml", "rodriguez_static_3_plus_1.yaml"):
        policy = load_policy(ROOT / "configs" / config)
        original_optical = original.build_optical_system(policy.sample(0.0), policy_name=policy.name, beam_mode="plane_wave")
        loaded_optical = loaded.build_optical_system(policy.sample(0.0), policy_name=policy.name, beam_mode="plane_wave")
        config_rows = []
        for x, v in ((0.0, 0.0), (-0.5, 0.0), (0.5, 0.0), (0.0, -0.5), (0.0, 0.5), (3.0, 1.4142135623730951)):
            position = np.array([x * 7.48e-3, 0.0, 0.0]); velocity = np.array([v * original.force_units.linewidth_rad_s / original.force_units.wave_number_rad_m, 0.0, 0.0])
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always", np.exceptions.ComplexWarning)
                a = original.force_at(position, velocity, original_optical, collect_solver_diagnostics=True)
                b = loaded.force_at(position, velocity, loaded_optical, collect_solver_diagnostics=True)
            diff = {
                "force": float(np.max(abs(a.normalized_force - b.normalized_force))),
                "population": float(np.max(abs(a.equilibrium_populations - b.equilibrium_populations))),
                "scattering": float(np.max(abs(a.per_laser_pumping_rate_sum - b.per_laser_pumping_rate_sum))),
            }
            for key in maximum: maximum[key] = max(maximum[key], diff[key])
            config_rows.append({"x_Gamma_over_muB_gradient": x, "v_Gamma_over_k": v, "original_force_x": float(a.normalized_force[0]), "loaded_force_x": float(b.normalized_force[0]), "differences": diff})
        original_dfdx = config_rows[2]["original_force_x"] - config_rows[1]["original_force_x"]
        loaded_dfdx = config_rows[2]["loaded_force_x"] - config_rows[1]["loaded_force_x"]
        original_dfdv = config_rows[4]["original_force_x"] - config_rows[3]["original_force_x"]
        loaded_dfdv = config_rows[4]["loaded_force_x"] - config_rows[3]["loaded_force_x"]
        rows.append({"config": config, "points": config_rows, "local_slopes": {"original_dF_dx": original_dfdx, "loaded_dF_dx": loaded_dfdx, "dF_dx_difference": abs(original_dfdx-loaded_dfdx), "original_dF_dv": original_dfdv, "loaded_dF_dv": loaded_dfdv, "dF_dv_difference": abs(original_dfdv-loaded_dfdv)}})
    return {"points": rows, "maximum_differences": maximum, "strict_tolerance": 2e-12, "passes": max(maximum.values()) < 2e-12}


def run() -> dict[str, Any]:
    protected = _protected(); before = _manifest(protected)
    backend = build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=True)
    package = package_from_accepted_backend(backend, date_created="2026-08-02", generator="MOTCS Run 012 export_accepted_molecular_model.py")
    files = write_package(package, BASE)
    loaded = load_package(BASE)
    packaged_backend = build_backend_from_package(loaded)
    validation = validate_package(loaded)
    matrix_comparison = compare_packages(package, loaded)
    forces = _force_comparison(backend, packaged_backend)
    arrays_exact = all(np.array_equal(package.arrays[name], loaded.arrays[name]) for name in package.arrays)
    array_maximum_differences = {name: float(np.max(abs(np.asarray(package.arrays[name]) - np.asarray(loaded.arrays[name])))) for name in package.arrays}
    transition_strength_difference = float(np.max(abs(abs(package.arrays["d_q"])**2 - abs(loaded.arrays["d_q"])**2)))
    after = _manifest(protected)
    result = {
        "label": RUN012_LABEL, "track": "provisional", "replication_valid": False,
        "package_files": {key: str(value.relative_to(ROOT)) for key, value in files.items()},
        "package_hashes": asdict(loaded.hashes()), "schema_validation": {
            "gate": validation.gate.value, "errors": list(validation.errors), "warnings": list(validation.warnings), "checks": validation.checks,
        },
        "complex_arrays_preserved_exactly": arrays_exact,
        "array_roundtrip_maximum_differences": array_maximum_differences,
        "transition_strength_roundtrip_maximum_difference": transition_strength_difference,
        "matrix_roundtrip_equivalent": matrix_comparison.equivalent,
        "matrix_comparison": asdict(matrix_comparison), "force_roundtrip": forces,
        "eigenvector_comparison_rule": "overlap after explicit label permutation and package-declared phase/degenerate-subspace transform; arbitrary nondegenerate mixing is not harmless",
        "protected_hashes_before": before, "protected_hashes_after": after, "protected_artifacts_unchanged": before == after,
        "accepted_physics_objects_modified": False, "accepted_caches_rebuilt": 0, "trajectories_integrated": 0,
        "molecular_model_interchange_authorized": True, "imported_model_force_authorized": False,
        "cache_rebuild_authorized": False, "trajectory_reintegration_authorized": False,
        "capture_authorized": False, "optimizer_authorized": False, "exact_replication_valid": False,
    }
    result["gate"] = "MOLECULAR_MODEL_INTERCHANGE_READY" if (
        validation.valid and arrays_exact and matrix_comparison.equivalent and forces["passes"] and before == after
    ) else "MOLECULAR_MODEL_INTERCHANGE_REFINEMENT_REQUIRED"
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    ROUNDTRIP.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT.write_text("\n".join([
        f"# {RUN012_LABEL}", "", "Run 012 provides a versioned molecular-model interchange and author handoff layer. It does not change accepted Track P physics or authorize imported models for production force calculations.", "",
        f"## {RUN012_LABEL} Reference export", "", f"Schema: `mgf-mot-molecular-model-v1`. Full package hash: `{loaded.hashes().full_package}`. Complex NPZ arrays, unit/axis metadata, and a canonical hash manifest are stored under `outputs/provisional/molecular_model_packages/run_012/`.", "",
        f"## {RUN012_LABEL} Round trip", "", f"Complex arrays preserved exactly: `{arrays_exact}`. Matrix equivalence: `{matrix_comparison.equivalent}`. Maximum force difference: `{forces['maximum_differences']['force']:.3e}`; population difference: `{forces['maximum_differences']['population']:.3e}`; pumping-total difference: `{forces['maximum_differences']['scattering']:.3e}`.", "",
        f"## {RUN012_LABEL} Boundaries", "", "The exported reference is provisional and explicitly records corrected ground magnetism, effective g'=0.001, the 0.5 MHz interval midpoint (not a measurement), and omission of the full independent Doppelbauer d operator. Imported models remain unauthorized until a later validation and force-benchmark decision. No cache was rebuilt and no trajectory was integrated.", "",
        result["gate"],
    ]) + "\n", encoding="utf-8")
    if before != after: raise RuntimeError("Run 012 modified a protected artifact")
    print(f"{RUN012_LABEL}: {result['gate']}")
    print(f"package hash: {loaded.hashes().full_package}")
    return result


if __name__ == "__main__":
    run()
