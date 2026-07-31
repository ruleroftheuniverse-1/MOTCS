import json
from math import exp
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.gaussian_beams import (
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from mgf_mot.geometry import X_PRIME, Y_PRIME, Z_AXIS
from mgf_mot.mgf_backend import (
    ApproximateMgFHamiltonian,
    MgFBackendCapabilityError,
    build_mgf_validation_model_from_sources,
)
from mgf_mot.provisional_force import ProvisionalForceMapConfig, force_at
from mgf_mot.tracks import BackendProvenance, ProjectTrack
from scripts.run_provisional_gaussian_geometry_validation import (
    GAUSSIAN_GEOMETRY_VALIDATION_LABEL,
    run,
)

CONFIG_PATH = (
    Path(__file__).parents[1]
    / "configs"
    / "rodriguez_gaussian_baseline.yaml"
)


@pytest.fixture
def envelope_config():
    return load_gaussian_envelope_config(CONFIG_PATH)


@pytest.fixture
def beam_set(envelope_config):
    return build_rodriguez_gaussian_beam_set(
        envelope_config,
        (1.45, 1.45, 2.17, 0.72),
    )


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


def test_center_and_one_radius_envelopes(beam_set) -> None:
    for beam in beam_set.beams:
        center = np.asarray(beam.center_m)
        u_point = center + beam.radius_u_m * np.asarray(beam.transverse_u)
        v_point = center + beam.radius_v_m * np.asarray(beam.transverse_v)
        assert beam.envelope(center) == pytest.approx(1.0)
        assert beam.envelope(u_point) == pytest.approx(exp(-2.0))
        assert beam.envelope(v_point) == pytest.approx(exp(-2.0))


def test_propagation_displacement_does_not_change_envelope(beam_set) -> None:
    for beam in beam_set.beams:
        transverse_offset = (
            0.4 * beam.radius_u_m * np.asarray(beam.transverse_u)
            + 0.3 * beam.radius_v_m * np.asarray(beam.transverse_v)
        )
        displaced = transverse_offset + 0.2 * np.asarray(
            beam.propagation_direction
        )
        assert beam.envelope(displaced) == pytest.approx(
            beam.envelope(transverse_offset)
        )


def test_beam_frames_are_orthonormal_and_right_handed(beam_set) -> None:
    for beam in beam_set.beams:
        k = np.asarray(beam.propagation_direction)
        u = np.asarray(beam.transverse_u)
        v = np.asarray(beam.transverse_v)
        assert np.linalg.norm(k) == pytest.approx(1.0)
        assert np.linalg.norm(u) == pytest.approx(1.0)
        assert np.linalg.norm(v) == pytest.approx(1.0)
        assert np.dot(k, u) == pytest.approx(0.0, abs=1e-12)
        assert np.dot(k, v) == pytest.approx(0.0, abs=1e-12)
        assert np.dot(u, v) == pytest.approx(0.0, abs=1e-12)
        assert np.cross(u, v) == pytest.approx(k)


def test_all_six_beams_have_intended_axes_radii_and_saturations(
    beam_set, envelope_config
) -> None:
    beams = {beam.name: beam for beam in beam_set.beams}
    expected_u = {
        "+x_prime": Y_PRIME,
        "-x_prime": tuple(-value for value in Y_PRIME),
        "+y_prime": tuple(-value for value in X_PRIME),
        "-y_prime": X_PRIME,
        "+z": (1.0, 0.0, 0.0),
        "-z": (-1.0, 0.0, 0.0),
    }
    for name, beam in beams.items():
        assert beam.transverse_u == pytest.approx(expected_u[name])
        if name.endswith("z"):
            assert beam.transverse_v == pytest.approx((0.0, 1.0, 0.0))
        else:
            assert beam.transverse_v == pytest.approx(Z_AXIS)
        assert beam.radius_u_m == pytest.approx(envelope_config.wxy_m)
        assert beam.radius_v_m == pytest.approx(envelope_config.wz_m)
        assert beam.component_saturations == (1.45, 1.45, 2.17, 0.72)
        assert beam.peak_intensity_multiplier == 1.0
        assert beam.provenance.track is ProjectTrack.PROVISIONAL
        assert beam.provenance.replication_valid is False


def test_counterpropagating_pairs_share_spatial_envelopes(beam_set) -> None:
    points = (
        (0.0, 0.0, 0.0),
        (-0.05, 0.0, 0.0),
        (0.01, -0.02, 0.03),
    )
    for pair_name in ("x_prime", "y_prime", "z"):
        forward, backward = beam_set.pair(pair_name)
        for point in points:
            assert forward.envelope(point) == pytest.approx(
                backward.envelope(point), abs=1e-15
            )


def test_total_power_is_metadata_without_inferred_allocation(envelope_config) -> None:
    assert envelope_config.total_power_w == 1.0
    assert envelope_config.power_allocation_status == "unresolved_no_conversion"
    assert not hasattr(envelope_config, "per_beam_power_w")
    assert not hasattr(envelope_config, "per_component_power_w")
    assert envelope_config.reported_peak_saturation_vectors == {
        "three_frequency": (1.45, 1.45, 2.89, 0.0),
        "three_plus_one": (1.45, 1.45, 2.17, 0.72),
    }


def test_gaussian_mode_requires_explicit_selection_and_beam_set(beam_set) -> None:
    with pytest.raises(ValueError, match="explicit GaussianBeamSet"):
        ProvisionalForceMapConfig(
            explicit_provisional_opt_in=True,
            beam_mode="elliptical_gaussian",
            position_unit="m",
        )
    with pytest.raises(ValueError, match="requires beam_mode"):
        ProvisionalForceMapConfig(
            explicit_provisional_opt_in=True,
            gaussian_beam_set=beam_set,
        )


def test_plane_wave_behavior_is_unchanged_and_gaussian_is_explicit(
    beam_set, lightweight_provisional_backend
) -> None:
    position = np.asarray((0.05, 0.0, 0.0))
    velocity = np.asarray((0.01, 0.0, 0.0))
    legacy_force, legacy_metadata = force_at(
        position,
        velocity,
        lightweight_provisional_backend,
        ProvisionalForceMapConfig(explicit_provisional_opt_in=True),
    )
    plane_force, plane_metadata = force_at(
        position,
        velocity,
        lightweight_provisional_backend,
        ProvisionalForceMapConfig(
            explicit_provisional_opt_in=True,
            beam_mode="plane_wave",
            position_unit="m",
        ),
    )
    gaussian_force, gaussian_metadata = force_at(
        position,
        velocity,
        lightweight_provisional_backend,
        ProvisionalForceMapConfig(
            explicit_provisional_opt_in=True,
            beam_mode="elliptical_gaussian",
            gaussian_beam_set=beam_set,
            position_unit="m",
        ),
    )
    assert plane_force == pytest.approx(legacy_force)
    assert plane_metadata.beam_mode == legacy_metadata.beam_mode == "plane_wave"
    assert gaussian_metadata.beam_mode == "elliptical_gaussian"
    assert abs(gaussian_force[0]) < abs(plane_force[0])


def test_exact_track_cannot_enter_gaussian_provisional_force_path(beam_set) -> None:
    exact_like = build_mgf_validation_model_from_sources()
    config = ProvisionalForceMapConfig(
        explicit_provisional_opt_in=True,
        beam_mode="elliptical_gaussian",
        gaussian_beam_set=beam_set,
        position_unit="m",
    )
    with pytest.raises(MgFBackendCapabilityError, match="provisional track"):
        force_at(np.zeros(3), np.zeros(3), exact_like, config)


def test_run_007_outputs_are_labeled_and_geometry_checks_pass(tmp_path) -> None:
    record = run(tmp_path, save_plot=False)
    for key in ("arrays_path", "metadata_path", "report_path"):
        path = record[key]
        assert path.parent == tmp_path
        assert GAUSSIAN_GEOMETRY_VALIDATION_LABEL in path.name

    metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["label"] == GAUSSIAN_GEOMETRY_VALIDATION_LABEL
    assert GAUSSIAN_GEOMETRY_VALIDATION_LABEL in metadata["title"]
    assert metadata["replication_valid"] is False
    assert metadata["force_ready"] is False
    assert metadata["geometry_config"]["wxy_m"] == pytest.approx(0.0175)
    assert metadata["geometry_config"]["wz_m"] == pytest.approx(0.010)
    assert metadata["geometry_config"]["total_power_w"] == 1.0
    assert metadata["total_power_conversion_performed"] is False
    assert metadata["peak_saturation_vector_used_directly"] == [
        1.45,
        1.45,
        2.17,
        0.72,
    ]
    for check in metadata["analytic_beam_checks"]:
        assert check["label"] == GAUSSIAN_GEOMETRY_VALIDATION_LABEL
        assert check["center_envelope"] == pytest.approx(1.0)
        assert check["u_radius_envelope"] == pytest.approx(exp(-2.0))
        assert check["v_radius_envelope"] == pytest.approx(exp(-2.0))
        assert check["longitudinal_displacement_envelope"] == pytest.approx(1.0)
        assert check["all_samples_finite"] is True
        assert check["all_samples_in_unit_interval"] is True
        assert check["right_handed_u_cross_v_equals_k"] is True
    assert all(
        check["identical_envelopes"]
        for check in metadata["counterpropagating_pair_checks"]
    )
    assert any(
        record["point_name"] == "x_minus_50_mm"
        for record in metadata["lab_frame_diagnostics"]
    )
    assert {snapshot["beam_mode"] for snapshot in metadata["force_snapshots"]} == {
        "plane_wave",
        "elliptical_gaussian",
    }
    assert metadata["arrays_finite"] is True

    arrays = np.load(record["arrays_path"])
    assert arrays["plane_wave_forces"].shape == (5, 1)
    assert arrays["elliptical_gaussian_forces"].shape == (5, 1)
    assert np.isfinite(arrays["diagnostic_envelopes"]).all()
    assert np.all(arrays["diagnostic_envelopes"] >= 0.0)
    assert np.all(arrays["diagnostic_envelopes"] <= 1.0)

    report = record["report_path"].read_text(encoding="utf-8")
    for heading in (line for line in report.splitlines() if line.startswith("#")):
        assert GAUSSIAN_GEOMETRY_VALIDATION_LABEL in heading
    assert "paper's stated radii and beam axes" in report
    assert "exact MgF Hamiltonian remains blocked" in report
    assert "peak saturation vectors are used directly" in report
    assert "retained as metadata" in report
    assert "No capture velocity or threshold search" in report
    assert "No physical conclusions" in report


def test_gaussian_module_adds_no_forbidden_public_protocol_apis() -> None:
    import mgf_mot.gaussian_beams as gaussian_beams

    forbidden = (
        "capture",
        "threshold",
        "distribution",
        "stochastic",
        "optimizer",
        "optimiser",
    )
    public_names = [
        name.lower() for name in dir(gaussian_beams) if not name.startswith("_")
    ]
    for word in forbidden:
        assert not any(word in name for name in public_names)
