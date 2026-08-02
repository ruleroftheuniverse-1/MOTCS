from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.accepted_backend import (
    AcceptedProvisionalBackendSelection,
    build_accepted_provisional_rateeq_backend,
)
from mgf_mot.excited_hyperfine import ExcitedHyperfineModel
from mgf_mot.excited_zeeman import ExcitedZeemanModel
from mgf_mot.force_field import (
    FORCE_FIELD_LABEL,
    ForceFieldCacheMismatchError,
    ForceFieldDomain,
    ForceFieldDomainError,
    ForceFieldGrid,
    ForceFieldProvenance,
    InterpolatedForceField,
    SeparatedHandoffForceFields,
    load_force_field_cache,
    save_force_field_cache,
)
from mgf_mot.mgf_backend import MgFBackendCapabilityError


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
METADATA_PATH = OUTPUT_DIR / f"{FORCE_FIELD_LABEL}_run_010_metadata.json"
REPORT_PATH = OUTPUT_DIR / f"{FORCE_FIELD_LABEL}_run_010.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_and_validate_provisional_force_fields.py"


def _provenance(kind="post_handoff_trap_3_plus_1", *, saturation=None):
    pre = kind == "pre_handoff_chirp_3"
    return ForceFieldProvenance(
        label=FORCE_FIELD_LABEL,
        field_kind=kind,
        track="provisional",
        backend_mode="pylcp_rate_equation",
        ground_zeeman_convention="project_energy_slope_corrected",
        excited_zeeman_model="rodriguez_effective_g_0p001",
        excited_hyperfine_model="source_aligned_effective_fprime_splitting",
        splitting_case="mid_range_0p5_mhz",
        splitting_mhz=0.5,
        splitting_interval_mhz=(0.0, 1.0),
        splitting_note="0.5 MHz interval midpoint, not measured",
        replication_valid=False,
        exact_track_blocked=True,
        unresolved_terms=("independent d",),
        normalized_force_unit="hbar*k*Gamma",
        canonical_values_are_si_acceleration=False,
        field_gradient_t_m=0.2,
        beam_mode="elliptical_gaussian",
        component_order=(1, 2, 3, 4),
        saturation_vector=saturation or ((1.45, 1.45, 2.89, 0.0) if pre else (1.45, 1.45, 2.17, 0.72)),
        detuning_specification="-8 to -1" if pre else "(-1,-1,-1,+2)",
        source_hashes=(("config.yaml", "abc"),),
        interpolation_method="trilinear" if pre else "bilinear",
    )


def _synthetic_fields():
    x, v, d = np.array([-1.0, 0.0, 1.0]), np.array([-2.0, 0.0, 2.0]), np.array([-8.0, -4.5, -1.0])
    pre_values = 2 * x[:, None, None] + 3 * v[None, :, None] + 4 * d[None, None, :]
    post_values = 2 * x[:, None] + 3 * v[None, :]
    pre = InterpolatedForceField(ForceFieldGrid(ForceFieldDomain(x, v, d), pre_values, _provenance("pre_handoff_chirp_3"), 1.0, 1.0))
    post = InterpolatedForceField(ForceFieldGrid(ForceFieldDomain(x, v), post_values, _provenance(), 1.0, 1.0))
    return pre, post


def test_accepted_backend_factory_locks_every_run009d_selection() -> None:
    backend = build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=True)
    assert backend.status.ground_zeeman_convention == "project_energy_slope_corrected"
    assert backend.status.excited_zeeman_model == ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001.value
    assert backend.status.excited_hyperfine_model == ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING.value
    assert backend.status.excited_hyperfine_splitting_mhz == 0.5
    assert backend.status.replication_valid is False
    with pytest.raises(MgFBackendCapabilityError, match="explicit provisional opt-in"):
        build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=False)
    collapsed = replace(
        AcceptedProvisionalBackendSelection(),
        excited_hyperfine_model=ExcitedHyperfineModel.PYLCP_COLLAPSED_ASTATE,
    )
    with pytest.raises(MgFBackendCapabilityError, match="immutable Run 009D"):
        build_accepted_provisional_rateeq_backend(explicit_provisional_opt_in=True, selection=collapsed)


def test_bilinear_and_trilinear_interpolation_preserve_normalized_force() -> None:
    pre, post = _synthetic_fields()
    assert pre.force_normalized(0.25, 0.5, -3.0) == pytest.approx(2 * 0.25 + 3 * 0.5 + 4 * -3.0)
    assert post.force_normalized(0.25, 0.5) == pytest.approx(2 * 0.25 + 3 * 0.5)
    assert pre.grid.provenance.normalized_force_unit == "hbar*k*Gamma"
    assert pre.grid.provenance.canonical_values_are_si_acceleration is False
    assert "acceleration" not in pre.grid.dimensionless_coordinates


def test_boundaries_are_inclusive_and_extrapolation_fails() -> None:
    pre, post = _synthetic_fields()
    assert np.isfinite(pre.force_normalized(-1.0, -2.0, -8.0))
    assert np.isfinite(pre.force_normalized(1.0, 2.0, -1.0))
    assert np.isfinite(post.force_normalized(1.0, 2.0))
    with pytest.raises(ForceFieldDomainError, match="extrapolation is disabled"):
        pre.force_normalized(1.0001, 0.0, -4.5)
    with pytest.raises(ForceFieldDomainError):
        pre.force_normalized(0.0, 0.0, -0.999)
    with pytest.raises(ForceFieldDomainError):
        post.force_normalized(0.0, -2.001)


def test_pre_post_fields_remain_separate_and_handoff_is_exact() -> None:
    pre, post = _synthetic_fields()
    fields = SeparatedHandoffForceFields(pre, post, handoff_time_s=0.001)
    before = fields.force_normalized(np.nextafter(0.001, -np.inf), 0.25, 0.5, -3.0)
    at = fields.force_normalized(0.001, 0.25, 0.5, -3.0)
    assert before == pytest.approx(pre.force_normalized(0.25, 0.5, -3.0))
    assert at == pytest.approx(post.force_normalized(0.25, 0.5))
    assert before != at


def test_cache_reuse_requires_exact_provenance_and_content_hash(tmp_path: Path) -> None:
    _, post = _synthetic_fields()
    stem = f"{FORCE_FIELD_LABEL}_synthetic"
    npz_path, metadata_path = tmp_path / f"{stem}.npz", tmp_path / f"{stem}_metadata.json"
    save_force_field_cache(post.grid, npz_path, metadata_path)
    loaded = load_force_field_cache(npz_path, metadata_path, post.grid.provenance)
    assert np.array_equal(loaded.normalized_force_x, post.grid.normalized_force_x)
    changed = _provenance(saturation=(1.45, 1.45, 2.18, 0.71))
    with pytest.raises(ForceFieldCacheMismatchError, match="provenance hash differs"):
        load_force_field_cache(npz_path, metadata_path, changed)


@pytest.fixture(scope="module")
def metadata():
    assert METADATA_PATH.exists(), "run the dedicated Run 010 script first"
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def test_run010_direct_holdouts_and_topology_pass_declared_thresholds(metadata) -> None:
    assert metadata["gate"] == "PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO"
    validation = metadata["validation"]
    holdouts = validation["holdouts"]
    thresholds = metadata["acceptance_thresholds_declared_in_config_before_run"]
    assert holdouts["all_holdouts_off_grid_nodes"] is True
    assert holdouts["normalized_rms_error_over_force_range"] <= thresholds["normalized_rms_error_over_force_range_max"]
    assert holdouts["maximum_important_region_error_over_force_range"] <= thresholds["maximum_important_region_error_over_force_range_max"]
    assert holdouts["population_health"]["passed"] is True
    assert validation["topology"]["topology_preserved"] is True
    assert validation["topology"]["post_restoring_and_damping_preserved"] is True
    assert all(row["zero_crossing_branch_count_preserved"] for row in validation["topology"]["features"])
    assert validation["component4"]["component4_stronger_confinement"] is True
    assert validation["component4"]["post_3plus1_stronger_than_static_3"] is True
    assert validation["gaussian_attenuation"]["passed"] is True


def test_run010_authorization_labels_and_prohibitions(metadata) -> None:
    assert metadata["accepted_backend_selection"]["splitting_note"].endswith("not a measured value")
    assert metadata["source_supported_splitting_interval_mhz"] == [0.0, 1.0]
    assert metadata["splitting_midpoint_is_measured_value"] is False
    assert metadata["provisional_static_authorized"] is True
    assert metadata["provisional_force_field_authorized"] is True
    assert metadata["provisional_trajectory_authorized"] is True
    assert metadata["capture_authorized"] is False
    assert metadata["exact_replication_valid"] is False
    assert metadata["exact_track_blocked"] is True
    assert metadata["trajectory_integrations_performed"] == 0
    assert metadata["capture_calculations_performed"] == 0
    assert metadata["pre_shape"] == [25, 33, 15]
    assert metadata["post_shape"] == [25, 33]
    assert all(stamp in REPORT_PATH.name and stamp in METADATA_PATH.name for stamp in (
        "PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY"
    ))
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(FORCE_FIELD_LABEL in line for line in report.splitlines() if line.startswith("#"))
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "integrate_policy_trajectory(", "run_trajectory_ensemble(", "solve_ivp(",
        "classify_trajectory(", "capture_velocity(",
    ):
        assert forbidden not in source
