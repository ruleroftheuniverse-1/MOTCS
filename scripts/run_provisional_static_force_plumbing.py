"""Run Track P provisional static force-map plumbing validation.

This script produces quarantined, visibly labeled engineering artifacts only.
It does not produce Rodriguez-valid MgF force maps.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from mgf_mot.mgf_backend import (
    ApproximationMode,
    build_mgf_hamiltonian_from_sources,
)
from mgf_mot.provisional_force import (
    FULL_WARNING_LABEL,
    ProvisionalForceMapConfig,
    force_grid_1d,
    normalized_force_plot_spec,
    save_normalized_force_plot,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
CONFIG_PATHS = (
    REPO_ROOT / "configs" / "rodriguez_static_3.yaml",
    REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml",
)


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "value") and value.__class__.__name__.endswith("Track"):
        return value.value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if config["beam_model"] != "infinite_plane_wave":
        raise ValueError(
            "provisional plumbing run supports only infinite_plane_wave configs"
        )
    return config


def _provisional_config_from_rodriguez_style(config: dict[str, Any]) -> ProvisionalForceMapConfig:
    enabled_components = [
        item for item in config["frequency_components"] if item.get("enabled", True)
    ]
    relative_saturation = sum(
        float(item.get("relative_saturation", 0.0)) for item in enabled_components
    )
    gradient_scale = float(config["magnetic_gradient"]["value"]) / 20.0
    return ProvisionalForceMapConfig(
        explicit_provisional_opt_in=True,
        normalized_spring=max(relative_saturation * gradient_scale, 0.0),
        normalized_damping=0.2,
    )


def _artifact_path(output_dir: Path, config_name: str, suffix: str) -> Path:
    return output_dir / f"{FULL_WARNING_LABEL}_{config_name}_{suffix}"


def run(output_dir: Path = DEFAULT_OUTPUT_DIR, *, save_plots: bool = True) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    provenance = backend.provenance

    print("Track P provisional static force-map plumbing validation")
    print(f"track: {provenance.track.value}")
    print(f"backend_mode: {provenance.backend_mode}")
    print(f"replication_valid: {provenance.replication_valid}")
    print(f"force_ready: {provenance.force_ready}")
    print("warnings:")
    for warning in provenance.warnings:
        print(f"  - {warning}")
    print("omitted_terms:")
    for term in provenance.omitted_terms:
        print(f"  - {term}")
    print("collapsed_terms:")
    for term in provenance.collapsed_terms:
        print(f"  - {term}")

    positions = np.linspace(-1.0, 1.0, 7)
    velocities = np.linspace(-0.5, 0.5, 5)
    run_records: list[dict[str, Any]] = []

    for config_path in CONFIG_PATHS:
        source_config = _load_config(config_path)
        config_name = source_config["name"]
        provisional_config = _provisional_config_from_rodriguez_style(source_config)
        grid = force_grid_1d(
            "z",
            positions,
            velocities,
            backend,
            provisional_config,
        )

        metadata_path = _artifact_path(output_dir, config_name, "metadata.json")
        arrays_path = _artifact_path(output_dir, config_name, "grid.npz")
        plot_path: Path | None = None

        np.savez_compressed(
            arrays_path,
            positions=grid.positions,
            velocities=grid.velocities,
            forces=grid.forces,
        )

        plot_spec = normalized_force_plot_spec(grid)
        if save_plots:
            try:
                raw_plot_path = save_normalized_force_plot(grid, output_dir)
                plot_path = _artifact_path(output_dir, config_name, "force_grid_1d_z_axis.png")
                raw_plot_path.replace(plot_path)
            except Exception as exc:  # pragma: no cover - depends on optional plotting stack
                plot_spec = dict(plot_spec)
                plot_spec["plot_error"] = repr(exc)

        metadata = {
            "label": FULL_WARNING_LABEL,
            "run_type": "provisional_static_force_plumbing",
            "source_config_path": str(config_path.relative_to(REPO_ROOT)),
            "source_config": source_config,
            "provisional_config": asdict(provisional_config),
            "backend_provenance": _json_safe(provenance),
            "grid_metadata": _json_safe(grid.metadata),
            "axis": grid.axis,
            "positions_shape": list(grid.positions.shape),
            "velocities_shape": list(grid.velocities.shape),
            "forces_shape": list(grid.forces.shape),
            "forces_finite": bool(np.isfinite(grid.forces).all()),
            "arrays_path": str(arrays_path.relative_to(output_dir)),
            "plot_path": None if plot_path is None else str(plot_path.relative_to(output_dir)),
            "plot_spec": _json_safe(plot_spec),
            "disclaimer": (
                "PROVISIONAL plumbing validation only; "
                "NOT_RODRIGUEZ_REPLICATION; no physical conclusions."
            ),
        }
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        run_records.append(
            {
                "config_name": config_name,
                "metadata_path": metadata_path,
                "arrays_path": arrays_path,
                "plot_path": plot_path,
                "forces_shape": grid.forces.shape,
                "forces_finite": bool(np.isfinite(grid.forces).all()),
            }
        )

    report_path = output_dir / f"{FULL_WARNING_LABEL}_run_001.md"
    report_lines = [
        f"# {FULL_WARNING_LABEL} run 001",
        "",
        "This is a Track P provisional static force-map plumbing validation.",
        "",
        "This is not an MgF/Rodriguez reproduction.",
        "Exact Track E remains blocked by the independent Doppelbauer `d` operator and excited Zeeman mappings.",
        "No physical conclusions should be drawn from force magnitudes, signs beyond plumbing diagnostics, or topology.",
        "",
        "No chirps, Gaussian beams, trajectories, capture velocities, or optimizers were used.",
        "",
        "## Backend provenance",
        "",
        f"- track: `{provenance.track.value}`",
        f"- backend mode: `{provenance.backend_mode}`",
        f"- replication_valid: `{provenance.replication_valid}`",
        f"- force_ready: `{provenance.force_ready}`",
        "",
        "## Outputs",
        "",
    ]
    for record in run_records:
        report_lines.extend(
            [
                f"### {record['config_name']}",
                "",
                f"- metadata: `{record['metadata_path'].name}`",
                f"- arrays: `{record['arrays_path'].name}`",
                f"- plot: `{None if record['plot_path'] is None else record['plot_path'].name}`",
                f"- force array shape: `{tuple(record['forces_shape'])}`",
                f"- finite: `{record['forces_finite']}`",
                "",
            ]
        )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote report: {report_path}")
    return run_records


def main() -> None:
    run()


if __name__ == "__main__":
    main()
