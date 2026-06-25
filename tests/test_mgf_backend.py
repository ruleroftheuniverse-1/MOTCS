from dataclasses import replace

import numpy as np
import pytest

from scripts.validate_mgf_hamiltonian import main as validate_mgf_hamiltonian_main
from mgf_mot.mgf_backend import (
    ApproximationMode,
    ExactBackendMode,
    MgFBackendCapabilityError,
    analyze_mgf_exact_backend_feasibility,
    build_mgf_approximate_hamiltonian_from_sources,
    build_mgf_hamiltonian_from_sources,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.spectroscopy import ALL_SPECTROSCOPY_CONSTANTS


@pytest.fixture(scope="module")
def model():
    return build_mgf_validation_model_from_sources()


def test_rodriguez_state_counts_and_dipole_shape(model) -> None:
    assert model.ground_state_count == 12
    assert model.excited_state_count == 4
    assert model.transition_dipole_q.shape == (3, 12, 4)
    assert np.isfinite(model.transition_dipole_q).all()


def test_ground_level_order_and_degeneracies(model) -> None:
    assert [level.label for level in model.ground_levels] == [
        "lower_F1",
        "F0",
        "upper_F1",
        "F2",
    ]
    assert [level.F for level in model.ground_levels] == [1, 0, 1, 2]
    assert [level.degeneracy for level in model.ground_levels] == [3, 1, 3, 5]


def test_ground_spacings_match_rodriguez(model) -> None:
    energies = [level.relative_energy_mhz for level in model.ground_levels]
    spacings = np.diff(energies)
    assert spacings == pytest.approx([109.0, 120.0, 9.0], abs=1.0)


def test_excited_energies_remain_explicitly_unknown(model) -> None:
    assert model.excited_energies_mhz == (None, None, None, None)
    assert not model.is_complete_hamiltonian
    assert any("d term" in limitation for limitation in model.backend_limitations)


def test_complete_factory_fails_on_backend_limitations() -> None:
    with pytest.raises(MgFBackendCapabilityError) as exc_info:
        build_mgf_hamiltonian_from_sources()
    message = str(exc_info.value)
    assert "excited_backend_b" in message
    assert "excited_backend_c" in message
    assert "d term" in message


def test_complete_factory_exact_mode_fails_by_default() -> None:
    with pytest.raises(MgFBackendCapabilityError, match="complete MgF Hamiltonian"):
        build_mgf_hamiltonian_from_sources(approximation_mode=ApproximationMode.NONE)


def test_approximation_mode_must_be_explicit() -> None:
    with pytest.raises(MgFBackendCapabilityError, match="requires an explicit"):
        build_mgf_approximate_hamiltonian_from_sources()


def test_explicit_approximation_reports_collapsed_physics_and_no_defaults() -> None:
    approximate = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    assert approximate.report.mode is ApproximationMode.COLLAPSED_PYLCP_ASTATE
    assert not approximate.report.force_ready_by_default
    assert approximate.report.undocumented_defaults_used == ()
    report_text = "\n".join(approximate.report.missing_or_collapsed_terms)
    assert "d=135 MHz is omitted" in report_text
    assert "b_F+2c/3 is collapsed" in report_text
    assert "gL, gl, glprime, gr, greprime, and gN are set to 0" in report_text
    assert approximate.hamiltonian.ns == [12, 4]


def test_exact_backend_feasibility_reports_precise_blockers_and_no_defaults() -> None:
    feasibility = analyze_mgf_exact_backend_feasibility()
    assert feasibility.mode is ExactBackendMode.LOCAL_EXTENDED_ASTATE
    assert not feasibility.can_construct
    assert not feasibility.force_ready
    assert feasibility.undocumented_defaults_used == ()
    assert feasibility.missing_source_constants == ()
    blocker_text = "\n".join(feasibility.blockers)
    assert "operator matrix element is not implemented" in blocker_text
    assert "gL, gl, glprime, gr, greprime, and gN" in blocker_text
    assert "g=+0.001" in blocker_text


def test_exact_backend_mode_fails_clearly_after_feasibility_check() -> None:
    with pytest.raises(MgFBackendCapabilityError) as exc_info:
        build_mgf_hamiltonian_from_sources(
            exact_backend_mode=ExactBackendMode.LOCAL_EXTENDED_ASTATE
        )
    message = str(exc_info.value)
    assert "local_extended_astate" in message
    assert "Doppelbauer" in message
    assert "Zeeman" in message


def test_exact_backend_mode_reports_missing_required_constants_first() -> None:
    constants = dict(ALL_SPECTROSCOPY_CONSTANTS)
    constants["excited_hyperfine_d"] = replace(
        constants["excited_hyperfine_d"],
        value=None,
        status="unknown",
        note="deliberately absent for test",
    )
    feasibility = analyze_mgf_exact_backend_feasibility(constants)
    assert [constant.name for constant in feasibility.missing_source_constants] == [
        "excited_hyperfine_d"
    ]
    with pytest.raises(MgFBackendCapabilityError) as exc_info:
        build_mgf_hamiltonian_from_sources(
            constants,
            exact_backend_mode=ExactBackendMode.LOCAL_EXTENDED_ASTATE,
        )
    assert "excited_hyperfine_d" in str(exc_info.value)


def test_exact_backend_and_approximation_modes_are_mutually_exclusive() -> None:
    with pytest.raises(MgFBackendCapabilityError, match="either an approximation_mode"):
        build_mgf_hamiltonian_from_sources(
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            exact_backend_mode=ExactBackendMode.LOCAL_EXTENDED_ASTATE,
        )


def test_validation_output_prints_exact_and_excited_assumptions(capsys) -> None:
    validate_mgf_hamiltonian_main()
    output = capsys.readouterr().out
    assert "Exact backend feasibility:" in output
    assert "mode: local_extended_astate" in output
    assert "Rodriguez excited g assumption: 0.001" in output
    assert "Doppelbauer independent excited hyperfine d=135 MHz" in output
    assert "force-ready: False" in output


def test_required_ground_value_is_never_replaced_by_default() -> None:
    constants = dict(ALL_SPECTROSCOPY_CONSTANTS)
    constants["ground_spin_rotation_gamma"] = replace(
        constants["ground_spin_rotation_gamma"],
        value=None,
        status="unknown",
        note="deliberately absent for test",
    )
    with pytest.raises(ValueError, match="ground_spin_rotation_gamma is unknown"):
        build_mgf_validation_model_from_sources(constants)
