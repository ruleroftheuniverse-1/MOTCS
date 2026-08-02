"""Reproducibly digitize Rodriguez et al. Figures 2, 3, and 4(a).

All crops and calibration anchors come from the Run 011B YAML file.  The source
PDF is read-only and is never copied into the output directory.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np
from PIL import Image
import pdfplumber
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "rodriguez_figure_digitization_run_011b.yaml"
LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011B_"
    "PAPER_FIGURE_FORCE_SHAPE_BENCHMARK_ONLY"
)
OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional" / "paper_digitization" / "run_011b"
METADATA_PATH = OUTPUT_DIR / f"{LABEL}_digitization_metadata.json"


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data["name"] != LABEL:
        raise ValueError("Run 011B digitization label mismatch")
    return data


def linear_calibration(anchors: list[list[float]]) -> tuple[float, float]:
    """Return data = slope*pixel + intercept from explicit anchors."""

    array = np.asarray(anchors, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2 or len(array) < 2:
        raise ValueError("calibration requires at least two [pixel,data] anchors")
    if not np.isfinite(array).all() or np.ptp(array[:, 0]) <= 0:
        raise ValueError("calibration anchors must be finite with distinct pixels")
    slope, intercept = np.polyfit(array[:, 0], array[:, 1], 1)
    residual = array[:, 1] - (slope * array[:, 0] + intercept)
    tolerance = max(abs(slope) * 0.75, 1e-10)
    if np.max(np.abs(residual)) > tolerance:
        raise ValueError(f"calibration anchors are inconsistent: residual {residual}")
    return float(slope), float(intercept)


def calibrated_values(pixels: np.ndarray, anchors: list[list[float]]) -> np.ndarray:
    slope, intercept = linear_calibration(anchors)
    return slope * np.asarray(pixels, dtype=float) + intercept


def _render_pages(config: dict[str, Any]) -> tuple[dict[int, Image.Image], dict[str, Any]]:
    source = REPO_ROOT / config["source"]["local_pdf"]
    source_hash = _hash(source)
    if source_hash.lower() != config["source"]["expected_sha256"].lower():
        raise RuntimeError("Rodriguez source PDF hash differs from the configured source")
    dpi = int(config["rendering"]["dpi"])
    pages: dict[int, Image.Image] = {}
    with pdfplumber.open(source) as document:
        for page_number in sorted(
            {config["figure_2"]["page"], config["figure_3"]["page"], config["figure_4a"]["page"]}
        ):
            rendered = document.pages[page_number - 1].to_image(
                resolution=dpi, antialias=bool(config["rendering"]["antialias"])
            ).original.convert("RGB")
            if list(rendered.size) != config["rendering"]["expected_pixel_size"]:
                raise RuntimeError(f"rendered page {page_number} has unexpected size {rendered.size}")
            pages[page_number] = rendered
            rendered.save(OUTPUT_DIR / f"{LABEL}_page_{page_number}_{dpi}dpi.png")
    provenance = {
        "paper_title": config["source"]["title"],
        "doi": config["source"]["doi"],
        "publication": config["source"]["publication"],
        "manuscript_date": str(config["source"]["manuscript_date"]),
        "source_path": str(source.relative_to(REPO_ROOT)),
        "source_sha256": source_hash,
        "source_pdf_committed_by_run_011b": False,
        "rendering_software": f"pdfplumber {pdfplumber.__version__}; Pillow {Image.__version__}",
        "python": platform.python_version(),
        "rendering_dpi": dpi,
        "rendering_antialias": bool(config["rendering"]["antialias"]),
        "rendered_pixel_size": config["rendering"]["expected_pixel_size"],
    }
    return pages, provenance


def _palette(page: Image.Image, colorbar: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    x = int(colorbar["sample_x"])
    y0, y1 = (int(value) for value in colorbar["sample_y_bounds"])
    rgb = np.asarray(page, dtype=np.uint8)[y0:y1, x, :3]
    ys = np.arange(y0, y1, dtype=float)
    values = calibrated_values(ys, colorbar["value_anchors"])
    return rgb, values


def _digitize_force_panel(
    page: Image.Image,
    panel: dict[str, Any],
    *,
    y_anchors: list[list[float]],
    colorbar: dict[str, Any],
    x_scale: float,
    name: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    page_array = np.asarray(page, dtype=np.uint8)
    left, top, right, bottom = (int(value) for value in panel["axes_bounds"])
    # Exclude the antialiased black frame itself.
    xs_px = np.arange(left + 2, right - 1, dtype=int)
    ys_px = np.arange(top + 2, bottom - 1, dtype=int)
    panel_rgb = page_array[np.ix_(ys_px, xs_px, np.arange(3))]
    palette_rgb, palette_values = _palette(page, colorbar)
    flat = panel_rgb.reshape(-1, 3).astype(float)
    palette_float = palette_rgb.astype(float)
    # Chunk to keep the color-distance matrix small and deterministic.
    nearest = np.empty(len(flat), dtype=int)
    distance = np.empty(len(flat), dtype=float)
    for start in range(0, len(flat), 20000):
        stop = min(start + 20000, len(flat))
        delta = flat[start:stop, None, :] - palette_float[None, :, :]
        dist2 = np.sum(delta * delta, axis=2)
        nearest[start:stop] = np.argmin(dist2, axis=1)
        distance[start:stop] = np.sqrt(np.min(dist2, axis=1))
    force = palette_values[nearest].reshape(panel_rgb.shape[:2])
    color_distance = distance.reshape(panel_rgb.shape[:2])
    threshold = float(config["uncertainty"]["antialiasing_palette_distance_threshold_rgb"])
    valid = color_distance <= threshold
    force = np.where(valid, force, np.nan)
    x = calibrated_values(xs_px, panel["x_anchors"]) * x_scale
    y = calibrated_values(ys_px, y_anchors)
    crop_path = OUTPUT_DIR / f"{LABEL}_{name}_panel.png"
    page.crop(tuple(panel["crop"])).save(crop_path)
    array_path = OUTPUT_DIR / f"{LABEL}_{name}_digitized.npz"
    np.savez_compressed(
        array_path,
        x=x,
        y=y,
        force_hbar_k_gamma=force,
        valid_mask=valid,
        color_distance_rgb=color_distance,
        source_pixel_x=xs_px,
        source_pixel_y=ys_px,
    )
    return {
        "label": LABEL,
        "name": name,
        "page": None,
        "crop": panel["crop"],
        "axes_bounds": panel["axes_bounds"],
        "x_anchors": panel["x_anchors"],
        "y_anchors": y_anchors,
        "colorbar": colorbar,
        "x_scale_applied": x_scale,
        "shape": list(force.shape),
        "valid_fraction": float(np.mean(valid)),
        "median_palette_distance_rgb": float(np.nanmedian(color_distance[valid])),
        "maximum_accepted_palette_distance_rgb": float(np.nanmax(color_distance[valid])),
        "panel_image": crop_path.name,
        "data_file": array_path.name,
        "data_sha256": _hash(array_path),
    }


def _axis_uncertainty(anchors: list[list[float]], displacements: list[int]) -> dict[str, float]:
    slope, _ = linear_calibration(anchors)
    span_px = float(np.ptp(np.asarray(anchors)[:, 0]))
    span_data = float(np.ptp(np.asarray(anchors)[:, 1]))
    result = {"source_raster_half_pixel_data": 0.5 * abs(slope)}
    for displacement in displacements:
        result[f"anchor_plus_minus_{displacement}px_data"] = abs(span_data) * displacement / max(span_px - 2 * displacement, 1.0)
    return result


def _colorbar_uncertainty(colorbar: dict[str, Any], displacements: list[int]) -> dict[str, float]:
    slope, _ = linear_calibration(colorbar["value_anchors"])
    return {
        f"colorbar_boundary_plus_minus_{displacement}px_force": abs(slope) * displacement
        for displacement in displacements
    }


def _digitize_trajectory(page: Image.Image, config: dict[str, Any]) -> dict[str, Any]:
    from scipy.ndimage import distance_transform_edt, label

    figure = config["figure_4a"]
    trajectory = figure["trajectory"]
    array = np.asarray(page, dtype=np.uint8)
    x0, x1 = (int(value) for value in trajectory["extraction_x_range_px"])
    y0, y1 = (int(value) for value in trajectory["extraction_y_range_px"])
    threshold = float(trajectory["dark_threshold_rgb_mean"])
    colors = array[y0 : y1 + 1, x0 : x1 + 1, :3].astype(float)
    dark = (np.mean(colors, axis=2) <= threshold) & (np.ptp(colors, axis=2) <= 18.0)
    components, count = label(dark, structure=np.ones((3, 3), dtype=int))
    sizes = np.bincount(components.ravel())
    if count < 1:
        raise RuntimeError("no thick-black Figure 4(a) trajectory component was found")
    selected = int(np.argmax(sizes[1:]) + 1)
    component = components == selected
    y_local, x_local = np.where(component)
    if len(x_local) < 100:
        raise RuntimeError("too few thick-black Figure 4(a) trajectory pixels were extracted")
    x_pixels = x_local.astype(float) + x0
    y_pixels = y_local.astype(float) + y0
    x_mm = calibrated_values(x_pixels, figure["x_anchors"])
    velocity = calibrated_values(y_pixels, figure["y_anchors"])
    y_slope, _ = linear_calibration(figure["y_anchors"])
    radius_px = distance_transform_edt(component)[component]
    line_uncertainty = abs(y_slope) * radius_px
    crop_path = OUTPUT_DIR / f"{LABEL}_figure_4a_panel.png"
    page.crop(tuple(figure["crop"])).save(crop_path)
    data_path = OUTPUT_DIR / f"{LABEL}_figure_4a_thick_trajectory_digitized.npz"
    np.savez_compressed(
        data_path,
        x_mm=x_mm,
        velocity_m_s=velocity,
        source_pixel_x=x_pixels,
        source_pixel_y=y_pixels,
        line_half_thickness_uncertainty_m_s=line_uncertainty,
    )
    return {
        "label": LABEL,
        "page": figure["page"],
        "crop": figure["crop"],
        "axes_bounds": figure["axes_bounds"],
        "x_anchors": figure["x_anchors"],
        "y_anchors": figure["y_anchors"],
        "extraction": trajectory,
        "sample_count": len(x_pixels),
        "x_range_mm": [float(np.min(x_mm)), float(np.max(x_mm))],
        "velocity_range_m_s": [float(np.min(velocity)), float(np.max(velocity))],
        "median_line_half_thickness_uncertainty_m_s": float(np.median(line_uncertainty)),
        "maximum_line_half_thickness_uncertainty_m_s": float(np.max(line_uncertainty)),
        "panel_image": crop_path.name,
        "data_file": data_path.name,
        "data_sha256": _hash(data_path),
    }


def protected_paths(config: dict[str, Any]) -> tuple[Path, ...]:
    paths: set[Path] = set()
    for pattern in config["protected"]["globs"]:
        paths.update(REPO_ROOT.glob(pattern))
    paths.update(REPO_ROOT / path for path in config["protected"]["explicit_files"])
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"protected Run 011B inputs missing: {missing}")
    return tuple(sorted(paths))


def hash_manifest(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(REPO_ROOT)): _hash(path) for path in paths}


def run() -> dict[str, Any]:
    config = _load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected = protected_paths(config)
    hashes_before = hash_manifest(protected)
    pages, source_provenance = _render_pages(config)
    records: dict[str, Any] = {}
    fig2 = config["figure_2"]
    for name, panel in fig2["panels"].items():
        records[f"figure_2_{name}"] = _digitize_force_panel(
            pages[fig2["page"]], panel,
            y_anchors=panel["y_anchors"], colorbar=panel["colorbar"],
            x_scale=1.0, name=f"figure_2_{name}", config=config,
        )
        records[f"figure_2_{name}"]["page"] = fig2["page"]
    fig3 = config["figure_3"]
    for name, panel in fig3["panels"].items():
        records[f"figure_3_{name}"] = _digitize_force_panel(
            pages[fig3["page"]], panel,
            y_anchors=fig3["common_y_anchors"], colorbar=fig3["common_colorbar"],
            x_scale=1.0, name=f"figure_3_{name}", config=config,
        )
        records[f"figure_3_{name}"]["page"] = fig3["page"]
        records[f"figure_3_{name}"]["detuning_gamma"] = float(panel["detuning_gamma"])
    trajectory = _digitize_trajectory(pages[config["figure_4a"]["page"]], config)
    uncertainty = {
        "separate_contributions": {
            "source_raster_resolution": "reported as half a rendered pixel on each calibrated axis",
            "axis_anchor_placement": "explicit +/-1 and +/-2 pixel perturbation bounds",
            "panel_cropping": "one rendered pixel; axes anchors make data calibration crop-independent",
            "colorbar_calibration": "explicit +/-1 and +/-2 pixel colorbar-boundary perturbations",
            "antialiasing": "nearest rendered colorbar color plus recorded RGB residual",
            "line_thickness": "half the detected thick-black vertical pixel span",
            "overlapping_trajectory_curves": config["uncertainty"]["overlapping_trajectory_note"],
            "compression_or_publication_artifacts": config["uncertainty"]["publication_compression_note"],
        },
        "figure_2_x": _axis_uncertainty(fig2["panels"]["mgf_3"]["x_anchors"], config["uncertainty"]["axis_anchor_displacements_px"]),
        "figure_2_y": _axis_uncertainty(fig2["panels"]["mgf_3"]["y_anchors"], config["uncertainty"]["axis_anchor_displacements_px"]),
        "figure_2_force": _colorbar_uncertainty(fig2["panels"]["mgf_3"]["colorbar"], config["uncertainty"]["colorbar_boundary_displacements_px"]),
        "figure_3_x_mm": _axis_uncertainty(fig3["panels"]["minus_8_gamma"]["x_anchors"], config["uncertainty"]["axis_anchor_displacements_px"]),
        "figure_3_y_m_s": _axis_uncertainty(fig3["common_y_anchors"], config["uncertainty"]["axis_anchor_displacements_px"]),
        "figure_3_force": _colorbar_uncertainty(fig3["common_colorbar"], config["uncertainty"]["colorbar_boundary_displacements_px"]),
        "figure_4_x_mm": _axis_uncertainty(config["figure_4a"]["x_anchors"], config["uncertainty"]["axis_anchor_displacements_px"]),
        "figure_4_y_m_s": _axis_uncertainty(config["figure_4a"]["y_anchors"], config["uncertainty"]["axis_anchor_displacements_px"]),
        "figure_4_line": {
            "median_half_thickness_m_s": trajectory["median_line_half_thickness_uncertainty_m_s"],
            "maximum_half_thickness_m_s": trajectory["maximum_line_half_thickness_uncertainty_m_s"],
        },
    }
    hashes_after = hash_manifest(protected)
    metadata = {
        "label": LABEL,
        "title": f"{LABEL} digitization metadata",
        "track": "provisional",
        "replication_valid": False,
        "source_provenance": source_provenance,
        "configuration_file": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "configuration_sha256": _hash(CONFIG_PATH),
        "all_manual_crops_and_anchors_are_config_backed": True,
        "force_panels": records,
        "figure_4a_trajectory": trajectory,
        "uncertainty": uncertainty,
        "protected_hashes_before": hashes_before,
        "protected_hashes_after": hashes_after,
        "protected_artifacts_unchanged": hashes_before == hashes_after,
        "physics_inputs_modified": False,
        "force_fields_rebuilt": 0,
        "trajectories_integrated": 0,
        "capture_calculations": 0,
        "optimizer_runs": 0,
    }
    if not metadata["protected_artifacts_unchanged"]:
        raise RuntimeError("protected Run 010/011/011A artifacts changed during digitization")
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{LABEL}: digitized {len(records)} force panels and Figure 4(a)")
    print(f"metadata: {METADATA_PATH}")
    return metadata


if __name__ == "__main__":
    run()
