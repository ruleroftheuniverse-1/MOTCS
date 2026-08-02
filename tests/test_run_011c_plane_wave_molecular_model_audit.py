from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from mgf_mot.accepted_backend import build_accepted_provisional_rateeq_backend
from mgf_mot.paper_rateeq_reference import evaluate_paper_rate_equations
from mgf_mot.policies import load_policy


REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_"
    "PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY"
)
AUDIT_DIR = REPO_ROOT / "outputs" / "provisional" / "molecular_model_audit" / "run_011c"
METADATA_PATH = AUDIT_DIR / f"{LABEL}_metadata.json"
MATRIX_PATH = AUDIT_DIR / f"{LABEL}_accepted_molecular_matrices.npz"
MATRIX_METADATA_PATH = AUDIT_DIR / f"{LABEL}_accepted_molecular_matrices_metadata.json"
STATE_PATH = AUDIT_DIR / f"{LABEL}_state_resolved_diagnostics.json"
REPORT_PATH = REPO_ROOT / "outputs" / "provisional" / f"{LABEL}.md"
SIGN_CONFIG = REPO_ROOT / "configs" / "rodriguez_figure2_sign_calibration_run_011c.yaml"
REFERENCE_PATH = REPO_ROOT / "src" / "mgf_mot" / "paper_rateeq_reference.py"
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_plane_wave_molecular_model.py"


def _json(path: Path) -> dict:
    assert path.exists(), f"run scripts/audit_plane_wave_molecular_model.py first: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def accepted_backend():
    return build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=True)


def test_figure2_sign_calibration_is_explicit_independent_and_resolved() -> None:
    config = yaml.safe_load(SIGN_CONFIG.read_text(encoding="utf-8"))
    metadata = _json(METADATA_PATH)["figure_2_sign_calibration"]
    assert config["calibration_is_independent_of_run_011b_metadata"] is True
    assert set(config["panels"]) == {"mgf_3", "mgf_3_plus_1"}
    for panel in config["panels"].values():
        assert len(panel["x_anchors_px_data"]) == 3
        assert len(panel["v_anchors_px_data"]) == 3
        assert len(panel["colorbar_anchors_px_force"]) == 3
    assert metadata["status"] == "FIGURE_SIGN_CALIBRATION_VALIDATED"
    assert metadata["colorbar_ordering"] == "top_positive_bottom_negative"
    assert metadata["correction_applied_to_run_011b"] is False
    assert metadata["panels"]["mgf_3"]["median_apparent_dF_dx"] < 0
    assert metadata["panels"]["mgf_3_plus_1"]["median_apparent_dF_dx"] > 0


def test_independent_paper_equations_match_pylcp_for_identical_inputs(accepted_backend) -> None:
    policy = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    optical = accepted_backend.build_optical_system(
        policy.sample(0.0), policy_name=policy.name, beam_mode="plane_wave"
    )
    position = np.array([0.5 * 7.48e-3, 0.0, 0.0])
    velocity = np.zeros(3)
    pylcp_result = accepted_backend.force_at(
        position, velocity, optical, collect_solver_diagnostics=True
    )
    reference = evaluate_paper_rate_equations(
        hamiltonian=accepted_backend.hamiltonian,
        pylcp_beams=optical.pylcp_beams,
        beam_index=optical.pylcp_beam_index,
        position_m=position,
        velocity_gamma_over_k=velocity,
        magnetic_field_gauss=np.asarray(accepted_backend.mag_field.Field(position)),
        svd_eps=accepted_backend.config.svd_eps,
    )
    assert reference.combined_population_solve_count == 1
    assert np.allclose(reference.normalized_force, pylcp_result.normalized_force, atol=1e-13)
    assert np.allclose(reference.equilibrium_populations, pylcp_result.equilibrium_populations, atol=1e-13)
    assert reference.residual_linf < 1e-12
    source = REFERENCE_PATH.read_text(encoding="utf-8")
    assert "pylcp.rateeq(" not in source
    assert ".force_at(" not in source


def test_exported_matrices_units_sum_rules_and_basis_metadata() -> None:
    metadata = _json(MATRIX_METADATA_PATH)
    arrays = np.load(MATRIX_PATH)
    assert arrays["ground_h0_gamma"].shape == (12, 12)
    assert arrays["excited_h0_gamma"].shape == (4, 4)
    assert arrays["dipole_q"].shape == (3, 12, 4)
    assert arrays["spontaneous_branching"].shape == (12, 4)
    assert np.allclose(np.sum(arrays["spontaneous_branching"], axis=0), 1.0)
    assert np.iscomplexobj(arrays["dipole_q"])
    assert len(metadata["ground_basis"]) == 12
    assert len(metadata["excited_basis"]) == 4
    assert set(metadata["ground_weak_field_slopes"]) == {"x", "y", "z"}
    checks = metadata["identities_and_sum_rules"]
    assert checks["dipole_shape"] == [3, 12, 4]
    assert checks["incompatible_basis_object_found"] is False
    assert checks["basis_rephasing_strength_max_error"] < 1e-12
    assert checks["ground_transform_unitarity_max_error"] < 1e-12
    assert "Gamma/G" in metadata["units"]["ground_magnetic_moment_gamma_per_gauss"]


def test_transition_state_and_component4_ledgers_are_combined_and_explicit() -> None:
    metadata = _json(METADATA_PATH)
    state = _json(STATE_PATH)
    ledger = metadata["transition_ledger"]
    assert ledger["row_count"] > 0
    assert set(ledger["summaries"]["ground_level"]) == {"lower_F1", "F0", "upper_F1", "F2"}
    assert set(ledger["summaries"]["excited_level"]) == {"Fprime0", "Fprime1"}
    assert set(ledger["summaries"]["q"]) == {"-1", "0", "1"}
    assert all(record["one_shared_population_solution"] for record in state["records"])
    component4 = metadata["component_4_diagnosis"]
    assert set(component4["variants"]) == {
        "three", "three_plus_one", "three_plus_one_component4_disabled", "component4_alone"
    }
    assert component4["accepted_level_specific_result"]["paper_hierarchy_reproduced"] is False
    for row in component4["variants"]["three_plus_one"]["rows"]:
        assert set(row["component4_force_by_ground_level"]) >= {"upper_F1", "F2"}
        assert row["one_shared_equilibrium_population_solution"] is True
    assert component4["population_redistribution"]


def test_official_history_missing_d_boundary_gate_and_protected_hashes() -> None:
    metadata = _json(METADATA_PATH)
    history = metadata["pylcp_version_history"]
    assert history["official_repository"] == "https://github.com/JQIamo/pylcp"
    assert history["v1_0_2_commit"] == "a7cb104f38fa98840ec198d13ec20c432e8ee3ff"
    assert all(history["installed_core_files_equal_official_v1_0_2"].values())
    assert history["exact_paper_checkout_published"] is False
    assert metadata["splitting_vs_eigenvector_physics"]["independent_d_operator_implemented_in_run_011c"] is False
    assert metadata["missing_d_operator_invented"] is False
    assert metadata["gate"] == "MOLECULAR_MODEL_DISCREPANCY_NARROWED"
    assert metadata["protected_artifacts_unchanged"] is True
    assert metadata["protected_hashes_before"] == metadata["protected_hashes_after"]
    assert metadata["accepted_physics_objects_modified"] is False
    assert metadata["accepted_caches_rebuilt"] == 0
    assert metadata["trajectories_integrated"] == 0
    assert metadata["capture_authorized"] is False
    assert metadata["capture_velocity_authorized"] is False
    assert metadata["optimizer_authorized"] is False
    assert metadata["exact_replication_valid"] is False


def test_every_output_is_stamped_and_no_forbidden_execution_path_exists() -> None:
    stamps = (
        "PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "RUN_011C",
        "PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY",
    )
    paths = list(AUDIT_DIR.iterdir()) + [REPORT_PATH]
    assert paths and all(all(stamp in path.name for stamp in stamps) for path in paths)
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(LABEL in line for line in report.splitlines() if line.startswith("#"))
    assert "MOLECULAR_MODEL_DISCREPANCY_NARROWED" in report
    source = AUDIT_SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "integrate_accepted_force_field_trajectory(", "save_force_field_cache(",
        "build_force_field(", "capture_velocity(", "threshold_search(", "optimizer(",
    ):
        assert forbidden not in source
