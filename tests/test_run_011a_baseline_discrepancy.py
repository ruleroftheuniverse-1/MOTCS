from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "analyze_run_011_baseline_discrepancy.py"
LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_"
    "RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY"
)
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
METADATA_PATH = OUTPUT_DIR / f"{LABEL}_metadata.json"
REPORT_PATH = OUTPUT_DIR / f"{LABEL}.md"


def _module():
    spec = importlib.util.spec_from_file_location("run011a_audit", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata() -> dict:
    assert METADATA_PATH.exists(), "run scripts/analyze_run_011_baseline_discrepancy.py first"
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def test_read_only_helpers_reconstruct_cached_extrema_and_hashes() -> None:
    module = _module()
    before = module.hash_manifest()
    cache = module._pre_cache()
    extremum = module.slowing_extremum(cache, -8.0)
    after = module.hash_manifest()
    assert before == after
    assert extremum["normalized_force"] < 0.0
    assert extremum["velocity_m_s"] == 87.5
    assert extremum["paper_boat_velocity_m_s"] == np.sqrt(2) * 8 * 7.53


def test_audit_gate_labels_authorizations_and_immutability() -> None:
    metadata = _metadata()
    assert metadata["label"] == LABEL
    assert metadata["gate"] == "BASELINE_DISCREPANCY_NARROWED"
    assert metadata["protected_artifacts_unchanged"] is True
    assert metadata["protected_hashes_before"] == metadata["protected_hashes_after"]
    assert metadata["trajectory_integrations_performed"] == 0
    assert metadata["force_field_rebuilds_performed"] == 0
    assert metadata["capture_authorized"] is False
    assert metadata["capture_velocity_authorized"] is False
    assert metadata["optimizer_authorized"] is False
    assert metadata["exact_replication_valid"] is False
    assert metadata["exact_track_blocked"] is True
    assert all(all(stamp in filename for stamp in ("PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY")) for filename in metadata["generated_files"])


def test_frequency_and_rate_conventions_are_explicitly_audited() -> None:
    metadata = _metadata()
    frequency = metadata["optical_frequency_audit"]
    assert len(frequency["samples"]["pre_handoff"]) == 4
    assert len(frequency["samples"]["post_handoff"]) == 4
    pre4 = frequency["samples"]["pre_handoff"][3]
    post4 = frequency["samples"]["post_handoff"][3]
    assert pre4["active"] is False and pre4["peak_saturation"] == 0.0
    assert post4["active"] is True and post4["peak_saturation"] == 0.72
    rate = metadata["rate_convention_audit"]
    assert rate["paper_rate_over_gamma"] == rate["pylcp_rate_over_gamma"]
    assert rate["factor_findings"]["rabi_factor_of_two"] == "MATCHES"
    assert rate["factor_findings"]["total_power_metadata_used_in_calculation"] is False
    assert np.allclose(rate["dipole_normalization_per_excited_state"], 1.0, atol=2e-7)


def test_saved_path_diagnostics_are_finite_complete_and_non_capture() -> None:
    metadata = _metadata()
    assert set(metadata["trajectories"]) == {
        "v_2_gamma_over_k", "v_4_gamma_over_k", "v_6_gamma_over_k",
        "v_7p5_gamma_over_k", "v_9_gamma_over_k",
    }
    seven = metadata["trajectories"]["v_7p5_gamma_over_k"]
    assert seven["final_or_termination"]["velocity_m_s"] > seven["initial"]["velocity_m_s"]
    assert seven["impulse_budget"]["impulse_before_tau_n_s"] < 0.0
    assert seven["impulse_budget"]["impulse_after_tau_n_s"] > 0.0
    assert seven["gaussian_timing_events"]["first_useful_force_encounter"] is not None
    assert set(seven["gaussian_timing_events"]) == {
        "first_useful_force_encounter", "closest_to_slowing_extremum", "handoff",
        "center_crossing", "last_appreciable_illumination",
    }
    for row in metadata["direct_point_audit"]:
        assert row["population_solver_health"]["passed"] is True
        assert np.isfinite(row["cached_normalized_force"])
        assert np.isfinite(row["direct_normalized_force"])


def test_report_and_source_obey_audit_only_boundary() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(LABEL in line for line in report.splitlines() if line.startswith("#"))
    assert "BASELINE_DISCREPANCY_NARROWED" in report
    assert "capture_authorized = false" in report
    assert "Saved 7.5 Gamma/k path envelope events" in report
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "integrate_accepted_force_field_trajectory(",
        "save_force_field_cache(",
        "build_force_field(",
        "capture_velocity(",
        "threshold_search(",
        "optimizer(",
    ):
        assert forbidden not in source

