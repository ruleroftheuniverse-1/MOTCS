from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.force_units import (
    MGF24_MASS,
    build_mgf_force_unit_audit,
    normalized_force_to_acceleration_m_s2,
    normalized_force_to_newtons,
    trapezoid_impulse,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_provisional_force_budget.py"
spec = importlib.util.spec_from_file_location("run008b_audit", SCRIPT_PATH)
audit_script = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit_script)


@pytest.fixture(scope="module")
def audit_record(tmp_path_factory):
    return audit_script.audit(
        REPO_ROOT / "outputs" / "provisional",
        tmp_path_factory.mktemp("run008b"),
        save_plots=False,
    )


def test_source_tagged_mgf_mass_and_force_unit_are_finite() -> None:
    unit = build_mgf_force_unit_audit()
    assert MGF24_MASS.isotopologue == "24Mg19F"
    assert MGF24_MASS.status == "derived_approximate"
    assert len(MGF24_MASS.source) == 3
    assert np.isfinite(MGF24_MASS.value_kg) and MGF24_MASS.value_kg > 0.0
    assert unit.wave_number_rad_m == pytest.approx(1.74872955947e7, rel=1e-11)
    assert unit.linewidth_rad_s == pytest.approx(1.31318572920e8, rel=1e-11)
    assert unit.hbar_k_gamma_n == pytest.approx(2.42172578801e-19, rel=1e-11)


def test_hbar_k_gamma_is_applied_exactly_once() -> None:
    unit = build_mgf_force_unit_audit()
    assert unit.conversion_count == 1
    force_n = normalized_force_to_newtons(1.0, unit)
    acceleration = normalized_force_to_acceleration_m_s2(1.0, unit)
    assert float(force_n) == pytest.approx(unit.hbar_k_gamma_n)
    assert float(acceleration) == pytest.approx(
        unit.hbar_k_gamma_n / unit.mass.value_kg
    )
    assert float(acceleration) != pytest.approx(
        unit.hbar_k_gamma_n**2 / unit.mass.value_kg
    )


def test_analytic_constant_force_impulse_matches_force_times_duration() -> None:
    times = np.linspace(0.0, 0.25, 101)
    force = np.full((times.size, 3), [2.0, -1.0, 0.5])
    impulse = trapezoid_impulse(times, force)
    assert impulse == pytest.approx(np.array([2.0, -1.0, 0.5]) * 0.25)


def test_saved_force_reconstruction_is_finite_and_outcomes_unchanged(audit_record) -> None:
    cases = audit_record["cases"]
    assert len(cases) == 5
    assert [case["initial_velocity_gamma_over_k"] for case in cases] == [
        2.0, 4.0, 6.0, 7.5, 9.0
    ]
    for case in cases:
        assert np.isfinite(case["physical_impulse_if_hbar_k_gamma_applied_once_n_s"]).all()
        assert np.isfinite(case["physical_delta_v_if_conversion_applied_once_m_s"]).all()
        assert case["current_adapter_reconstruction_max_abs_error_m_s"] < 1.0e-6
        assert case["official_outcome_label"] == "UNRESOLVED"
    immutability = audit_record["metadata"]["immutability_audit"]
    assert immutability["all_source_hashes_unchanged"] is True
    assert immutability["official_outcome_labels_unchanged"] is True
    assert immutability["trajectory_integrations_performed"] == 0


def test_plane_wave_and_gaussian_local_slopes_are_separate(audit_record) -> None:
    local = audit_record["metadata"]["local_force_audits"]
    assert [item["beam_mode"] for item in local] == [
        "plane_wave",
        "elliptical_gaussian",
    ]
    for item in local:
        assert item["restoring_status"] == "restoring"
        assert item["damping_status"] == "damping"
        assert np.isfinite(item["dFdx_normalized_per_m"])
        assert np.isfinite(item["dFdv_normalized_per_m_s"])


def test_gaussian_application_failure_is_explicit_not_hidden(audit_record) -> None:
    gaussian = audit_record["metadata"]["gaussian_application_audit"]
    assert gaussian["per_beam_envelopes_available"] is True
    assert gaussian["counterpropagating_pair_envelopes_equal"] is True
    assert gaussian["per_beam_envelopes_applied_before_force_summation"] is False
    assert gaussian["mean_envelope_applied_after_force_summation"] is True
    assert gaussian["saturation_squared"] is False
    assert gaussian["all_beams_multiplied_by_weakest_envelope"] is False
    assert gaussian["position_units_m"] is True
    assert gaussian["diagnosis"] == "GAUSSIAN_APPLICATION_SUSPECT"


def test_backend_decomposition_limitation_and_unit_suspect_are_reported(audit_record) -> None:
    metadata = audit_record["metadata"]
    assert metadata["unit_audit"]["run008_physical_conversion_application_count"] == 0
    assert metadata["unit_audit"]["audited_conversion_application_count"] == 1
    assert metadata["beam_frequency_decomposition"]["decomposition_available"] is False
    assert set(metadata["overall_engineering_diagnoses"]) == {
        "UNIT_CONVERSION_SUSPECT",
        "GAUSSIAN_APPLICATION_SUSPECT",
        "PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT",
    }


def test_exact_track_rejected_and_outputs_quarantined(audit_record) -> None:
    with pytest.raises(ValueError, match="exact Track E"):
        audit_script._validate_saved_run(
            {
                "label": audit_script.RUN_008_LABEL,
                "replication_valid": True,
                "protocol": {"track": "exact"},
            }
        )
    assert audit_script.AUDIT_LABEL in audit_record["metadata_path"].name
    assert audit_script.AUDIT_LABEL in audit_record["report_path"].name
    metadata = json.loads(audit_record["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["label"] == audit_script.AUDIT_LABEL
    assert metadata["replication_valid"] is False
    report = audit_record["report_path"].read_text(encoding="utf-8")
    assert all(
        audit_script.AUDIT_LABEL in line
        for line in report.splitlines()
        if line.startswith("#")
    )


def test_no_forbidden_or_trajectory_public_api_is_added() -> None:
    forbidden = (
        "capture_velocity",
        "threshold_search",
        "new_velocity",
        "source_distribution",
        "stochastic",
        "optimizer",
        "integrate_policy_trajectory",
        "run_trajectory_ensemble",
    )
    public = [name.lower() for name in dir(audit_script) if not name.startswith("_")]
    for term in forbidden:
        assert not any(term in name for name in public)
