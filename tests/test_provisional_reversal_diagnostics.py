import json

import numpy as np
import pytest

from mgf_mot.mgf_backend import (
    ApproximationMode,
    MgFBackendCapabilityError,
    build_mgf_hamiltonian_from_sources,
)
from mgf_mot.provisional_force import (
    FULL_WARNING_LABEL,
    ProvisionalForceMapConfig,
    force_at,
)
from scripts.run_provisional_reversal_diagnostics import CASE_DEFINITIONS, run


def test_run_002_reversal_diagnostics_outputs_all_cases(tmp_path) -> None:
    records = run(tmp_path, save_plots=False)
    assert len(records) == 8
    assert {
        (record["config_name"], record["case"]) for record in records
    } == {
        (config_name, case_name)
        for config_name in ("rodriguez_static_3", "rodriguez_static_3_plus_1")
        for case_name in CASE_DEFINITIONS
    }

    for record in records:
        assert FULL_WARNING_LABEL in record["metadata_path"].name
        assert FULL_WARNING_LABEL in record["arrays_path"].name
        metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
        assert FULL_WARNING_LABEL in metadata["label"]
        assert FULL_WARNING_LABEL in metadata["title"]
        assert metadata["backend_provenance"]["track"] == "provisional"
        assert metadata["backend_provenance"]["replication_valid"] is False
        assert metadata["backend_provenance"]["force_ready"] is False
        assert metadata["grid_metadata"]["replication_valid"] is False
        assert metadata["forces_shape"] == [9, 9]
        assert metadata["force_vs_position_shape"] == [9]
        assert metadata["force_vs_velocity_shape"] == [9]
        assert metadata["forces_finite"] is True
        assert metadata["force_vs_position_finite"] is True
        assert metadata["force_vs_velocity_finite"] is True
        assert np.isfinite(metadata["dF_dx"])
        assert np.isfinite(metadata["dF_dv"])

        arrays = np.load(record["arrays_path"])
        assert arrays["forces"].shape == (9, 9)
        assert arrays["force_vs_position_v0"].shape == (9,)
        assert arrays["force_vs_velocity_x0"].shape == (9,)
        assert np.isfinite(arrays["forces"]).all()

    report = tmp_path / f"{FULL_WARNING_LABEL}_run_002_reversal_diagnostics.md"
    assert report.exists()
    assert FULL_WARNING_LABEL in report.name
    text = report.read_text(encoding="utf-8")
    assert text.startswith(f"# {FULL_WARNING_LABEL}")
    assert "provisional convention/plumbing diagnostic" in text
    assert "Exact MgF force readiness remains blocked" in text
    assert "No physical conclusions" in text
    assert "wiring/sign/configuration errors" in text


def test_run_002_prints_backend_provenance(tmp_path, capsys) -> None:
    run(tmp_path, save_plots=False)
    output = capsys.readouterr().out
    assert "track: provisional" in output
    assert "backend_mode: collapsed_pylcp_astate" in output
    assert "replication_valid: False" in output
    assert "force_ready: False" in output
    assert "omitted_terms:" in output
    assert "collapsed_terms:" in output


def test_run_002_exact_track_cannot_use_this_path() -> None:
    with pytest.raises(MgFBackendCapabilityError, match="complete MgF Hamiltonian"):
        build_mgf_hamiltonian_from_sources()


def test_run_002_provisional_opt_in_still_required() -> None:
    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    with pytest.raises(MgFBackendCapabilityError, match="explicit_provisional_opt_in"):
        force_at(np.zeros(3), np.zeros(3), backend, ProvisionalForceMapConfig())
