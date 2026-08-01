import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.mgf_backend import (
    MgFBackendCapabilityError,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.named_protocol import (
    REQUIRED_PROTOCOL_LABELS,
    load_rodriguez_named_trajectory_protocol,
)
from mgf_mot.outcomes import OutcomeLabel, run_trajectory_ensemble
from mgf_mot.policies import ChirpToTrapHandoffPolicy, load_policy
from mgf_mot.provisional_force import ProvisionalForceMapConfig
from scripts.run_provisional_named_trajectories import (
    NAMED_TRAJECTORY_PROTOCOL_LABEL,
    run,
)

REPO_ROOT = Path(__file__).parents[1]
PROTOCOL_PATH = REPO_ROOT / "configs" / "rodriguez_named_trajectory_protocol.yaml"


@pytest.fixture
def protocol():
    return load_rodriguez_named_trajectory_protocol(PROTOCOL_PATH)


def test_protocol_initial_position_and_direction_are_exact(protocol) -> None:
    assert protocol.initial_position_m == (-0.05, 0.0, 0.0)
    assert protocol.labels == REQUIRED_PROTOCOL_LABELS
    assert protocol.label == NAMED_TRAJECTORY_PROTOCOL_LABEL
    states = protocol.initial_states()
    assert len(states) == 5
    for state in states:
        assert state.position == (-0.05, 0.0, 0.0)
        assert state.velocity[0] > 0.0
        assert state.velocity[1:] == (0.0, 0.0)


def test_named_velocities_preserve_exact_gamma_over_k_values(protocol) -> None:
    assert tuple(
        item.gamma_over_k for item in protocol.named_velocities
    ) == (2.0, 4.0, 6.0, 7.5, 9.0)
    assert tuple(
        item.velocity_m_s for item in protocol.named_velocities
    ) == (15.06, 30.12, 45.18, 56.475, 67.77)
    for item in protocol.named_velocities:
        assert item.velocity_m_s == pytest.approx(
            item.gamma_over_k * 7.53, abs=1e-12
        )


def test_protocol_apparatus_and_units_are_explicit(protocol) -> None:
    assert protocol.simulation_duration_s == 0.020
    assert protocol.time_step_s == 0.0001
    assert protocol.magnetic_gradient_t_m == 0.2
    assert protocol.normalized_gradient_scale == 1.0
    assert protocol.total_laser_power_w == 1.0
    assert protocol.power_allocation_status == "unresolved_no_conversion"
    assert protocol.pre_handoff_saturations == (1.45, 1.45, 2.89, 0.0)
    assert protocol.post_handoff_saturations == (1.45, 1.45, 2.17, 0.72)
    trajectory_config = protocol.trajectory_config()
    assert trajectory_config.position_unit == "m"
    assert trajectory_config.velocity_unit == "m/s"


def test_gaussian_mode_is_explicit_and_exact_track_is_rejected(protocol) -> None:
    gaussian_config = load_gaussian_envelope_config(
        REPO_ROOT / protocol.gaussian_config_path
    )
    beam_set = build_rodriguez_gaussian_beam_set(
        gaussian_config, protocol.post_handoff_saturations
    )
    force_config = ProvisionalForceMapConfig(
        explicit_provisional_opt_in=True,
        beam_mode="elliptical_gaussian",
        gaussian_beam_set=beam_set,
        position_unit="m",
        magnetic_gradient_t_m=protocol.magnetic_gradient_t_m,
        normalized_gradient_scale=protocol.normalized_gradient_scale,
    )
    assert force_config.beam_mode == "elliptical_gaussian"
    policy = load_policy(REPO_ROOT / protocol.handoff_policy_config_path)
    assert isinstance(policy, ChirpToTrapHandoffPolicy)
    exact_like = build_mgf_validation_model_from_sources()
    with pytest.raises(MgFBackendCapabilityError, match="Track P provisional backend"):
        run_trajectory_ensemble(
            protocol.initial_states(),
            policy,
            exact_like,  # type: ignore[arg-type]
            force_config,
            protocol.trajectory_config(),
            protocol.outcome_criteria,
        )


def test_run_008_named_cases_are_finite_ordered_and_event_aware(tmp_path) -> None:
    record = run(tmp_path, save_plots=False)
    protocol = record["protocol"]
    ensemble = record["ensemble"]
    assert record["force_config"].beam_mode == "elliptical_gaussian"
    assert tuple(member.initial_state for member in ensemble.members) == (
        protocol.initial_states()
    )
    assert ensemble.metadata.replication_valid is False
    assert len(record["case_records"]) == 5

    for named_velocity, case_record, member in zip(
        protocol.named_velocities, record["case_records"], ensemble.members
    ):
        assert case_record["named_velocity"] == named_velocity
        trajectory = member.trajectory
        assert trajectory is not None
        assert np.isfinite(trajectory.times_s).all()
        assert np.isfinite(trajectory.positions).all()
        assert np.isfinite(trajectory.velocities).all()
        assert np.isfinite(trajectory.forces).all()
        tau = record["policy"].handoff_time_s
        assert np.any(trajectory.times_s == tau)
        assert trajectory.metadata.encountered_event_times_s == (tau,)
        assert not trajectory.component_active[trajectory.times_s < tau, 3].any()
        assert trajectory.component_active[trajectory.times_s >= tau, 3].all()
        diagnostics = case_record["diagnostics"]
        assert diagnostics["initial_velocity_gamma_over_k"] == (
            named_velocity.gamma_over_k
        )
        assert diagnostics["initial_velocity_m_s"] == named_velocity.velocity_m_s
        assert diagnostics["trajectory_arrays_finite"] is True
        assert diagnostics["component_4_inactive_before_tau"] is True
        assert diagnostics["component_4_active_at_and_after_tau"] is True
        assert len(diagnostics["inside_position_bounds"]) == 3


def test_center_crossing_is_not_bounded_final_state(tmp_path) -> None:
    record = run(tmp_path, save_plots=False)
    for case_record in record["case_records"]:
        diagnostics = case_record["diagnostics"]
        assert diagnostics["crossed_x_zero"] is True
        assert diagnostics["outcome_label"] != OutcomeLabel.BOUNDED_FINAL_STATE.value
        assert diagnostics["remained_within_provisional_final_bounds"] is False
        assert diagnostics["center_crossing_without_bounded_final_state"] is True


def test_run_008_outputs_are_separate_labeled_and_non_replication_valid(
    tmp_path,
) -> None:
    record = run(tmp_path, save_plots=False)
    assert NAMED_TRAJECTORY_PROTOCOL_LABEL in record["metadata_path"].name
    assert NAMED_TRAJECTORY_PROTOCOL_LABEL in record["report_path"].name
    arrays_paths = [
        case_record["arrays_path"] for case_record in record["case_records"]
    ]
    assert len(arrays_paths) == len(set(arrays_paths)) == 5
    for path in arrays_paths:
        assert path.exists()
        assert NAMED_TRAJECTORY_PROTOCOL_LABEL in path.name
        arrays = np.load(path)
        assert np.isfinite(arrays["positions_m"]).all()
        assert np.isfinite(arrays["velocities_m_s"]).all()
        assert np.isfinite(arrays["normalized_forces"]).all()

    metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["label"] == NAMED_TRAJECTORY_PROTOCOL_LABEL
    assert NAMED_TRAJECTORY_PROTOCOL_LABEL in metadata["title"]
    assert metadata["replication_valid"] is False
    assert metadata["force_ready"] is False
    assert metadata["beam_mode"] == "elliptical_gaussian"
    assert metadata["total_power_conversion_performed"] is False
    assert metadata["initial_state_order_preserved"] is True
    assert len(metadata["case_records"]) == 5
    for case in metadata["case_records"]:
        assert case["label"] == NAMED_TRAJECTORY_PROTOCOL_LABEL
        assert NAMED_TRAJECTORY_PROTOCOL_LABEL in case["title"]
        case_metadata = json.loads(
            (tmp_path / case["metadata_path"]).read_text(encoding="utf-8")
        )
        assert case_metadata["label"] == NAMED_TRAJECTORY_PROTOCOL_LABEL
        assert case_metadata["replication_valid"] is False
        assert case_metadata["backend_provenance"]["replication_valid"] is False
        assert (
            case_metadata["member_provenance"]["label"]
            == NAMED_TRAJECTORY_PROTOCOL_LABEL
        )
        assert (
            case_metadata["trajectory_metadata"]["label"]
            == NAMED_TRAJECTORY_PROTOCOL_LABEL
        )
        assert (
            case_metadata["outcome"]["artifact_label"]
            == NAMED_TRAJECTORY_PROTOCOL_LABEL
        )

    report = record["report_path"].read_text(encoding="utf-8")
    for heading in (line for line in report.splitlines() if line.startswith("#")):
        assert NAMED_TRAJECTORY_PROTOCOL_LABEL in heading
    assert "end-to-end provisional apparatus/plumbing test" in report
    assert "exact excited-state Hamiltonian remains unresolved" in report
    assert "Outcomes are not physical capture claims" in report
    assert "No capture boundary or maximum capture velocity" in report
    assert "No molecular source distribution" in report
    assert "No stochastic recoil or diffusion" in report
    assert "not converted through a guessed allocation" in report
    assert "No conclusion should be drawn about agreement with Rodriguez" in report


def test_named_protocol_adds_no_search_or_forbidden_public_api() -> None:
    import mgf_mot.named_protocol as named_protocol

    forbidden = (
        "capture_velocity",
        "threshold_search",
        "boundary_search",
        "distribution",
        "stochastic",
        "optimizer",
        "optimiser",
    )
    public_names = [
        name.lower() for name in dir(named_protocol) if not name.startswith("_")
    ]
    for word in forbidden:
        assert not any(word in name for name in public_names)
