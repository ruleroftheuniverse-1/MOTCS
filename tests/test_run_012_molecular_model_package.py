from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.molecular_model_package import (
    ImportGate, MolecularModelPackage, MolecularModelPackageError, RUN012_LABEL,
    compare_packages, load_package, package_hashes, validate_package,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "outputs/provisional/molecular_model_packages/run_012"
BASE = PACKAGE_DIR / f"{RUN012_LABEL}_ACCEPTED_PROVISIONAL_REFERENCE_PACKAGE"
ROUNDTRIP = PACKAGE_DIR / f"{RUN012_LABEL}_roundtrip_validation.json"
VALIDATION = PACKAGE_DIR / f"{RUN012_LABEL}_import_validation.json"
COMPARISON = PACKAGE_DIR / f"{RUN012_LABEL}_model_difference_report.json"
BENCHMARK = PACKAGE_DIR / f"{RUN012_LABEL}_paper_benchmark.json"
REPORT = ROOT / "outputs/provisional" / f"{RUN012_LABEL}.md"
TEMPLATE = ROOT / "examples/molecular_model_package_template" / f"{RUN012_LABEL}_template_metadata.json"


@pytest.fixture(scope="module")
def package() -> MolecularModelPackage:
    return load_package(BASE)


def _transform(package: MolecularModelPackage, ug: np.ndarray, ue: np.ndarray) -> MolecularModelPackage:
    a = {key: np.asarray(value).copy() for key, value in package.arrays.items()}
    a["H0_g"] = ug.conj().T @ a["H0_g"] @ ug
    a["mu_q_g"] = np.asarray([ug.conj().T @ q @ ug for q in a["mu_q_g"]])
    a["H0_e"] = ue.conj().T @ a["H0_e"] @ ue
    a["mu_q_e"] = np.asarray([ue.conj().T @ q @ ue for q in a["mu_q_e"]])
    a["d_q"] = np.asarray([ug.conj().T @ q @ ue for q in a["d_q"]])
    strength = np.sum(abs(a["d_q"]) ** 2, axis=0); a["branching"] = strength / np.sum(strength, axis=0, keepdims=True)
    a["ground_eigenvectors"] = ug.conj().T @ a["ground_eigenvectors"]
    a["excited_eigenvectors"] = ue.conj().T @ a["excited_eigenvectors"]
    a["construction_to_working_g"] = a["construction_to_working_g"] @ ug
    a["construction_to_working_e"] = a["construction_to_working_e"] @ ue
    a["working_to_canonical_g"] = ug
    a["working_to_canonical_e"] = ue
    return MolecularModelPackage(a, deepcopy(package.metadata))


def _permuted(package: MolecularModelPackage, pg: np.ndarray, pe: np.ndarray) -> MolecularModelPackage:
    a = {key: np.asarray(value).copy() for key, value in package.arrays.items()}; m = deepcopy(package.metadata)
    a["H0_g"] = a["H0_g"][np.ix_(pg, pg)]; a["mu_q_g"] = a["mu_q_g"][:, pg][:, :, pg]
    a["H0_e"] = a["H0_e"][np.ix_(pe, pe)]; a["mu_q_e"] = a["mu_q_e"][:, pe][:, :, pe]
    a["d_q"] = a["d_q"][:, pg][:, :, pe]; a["branching"] = a["branching"][np.ix_(pg, pe)]
    a["ground_eigenvectors"] = a["ground_eigenvectors"][pg]; a["excited_eigenvectors"] = a["excited_eigenvectors"][pe]
    a["construction_to_working_g"] = a["construction_to_working_g"][:, pg]
    a["construction_to_working_e"] = a["construction_to_working_e"][:, pe]
    cg = np.zeros((12, 12), complex); ce = np.zeros((4, 4), complex)
    for new, old in enumerate(pg): cg[old, new] = 1
    for new, old in enumerate(pe): ce[old, new] = 1
    a["working_to_canonical_g"], a["working_to_canonical_e"] = cg, ce
    for manifold, permutation in (("ground", pg), ("excited", pe)):
        old = m["basis"][manifold]; m["basis"][manifold] = [{**old[int(source)], "index": index} for index, source in enumerate(permutation)]
    return MolecularModelPackage(a, m)


def test_complex_arrays_roundtrip_exactly_and_hashes_are_deterministic(package) -> None:
    with np.load(f"{BASE}.npz", allow_pickle=False) as archive:
        assert np.iscomplexobj(archive["H0_g"])
        assert np.iscomplexobj(archive["mu_q_g"])
        assert np.iscomplexobj(archive["d_q"])
        assert all(np.array_equal(archive[name], package.arrays[name]) for name in archive.files)
    assert package_hashes(package.arrays, package.metadata) == package_hashes(dict(reversed(list(package.arrays.items()))), deepcopy(package.metadata))
    manifest = json.loads(Path(f"{BASE}.manifest.json").read_text(encoding="utf-8"))
    assert manifest["hashes"]["full_package"] == package.hashes().full_package


def test_units_axes_and_missing_fields_fail_without_defaults(package) -> None:
    metadata = deepcopy(package.metadata); del metadata["array_specs"]["d_q"]["units"]
    report = validate_package(MolecularModelPackage(package.arrays, metadata), include_equilibrium=False)
    assert report.gate is ImportGate.IMPORT_INVALID
    assert any("units and axis meanings" in item for item in report.errors)
    arrays = dict(package.arrays); del arrays["mu_q_e"]
    report = validate_package(MolecularModelPackage(arrays, package.metadata), include_equilibrium=False)
    assert report.gate is ImportGate.IMPORT_INVALID
    assert any("defaults are forbidden" in item for item in report.errors)
    with pytest.raises(MolecularModelPackageError, match="missing"):
        load_package(ROOT / "does_not_exist")


def test_basis_permutation_phase_and_degenerate_rotation_are_recognized(package) -> None:
    pg = np.array([3, 0, 1, 2, 7, 8, 9, 10, 11, 4, 5, 6]); pe = np.array([1, 2, 3, 0])
    permutation = compare_packages(package, _permuted(package, pg, pe))
    assert permutation.equivalent
    assert "basis_permutation" in permutation.difference_classes
    phases_g = np.exp(1j * np.linspace(0.0, 1.7, 12)); phases_e = np.exp(1j * np.linspace(0.2, 1.1, 4))
    phase = compare_packages(package, _transform(package, np.diag(phases_g), np.diag(phases_e)))
    assert phase.equivalent
    rng = np.random.default_rng(12)
    ug, ue = np.eye(12, dtype=complex), np.eye(4, dtype=complex)
    for indices in ([0, 1, 2], [4, 5, 6], [7, 8, 9, 10, 11]):
        q, _ = np.linalg.qr(rng.normal(size=(len(indices), len(indices))) + 1j*rng.normal(size=(len(indices), len(indices))))
        ug[np.ix_(indices, indices)] = q
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)) + 1j*rng.normal(size=(3, 3))); ue[1:, 1:] = q
    degenerate = compare_packages(package, _transform(package, ug, ue))
    assert degenerate.equivalent
    assert max(degenerate.aligned_differences.values()) < 1e-10


def test_nondegenerate_mixing_and_real_matrix_change_are_not_equivalent(package) -> None:
    theta = 0.2; ug = np.eye(12, dtype=complex); ug[0, 0] = ug[3, 3] = np.cos(theta); ug[0, 3] = np.sin(theta); ug[3, 0] = -np.sin(theta)
    mixed = _transform(package, ug, np.eye(4))
    validation = validate_package(mixed, include_equilibrium=False)
    assert validation.gate is ImportGate.IMPORT_VALID_WITH_WARNINGS
    assert any("nondegenerate mixing" in item for item in validation.warnings)
    assert not compare_packages(package, mixed).equivalent
    arrays = {key: np.asarray(value).copy() for key, value in package.arrays.items()}; arrays["d_q"][0, 0, 0] += 1e-3
    strength = np.sum(abs(arrays["d_q"])**2, axis=0); arrays["branching"] = strength / np.sum(strength, axis=0, keepdims=True)
    altered = compare_packages(package, MolecularModelPackage(arrays, deepcopy(package.metadata)))
    assert not altered.equivalent
    assert "dipole_amplitudes_or_eigenvectors" in altered.difference_classes


def test_reference_roundtrip_validation_comparison_and_benchmark_outputs() -> None:
    roundtrip = json.loads(ROUNDTRIP.read_text(encoding="utf-8")); validation = json.loads(VALIDATION.read_text(encoding="utf-8")); comparison = json.loads(COMPARISON.read_text(encoding="utf-8")); benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    assert roundtrip["gate"] == "MOLECULAR_MODEL_INTERCHANGE_READY"
    assert roundtrip["complex_arrays_preserved_exactly"] is True
    assert roundtrip["force_roundtrip"]["passes"] is True
    assert roundtrip["protected_artifacts_unchanged"] is True
    assert validation["gate"] == "IMPORT_VALID"
    assert comparison["equivalent"] is True
    assert benchmark["package_hash"] == roundtrip["package_hashes"]["full_package"]
    assert set(benchmark["figure_2"]) == {"mgf_3", "mgf_3_plus_1"}
    assert set(benchmark["selected_figure_3_detunings"]) == {"-2.0", "-4.0", "-6.0", "-8.0"}
    assert benchmark["cache_rebuild_authorized"] is False
    assert benchmark["trajectory_reintegration_authorized"] is False


def test_labels_authorization_template_and_forbidden_paths() -> None:
    metadata = json.loads(Path(f"{BASE}.metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "provisional" and metadata["replication_valid"] is False
    assert metadata["approximations"]["effective_excited_g_prime"] == 0.001
    assert metadata["approximations"]["effective_Fprime_splitting_MHz"] == 0.5
    assert "not a measurement" in metadata["approximations"]["effective_Fprime_splitting_status"]
    assert metadata["approximations"]["full_independent_d_operator_included"] is False
    assert metadata["authorization"]["imported_model_force_authorized"] is False
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert template["synthetic_template_only"] is True
    assert template["contains_physical_matrix_values"] is False
    assert "expected_arrays_not_supplied" in template
    paths = list(PACKAGE_DIR.iterdir()) + [REPORT]
    assert all(all(stamp in path.name for stamp in ("PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "RUN_012", "MOLECULAR_MODEL_INTERCHANGE_AND_AUTHOR_HANDOFF_ONLY")) for path in paths)
    source = "\n".join((ROOT / "scripts" / name).read_text(encoding="utf-8") for name in ("export_accepted_molecular_model.py", "validate_molecular_model_package.py", "compare_molecular_model_packages.py", "benchmark_imported_molecular_model.py"))
    for forbidden in ("save_force_field_cache(", "integrate_accepted_force_field_trajectory(", "capture_velocity(", "optimizer(", "send_email("):
        assert forbidden not in source
