from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "analyze_provisional_named_trajectories.py"
spec = importlib.util.spec_from_file_location("run008a_audit", SCRIPT_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


@pytest.fixture(scope="module")
def audit_record(tmp_path_factory):
    return audit.analyze(
        REPO_ROOT / "outputs" / "provisional",
        tmp_path_factory.mktemp("run008a"),
        save_plots=False,
    )


def test_all_five_saved_cases_are_analyzed_in_order(audit_record) -> None:
    cases = audit_record["cases"]
    assert len(cases) == 5
    assert [case["initial_velocity_gamma_over_k"] for case in cases] == [
        2.0, 4.0, 6.0, 7.5, 9.0
    ]
    assert all(case["official_outcome_label"] == "UNRESOLVED" for case in cases)
    assert all(case["diagnostic_category"] for case in cases)
    assert all(
        case["diagnostic_category"] != case["official_outcome_label"]
        for case in cases
    )


def test_criteria_are_audited_without_modification(audit_record) -> None:
    criteria = audit_record["metadata"]["criteria_audit"]
    assert criteria["criteria_modified"] is False
    assert criteria["current_criteria_equal_saved_run_008_criteria"] is True
    assert criteria["position_bound_m"] == 0.01
    assert criteria["velocity_bound_m_s"] == 1.0
    assert criteria["dwell_window_s"] == 0.002
    assert criteria["minimum_dwell_samples"] == 10
    assert criteria["escape_position_m"] == 2.0
    assert criteria["escape_speed_m_s"] == 100.0
    assert criteria["can_in_principle_satisfy_duration"] is True
    assert criteria["can_in_principle_satisfy_sample_minimum"] is True


def test_saved_metadata_consistency_and_provenance(audit_record) -> None:
    consistency = audit_record["metadata"]["consistency_audit"]
    assert consistency["initial_position_is_minus_50_mm"] is True
    assert consistency["velocity_order_exact"] is True
    assert consistency["gaussian_mode_active"] is True
    assert consistency["handoff_exact_all_cases"] is True
    assert consistency["component_4_switch_correct_all_cases"] is True
    assert consistency["pre_saturations_exact_all_cases"] is True
    assert consistency["post_saturations_exact_all_cases"] is True
    assert consistency["track"] == "provisional"
    assert consistency["replication_valid"] is False


def test_exact_track_cannot_enter_audit() -> None:
    with pytest.raises(ValueError, match="exact or replication-valid"):
        audit._validate_run_metadata(
            {
                "label": audit.RUN_008_LABEL,
                "replication_valid": True,
                "protocol": {"track": "exact"},
                "beam_mode": "elliptical_gaussian",
            }
        )


def test_outputs_and_nested_metadata_are_quarantined(audit_record) -> None:
    assert audit.AUDIT_LABEL in audit_record["metadata_path"].name
    assert audit.AUDIT_LABEL in audit_record["report_path"].name
    metadata = json.loads(audit_record["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["label"] == audit.AUDIT_LABEL
    assert metadata["replication_valid"] is False
    for obj in (metadata["criteria_audit"], metadata["consistency_audit"], *metadata["cases"]):
        assert obj["label"] == audit.AUDIT_LABEL
        assert audit.AUDIT_LABEL in obj["title"]
    report = audit_record["report_path"].read_text(encoding="utf-8")
    assert all(audit.AUDIT_LABEL in line for line in report.splitlines() if line.startswith("#"))


def test_audit_adds_no_forbidden_public_api() -> None:
    forbidden = (
        "capture_velocity",
        "threshold_search",
        "boundary_search",
        "source_distribution",
        "stochastic",
        "optimizer",
    )
    public = [name.lower() for name in dir(audit) if not name.startswith("_")]
    for term in forbidden:
        assert not any(term in name for name in public)
