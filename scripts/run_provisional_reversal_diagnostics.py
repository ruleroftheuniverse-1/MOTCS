"""Run Track P provisional static force-map reversal diagnostics.

This script is a convention/plumbing diagnostic only. It does not produce
Rodriguez-valid MgF force maps.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass, replace
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
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
CONFIG_PATHS = (
    REPO_ROOT / "configs" / "rodriguez_static_3.yaml",
    REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml",
)
CASE_DEFINITIONS = {
    "nominal": {"flipped_polarization": False, "flipped_gradient": False},
    "flipped_polarization": {"flipped_polarization": True, "flipped_gradient": False},
    "flipped_gradient": {"flipped_polarization": False, "flipped_gradient": True},
    "flipped_both": {"flipped_polarization": True, "flipped_gradient": True},
}


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
            "provisional reversal diagnostics support only infinite_plane_wave configs"
        )
    return config


def _base_provisional_config(config: dict[str, Any]) -> ProvisionalForceMapConfig:
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


def _case_config(base: ProvisionalForceMapConfig, case_name: str) -> ProvisionalForceMapConfig:
    case = CASE_DEFINITIONS[case_name]
    return replace(
        base,
        flipped_polarization=case["flipped_polarization"],
        flipped_gradient=case["flipped_gradient"],
    )


def _artifact_path(output_dir: Path, config_name: str, case_name: str, suffix: str) -> Path:
    return output_dir / f"{FULL_WARNING_LABEL}_{config_name}_{case_name}_{suffix}"


def _central_slope(x: np.ndarray, y: np.ndarray) -> float:
    zero_index = int(np.argmin(np.abs(x)))
    if zero_index == 0 or zero_index == len(x) - 1:
        raise ValueError("grid must include points on both sides of zero")
    return float((y[zero_index + 1] - y[zero_index - 1]) / (x[zero_index + 1] - x[zero_index - 1]))


def _save_case_plots(
    output_dir: Path,
    config_name: str,
    case_name: str,
    title: str,
    positions: np.ndarray,
    velocities: np.ndarray,
    forces: np.ndarray,
    force_vs_position: np.ndarray,
    force_vs_velocity: np.ndarray,
) -> list[Path]:
    import matplotlib.pyplot as plt

    paths: list[Path] = []

    grid_path = _artifact_path(output_dir, config_name, case_name, "grid.png")
    fig, ax = plt.subplots()
    mesh = ax.imshow(
        forces.T,
        origin="lower",
        aspect="auto",
        extent=[
            float(positions.min()),
            float(positions.max()),
            float(velocities.min()),
            float(velocities.max()),
        ],
    )
    ax.set_title(f"{title} force grid")
    ax.set_xlabel("z position [normalized]")
    ax.set_ylabel("z velocity [normalized]")
    fig.colorbar(mesh, ax=ax, label=f"F_z [{FULL_WARNING_LABEL}]")
    fig.savefig(grid_path)
    plt.close(fig)
    paths.append(grid_path)

    position_path = _artifact_path(output_dir, config_name, case_name, "force_vs_position_v0.png")
    fig, ax = plt.subplots()
    ax.plot(positions, force_vs_position, marker="o")
    ax.set_title(f"{title} F_z(z) at v=0")
    ax.set_xlabel("z position [normalized]")
    ax.set_ylabel(f"F_z [{FULL_WARNING_LABEL}]")
    fig.savefig(position_path)
    plt.close(fig)
    paths.append(position_path)

    velocity_path = _artifact_path(output_dir, config_name, case_name, "force_vs_velocity_x0.png")
    fig, ax = plt.subplots()
    ax.plot(velocities, force_vs_velocity, marker="o")
    ax.set_title(f"{title} F_z(v) at z=0")
    ax.set_xlabel("z velocity [normalized]")
    ax.set_ylabel(f"F_z [{FULL_WARNING_LABEL}]")
    fig.savefig(velocity_path)
    plt.close(fig)
    paths.append(velocity_path)

    return paths


def run(output_dir: Path = DEFAULT_OUTPUT_DIR, *, save_plots: bool = True) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    backend = build_mgf_hamiltonian_from_sources(
        approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE
    )
    provenance = backend.provenance

    print("Track P provisional reversal diagnostics")
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

    positions = np.linspace(-0.4, 0.4, 9)
    velocities = np.linspace(-0.4, 0.4, 9)
    zero_position_index = int(np.argmin(np.abs(positions)))
    zero_velocity_index = int(np.argmin(np.abs(velocities)))
    records: list[dict[str, Any]] = []

    for config_path in CONFIG_PATHS:
        source_config = _load_config(config_path)
        config_name = source_config["name"]
        base_config = _base_provisional_config(source_config)

        for case_name in CASE_DEFINITIONS:
            provisional_config = _case_config(base_config, case_name)
            grid = force_grid_1d(
                "z",
                positions,
                velocities,
                backend,
                provisional_config,
            )
            force_vs_position = grid.forces[:, zero_velocity_index]
            force_vs_velocity = grid.forces[zero_position_index, :]
            dF_dx = _central_slope(positions, force_vs_position)
            dF_dv = _central_slope(velocities, force_vs_velocity)
            title = f"{FULL_WARNING_LABEL} run 002 {config_name} {case_name}"

            arrays_path = _artifact_path(output_dir, config_name, case_name, "diagnostics.npz")
            metadata_path = _artifact_path(output_dir, config_name, case_name, "metadata.json")
            np.savez_compressed(
                arrays_path,
                positions=positions,
                velocities=velocities,
                forces=grid.forces,
                force_vs_position_v0=force_vs_position,
                force_vs_velocity_x0=force_vs_velocity,
                dF_dx=np.array(dF_dx),
                dF_dv=np.array(dF_dv),
            )

            plot_paths: list[Path] = []
            plot_error: str | None = None
            if save_plots:
                try:
                    plot_paths = _save_case_plots(
                        output_dir,
                        config_name,
                        case_name,
                        title,
                        positions,
                        velocities,
                        grid.forces,
                        force_vs_position,
                        force_vs_velocity,
                    )
                except Exception as exc:  # pragma: no cover - depends on optional plotting stack
                    plot_error = repr(exc)

            metadata = {
                "label": FULL_WARNING_LABEL,
                "title": title,
                "run_type": f"{FULL_WARNING_LABEL}_run_002_reversal_diagnostics",
                "case": case_name,
                "source_config_path": str(config_path.relative_to(REPO_ROOT)),
                "source_config": source_config,
                "provisional_config": asdict(provisional_config),
                "backend_provenance": _json_safe(provenance),
                "grid_metadata": _json_safe(grid.metadata),
                "axis": grid.axis,
                "positions_shape": list(positions.shape),
                "velocities_shape": list(velocities.shape),
                "forces_shape": list(grid.forces.shape),
                "force_vs_position_shape": list(force_vs_position.shape),
                "force_vs_velocity_shape": list(force_vs_velocity.shape),
                "forces_finite": bool(np.isfinite(grid.forces).all()),
                "force_vs_position_finite": bool(np.isfinite(force_vs_position).all()),
                "force_vs_velocity_finite": bool(np.isfinite(force_vs_velocity).all()),
                "dF_dx": dF_dx,
                "dF_dv": dF_dv,
                "arrays_path": str(arrays_path.relative_to(output_dir)),
                "plot_paths": [str(path.relative_to(output_dir)) for path in plot_paths],
                "plot_error": plot_error,
                "disclaimer": (
                    "PROVISIONAL convention/plumbing diagnostic only; "
                    "NOT_RODRIGUEZ_REPLICATION; no physical conclusions."
                ),
            }
            metadata_path.write_text(
                json.dumps(metadata, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            records.append(
                {
                    "config_name": config_name,
                    "case": case_name,
                    "metadata_path": metadata_path,
                    "arrays_path": arrays_path,
                    "plot_paths": plot_paths,
                    "forces_shape": grid.forces.shape,
                    "force_vs_position_shape": force_vs_position.shape,
                    "force_vs_velocity_shape": force_vs_velocity.shape,
                    "forces_finite": bool(np.isfinite(grid.forces).all()),
                    "dF_dx": dF_dx,
                    "dF_dv": dF_dv,
                }
            )

    report_path = output_dir / f"{FULL_WARNING_LABEL}_run_002_reversal_diagnostics.md"
    report_lines = [
        f"# {FULL_WARNING_LABEL} run 002 reversal diagnostics",
        "",
        "This is a provisional convention/plumbing diagnostic.",
        "",
        "This is not an MgF/Rodriguez reproduction.",
        "Exact MgF force readiness remains blocked by the independent Doppelbauer `d` operator and excited Zeeman mappings.",
        "No physical conclusions should be drawn from force magnitudes, topology, or comparison to Rodriguez figures.",
        "Reversal behavior is used only to catch wiring/sign/configuration errors.",
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
        "## Cases",
        "",
    ]
    for record in records:
        report_lines.extend(
            [
                f"### {FULL_WARNING_LABEL} {record['config_name']} {record['case']}",
                "",
                f"- metadata: `{record['metadata_path'].name}`",
                f"- arrays: `{record['arrays_path'].name}`",
                f"- plots: `{[path.name for path in record['plot_paths']]}`",
                f"- force grid shape: `{tuple(record['forces_shape'])}`",
                f"- F(z)|v=0 shape: `{tuple(record['force_vs_position_shape'])}`",
                f"- F(v)|z=0 shape: `{tuple(record['force_vs_velocity_shape'])}`",
                f"- finite: `{record['forces_finite']}`",
                f"- dF/dx: `{record['dF_dx']:.6g}`",
                f"- dF/dv: `{record['dF_dv']:.6g}`",
                "",
            ]
        )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote report: {report_path}")
    return records


def main() -> None:
    run()


if __name__ == "__main__":
    main()
