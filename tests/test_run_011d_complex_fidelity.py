from __future__ import annotations

import json
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_"
    "COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY"
)
AUDIT_DIR = REPO_ROOT / "outputs" / "provisional" / "molecular_model_audit" / "run_011d"
REPORT_PATH = REPO_ROOT / "outputs" / "provisional" / f"{LABEL}.md"
METADATA_PATH = AUDIT_DIR / f"{LABEL}_metadata.json"
WARNING_PATH = AUDIT_DIR / f"{LABEL}_warning_trace_and_cast_ledger.json"
DTYPE_PATH = AUDIT_DIR / f"{LABEL}_dtype_and_imaginary_content_ledger.json"
COMPARISON_PATH = AUDIT_DIR / f"{LABEL}_three_path_comparison.json"
REPHASING_PATH = AUDIT_DIR / f"{LABEL}_basis_rephasing_and_polarization_audit.json"
REFERENCE_PATH = REPO_ROOT / "src" / "mgf_mot" / "complex_fidelity_reference.py"
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_complex_number_fidelity.py"


def _json(path: Path) -> dict:
    assert path.exists(), f"run scripts/audit_complex_number_fidelity.py first: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_warning_is_localized_and_discarded_imaginary_content_is_quantified() -> None:
    ledger = _json(WARNING_PATH)
    trace = ledger["minimal_exception_capture"]
    assert trace["origin"] == "pylcp"
    assert trace["source_line"] == 264
    assert trace["function"] == "pylcp.rateeq._calc_pumping_rates"
    assert "ComplexWarning" in trace["full_traceback"]
    assert ledger["warning_disposition"] == "WARNING_IS_NUMERICAL_ROUNDOFF"
    assert ledger["maximum_discarded_absolute_imaginary"] == 0.0
    assert ledger["warning_globally_suppressed"] is False
    for case in ledger["cases"].values():
        assert case["warning_count"] == case["active_laser_count"]
        assert case["pre_cast_arrays"]
        for row in case["pre_cast_arrays"]:
            assert row["shape"] == [12, 4]
            assert row["source_dtype"] == "complex128"
            assert row["destination_dtype"] == "float64"
            assert row["maximum_absolute_imaginary"] == 0.0
            assert row["rms_imaginary"] == 0.0
            assert np.isfinite(row["max_imaginary_over_max_real"])


def test_complex_reference_retains_amplitudes_and_final_observables_are_real() -> None:
    dtype = _json(DTYPE_PATH)
    stages = {row["stage"]: row for row in dtype["stages"]}
    assert stages["laser_coupling_amplitudes"]["dtype"] == "complex128"
    assert stages["laser_coupling_amplitudes"]["maximum_absolute_imaginary"] > 0.1
    assert stages["pumping_matrices"]["dtype"] == "float64"
    assert stages["normalized_force"]["maximum_absolute_imaginary"] == 0.0
    comparison = _json(COMPARISON_PATH)
    assert comparison["all_final_complex_observables_real_within_tolerance"] is True
    maximum = comparison["maximum_differences"]
    assert maximum["accepted_vs_complex_force_max"] < 1e-12
    assert maximum["accepted_vs_complex_per_laser_scattering_max"] < 1e-12
    assert maximum["accepted_vs_complex_population_group_max"] < 2e-12
    assert maximum["accepted_vs_complex_total_scattering"] < 1e-12


def test_rephasing_conjugate_transpose_and_complex_polarization_pass() -> None:
    phase = _json(REPHASING_PATH)
    rephasing = phase["basis_rephasing"]
    assert rephasing["all_invariant_within_1e_12"] is True
    assert {row["phase_set"] for row in rephasing["phase_sets"]} == {
        "signs_only", "plus_minus_i", "deterministic_pseudorandom"
    }
    polarization = phase["spherical_polarization"]
    assert polarization["complex_circular_polarization_preserved_until_coherent_sum"] is True
    assert len(polarization["beams"]) == 6
    assert all(abs(row["normalization"] - 1.0) < 1e-12 for row in polarization["beams"])
    assert all(row["transversality_abs_k_dot_epsilon"] < 1e-12 for row in polarization["beams"])
    dtype = _json(DTYPE_PATH)
    assert dtype["eigenvector_and_dipole_transform_audit"]["complex_reference_uses_conjugate_transpose"] is True
    source = REFERENCE_PATH.read_text(encoding="utf-8")
    assert ".conj().T @ item @" in source
    assert "abs(amplitudes[index]) ** 2" in source


def test_component4_dark_state_gate_and_protected_artifacts_are_unchanged() -> None:
    metadata = _json(METADATA_PATH)
    assert metadata["gate"] == "COMPLEX_FIDELITY_RULED_OUT"
    assert metadata["component_4_fidelity"]["paper_hierarchy_reproduced"] is False
    assert metadata["component_4_fidelity"]["complex_preservation_changes_run011c_conclusion"] is False
    assert metadata["dark_state_fidelity"]["premature_real_cast_strengthens_dark_states_or_cancellation"] is False
    assert metadata["protected_artifacts_unchanged"] is True
    assert metadata["protected_hashes_before"] == metadata["protected_hashes_after"]
    assert metadata["accepted_physics_objects_modified"] is False
    assert metadata["pylcp_source_modified"] is False
    assert metadata["accepted_caches_rebuilt"] == 0
    assert metadata["trajectories_integrated"] == 0
    assert metadata["capture_authorized"] is False
    assert metadata["capture_velocity_authorized"] is False
    assert metadata["optimizer_authorized"] is False
    assert metadata["exact_replication_valid"] is False


def test_outputs_are_stamped_and_no_forbidden_or_global_suppression_path_exists() -> None:
    stamps = (
        "PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "RUN_011D",
        "COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY",
    )
    paths = list(AUDIT_DIR.iterdir()) + [REPORT_PATH]
    assert paths and all(all(stamp in path.name for stamp in stamps) for path in paths)
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(LABEL in line for line in report.splitlines() if line.startswith("#"))
    assert "WARNING_IS_NUMERICAL_ROUNDOFF" in report
    assert "COMPLEX_FIDELITY_RULED_OUT" in report
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'filterwarnings("ignore"' not in source
    assert "simplefilter(\"ignore\"" not in source
    for forbidden in (
        "integrate_accepted_force_field_trajectory(", "save_force_field_cache(",
        "build_force_field(", "capture_velocity(", "threshold_search(", "optimizer(",
    ):
        assert forbidden not in source
