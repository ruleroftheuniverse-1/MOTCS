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
from scripts.run_provisional_static_force_plumbing import run


def test_run_provisional_static_force_plumbing_outputs_are_quarantined(tmp_path) -> None:
    records = run(tmp_path, save_plots=False)
    assert [record["config_name"] for record in records] == [
        "rodriguez_static_3",
        "rodriguez_static_3_plus_1",
    ]

    for record in records:
        for key in ("metadata_path", "arrays_path"):
            path = record[key]
            assert path.exists()
            assert FULL_WARNING_LABEL in path.name

        metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
        assert metadata["label"] == FULL_WARNING_LABEL
        assert metadata["backend_provenance"]["track"] == "provisional"
        assert metadata["backend_provenance"]["replication_valid"] is False
        assert metadata["backend_provenance"]["force_ready"] is False
        assert metadata["grid_metadata"]["replication_valid"] is False
        assert metadata["forces_shape"] == [7, 5]
        assert metadata["forces_finite"] is True
        assert "PROVISIONAL" in metadata["disclaimer"]
        assert "NOT_RODRIGUEZ_REPLICATION" in metadata["disclaimer"]

        arrays = np.load(record["arrays_path"])
        assert arrays["forces"].shape == (7, 5)
        assert np.isfinite(arrays["forces"]).all()

    report = tmp_path / f"{FULL_WARNING_LABEL}_run_001.md"
    assert report.exists()
    assert FULL_WARNING_LABEL in report.name
    text = report.read_text(encoding="utf-8")
    assert "plumbing validation" in text
    assert "not an MgF/Rodriguez reproduction" in text
    assert "Exact Track E remains blocked" in text
    assert "No physical conclusions" in text


def test_run_provisional_static_force_plumbing_prints_provenance(tmp_path, capsys) -> None:
    run(tmp_path, save_plots=False)
    output = capsys.readouterr().out
    assert "track: provisional" in output
    assert "backend_mode: collapsed_pylcp_astate" in output
    assert "replication_valid: False" in output
    assert "force_ready: False" in output
    assert "omitted_terms:" in output
    assert "collapsed_terms:" in output


def test_exact_backend_still_cannot_enter_provisional_path() -> None:
    with pytest.raises(MgFBackendCapabilityError, match="complete MgF Hamiltonian"):
        build_mgf_hamiltonian_from_sources()


def test_provisional_path_still_requires_explicit_opt_in() -> None:
    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    with pytest.raises(MgFBackendCapabilityError, match="explicit_provisional_opt_in"):
        force_at(np.zeros(3), np.zeros(3), backend, ProvisionalForceMapConfig())
