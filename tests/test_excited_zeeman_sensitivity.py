from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.conventions import GroundZeemanConvention
from mgf_mot.excited_zeeman import (
    ExcitedZeemanModel,
    build_excited_zeeman_operator,
    excited_basis_order,
    validate_excited_zeeman_operator,
)
from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.rateeq_backend import (
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
)
from mgf_mot.spectroscopy import (
    BOHR_MAGNETON_MHZ_PER_GAUSS,
    EXCITED_G_FACTOR_RODRIGUEZ,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_provisional_excited_zeeman_sensitivity.py"
SPEC = importlib.util.spec_from_file_location("run009c", SCRIPT)
run009c = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run009c)
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
METADATA_PATH = OUTPUT_DIR / f"{run009c.RUN009C_LABEL}_run_009C_metadata.json"
REPORT_PATH = OUTPUT_DIR / f"{run009c.RUN009C_LABEL}_run_009C.md"


def _backend(model: ExcitedZeemanModel) -> ProvisionalPylcpRateEquationBackend:
    return ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            ground_zeeman_convention=(
                GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
            ),
            excited_zeeman_model=model,
        )
    )


@pytest.fixture(scope="module")
def metadata():
    assert METADATA_PATH.exists(), "run the dedicated Run 009C script first"
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def test_excited_model_selection_is_named_explicit_and_conservative_by_default() -> None:
    default = _backend(ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT)
    effective = _backend(ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001)
    assert default.config.excited_zeeman_model is ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT
    assert default.status.excited_zeeman_override_applied is False
    assert effective.status.excited_zeeman_override_applied is True
    assert effective.status.excited_zeeman_model == "rodriguez_effective_g_0p001"
    assert not hasattr(__import__("mgf_mot"), "effective_isotropic_excited_muq")


def test_rodriguez_operator_is_source_tagged_hermitian_and_has_expected_slopes() -> None:
    backend = _backend(ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001)
    operator = backend.excited_zeeman_operator
    validation = validate_excited_zeeman_operator(operator)
    assert operator.effective_g == EXCITED_G_FACTOR_RODRIGUEZ.require() == 0.001
    assert operator.source == EXCITED_G_FACTOR_RODRIGUEZ.source
    assert operator.tensor_mhz_per_gauss.shape == (3, 4, 4)
    assert all(validation["cartesian_components_hermitian"])
    assert validation["spherical_hermiticity_relation"] is True
    assert validation["f0_first_order_slope_zero"] is True
    assert validation["f0_f1_off_block_zero"] is True
    assert validation["weak_field_slopes_match_selected_g"] is True
    mu_b = BOHR_MAGNETON_MHZ_PER_GAUSS.require()
    assert validation["axes"]["z"]["dE_dB_mhz_per_gauss_sorted"] == pytest.approx(
        [-0.001 * mu_b, 0.0, 0.0, 0.001 * mu_b], abs=1e-14
    )


def test_effective_operator_fails_closed_on_ambiguous_basis() -> None:
    backend = _backend(ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT)
    basis = backend.source_backend.validation_model.excited_basis.copy()[::-1]
    raw = backend.source_backend.hamiltonian.blocks[1, 1][1].matrix
    with pytest.raises(ValueError, match="requires basis"):
        build_excited_zeeman_operator(
            ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001,
            basis=basis,
            pylcp_collapsed_tensor_mhz_per_gauss=raw,
        )
    assert excited_basis_order(backend.source_backend.validation_model.excited_basis) == (
        (0, 0), (1, -1), (1, 0), (1, 1)
    )


def test_excited_and_ground_conventions_are_independent_and_applied_once(metadata) -> None:
    effective = metadata["candidate_models"]["rodriguez_effective_g_0p001"]
    status = effective["backend_status"]
    operator = effective["operator"]
    assert status["ground_zeeman_convention"] == "project_energy_slope_corrected"
    assert status["ground_magnetic_moment_correction_count"] == 1
    assert status["downstream_zeeman_sign_correction_count"] == 0
    assert status["excited_zeeman_model_application_count"] == 1
    assert status["excited_zeeman_model_application_location"] == "Hamiltonian boundary"
    assert operator["ground_tensor_modified"] is False
    assert operator["model_application_count"] == 1


def test_all_models_share_non_zeeman_inputs_and_healthy_population_solves(metadata) -> None:
    candidates = metadata["candidate_models"]
    fingerprints = [record["non_zeeman_input_fingerprint"] for record in candidates.values()]
    assert all(item == fingerprints[0] for item in fingerprints[1:])
    for record in candidates.values():
        health = record["population_health"]
        assert health["number_of_solves"] == 7 * 17 * 17
        assert health["passed"] is True
        assert health["fallback_count"] == 0
        assert health["nonfinite_count"] == 0
    assert metadata["source_yaml_unchanged"] is True


def test_sensitivity_result_and_static_acceptance_are_explicit(metadata) -> None:
    assert metadata["gate"] == "RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED"
    assert metadata["preferred_track_p_static_excited_zeeman_model"] == (
        "rodriguez_effective_g_0p001"
    )
    assert metadata["preferred_model_still_requires_explicit_selection"] is True
    assert all(metadata["acceptance_checks"].values())
    interpretation = metadata["sensitivity_interpretation"]
    assert interpretation["g_0p001_effectively_indistinguishable_from_zero"] is True
    assert interpretation["collapsed_g_0p334_materially_changes_any_observable"] is True
    assert metadata["comparisons"]["zero_vs_rodriguez_0p001"]["any_topology_change"] is False


def test_run009c_outputs_and_mandatory_locks(metadata) -> None:
    assert metadata["trajectory_authorized"] is False
    assert metadata["capture_authorized"] is False
    assert metadata["exact_replication_valid"] is False
    assert metadata["exact_track_blocked"] is True
    assert metadata["trajectory_integrations_performed"] == 0
    assert metadata["capture_results_calculated"] == 0
    assert run009c.RUN009C_LABEL in METADATA_PATH.name
    assert run009c.RUN009C_LABEL in REPORT_PATH.name
    assert run009c.RUN009C_LABEL in metadata["arrays"]
    assert run009c.RUN009C_LABEL in metadata["plot"]
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(
        run009c.RUN009C_LABEL in line
        for line in report.splitlines()
        if line.startswith("#")
    )
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden_call in (
        "integrate_policy_trajectory(",
        "run_trajectory_ensemble(",
        "solve_ivp(",
        "evolve_motion(",
        "evolve_populations(",
    ):
        assert forbidden_call not in source
