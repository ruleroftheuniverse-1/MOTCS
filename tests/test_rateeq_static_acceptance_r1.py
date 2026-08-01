from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.conventions import GroundZeemanConvention
from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.rateeq_backend import (
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_provisional_rateeq_static_acceptance_audit_r1.py"
SPEC = importlib.util.spec_from_file_location("run009a_r1", SCRIPT)
run009a_r1 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run009a_r1)

OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
METADATA_PATH = OUTPUT_DIR / f"{run009a_r1.R1_LABEL}_metadata.json"
ARRAYS_PATH = OUTPUT_DIR / f"{run009a_r1.R1_LABEL}_corrected_static_arrays.npz"
REPORT_PATH = OUTPUT_DIR / f"{run009a_r1.R1_LABEL}.md"


@pytest.fixture(scope="module")
def result():
    assert METADATA_PATH.exists(), "run the dedicated Run 009A-R1 script first"
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def test_r1_preserves_history_and_generates_new_corrected_surfaces(result) -> None:
    chain = result["provenance_chain"]
    assert chain["historical_artifacts_unchanged"] is True
    assert chain["historical_hashes_before"] == chain["historical_hashes_after"]
    assert chain["source_yaml_unchanged"] is True
    assert chain["source_yaml_hashes_before"] == chain["source_yaml_hashes_after"]
    assert result["corrected_surfaces_newly_generated"] is True
    assert result["reused_pre_correction_force_arrays"] is False
    corrected = np.load(ARRAYS_PATH)
    historical = np.load(run009a_r1.HISTORICAL_PATHS[0])
    assert not np.allclose(
        corrected["force_plane_wave_3"], historical["force_plane_wave_3"]
    )


def test_r1_ground_correction_is_exactly_once_at_boundary(result) -> None:
    provenance = result["convention_provenance"]
    assert provenance["ground_magnetic_moment_correction_applied"] is True
    assert provenance["ground_magnetic_moment_correction_count"] == 1
    assert provenance["ground_magnetic_moment_correction_location"] == "Hamiltonian boundary"
    assert provenance["downstream_zeeman_sign_correction_count"] == 0
    assert provenance["source_yaml_unchanged"] is True
    assert provenance["polarization_mapping_unchanged"] is True
    assert provenance["field_convention_unchanged"] is True
    raw = ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            ground_zeeman_convention=GroundZeemanConvention.RAW_XFMOLECULES,
        )
    )
    with pytest.raises(RuntimeError, match="zero ground correction"):
        run009a_r1._require_single_boundary_correction(raw)


def test_r1_local_slopes_reversal_and_component_four_pass(result) -> None:
    local = result["local_slope_audit"]["cases"]
    assert local["plane_wave_3"]["dFdx_normalized_per_m"] < 0
    assert local["plane_wave_3"]["dFdv_normalized_per_m_s"] < 0
    assert (
        local["plane_wave_3_plus_1"]["dFdx_normalized_per_m"]
        < local["plane_wave_3"]["dFdx_normalized_per_m"]
    )
    reversal = result["reversal_audit"]["cases"]
    assert reversal["nominal"]["dFdx_normalized_per_m"] < 0
    assert reversal["polarization_flipped"]["dFdx_normalized_per_m"] > 0
    assert reversal["gradient_flipped"]["dFdx_normalized_per_m"] > 0
    assert reversal["both_flipped"]["dFdx_normalized_per_m"] < 0
    assert result["component_4_audit"]["passed"] is True


def test_r1_population_chirp_gaussian_and_refinement_are_audited(result) -> None:
    health = result["solver_health"]
    assert health["number_of_solves"] == 7 * 17 * 17
    assert health["nonfinite_count"] == 0
    assert health["fallback_count"] == 0
    assert health["nullspace_dimensions_observed"] == [1]
    assert health["passed"] is True
    assert result["chirp_feature_audit"]["passed"] is True
    assert result["gaussian_audit"]["passed"] is True
    assert result["grid_convergence"]["topology_preserved"] is True
    assert result["force_scale_audit"]["passed"] is True


def test_r1_gate_and_mandatory_motion_locks(result) -> None:
    assert result["gate"] == "PROVISIONAL_STATIC_GO"
    assert result["trajectory_authorized"] is False
    assert result["capture_authorized"] is False
    assert result["exact_replication_valid"] is False
    assert result["trajectory_integrations_performed"] == 0
    assert result["capture_results_calculated"] == 0
    reason = result["authorization_lock_reason"]
    assert reason["excited_state_magnetic_tensor_unresolved"] is True
    assert reason["provisional_effective_excited_g"] == pytest.approx(0.3337199)
    assert reason["rodriguez_representative_excited_g"] == pytest.approx(0.001)


def test_r1_outputs_are_fully_labeled_and_static_only(result) -> None:
    assert all(
        run009a_r1.R1_LABEL in path.name
        for path in (ARRAYS_PATH, METADATA_PATH, REPORT_PATH)
    )
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(
        run009a_r1.R1_LABEL in line
        for line in report.splitlines()
        if line.startswith("#")
    )
    assert "PROVISIONAL_STATIC_GO" in report
    assert "trajectory_authorized = false" in report
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden_call in (
        "integrate_policy_trajectory(",
        "run_trajectory_ensemble(",
        "solve_ivp(",
        "evolve_motion(",
        "evolve_populations(",
    ):
        assert forbidden_call not in source

