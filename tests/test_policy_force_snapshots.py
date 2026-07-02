import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.mgf_backend import (
    ApproximationMode,
    MgFBackendCapabilityError,
    build_mgf_hamiltonian_from_sources,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.policies import load_policy
from mgf_mot.policy_force import (
    POLICY_FORCE_SNAPSHOT_LABEL,
    PolicyForceGridConfig,
    force_grid_for_policy_snapshot,
)
from mgf_mot.provisional_force import ProvisionalForceMapConfig
from scripts.run_provisional_policy_force_snapshots import run

CONFIG_DIR = Path(__file__).parents[1] / "configs"


@pytest.fixture(scope="module")
def provisional_backend():
    return build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )


@pytest.fixture(scope="module")
def chirp_policy():
    return load_policy(CONFIG_DIR / "rodriguez_baseline_linear_chirp.yaml")


def test_policy_snapshot_exact_track_cannot_use_this_path(chirp_policy) -> None:
    exact_like = build_mgf_validation_model_from_sources()
    with pytest.raises(MgFBackendCapabilityError, match="Track P provisional backend"):
        force_grid_for_policy_snapshot(
            chirp_policy,
            0.0,
            exact_like,
            ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
            PolicyForceGridConfig(),
        )


def test_policy_snapshot_requires_explicit_opt_in(chirp_policy, provisional_backend) -> None:
    with pytest.raises(MgFBackendCapabilityError, match="explicit_provisional_opt_in"):
        force_grid_for_policy_snapshot(
            chirp_policy,
            0.0,
            provisional_backend,
            ProvisionalForceMapConfig(),
            PolicyForceGridConfig(),
        )


def test_policy_snapshot_metadata_and_shapes(chirp_policy, provisional_backend) -> None:
    snapshot = force_grid_for_policy_snapshot(
        chirp_policy,
        0.0,
        provisional_backend,
        ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
        PolicyForceGridConfig(),
    )
    assert snapshot.metadata.label == POLICY_FORCE_SNAPSHOT_LABEL
    assert POLICY_FORCE_SNAPSHOT_LABEL in snapshot.metadata.title
    assert POLICY_FORCE_SNAPSHOT_LABEL in snapshot.metadata.filename_stem
    assert not snapshot.metadata.replication_valid
    assert not snapshot.metadata.force_ready
    assert snapshot.metadata.component_detunings_gamma == (-8.0, -8.0, -8.0, 2.0)
    assert snapshot.grid.forces.shape == (5, 3)
    assert np.isfinite(snapshot.grid.forces).all()
    assert snapshot.grid.metadata.replication_valid is False
    assert snapshot.derived_force_config.explicit_provisional_opt_in is True


def test_policy_snapshot_run_outputs_and_endpoint_metadata(tmp_path) -> None:
    records = run(tmp_path, save_plots=False)
    assert len(records) == 4
    assert [record["time_s"] for record in records] == pytest.approx([0.0, 0.0005, 0.001, 0.002])
    expected_detunings = [
        (-8.0, -8.0, -8.0, 2.0),
        (-4.5, -4.5, -4.5, 2.0),
        (-1.0, -1.0, -1.0, 2.0),
        (-1.0, -1.0, -1.0, 2.0),
    ]
    for record, expected in zip(records, expected_detunings):
        assert POLICY_FORCE_SNAPSHOT_LABEL in record["metadata_path"].name
        assert POLICY_FORCE_SNAPSHOT_LABEL in record["arrays_path"].name
        metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
        assert metadata["label"] == POLICY_FORCE_SNAPSHOT_LABEL
        assert POLICY_FORCE_SNAPSHOT_LABEL in metadata["title"]
        assert metadata["replication_valid"] is False
        assert metadata["force_ready"] is False
        assert metadata["backend_provenance"]["track"] == "provisional"
        assert metadata["backend_provenance"]["replication_valid"] is False
        assert metadata["snapshot_metadata"]["component_detunings_gamma"] == list(expected)
        assert metadata["forces_shape"] == [5, 3]
        assert metadata["forces_finite"] is True
        arrays = np.load(record["arrays_path"])
        assert arrays["forces"].shape == (5, 3)
        assert np.isfinite(arrays["forces"]).all()

    report = tmp_path / f"{POLICY_FORCE_SNAPSHOT_LABEL}_run_003.md"
    assert report.exists()
    assert report.read_text(encoding="utf-8").startswith(f"# {POLICY_FORCE_SNAPSHOT_LABEL}")
    text = report.read_text(encoding="utf-8")
    assert "frozen-time static force snapshot" in text
    assert "No molecule trajectory was integrated" in text
    assert "No capture velocity was computed" in text
    assert "Exact MgF force readiness remains blocked" in text
    assert "No physical conclusions" in text


def test_policy_snapshot_no_forbidden_public_runtime_names() -> None:
    import mgf_mot.policy_force as policy_force

    forbidden = ("trajectory", "capture_velocity", "gaussian", "optimizer")
    public_names = [name.lower() for name in dir(policy_force) if not name.startswith("_")]
    for word in forbidden:
        assert not any(word in name for name in public_names)
