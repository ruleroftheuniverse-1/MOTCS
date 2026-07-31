import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.mgf_backend import (
    ApproximateMgFHamiltonian,
    MgFBackendCapabilityError,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.policies import load_policy
from mgf_mot.provisional_force import ProvisionalForceMapConfig
from mgf_mot.tracks import BackendProvenance, ProjectTrack
from mgf_mot.trajectory import (
    ANALYTIC_TEST_HOOK_LABEL,
    TRAJECTORY_SCAFFOLD_LABEL,
    TrajectoryConfig,
    TrajectoryInitialState,
    integrate_analytic_test_trajectory,
    integrate_policy_trajectory,
)
from scripts.run_provisional_trajectory_scaffold import run

CONFIG_DIR = Path(__file__).parents[1] / "configs"


@pytest.fixture
def lightweight_provisional_backend() -> ApproximateMgFHamiltonian:
    provenance = BackendProvenance(
        track=ProjectTrack.PROVISIONAL,
        backend_mode="collapsed_pylcp_astate",
        force_ready=False,
        replication_valid=False,
        warnings=(
            "PROVISIONAL test backend.",
            "NOT_RODRIGUEZ_REPLICATION test backend.",
        ),
        omitted_terms=("excited_hyperfine_d operator",),
        collapsed_terms=("test-only provenance fixture",),
    )
    # The normalized plumbing force never reads the pylcp Hamiltonian payload.
    return ApproximateMgFHamiltonian(
        hamiltonian=None,  # type: ignore[arg-type]
        validation_model=None,  # type: ignore[arg-type]
        report=None,  # type: ignore[arg-type]
        provenance=provenance,
    )


@pytest.fixture
def chirp_policy():
    return load_policy(CONFIG_DIR / "rodriguez_baseline_linear_chirp.yaml")


def test_zero_force_preserves_velocity_and_linear_position() -> None:
    initial = TrajectoryInitialState(
        position=(1.0, -1.0, 0.5),
        velocity=(0.25, -0.5, 2.0),
    )
    config = TrajectoryConfig(0.0, 0.2, 0.01)
    result = integrate_analytic_test_trajectory(
        initial,
        config,
        lambda _t, _r, _v: np.zeros(3),
        model_name="zero_force_equivalent_acceleration",
    )
    expected_positions = (
        np.asarray(initial.position)
        + result.times_s[:, None] * np.asarray(initial.velocity)
    )
    assert result.label == ANALYTIC_TEST_HOOK_LABEL
    assert result.uses_mgf_backend is False
    assert result.positions == pytest.approx(expected_positions, abs=1e-13)
    assert result.velocities == pytest.approx(
        np.broadcast_to(initial.velocity, result.velocities.shape), abs=1e-13
    )
    assert np.count_nonzero(result.accelerations) == 0


def test_constant_force_equivalent_acceleration_is_quadratic() -> None:
    acceleration = np.asarray((1.0, -2.0, 0.5))
    initial = TrajectoryInitialState(
        position=(0.2, -0.1, 0.3),
        velocity=(0.4, 0.5, -0.2),
    )
    config = TrajectoryConfig(0.0, 0.25, 0.01)
    result = integrate_analytic_test_trajectory(
        initial,
        config,
        lambda _t, _r, _v: acceleration,
        model_name="constant_force_equivalent_acceleration",
    )
    expected_positions = (
        np.asarray(initial.position)
        + result.times_s[:, None] * np.asarray(initial.velocity)
        + 0.5 * result.times_s[:, None] ** 2 * acceleration
    )
    expected_velocities = (
        np.asarray(initial.velocity) + result.times_s[:, None] * acceleration
    )
    assert result.positions == pytest.approx(expected_positions, abs=1e-12)
    assert result.velocities == pytest.approx(expected_velocities, abs=1e-12)


def test_linear_damping_reduces_speed() -> None:
    result = integrate_analytic_test_trajectory(
        TrajectoryInitialState((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        TrajectoryConfig(0.0, 0.5, 0.01),
        lambda _t, _r, velocity: -2.0 * velocity,
        model_name="linear_damping",
    )
    assert np.linalg.norm(result.velocities[-1]) < np.linalg.norm(
        result.velocities[0]
    )


def test_exact_track_cannot_use_trajectory_path(chirp_policy) -> None:
    exact_like = build_mgf_validation_model_from_sources()
    with pytest.raises(MgFBackendCapabilityError, match="Track P provisional backend"):
        integrate_policy_trajectory(
            chirp_policy,
            TrajectoryInitialState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            exact_like,  # type: ignore[arg-type]
            ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
            TrajectoryConfig(0.0, 0.0001, 0.00001),
        )


def test_policy_trajectory_requires_explicit_opt_in(
    chirp_policy, lightweight_provisional_backend
) -> None:
    with pytest.raises(MgFBackendCapabilityError, match="explicit_provisional_opt_in"):
        integrate_policy_trajectory(
            chirp_policy,
            TrajectoryInitialState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            lightweight_provisional_backend,
            ProvisionalForceMapConfig(),
            TrajectoryConfig(0.0, 0.0001, 0.00001),
        )


def test_policy_trajectory_metadata_shapes_and_component_4_state(
    chirp_policy, lightweight_provisional_backend
) -> None:
    result = integrate_policy_trajectory(
        chirp_policy,
        TrajectoryInitialState((0.0, 0.0, 0.05), (0.0, 0.0, 0.0)),
        lightweight_provisional_backend,
        ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
        TrajectoryConfig(0.0, 0.0002, 0.00002),
    )
    sample_count = result.times_s.size
    assert result.metadata.label == TRAJECTORY_SCAFFOLD_LABEL
    assert TRAJECTORY_SCAFFOLD_LABEL in result.metadata.title
    assert TRAJECTORY_SCAFFOLD_LABEL in result.metadata.filename_stem
    assert result.metadata.track is ProjectTrack.PROVISIONAL
    assert result.metadata.replication_valid is False
    assert result.metadata.force_ready is False
    assert result.times_s.shape == (sample_count,)
    assert result.positions.shape == (sample_count, 3)
    assert result.velocities.shape == (sample_count, 3)
    assert result.forces.shape == (sample_count, 3)
    assert result.component_detunings_gamma.shape == (sample_count, 4)
    assert result.component_saturations.shape == (sample_count, 4)
    assert result.component_active.shape == (sample_count, 4)
    assert np.isfinite(result.positions).all()
    assert np.isfinite(result.velocities).all()
    assert np.isfinite(result.forces).all()
    assert result.component_detunings_gamma[:, 3] == pytest.approx(2.0)
    assert result.component_saturations[:, 3] == pytest.approx(0.0)
    assert not result.component_active[:, 3].any()


def test_run_004_outputs_are_quarantined_and_labeled(tmp_path) -> None:
    record = run(tmp_path, save_plot=False)
    result = record["result"]
    output_paths = (
        record["arrays_path"],
        record["metadata_path"],
        record["report_path"],
    )
    for path in output_paths:
        assert path.parent == tmp_path
        assert TRAJECTORY_SCAFFOLD_LABEL in path.name

    metadata = json.loads(
        record["metadata_path"].read_text(encoding="utf-8")
    )
    assert metadata["label"] == TRAJECTORY_SCAFFOLD_LABEL
    assert TRAJECTORY_SCAFFOLD_LABEL in metadata["title"]
    assert metadata["replication_valid"] is False
    assert metadata["force_ready"] is False
    assert metadata["backend_provenance"]["track"] == "provisional"
    assert metadata["backend_provenance"]["replication_valid"] is False
    assert metadata["beam_model"] == "infinite_plane_wave"
    assert metadata["component_4_active_any"] is False
    assert metadata["component_4_saturation_max"] == 0.0
    assert metadata["arrays_finite"] is True

    arrays = np.load(record["arrays_path"])
    assert arrays["positions"].shape == result.positions.shape
    assert arrays["velocities"].shape == result.velocities.shape
    assert arrays["forces"].shape == result.forces.shape
    assert np.isfinite(arrays["positions"]).all()
    assert np.isfinite(arrays["velocities"]).all()
    assert np.isfinite(arrays["forces"]).all()
    assert not arrays["component_active"][:, 3].any()

    report = record["report_path"].read_text(encoding="utf-8")
    for heading in (line for line in report.splitlines() if line.startswith("#")):
        assert TRAJECTORY_SCAFFOLD_LABEL in heading
    assert "validates trajectory plumbing only" in report
    assert "Exact MgF force readiness remains blocked" in report
    assert "No capture velocity" in report
    assert "No molecular-beam source distribution" in report
    assert "No Gaussian beams" in report
    assert "No physical conclusions" in report


def test_trajectory_module_has_no_forbidden_public_apis() -> None:
    import mgf_mot.trajectory as trajectory

    forbidden = ("capture", "gaussian", "optimizer", "optimiser")
    public_names = [name.lower() for name in dir(trajectory) if not name.startswith("_")]
    for word in forbidden:
        assert not any(word in name for name in public_names)
