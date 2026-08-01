from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.mgf_backend import ApproximationMode
from mgf_mot.policies import load_policy
from mgf_mot.rateeq_backend import (
    ProvisionalPylcpRateEquationBackend,
    RateEquationBackendConfig,
)
from mgf_mot.static_acceptance import (
    RUN009A_LABEL,
    centered_slope,
    decide_acceptance_gate,
    flip_policy_polarizations,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_provisional_rateeq_static_acceptance_audit.py"
spec = importlib.util.spec_from_file_location("run009a", SCRIPT_PATH)
run009a = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(run009a)


def test_flip_policy_polarizations_is_explicit_and_preserves_component_order() -> None:
    policy = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml")
    sample = policy.sample(0.0)
    flipped = flip_policy_polarizations(sample)
    assert flipped.component_order == (1, 2, 3, 4)
    assert tuple(component.component_id for component in flipped.components) == (1, 2, 3, 4)
    expected = {"sigma_plus": "sigma_minus", "sigma_minus": "sigma_plus"}
    assert tuple(component.polarization for component in flipped.components) == tuple(
        expected[component.polarization] for component in sample.components
    )


def test_centered_slope_and_gate_require_every_condition() -> None:
    assert centered_slope(np.array([-1.0, 0.0, 1.0]), np.array([2.0, 0.0, -2.0])) == -2.0
    go = decide_acceptance_gate({"one": True}, {"one": "failed one"})
    assert go.decision == "GO"
    assert go.trajectories_authorized is True
    no_go = decide_acceptance_gate(
        {"one": True, "two": False}, {"one": "failed one", "two": "failed two"}
    )
    assert no_go.decision == "NO-GO"
    assert no_go.diagnoses == ("failed two",)
    assert no_go.trajectories_authorized is False


def test_backend_solver_diagnostics_are_explicit() -> None:
    backend = ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
        )
    )
    policy = load_policy(REPO_ROOT / "configs" / "rodriguez_static_3.yaml")
    system = backend.build_optical_system(
        policy.sample(0.0), policy_name=policy.name, beam_mode="plane_wave"
    )
    result = backend.force_at(
        np.zeros(3), np.zeros(3), system, collect_solver_diagnostics=True
    )
    assert np.isfinite(result.equilibrium_populations).all()
    assert result.population_minimum >= -1e-10
    assert result.population_sum == pytest.approx(1.0, abs=1e-12)
    assert result.steady_state_residual_linf < 1e-12
    assert result.nullspace_dimension == 1
    assert result.equilibrium_solver == "pylcp_svd_nullspace"
    assert result.singular_solver_fallback_used is False


@pytest.fixture(scope="module")
def audit_smoke(tmp_path_factory):
    return run009a.run(
        tmp_path_factory.mktemp("run009a"),
        solver_stride=16,
        refinement_factor=2,
        chirp_velocity_axis_m_s=np.array([0.0, 10.0, 48.0, 85.0, 110.0]),
        save_plot=False,
    )


def test_run009a_audits_lab_x_and_returns_no_go(audit_smoke) -> None:
    metadata = audit_smoke["metadata"]
    coordinate = metadata["coordinate_audit"]
    assert coordinate["reported_force_component"] == "F_x"
    assert coordinate["position_vector_m"] == "[x, 0, 0]"
    assert coordinate["velocity_vector_m_s"] == "[v_x, 0, 0]"
    assert coordinate["forty_five_degree_doppler_projection_verified"] is True
    assert coordinate["not_z_map"] is True
    assert audit_smoke["gate"].decision == "NO-GO"
    assert audit_smoke["gate"].trajectories_authorized is False
    assert metadata["trajectory_integrations_performed"] == 0


def test_run009a_records_solver_reversal_chirp_gaussian_and_convergence(audit_smoke) -> None:
    metadata = audit_smoke["metadata"]
    health = metadata["solver_health"]
    assert health["populations_and_forces_finite"] is True
    assert health["nullspace_dimensions_observed"] == [1]
    assert health["singular_solver_fallback_count"] == 0
    assert metadata["tolerance_stability"]["passed"] is True
    assert set(metadata["reversal_audit"]["cases"]) == {
        "nominal",
        "polarization_flipped",
        "gradient_flipped",
        "both_flipped",
    }
    assert metadata["chirp_feature_audit"]["feature_velocity_decreases_with_less_negative_detuning"] is True
    assert metadata["gaussian_audit"]["center_agreement_at_nonzero_velocity"] is True
    assert metadata["gaussian_audit"]["not_mean_envelope_after_sum"] is True
    assert metadata["grid_convergence"]["passed"] is True


def test_run009a_outputs_are_labeled_and_static_only(audit_smoke) -> None:
    for key in ("metadata_path", "report_path"):
        assert RUN009A_LABEL in audit_smoke[key].name
    report = audit_smoke["report_path"].read_text(encoding="utf-8")
    assert all(
        RUN009A_LABEL in line
        for line in report.splitlines()
        if line.startswith("#")
    )
    assert "NO-GO" in report
    assert "Trajectory reconnection authorized by this audit: `False`" in report
    assert "runs no trajectory" in report


def test_static_acceptance_module_has_no_trajectory_or_capture_api() -> None:
    import mgf_mot.static_acceptance as module

    public = [name.lower() for name in dir(module) if not name.startswith("_")]
    for forbidden in ("integrate", "trajectory", "capture", "optimizer", "stochastic"):
        assert not any(forbidden in name for name in public)
