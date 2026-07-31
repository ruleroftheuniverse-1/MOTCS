import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mgf_mot.mgf_backend import (
    ApproximateMgFHamiltonian,
    MgFBackendCapabilityError,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.outcomes import (
    OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
    OutcomeCriteria,
    OutcomeLabel,
    classify_trajectory,
    run_trajectory_ensemble,
)
from mgf_mot.policies import ChirpToTrapHandoffPolicy, load_policy
from mgf_mot.provisional_force import ProvisionalForceMapConfig
from mgf_mot.tracks import BackendProvenance, ProjectTrack
from mgf_mot.trajectory import (
    TrajectoryConfig,
    TrajectoryInitialState,
    integrate_analytic_test_trajectory,
)
from scripts.run_provisional_trajectory_ensemble import run

CONFIG_PATH = (
    Path(__file__).parents[1]
    / "configs"
    / "rodriguez_chirp_to_3_plus_1_handoff.yaml"
)


@pytest.fixture
def criteria() -> OutcomeCriteria:
    return OutcomeCriteria(
        max_position=0.05,
        max_speed=0.05,
        final_dwell_window_s=1.0,
        min_dwell_samples=50,
        required_dwell_fraction=1.0,
        hard_escape_position=2.0,
        hard_speed=6.0,
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


def test_damped_harmonic_motion_has_bounded_final_state(criteria) -> None:
    result = integrate_analytic_test_trajectory(
        TrajectoryInitialState((1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        TrajectoryConfig(0.0, 5.0, 0.01),
        lambda _t, position, velocity: -4.0 * position - 3.0 * velocity,
        model_name="damped_harmonic_motion",
    )
    outcome = classify_trajectory(result, criteria)
    assert outcome.label is OutcomeLabel.BOUNDED_FINAL_STATE
    assert outcome.dwell_sample_count >= criteria.min_dwell_samples
    assert outcome.dwell_in_bounds_fraction == 1.0


def test_fast_zero_force_motion_is_escaped(criteria) -> None:
    result = integrate_analytic_test_trajectory(
        TrajectoryInitialState((0.0, 0.0, 0.0), (5.0, 0.0, 0.0)),
        TrajectoryConfig(0.0, 1.0, 0.01),
        lambda _t, _position, _velocity: np.zeros(3),
        model_name="fast_zero_force_motion",
    )
    outcome = classify_trajectory(result, criteria)
    assert outcome.label is OutcomeLabel.ESCAPED
    assert "hard escape bound" in outcome.numerical_reason


def test_trajectory_shorter_than_dwell_window_is_unresolved(criteria) -> None:
    result = integrate_analytic_test_trajectory(
        TrajectoryInitialState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        TrajectoryConfig(0.0, 0.5, 0.01),
        lambda _t, _position, _velocity: np.zeros(3),
        model_name="short_zero_force_motion",
    )
    outcome = classify_trajectory(result, criteria)
    assert outcome.label is OutcomeLabel.UNRESOLVED
    assert "shorter than required dwell window" in outcome.numerical_reason


def test_nonfinite_trajectory_is_invalid(criteria) -> None:
    result = SimpleNamespace(
        times_s=np.asarray((0.0, 1.0)),
        positions=np.asarray(((0.0, 0.0, 0.0), (np.nan, 0.0, 0.0))),
        velocities=np.zeros((2, 3)),
    )
    outcome = classify_trajectory(result, criteria)
    assert outcome.label is OutcomeLabel.INVALID
    assert "NaN or nonfinite" in outcome.numerical_reason


def test_final_point_and_center_crossing_do_not_bypass_dwell_window() -> None:
    result = SimpleNamespace(
        times_s=np.asarray((0.0, 1.0, 2.0, 3.0)),
        positions=np.asarray(
            (
                (0.5, 0.0, 0.0),
                (0.4, 0.0, 0.0),
                (0.3, 0.0, 0.0),
                (0.0, 0.0, 0.0),
            )
        ),
        velocities=np.zeros((4, 3)),
    )
    outcome = classify_trajectory(
        result,
        OutcomeCriteria(
            max_position=0.1,
            max_speed=0.1,
            final_dwell_window_s=2.0,
            min_dwell_samples=3,
            hard_escape_position=1.0,
        ),
    )
    assert outcome.label is OutcomeLabel.UNRESOLVED
    assert outcome.dwell_sample_count == 3
    assert outcome.dwell_in_bounds_count == 1
    assert outcome.dwell_in_bounds_fraction == pytest.approx(1.0 / 3.0)


def _ensemble_inputs():
    initial_states = (
        TrajectoryInitialState((0.0, 0.0, 0.05), (0.0, 0.0, -0.05)),
        TrajectoryInitialState((0.0, 0.0, 0.05), (0.0, 0.0, 0.0)),
        TrajectoryInitialState((0.0, 0.0, 0.05), (0.0, 0.0, 0.05)),
    )
    trajectory_config = TrajectoryConfig(0.0, 0.0014, 0.0003)
    outcome_criteria = OutcomeCriteria(
        max_position=0.1,
        max_speed=0.1,
        final_dwell_window_s=0.0002,
        min_dwell_samples=2,
        hard_escape_position=0.5,
        hard_speed=0.5,
    )
    return initial_states, trajectory_config, outcome_criteria


def test_ensemble_preserves_order_event_and_component_activity(
    handoff_policy, lightweight_provisional_backend
) -> None:
    initial_states, trajectory_config, outcome_criteria = _ensemble_inputs()
    ensemble = run_trajectory_ensemble(
        initial_states,
        handoff_policy,
        lightweight_provisional_backend,
        ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
        trajectory_config,
        outcome_criteria,
    )
    assert tuple(member.initial_state for member in ensemble.members) == initial_states
    assert ensemble.metadata.replication_valid is False
    assert ensemble.metadata.track is ProjectTrack.PROVISIONAL
    for member in ensemble.members:
        assert member.provenance.initial_state == member.initial_state
        assert member.provenance.replication_valid is False
        assert member.provenance.outcome_label == member.outcome.label
        assert member.integration_status == "completed"
        trajectory = member.trajectory
        assert trajectory is not None
        tau = handoff_policy.handoff_time_s
        assert np.any(trajectory.times_s == tau)
        assert trajectory.metadata.encountered_event_times_s == (tau,)
        assert not trajectory.component_active[trajectory.times_s < tau, 3].any()
        assert trajectory.component_active[trajectory.times_s >= tau, 3].all()


def test_exact_track_cannot_use_ensemble_path(handoff_policy) -> None:
    initial_states, trajectory_config, outcome_criteria = _ensemble_inputs()
    exact_like = build_mgf_validation_model_from_sources()
    with pytest.raises(MgFBackendCapabilityError, match="Track P provisional backend"):
        run_trajectory_ensemble(
            initial_states,
            handoff_policy,
            exact_like,  # type: ignore[arg-type]
            ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
            trajectory_config,
            outcome_criteria,
        )


def test_ensemble_requires_explicit_opt_in(
    handoff_policy, lightweight_provisional_backend
) -> None:
    initial_states, trajectory_config, outcome_criteria = _ensemble_inputs()
    with pytest.raises(MgFBackendCapabilityError, match="explicit_provisional_opt_in"):
        run_trajectory_ensemble(
            initial_states,
            handoff_policy,
            lightweight_provisional_backend,
            ProvisionalForceMapConfig(),
            trajectory_config,
            outcome_criteria,
        )


def test_run_006_outputs_are_labeled_and_non_replication_valid(tmp_path) -> None:
    record = run(tmp_path, save_plot=False)
    for key in ("arrays_path", "metadata_path", "report_path"):
        path = record[key]
        assert path.parent == tmp_path
        assert OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL in path.name

    metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["label"] == OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL
    assert OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL in metadata["title"]
    assert metadata["replication_valid"] is False
    assert metadata["force_ready"] is False
    assert metadata["beam_model"] == "infinite_plane_wave"
    assert metadata["criteria_status"] == "provisional_engineering_defined"
    assert metadata["event_time_exact_in_all_members"] is True
    assert metadata["initial_state_order_preserved"] is True
    assert metadata["arrays_finite"] is True
    assert len(metadata["members"]) == 3
    for index, member in enumerate(metadata["members"]):
        assert member["index"] == index
        assert member["label"] == OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL
        assert OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL in member["title"]
        assert member["provenance"]["replication_valid"] is False
        assert member["component_4_active_before_handoff"] is False
        assert member["component_4_active_at_and_after_handoff"] is True

    analytic_labels = {
        example["case"]: example["outcome"]["label"]
        for example in metadata["analytic_examples"]
    }
    assert analytic_labels == {
        "damped_bounded": "BOUNDED_FINAL_STATE",
        "fast_escaped": "ESCAPED",
        "short_unresolved": "UNRESOLVED",
        "nonfinite_invalid": "INVALID",
        "center_crossing_not_bounded": "UNRESOLVED",
    }
    arrays = np.load(record["arrays_path"])
    assert arrays["positions"].shape[0] == 3
    assert np.any(arrays["times_s"] == 0.001)
    assert np.isfinite(arrays["positions"]).all()
    assert np.isfinite(arrays["velocities"]).all()
    assert np.isfinite(arrays["forces"]).all()

    report = record["report_path"].read_text(encoding="utf-8")
    for heading in (line for line in report.splitlines() if line.startswith("#")):
        assert OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL in heading
    assert "criteria are provisional and engineering-defined" in report
    assert "not equivalent to physical MOT capture" in report
    assert "Exact MgF force readiness remains blocked" in report
    assert "Infinite plane waves were used" in report
    assert "No Gaussian beam envelope or molecular source distribution" in report
    assert "No capture velocity was calculated" in report
    assert "No physical conclusions" in report


def test_outcome_module_has_no_threshold_or_forbidden_public_apis() -> None:
    import mgf_mot.outcomes as outcomes

    forbidden = (
        "capture_velocity",
        "threshold_search",
        "gaussian",
        "distribution",
        "optimizer",
        "optimiser",
    )
    public_names = [name.lower() for name in dir(outcomes) if not name.startswith("_")]
    for word in forbidden:
        assert not any(word in name for name in public_names)
