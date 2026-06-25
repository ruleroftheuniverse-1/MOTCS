import numpy as np
import pytest

from mgf_mot.mgf_backend import (
    ApproximationMode,
    MgFBackendCapabilityError,
    build_mgf_hamiltonian_from_sources,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.provisional_force import (
    FULL_WARNING_LABEL,
    NOT_REPLICATION_LABEL,
    PROVISIONAL_LABEL,
    ProvisionalForceMapConfig,
    diagnostic_configs,
    force_at,
    force_grid_1d,
    normalized_force_plot_spec,
)
from mgf_mot.tracks import ProjectTrack


@pytest.fixture(scope="module")
def provisional_backend():
    return build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )


def test_exact_track_cannot_produce_force_maps_while_blocked() -> None:
    exact_like = build_mgf_validation_model_from_sources()
    config = ProvisionalForceMapConfig(explicit_provisional_opt_in=True)
    with pytest.raises(MgFBackendCapabilityError, match="provisional track"):
        force_at(np.zeros(3), np.zeros(3), exact_like, config)


def test_no_default_call_path_silently_uses_approximation() -> None:
    with pytest.raises(MgFBackendCapabilityError, match="complete MgF Hamiltonian"):
        build_mgf_hamiltonian_from_sources()


def test_provisional_track_requires_explicit_opt_in(provisional_backend) -> None:
    config = ProvisionalForceMapConfig()
    with pytest.raises(MgFBackendCapabilityError, match="explicit_provisional_opt_in"):
        force_at(np.zeros(3), np.zeros(3), provisional_backend, config)


def test_provisional_backend_metadata_is_not_replication_valid(provisional_backend) -> None:
    provenance = provisional_backend.provenance
    assert provenance.track is ProjectTrack.PROVISIONAL
    assert provenance.backend_mode == "collapsed_pylcp_astate"
    assert not provenance.force_ready
    assert not provenance.replication_valid
    assert any(PROVISIONAL_LABEL in warning for warning in provenance.warnings)
    assert any(NOT_REPLICATION_LABEL in warning for warning in provenance.warnings)
    assert "excited_hyperfine_d operator" in provenance.omitted_terms
    assert any("b_F_plus_2c_over_3" in term for term in provenance.collapsed_terms)


def test_force_at_returns_warning_metadata(provisional_backend) -> None:
    config = ProvisionalForceMapConfig(explicit_provisional_opt_in=True)
    force, metadata = force_at(
        np.array([1.0, 0.0, 0.0]),
        np.array([0.5, 0.0, 0.0]),
        provisional_backend,
        config,
    )
    assert force.tolist() == pytest.approx([-1.1, 0.0, 0.0])
    assert metadata.track is ProjectTrack.PROVISIONAL
    assert not metadata.replication_valid
    assert not metadata.force_ready
    assert PROVISIONAL_LABEL in metadata.title
    assert NOT_REPLICATION_LABEL in metadata.title
    assert PROVISIONAL_LABEL in metadata.filename
    assert NOT_REPLICATION_LABEL in metadata.filename


def test_nominal_and_flip_diagnostics_have_expected_signs(provisional_backend) -> None:
    position = np.array([0.0, 0.0, 1.0])
    velocity = np.zeros(3)
    configs = diagnostic_configs()
    nominal, _ = force_at(position, velocity, provisional_backend, configs["nominal"])
    flip_pol, _ = force_at(
        position, velocity, provisional_backend, configs["flipped_polarization"]
    )
    flip_grad, _ = force_at(
        position, velocity, provisional_backend, configs["flipped_gradient"]
    )
    flip_both, _ = force_at(
        position, velocity, provisional_backend, configs["flipped_both"]
    )
    assert nominal[2] < 0
    assert flip_pol[2] > 0
    assert flip_grad[2] > 0
    assert flip_both[2] == pytest.approx(nominal[2])


def test_force_grid_and_plot_spec_include_warning_labels(provisional_backend) -> None:
    config = ProvisionalForceMapConfig(explicit_provisional_opt_in=True)
    grid = force_grid_1d(
        "z",
        np.array([-1.0, 0.0, 1.0]),
        np.array([0.0]),
        provisional_backend,
        config,
    )
    assert grid.forces.shape == (3, 1)
    assert grid.forces[:, 0].tolist() == pytest.approx([1.0, 0.0, -1.0])
    assert not grid.metadata.replication_valid
    spec = normalized_force_plot_spec(grid)
    for key in ("title", "filename", "zlabel"):
        assert PROVISIONAL_LABEL in str(spec[key])
        assert NOT_REPLICATION_LABEL in str(spec[key])
    assert FULL_WARNING_LABEL in str(spec["filename"])


def test_existing_12_plus_4_validation_remains_unchanged() -> None:
    model = build_mgf_validation_model_from_sources()
    assert model.ground_state_count == 12
    assert model.excited_state_count == 4
    assert model.transition_dipole_q.shape == (3, 12, 4)
    spacings = np.diff([level.relative_energy_mhz for level in model.ground_levels])
    assert spacings == pytest.approx([109.0, 120.0, 9.0], abs=1.0)
