from __future__ import annotations

import importlib.util
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_"
    "PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY"
)
CONFIG_PATH = REPO_ROOT / "configs" / "rodriguez_figure_digitization_run_011b.yaml"
DIGITIZER_PATH = REPO_ROOT / "scripts" / "digitize_rodriguez_force_figures.py"
COMPARE_PATH = REPO_ROOT / "scripts" / "compare_accepted_force_to_rodriguez_figures.py"
DIGITIZED_DIR = REPO_ROOT / "outputs" / "provisional" / "paper_digitization" / "run_011b"
DIGITIZATION_METADATA = DIGITIZED_DIR / f"{LABEL}_digitization_metadata.json"
COMPARISON_METADATA = REPO_ROOT / "outputs" / "provisional" / f"{LABEL}_comparison_metadata.json"
REPORT_PATH = REPO_ROOT / "outputs" / "provisional" / f"{LABEL}.md"


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path) -> dict:
    assert path.exists(), f"generate Run 011B output first: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_manual_calibration_and_crop_points_are_config_backed() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["name"] == LABEL
    assert config["coordinate_convention"]["pixel_origin"] == "upper_left"
    for figure_name in ("figure_2", "figure_3"):
        figure = config[figure_name]
        assert figure["page"] in (4, 5)
        for panel in figure["panels"].values():
            assert len(panel["crop"]) == 4
            assert len(panel["axes_bounds"]) == 4
            assert len(panel["x_anchors"]) >= 2
    assert len(config["figure_2"]["panels"]["mgf_3"]["colorbar"]["value_anchors"]) == 2
    assert len(config["figure_3"]["common_colorbar"]["value_anchors"]) == 2
    assert len(config["figure_4a"]["x_anchors"]) == 3
    assert len(config["figure_4a"]["y_anchors"]) == 4
    assert config["uncertainty"]["axis_anchor_displacements_px"] == [1, 2]
    assert config["uncertainty"]["colorbar_boundary_displacements_px"] == [1, 2]


def test_axis_calibration_is_reproducible_and_exact_at_anchors() -> None:
    module = _module(DIGITIZER_PATH, "run011b_digitizer")
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    anchor_sets = [
        config["figure_2"]["panels"]["mgf_3"]["x_anchors"],
        config["figure_3"]["common_y_anchors"],
        config["figure_4a"]["x_anchors"],
        config["figure_4a"]["y_anchors"],
    ]
    for anchors in anchor_sets:
        pixels = np.asarray([row[0] for row in anchors], dtype=float)
        expected = np.asarray([row[1] for row in anchors], dtype=float)
        first = module.calibrated_values(pixels, anchors)
        second = module.calibrated_values(pixels, anchors)
        assert np.array_equal(first, second)
        assert np.allclose(first, expected, atol=0.08)


def test_digitization_provenance_uncertainty_arrays_and_hash_protection() -> None:
    metadata = _json(DIGITIZATION_METADATA)
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    source = REPO_ROOT / config["source"]["local_pdf"]
    assert sha256(source.read_bytes()).hexdigest() == config["source"]["expected_sha256"]
    assert metadata["label"] == LABEL
    assert metadata["source_provenance"]["rendering_dpi"] == 300
    assert "pdfplumber" in metadata["source_provenance"]["rendering_software"]
    assert metadata["protected_artifacts_unchanged"] is True
    assert metadata["protected_hashes_before"] == metadata["protected_hashes_after"]
    assert set(metadata["uncertainty"]["separate_contributions"]) == {
        "source_raster_resolution", "axis_anchor_placement", "panel_cropping",
        "colorbar_calibration", "antialiasing", "line_thickness",
        "overlapping_trajectory_curves", "compression_or_publication_artifacts",
    }
    for panel in metadata["force_panels"].values():
        data = np.load(DIGITIZED_DIR / panel["data_file"])
        assert data["force_hbar_k_gamma"].shape == tuple(panel["shape"])
        assert np.isfinite(data["force_hbar_k_gamma"][data["valid_mask"]]).all()


def test_comparison_uses_exact_planes_matching_units_and_explicit_widths() -> None:
    metadata = _json(COMPARISON_METADATA)
    assert metadata["figure_3_exact_detunings_gamma"] == [-8.0, -6.0, -4.0, -2.0]
    assert metadata["plane_wave_and_gaussian_comparisons_separate"] is True
    assert metadata["accepted_force_fields_rebuilt"] == 0
    assert metadata["trajectories_integrated"] == 0
    for row in metadata["figure_3"].values():
        assert row["accepted_cache_plane_used_exactly"] is True
        assert row["units"] == {"x": "mm", "y": "m/s", "force": "hbar*k*Gamma"}
        for widths in (row["paper_widths"], row["model_widths"]):
            assert set(widths) >= {
                "spatial_through_actual_extremum",
                "spatial_at_paper_motivated_velocity",
                "velocity_at_x_zero",
                "velocity_through_actual_extremum",
                "fixed_negative_force_contours",
            }
            assert set(widths["spatial_through_actual_extremum"]) >= {
                "half_maximum", "one_over_e", "one_over_e2"
            }
        surface = row["surface_metrics"]
        assert "no_fitted_correction" in surface
        assert "after_diagnostic_scale_only" in surface
        assert np.isfinite(surface["signed_area_difference_data_units"])
    for row in metadata["figure_2"].values():
        assert row["units"] == {
            "x": "hbar*Gamma/(mu_B*Bprime)", "y": "Gamma/k", "force": "hbar*k*Gamma"
        }


def test_gate_authorizations_labels_and_no_physics_mutation() -> None:
    metadata = _json(COMPARISON_METADATA)
    assert metadata["gate"] == "PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED"
    assert metadata["protected_artifacts_unchanged"] is True
    assert metadata["protected_hashes_before"] == metadata["protected_hashes_after"]
    assert metadata["fitted_model_parameters"] == []
    assert metadata["physics_inputs_modified"] is False
    assert metadata["capture_authorized"] is False
    assert metadata["capture_velocity_authorized"] is False
    assert metadata["optimizer_authorized"] is False
    assert metadata["exact_replication_valid"] is False
    assert metadata["exact_track_blocked"] is True
    assert metadata["trajectory"]["initial_offset_normalized_shape_diagnostic"]["not_a_backend_parameter_fit"] is True
    stamps = ("PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "RUN_011B", "PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY")
    generated = list(DIGITIZED_DIR.iterdir()) + [REPORT_PATH, COMPARISON_METADATA]
    assert generated
    assert all(all(stamp in path.name for stamp in stamps) for path in generated)
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert all(LABEL in line for line in report.splitlines() if line.startswith("#"))
    assert "PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED" in report


def test_run011b_scripts_cannot_rebuild_reintegrate_capture_or_optimize() -> None:
    for path in (DIGITIZER_PATH, COMPARE_PATH):
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "integrate_accepted_force_field_trajectory(",
            "save_force_field_cache(",
            "build_force_field(",
            "capture_velocity(",
            "threshold_search(",
            "optimizer(",
        ):
            assert forbidden not in source
