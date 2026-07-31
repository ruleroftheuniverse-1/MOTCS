import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.mgf_backend import (
    ApproximateMgFHamiltonian,
    MgFBackendCapabilityError,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.policies import ChirpToTrapHandoffPolicy, load_policy
from mgf_mot.provisional_force import ProvisionalForceMapConfig
from mgf_mot.tracks import BackendProvenance, ProjectTrack
from mgf_mot.trajectory import (
    TrajectoryConfig,
    TrajectoryInitialState,
    integrate_policy_trajectory,
)
from scripts.run_provisional_handoff_validation import (
    BOUNDARY_EPSILON_S,
    HANDOFF_VALIDATION_LABEL,
    run,
)

CONFIG_PATH = (
    Path(__file__).parents[1]
    / "configs"
    / "rodriguez_chirp_to_3_plus_1_handoff.yaml"
)


@pytest.fixture
def handoff_policy() -> ChirpToTrapHandoffPolicy:
    policy = load_policy(CONFIG_PATH)
    assert isinstance(policy, ChirpToTrapHandoffPolicy)
    return policy


@pytest.fixture
def lightweight_provisional_backend() -> ApproximateMgFHamiltonian:
    return ApproximateMgFHamiltonian(
        hamiltonian=None,  # type: ignore[arg-type]
        validation_model=None,  # type: ignore[arg-type]
        report=None,  # type: ignore[arg-type]
        provenance=BackendProvenance(
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
        ),
    )


def _state_vectors(policy: ChirpToTrapHandoffPolicy, time_s: float):
    sample = policy.sample(time_s)
    return (
        tuple(component.detuning_gamma for component in sample.components),
        tuple(component.saturation for component in sample.components),
        tuple(component.enabled for component in sample.components),
        tuple(component.active for component in sample.components),
        sample,
    )


def test_handoff_policy_uses_three_component_values_before_tau(
    handoff_policy,
) -> None:
    tau = handoff_policy.handoff_time_s
    detunings, saturations, enabled, active, sample = _state_vectors(
        handoff_policy, tau - BOUNDARY_EPSILON_S
    )
    assert detunings[:3] == pytest.approx((-1.000007, -1.000007, -1.000007))
    assert detunings[3] == 2.0
    assert saturations == (1.45, 1.45, 2.89, 0.0)
    assert enabled == (True, True, True, False)
    assert active == (True, True, True, False)
    assert sample.components[3].off_reason == "parked_off_until_3_plus_1_handoff"
    assert sample.segment == "chirp_3"
    assert sample.handoff_occurred is False


@pytest.mark.parametrize("time_factor", [1.0, 1.000001, 2.0])
def test_handoff_policy_uses_three_plus_one_values_at_and_after_tau(
    handoff_policy, time_factor
) -> None:
    tau = handoff_policy.handoff_time_s
    detunings, saturations, enabled, active, sample = _state_vectors(
        handoff_policy, time_factor * tau
    )
    assert detunings == (-1.0, -1.0, -1.0, 2.0)
    assert saturations == (1.45, 1.45, 2.17, 0.72)
    assert enabled == (True, True, True, True)
    assert active == (True, True, True, True)
    assert sample.segment == "trap_3_plus_1"
    assert sample.handoff_occurred is True


def test_handoff_policy_exposes_exact_event_time(handoff_policy) -> None:
    assert handoff_policy.event_times_s == (0.001,)


def test_event_aware_rk4_lands_exactly_on_tau_and_restarts_post_handoff(
    handoff_policy, lightweight_provisional_backend
) -> None:
    tau = handoff_policy.handoff_time_s
    result = integrate_policy_trajectory(
        handoff_policy,
        TrajectoryInitialState((0.0, 0.0, 0.05), (0.0, 0.0, 0.0)),
        lightweight_provisional_backend,
        ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
        TrajectoryConfig(0.0007, 0.0013, 0.0005),
    )
    assert result.times_s.tolist() == [0.0007, tau, 0.0013]
    assert result.times_s[1] == tau
    assert result.metadata.known_event_times_s == (tau,)
    assert result.metadata.encountered_event_times_s == (tau,)
    assert result.policy_segments == ("chirp_3", "trap_3_plus_1", "trap_3_plus_1")
    assert result.handoff_occurred.tolist() == [False, True, True]
    assert result.component_active[:, 3].tolist() == [False, True, True]
    assert result.component_saturations[:, 2].tolist() == [2.89, 2.17, 2.17]
    assert result.component_saturations[:, 3].tolist() == [0.0, 0.72, 0.72]
    assert np.isfinite(result.positions).all()
    assert np.isfinite(result.velocities).all()
    assert np.isfinite(result.forces).all()


def test_exact_track_cannot_use_handoff_trajectory(handoff_policy) -> None:
    exact_like = build_mgf_validation_model_from_sources()
    with pytest.raises(MgFBackendCapabilityError, match="Track P provisional backend"):
        integrate_policy_trajectory(
            handoff_policy,
            TrajectoryInitialState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            exact_like,  # type: ignore[arg-type]
            ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
            TrajectoryConfig(0.0007, 0.0013, 0.0005),
        )


def test_handoff_trajectory_requires_explicit_opt_in(
    handoff_policy, lightweight_provisional_backend
) -> None:
    with pytest.raises(MgFBackendCapabilityError, match="explicit_provisional_opt_in"):
        integrate_policy_trajectory(
            handoff_policy,
            TrajectoryInitialState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            lightweight_provisional_backend,
            ProvisionalForceMapConfig(),
            TrajectoryConfig(0.0007, 0.0013, 0.0005),
        )


def test_run_005_outputs_and_metadata_are_labeled(tmp_path) -> None:
    record = run(tmp_path, save_plot=False)
    for key in ("arrays_path", "metadata_path", "report_path"):
        path = record[key]
        assert path.parent == tmp_path
        assert HANDOFF_VALIDATION_LABEL in path.name

    metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["label"] == HANDOFF_VALIDATION_LABEL
    assert HANDOFF_VALIDATION_LABEL in metadata["title"]
    assert metadata["replication_valid"] is False
    assert metadata["force_ready"] is False
    assert metadata["beam_model"] == "infinite_plane_wave"
    assert metadata["boundary_epsilon_s"] == BOUNDARY_EPSILON_S
    assert len(metadata["snapshots"]) == 6
    for snapshot in metadata["snapshots"]:
        assert snapshot["label"] == HANDOFF_VALIDATION_LABEL
        assert HANDOFF_VALIDATION_LABEL in snapshot["title"]

    checks = metadata["trajectory_checks"]
    assert checks["label"] == HANDOFF_VALIDATION_LABEL
    assert HANDOFF_VALIDATION_LABEL in checks["title"]
    for key in (
        "tau_exact_in_time_array",
        "step_ends_exactly_at_tau",
        "next_step_starts_at_tau_with_post_handoff_state",
        "component_4_inactive_before_tau",
        "component_4_active_at_tau",
        "component_4_active_after_tau",
    ):
        assert checks[key] is True
    assert checks["component_3_saturation_before_tau"] == 2.89
    assert checks["component_3_saturation_at_tau"] == 2.17
    assert metadata["trajectory_metadata"]["label"] == HANDOFF_VALIDATION_LABEL
    assert HANDOFF_VALIDATION_LABEL in metadata["trajectory_metadata"]["title"]
    assert metadata["backend_provenance"]["label"] == HANDOFF_VALIDATION_LABEL
    assert HANDOFF_VALIDATION_LABEL in metadata["backend_provenance"]["title"]
    assert metadata["backend_provenance"]["replication_valid"] is False
    assert metadata["arrays_finite"] is True

    arrays = np.load(record["arrays_path"])
    assert np.any(arrays["times_s"] == 0.001)
    assert arrays["component_active"][:, 3].tolist() == [False, True, True]
    assert np.isfinite(arrays["positions"]).all()
    assert np.isfinite(arrays["velocities"]).all()
    assert np.isfinite(arrays["forces"]).all()

    report = record["report_path"].read_text(encoding="utf-8")
    for heading in (line for line in report.splitlines() if line.startswith("#")):
        assert HANDOFF_VALIDATION_LABEL in heading
    assert "No capture velocity or capture/loss classification" in report
    assert "No molecular-beam source distribution" in report
    assert "No Gaussian beams or optimizer" in report
    assert "No physical conclusions" in report


def test_handoff_layers_introduce_no_forbidden_public_apis() -> None:
    import mgf_mot.policies as policies
    import mgf_mot.trajectory as trajectory

    forbidden = ("capture", "gaussian", "distribution", "optimizer", "optimiser")
    public_names = [
        name.lower()
        for module in (policies, trajectory)
        for name in dir(module)
        if not name.startswith("_")
    ]
    for word in forbidden:
        assert not any(word in name for name in public_names)
