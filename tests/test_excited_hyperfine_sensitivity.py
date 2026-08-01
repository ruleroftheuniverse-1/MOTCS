from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.excited_hyperfine import (
    ExcitedHyperfineModel,
    ExcitedHyperfineModelError,
    SourceAlignedSplittingCase,
    build_excited_f_projectors,
    build_excited_hyperfine_operator,
    validate_excited_f_projectors,
    validate_excited_hyperfine_operator,
)
from mgf_mot.excited_zeeman import ExcitedZeemanModel
from mgf_mot.spectroscopy import EXCITED_HYPERFINE_D_MHZ


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_provisional_excited_hyperfine_sensitivity.py"
SPEC = importlib.util.spec_from_file_location("run009d", SCRIPT)
run009d = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run009d)
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
METADATA_PATH = OUTPUT_DIR / f"{run009d.RUN009D_LABEL}_run_009D_metadata.json"
REPORT_PATH = OUTPUT_DIR / f"{run009d.RUN009D_LABEL}_run_009D.md"


@pytest.fixture(scope="module")
def collapsed_backend():
    return run009d._backend(ExcitedHyperfineModel.PYLCP_COLLAPSED_ASTATE, None)


@pytest.fixture(scope="module")
def metadata():
    assert METADATA_PATH.exists(), "run the dedicated Run 009D script first"
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def test_fprime_projectors_are_complete_orthogonal_projectors(collapsed_backend) -> None:
    basis = collapsed_backend.source_backend.validation_model.excited_basis
    projectors = build_excited_f_projectors(basis)
    validation = validate_excited_f_projectors(projectors)
    assert validation["hermitian"] is True
    assert validation["idempotent"] is True
    assert validation["orthogonal"] is True
    assert validation["complete"] is True
    assert validation["dimensions"] == [1, 3]
    assert validation["basis_order"] == [[0, 0], [1, -1], [1, 0], [1, 1]]


def test_named_candidate_hamiltonians_are_hermitian_and_preserve_cog(collapsed_backend) -> None:
    basis = collapsed_backend.source_backend.validation_model.excited_basis
    raw = collapsed_backend.source_backend.hamiltonian.blocks[1, 1][0].matrix
    operators = [
        build_excited_hyperfine_operator(
            ExcitedHyperfineModel.PYLCP_COLLAPSED_ASTATE,
            basis=basis,
            pylcp_collapsed_h0_mhz=raw,
        ),
        build_excited_hyperfine_operator(
            ExcitedHyperfineModel.NO_EXCITED_HYPERFINE_SPLITTING,
            basis=basis,
            pylcp_collapsed_h0_mhz=raw,
        ),
        build_excited_hyperfine_operator(
            ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING,
            basis=basis,
            pylcp_collapsed_h0_mhz=raw,
            splitting_case=SourceAlignedSplittingCase.MID_RANGE_0P5_MHZ,
        ),
    ]
    assert all(validate_excited_hyperfine_operator(op)["hermitian"] for op in operators)
    assert all(op.center_of_gravity_mhz == pytest.approx(operators[0].center_of_gravity_mhz) for op in operators)
    assert operators[1].engineering_stress_test is True
    assert operators[1].source_supported_family is False
    assert operators[2].source_supported_family is True
    assert operators[2].splitting_mhz == 0.5
    assert operators[2].changes_eigenvectors is False
    assert operators[2].modifies_transition_strengths is False


def test_full_d_operator_is_not_invented_and_arbitrary_float_is_not_exposed(collapsed_backend) -> None:
    basis = collapsed_backend.source_backend.validation_model.excited_basis
    raw = collapsed_backend.source_backend.hamiltonian.blocks[1, 1][0].matrix
    assert EXCITED_HYPERFINE_D_MHZ.require() == 135.0
    with pytest.raises(ExcitedHyperfineModelError, match="unavailable"):
        build_excited_hyperfine_operator(
            ExcitedHyperfineModel.FULL_DOPPELBAUER_D_OPERATOR,
            basis=basis,
            pylcp_collapsed_h0_mhz=raw,
        )
    with pytest.raises(ExcitedHyperfineModelError, match="requires an explicit"):
        build_excited_hyperfine_operator(
            ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING,
            basis=basis,
            pylcp_collapsed_h0_mhz=raw,
        )
    assert "splitting_mhz" not in build_excited_hyperfine_operator.__annotations__


def test_run009d_freezes_zeeman_and_all_non_hyperfine_inputs(metadata) -> None:
    candidates = metadata["candidate_models"]
    fingerprints = [json.dumps(row["non_hyperfine_input_fingerprint"], sort_keys=True) for row in candidates.values()]
    assert len(set(fingerprints)) == 1
    for row in candidates.values():
        status = row["backend_status"]
        assert status["ground_zeeman_convention"] == "project_energy_slope_corrected"
        assert status["ground_magnetic_moment_correction_count"] == 1
        assert status["excited_zeeman_model"] == ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001.value
        assert status["excited_zeeman_model_application_count"] == 1
        assert status["excited_hyperfine_model_application_count"] == 1


def test_static_suite_is_finite_healthy_and_source_models_are_distinguished(metadata) -> None:
    candidates = metadata["candidate_models"]
    assert set(candidates) == {
        "pylcp_collapsed", "zero_splitting_stress", "source_mid_range_0p5_mhz",
        "source_upper_boundary_stress_1_mhz",
    }
    assert candidates["zero_splitting_stress"]["hyperfine_operator"]["engineering_stress_test"] is True
    assert candidates["source_mid_range_0p5_mhz"]["hyperfine_operator"]["source_supported_family"] is True
    for row in candidates.values():
        health = row["population_health"]
        assert health["number_of_solves"] == 7 * 17 * 17
        assert health["passed"] is True
        assert health["nonfinite_count"] == 0


def test_gate_provenance_and_output_quarantine(metadata) -> None:
    assert metadata["gate"] in {
        "PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO", "STATIC_ONLY_CONTINUE",
        "D_TERM_BLOCKER_REMAINS", "EXCITED_HYPERFINE_NO_GO",
    }
    assert metadata["provisional_static_authorized"] is True
    assert metadata["capture_authorized"] is False
    assert metadata["exact_replication_valid"] is False
    assert metadata["exact_track_blocked"] is True
    assert metadata["trajectory_integrations_performed"] == 0
    assert metadata["capture_calculations_performed"] == 0
    assert metadata["selected_excited_zeeman_model"] == "rodriguez_effective_g_0p001"
    assert metadata["selected_excited_hyperfine_model"] == "source_aligned_effective_fprime_splitting"
    assert metadata["full_d_operator_implementation"]["implemented"] is False
    assert metadata["non_hyperfine_inputs_identical"] is True
    for path in (METADATA_PATH, REPORT_PATH):
        assert run009d.RUN009D_LABEL in path.name
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(run009d.RUN009D_LABEL in line for line in report.splitlines() if line.startswith("#"))
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "integrate_policy_trajectory(", "run_trajectory_ensemble(", "solve_ivp(",
        "capture_velocity", "classify_trajectory(",
    ):
        assert forbidden not in source
