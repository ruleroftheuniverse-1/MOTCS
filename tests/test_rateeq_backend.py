from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.force_units import (
    acceleration_m_s2_to_normalized_force,
    normalized_force_to_acceleration_m_s2,
)
from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.mgf_backend import ApproximationMode, MgFBackendCapabilityError
from mgf_mot.policies import load_policy
from mgf_mot.provisional_force import TOY_HEURISTIC_FORCE_BACKEND
from mgf_mot.rateeq_backend import (
    RATEEQ_STATIC_LABEL,
    RateEquationBackendConfig,
)
from mgf_mot.tracks import ProjectTrack


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_provisional_pylcp_rateeq_static_validation.py"
spec = importlib.util.spec_from_file_location("run009", SCRIPT_PATH)
run009 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(run009)


@pytest.fixture(scope="module")
def run_record(tmp_path_factory):
    return run009.run(
        tmp_path_factory.mktemp("run009"),
        save_plots=False,
        positions_m=np.array([-0.002, 0.0, 0.002]),
        velocities_m_s=np.array([-1.0, 0.0, 1.0]),
    )


def _systems(backend):
    static3 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3.yaml")
    static31 = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    gaussian_config = load_gaussian_envelope_config(
        REPO_ROOT / "configs" / "rodriguez_gaussian_baseline.yaml"
    )
    gaussian3 = build_rodriguez_gaussian_beam_set(
        gaussian_config, (1.45, 1.45, 2.89, 0.0)
    )
    return (
        static3,
        static31,
        gaussian3,
        backend.build_optical_system(
            static3.sample(0.0), policy_name=static3.name, beam_mode="plane_wave"
        ),
        backend.build_optical_system(
            static31.sample(0.0), policy_name=static31.name, beam_mode="plane_wave"
        ),
        backend.build_optical_system(
            static3.sample(0.0),
            policy_name=static3.name,
            beam_mode="elliptical_gaussian",
            gaussian_beam_set=gaussian3,
        ),
    )


def test_toy_backend_is_plumbing_only() -> None:
    assert TOY_HEURISTIC_FORCE_BACKEND.force_model == "toy_heuristic_spring_damping"
    assert TOY_HEURISTIC_FORCE_BACKEND.physics_valid is False
    assert TOY_HEURISTIC_FORCE_BACKEND.physics_scope == "analytic_and_interface_plumbing_only"
    assert "Run 008B" in TOY_HEURISTIC_FORCE_BACKEND.supersedes_run_outputs


def test_rateeq_requires_explicit_collapsed_track_p_opt_in() -> None:
    with pytest.raises(MgFBackendCapabilityError, match="explicit provisional opt-in"):
        RateEquationBackendConfig(
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
        )
    with pytest.raises(MgFBackendCapabilityError, match="Track P"):
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            track=ProjectTrack.EXACT,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
        )
    with pytest.raises(MgFBackendCapabilityError, match="COLLAPSED_PYLCP_ASTATE"):
        RateEquationBackendConfig(explicit_provisional_opt_in=True)


def test_combined_optical_system_and_component_4(run_record) -> None:
    _, _, _, system3, system31, _ = _systems(run_record["backend"])
    assert system3.combined_solve is True
    assert system31.combined_solve is True
    assert system3.active_component_count == 18
    assert system31.active_component_count == 24
    assert not any(component == 4 for _, component in system3.pylcp_beam_index)
    assert sum(component == 4 for _, component in system31.pylcp_beam_index) == 6
    assert tuple(system3.component_order) == (1, 2, 3, 4)


def test_gaussian_envelopes_scale_each_beam_before_combined_solve(run_record) -> None:
    _, _, gaussian_set, _, _, system = _systems(run_record["backend"])
    point = np.array([0.025, 0.0, 0.0])
    beam_names = tuple(item.name for item in system.physical_beams)
    for index, (beam_name, component_id) in enumerate(system.pylcp_beam_index):
        peak = system.physical_beams[beam_names.index(beam_name)].components[
            component_id - 1
        ].peak_saturation
        expected = peak * gaussian_set.envelopes(point)[beam_name]
        assert system.pylcp_beams.beam_vector[index].intensity(point) == pytest.approx(
            expected
        )
    assert system.per_beam_envelope_before_solve is True
    assert system.post_sum_envelope_used is False


def test_required_force_differences_and_origin_agreement(run_record) -> None:
    comparisons = run_record["metadata"]["comparisons"]
    assert comparisons["three_vs_three_plus_one_different"] is True
    assert comparisons["component_4_changes_optical_system"] is True
    assert comparisons["chirp_minus_8_vs_minus_4p5_different"] is True
    assert comparisons["chirp_minus_4p5_vs_minus_1_different"] is True
    assert comparisons["plane_gaussian_three_agree_at_origin"] is True
    assert comparisons["plane_gaussian_three_differ_away"] is True
    assert comparisons["origin_symmetry_all_cases"] is True


def test_one_population_solve_exposes_groupable_contributions(run_record) -> None:
    backend = run_record["backend"]
    _, _, _, _, system31, _ = _systems(backend)
    result = backend.force_at(np.zeros(3), np.array([1.0, 0.0, 0.0]), system31)
    assert result.equilibrium_populations.shape == (16,)
    assert np.sum(result.equilibrium_populations) == pytest.approx(1.0)
    assert result.per_laser_normalized_force.shape == (3, 24)
    assert sum(result.per_component_normalized_force.values()) == pytest.approx(
        result.normalized_force
    )
    assert sum(result.per_physical_beam_normalized_force.values()) == pytest.approx(
        result.normalized_force
    )


def test_normalized_si_acceleration_round_trip_applies_scale_once(run_record) -> None:
    units = run_record["backend"].force_units
    normalized = np.array([0.01, -0.03, 1.0])
    acceleration = normalized_force_to_acceleration_m_s2(normalized, units)
    assert acceleration_m_s2_to_normalized_force(acceleration, units) == pytest.approx(
        normalized
    )
    metadata = run_record["metadata"]["force_units"]
    assert metadata["normalized_force_conversion_count"] == 0
    assert metadata["si_acceleration_conversion_count"] == 1


def test_run009_outputs_labeled_and_no_trajectory_or_capture(run_record) -> None:
    for key in ("arrays_path", "metadata_path", "report_path"):
        assert RATEEQ_STATIC_LABEL in run_record[key].name
    metadata = run_record["metadata"]
    assert metadata["replication_valid"] is False
    assert metadata["trajectory_integrations_performed"] == 0
    assert metadata["capture_results_calculated"] == 0
    assert metadata["hamiltonian_structure"]["ground_states"] == 12
    assert metadata["hamiltonian_structure"]["excited_states"] == 4
    assert metadata["hamiltonian_structure"]["dipole_shape"] == [3, 12, 4]
    report = run_record["report_path"].read_text(encoding="utf-8")
    assert all(
        RATEEQ_STATIC_LABEL in line
        for line in report.splitlines()
        if line.startswith("#")
    )
    assert "No trajectory was rerun" in report
    assert "no capture result was calculated" in report
    assert "remain physically uninterpretable" in report


def test_no_forbidden_or_trajectory_api_added() -> None:
    import mgf_mot.rateeq_backend as module

    forbidden = (
        "capture",
        "source_distribution",
        "stochastic",
        "optimizer",
        "integrate_trajectory",
        "run_trajectory",
    )
    public = [name.lower() for name in dir(module) if not name.startswith("_")]
    for term in forbidden:
        assert not any(term in name for name in public)
