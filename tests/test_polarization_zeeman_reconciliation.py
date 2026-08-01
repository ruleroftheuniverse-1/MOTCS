from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.conventions import (
    GroundZeemanConvention,
    PaperHelicityTranslation,
    paper_helicity_to_pylcp_pol,
    translate_xstate_ground_muq_for_pylcp,
)
from mgf_mot.policies import load_policy
from mgf_mot.rateeq_backend import RateEquationBackendConfig


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_provisional_polarization_zeeman_reconciliation.py"
spec = importlib.util.spec_from_file_location("run009b", SCRIPT_PATH)
run009b = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(run009b)


def test_source_yaml_paper_labels_remain_frozen() -> None:
    expected = ("sigma_plus", "sigma_minus", "sigma_minus", "sigma_plus")
    for filename in ("rodriguez_static_3.yaml", "rodriguez_static_3_plus_1.yaml"):
        policy = load_policy(REPO_ROOT / "configs" / filename)
        assert tuple(component.polarization for component in policy.components) == expected


def test_paper_labels_and_pylcp_helicity_are_separate_centralized_concepts() -> None:
    assert paper_helicity_to_pylcp_pol("sigma_plus") == 1
    assert paper_helicity_to_pylcp_pol("sigma_minus") == -1
    assert paper_helicity_to_pylcp_pol(
        "sigma_plus",
        translation=PaperHelicityTranslation.GLOBAL_INVERSION_DIAGNOSTIC,
    ) == -1
    with pytest.raises(ValueError, match="explicit"):
        paper_helicity_to_pylcp_pol("working_sign")
    assert (
        RateEquationBackendConfig.__dataclass_fields__["ground_zeeman_convention"].default
        is GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
    )


def test_ground_zeeman_translation_is_one_named_tensor_boundary() -> None:
    raw = np.arange(12, dtype=float).reshape(3, 2, 2).astype(complex)
    unchanged = translate_xstate_ground_muq_for_pylcp(
        raw, convention=GroundZeemanConvention.RAW_XFMOLECULES
    )
    corrected = translate_xstate_ground_muq_for_pylcp(
        raw, convention=GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
    )
    assert unchanged == pytest.approx(raw)
    assert corrected == pytest.approx(-raw)
    assert np.array_equal(raw, np.arange(12).reshape(3, 2, 2))


@pytest.fixture(scope="module")
def reconciliation(tmp_path_factory):
    return run009b.run(tmp_path_factory.mktemp("run009b"))


def test_actual_polarizations_are_normalized_transverse_and_partnered(reconciliation) -> None:
    audit = reconciliation["metadata"]["polarization_audit"]
    assert audit["all_vectors_normalized"] is True
    assert audit["all_vectors_transverse"] is True
    assert audit["rotated_frame_handedness_consistent"] is True
    assert audit["equal_scalar_pol_on_opposite_k_reverses_fixed_axis_q"] is True
    assert len(audit["records"]) == 12
    assert len(audit["counterpropagating_relations"]) == 6
    for record in audit["records"].values():
        assert set(record["spherical_relative_to_lab_axes"]) == {
            "lab_x",
            "lab_y",
            "lab_z",
        }


def test_dipole_q_order_and_selection_rules_are_verified(reconciliation) -> None:
    audit = reconciliation["metadata"]["dipole_audit"]
    assert audit["tensor_shape"] == [3, 12, 4]
    assert audit["tensor_first_axis_order"] == [-1, 0, 1]
    assert audit["nonzero_forbidden_transition_count"] == 0
    assert len(audit["selected_allowed_transitions"]) == 3
    assert audit["q_index_reversal_candidate_justified"] is False
    assert audit["passed"] is True


def test_zeeman_slopes_identify_and_correct_global_ground_sign(reconciliation) -> None:
    audit = reconciliation["metadata"]["zeeman_audit"]
    assert audit["field_samples_gauss"] == [-1e-4, 0.0, 1e-4]
    assert audit["raw_ground_signs_globally_reversed"] is True
    assert audit["corrected_ground_signs_match"] is True
    assert audit["mapping_d_justified"] is True
    assert audit["excited_treatment_matches_rodriguez_magnitude"] is False
    assert audit["excited_provisional_effective_g_magnitude"] == pytest.approx(0.3337199)
    for record in audit["corrected_ground_manifolds"]:
        assert "sublevels" in record
        assert all("dE_dBx_mhz_per_gauss" in row for row in record["sublevels"])


def test_only_causally_justified_mapping_is_accepted(reconciliation) -> None:
    metadata = reconciliation["metadata"]
    candidates = metadata["candidate_mappings"]
    assert candidates["mapping_b_global_helicity_inversion_diagnostic"]["force_behavior_passed"] is True
    gate = metadata["mapping_change_gate"]
    assert gate["passed"] is True
    assert gate["accepted_mapping"] == "project_energy_slope_corrected"
    assert metadata["result"] == "CONVENTION_ERROR_IDENTIFIED"
    assert metadata["resonance_direction_audit"][
        "corrected_mapping_closer_group_matches_expected_for_all_representatives"
    ] is True
    assert metadata["chirp_direction_audit"]["passed"] is True


def test_run009b_outputs_labeled_and_keeps_tracks_blocked(reconciliation) -> None:
    for key in ("metadata_path", "report_path"):
        assert run009b.RUN009B_LABEL in reconciliation[key].name
    metadata = reconciliation["metadata"]
    assert metadata["replication_valid"] is False
    assert metadata["exact_track_blocked"] is True
    assert metadata["trajectory_integrations_performed"] == 0
    assert metadata["capture_results_calculated"] == 0
    assert metadata["trajectories_authorized"] is False
    report = reconciliation["report_path"].read_text(encoding="utf-8")
    assert all(
        run009b.RUN009B_LABEL in line
        for line in report.splitlines()
        if line.startswith("#")
    )
    assert "CONVENTION_ERROR_IDENTIFIED" in report
    assert "Trajectories remain unauthorized" in report


def test_run009b_source_invokes_no_motion_or_capture_path() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden_call in (
        "integrate_policy_trajectory(",
        "run_trajectory_ensemble(",
        "solve_ivp(",
        "evolve_motion(",
        "evolve_populations(",
    ):
        assert forbidden_call not in source
