from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.accepted_trajectory import (
    RUN011_LABEL,
    IntegrationTerminationStatus,
    InterpolatedRateEquationTrajectoryForce,
    integrate_accepted_force_field_trajectory,
)
from mgf_mot.force_units import normalized_force_to_acceleration_m_s2, normalized_force_to_newtons
from mgf_mot.mgf_backend import MgFBackendCapabilityError
from mgf_mot.named_protocol import load_rodriguez_named_trajectory_protocol
from mgf_mot.outcomes import OutcomeLabel, classify_trajectory
from mgf_mot.policies import load_policy
from mgf_mot.tracks import ProjectTrack
from mgf_mot.trajectory import TrajectoryInitialState


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
METADATA_PATH = OUTPUT_DIR / f"{RUN011_LABEL}_metadata.json"
REPORT_PATH = OUTPUT_DIR / "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_run_011.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_accepted_provisional_named_trajectories.py"


@pytest.fixture(scope="module")
def adapter():
    return InterpolatedRateEquationTrajectoryForce(
        repo_root=REPO_ROOT,
        explicit_provisional_opt_in=True,
        acknowledge_midpoint_not_measured=True,
    )


@pytest.fixture(scope="module")
def policy():
    return load_policy(REPO_ROOT / "configs" / "rodriguez_chirp_to_3_plus_1_handoff.yaml")


@pytest.fixture(scope="module")
def protocol():
    return load_rodriguez_named_trajectory_protocol(
        REPO_ROOT / "configs" / "rodriguez_named_trajectory_protocol.yaml"
    )


@pytest.fixture(scope="module")
def metadata():
    assert METADATA_PATH.exists(), "run the dedicated Run 011 script first"
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def test_adapter_requires_midpoint_acknowledgment_track_p_and_accepted_models(adapter) -> None:
    assert adapter.backend.status.ground_zeeman_convention == "project_energy_slope_corrected"
    assert adapter.backend.status.excited_zeeman_model == "rodriguez_effective_g_0p001"
    assert adapter.backend.status.excited_hyperfine_model == "source_aligned_effective_fprime_splitting"
    assert adapter.backend.status.excited_hyperfine_splitting_mhz == 0.5
    assert adapter.backend.status.replication_valid is False
    with pytest.raises(MgFBackendCapabilityError, match="acknowledgment"):
        InterpolatedRateEquationTrajectoryForce(
            repo_root=REPO_ROOT, explicit_provisional_opt_in=True,
            acknowledge_midpoint_not_measured=False,
        )
    with pytest.raises(MgFBackendCapabilityError, match="Track E"):
        InterpolatedRateEquationTrajectoryForce(
            repo_root=REPO_ROOT, explicit_provisional_opt_in=True,
            acknowledge_midpoint_not_measured=True, track=ProjectTrack.EXACT,
        )
    assert "backend" not in inspect.signature(InterpolatedRateEquationTrajectoryForce).parameters


def test_force_selection_handoff_and_si_conversion_are_exactly_once(adapter, policy) -> None:
    before = adapter.evaluate(policy, np.nextafter(0.001, -np.inf), -0.01, 5.0)
    at = adapter.evaluate(policy, 0.001, -0.01, 5.0)
    assert before.field_selection == "pre_handoff_chirp_3"
    assert at.field_selection == "post_handoff_trap_3_plus_1"
    assert before.component_active == (True, True, True, False)
    assert at.component_active == (True, True, True, True)
    assert before.acceleration_x_m_s2 == pytest.approx(
        float(normalized_force_to_acceleration_m_s2(before.normalized_force_x, adapter.force_units))
    )
    assert before.force_x_n == pytest.approx(
        float(normalized_force_to_newtons(before.normalized_force_x, adapter.force_units))
    )
    assert adapter.force_units.conversion_count == 1


def test_event_aware_integration_lands_exactly_at_handoff(adapter, policy, protocol) -> None:
    result = integrate_accepted_force_field_trajectory(
        adapter=adapter, policy=policy, initial_state=protocol.initial_states()[0],
        duration_s=0.0012, timestep_s=0.0003,
    )
    assert result.handoff_event_times_s == (0.001,)
    index = int(np.flatnonzero(result.times_s == 0.001)[0])
    assert result.field_selections[index - 1] == "pre_handoff_chirp_3"
    assert result.field_selections[index] == "post_handoff_trap_3_plus_1"


def test_domain_exit_stops_at_exact_boundary_and_is_not_an_outcome(adapter, policy, protocol) -> None:
    result = integrate_accepted_force_field_trajectory(
        adapter=adapter, policy=policy,
        initial_state=TrajectoryInitialState(position=(0.059, 0, 0), velocity=(50, 0, 0)),
        duration_s=0.002, timestep_s=0.0001,
    )
    assert result.termination_status is IntegrationTerminationStatus.FORCE_FIELD_DOMAIN_EXIT
    assert result.domain_exit is not None
    assert result.domain_exit.violated_coordinate == "position_m"
    assert result.positions[-1, 0] == pytest.approx(0.06, abs=1e-14)
    outcome = classify_trajectory(result, protocol.outcome_criteria)
    assert outcome.label in (OutcomeLabel.UNRESOLVED, OutcomeLabel.ESCAPED)
    assert result.domain_exit.message != outcome.numerical_reason


def test_center_crossing_alone_does_not_imply_bounded(protocol) -> None:
    class Result:
        times_s = np.linspace(0, 0.02, 201)
        positions = np.column_stack((np.linspace(-0.05, 0.05, 201), np.zeros((201, 2))))
        velocities = np.column_stack((np.full(201, 5.0), np.zeros((201, 2))))
    outcome = classify_trajectory(Result(), protocol.outcome_criteria)
    assert outcome.label is not OutcomeLabel.BOUNDED_FINAL_STATE


def test_run011_named_order_convergence_pathwise_and_authorization(metadata) -> None:
    assert metadata["gate"] == "PROVISIONAL_NAMED_TRAJECTORY_GO"
    assert metadata["named_velocity_order_gamma_over_k"] == [2.0, 4.0, 6.0, 7.5, 9.0]
    assert metadata["baseline_timestep_s"] == 0.0001
    assert metadata["refined_timestep_s"] == 0.00005
    assert all(row["passed"] for row in metadata["convergence"].values())
    assert metadata["pathwise_interpolation_gate"] == "PATHWISE_INTERPOLATION_PASS"
    assert metadata["provisional_static_authorized"] is True
    assert metadata["provisional_force_field_authorized"] is True
    assert metadata["provisional_named_trajectory_authorized"] is True
    assert metadata["capture_authorized"] is False
    assert metadata["capture_velocity_authorized"] is False
    assert metadata["optimizer_authorized"] is False
    assert metadata["exact_replication_valid"] is False
    assert metadata["exact_track_blocked"] is True
    assert all(metadata["acceptance_checks"].values())


def test_run011_outputs_are_finite_labeled_and_historical_run008_is_unchanged(metadata) -> None:
    assert metadata["historical_run008_unchanged"] is True
    assert metadata["historical_run008_hashes_before"] == metadata["historical_run008_hashes_after"]
    assert set(metadata["termination_statuses"].values()) <= {
        "COMPLETED_TIME_INTERVAL", "FORCE_FIELD_DOMAIN_EXIT", "NUMERICAL_FAILURE"
    }
    for name, files in metadata["files"].items():
        for filename in files.values():
            assert all(stamp in filename for stamp in (
                "PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION",
                "ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY", "RUN_011",
            ))
        with np.load(OUTPUT_DIR / files["arrays"]) as arrays:
            for key in ("times_s", "positions_m", "velocities_m_s", "normalized_force_x", "force_x_n", "acceleration_x_m_s2", "cumulative_impulse_x_n_s"):
                assert np.isfinite(arrays[key]).all()
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(RUN011_LABEL in line for line in report.splitlines() if line.startswith("#"))
    assert "not scientifically meaningful" in report


def test_direct_path_samples_do_not_alter_trajectories_and_forbidden_apis_absent(metadata) -> None:
    pathwise = json.loads((OUTPUT_DIR / metadata["pathwise_validation_file"]).read_text(encoding="utf-8"))
    for record in pathwise["trajectories"].values():
        assert record["direct_validation_did_not_alter_trajectory"] is True
        assert record["gate"] == "PATHWISE_INTERPOLATION_PASS"
        assert record["records"]
        assert all("absolute_error" in row and "error_over_force_range" in row for row in record["records"])
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "capture_velocity(", "threshold_search(", "run_trajectory_ensemble(",
        "source_distribution(", "stochastic_diffusion(", "optimizer(",
    ):
        assert forbidden not in source
