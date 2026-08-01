"""Provisional static force-map plumbing for non-replication diagnostics.

The functions in this module are deliberately gated engineering utilities. They
do not claim Rodriguez/MgF force validity and do not use exact-track backends.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from .gaussian_beams import GaussianBeamSet
from .mgf_backend import ApproximateMgFHamiltonian, MgFBackendCapabilityError
from .tracks import BackendProvenance, ProjectTrack

Axis = Literal["x", "y", "z"]
BeamMode = Literal["plane_wave", "elliptical_gaussian"]
FloatArray = NDArray[np.float64]

PROVISIONAL_LABEL = "PROVISIONAL"
NOT_REPLICATION_LABEL = "NOT_RODRIGUEZ_REPLICATION"
FULL_WARNING_LABEL = f"{PROVISIONAL_LABEL}_{NOT_REPLICATION_LABEL}"


@dataclass(frozen=True)
class ToyHeuristicForceBackend:
    """Identity card for the historical spring/damping plumbing law."""

    force_model: str = "toy_heuristic_spring_damping"
    physics_valid: bool = False
    physics_scope: str = "analytic_and_interface_plumbing_only"
    supersedes_run_outputs: str = (
        "Run 008B supersedes physical interpretation of force-dependent Runs 001-008"
    )
    warnings: tuple[str, ...] = (
        "PLUMBING_ONLY: not a physical force backend.",
        "The toy law ignores detuning, components, populations, and Hamiltonian topology.",
    )


TOY_HEURISTIC_FORCE_BACKEND = ToyHeuristicForceBackend()


@dataclass(frozen=True)
class ProvisionalForceMapConfig:
    """Explicit opt-in configuration for provisional normalized force plumbing."""

    explicit_provisional_opt_in: bool = False
    normalized_spring: float = 1.0
    normalized_damping: float = 0.2
    flipped_polarization: bool = False
    flipped_gradient: bool = False
    units: str = "hbar*k*Gamma"
    beam_mode: BeamMode = "plane_wave"
    gaussian_beam_set: GaussianBeamSet | None = None
    position_unit: str = "normalized_position"
    magnetic_gradient_t_m: float | None = None
    normalized_gradient_scale: float = 1.0

    def __post_init__(self) -> None:
        if self.beam_mode == "plane_wave":
            if self.gaussian_beam_set is not None:
                raise ValueError(
                    "gaussian_beam_set requires beam_mode='elliptical_gaussian'"
                )
        elif self.beam_mode == "elliptical_gaussian":
            if self.gaussian_beam_set is None:
                raise ValueError(
                    "elliptical_gaussian mode requires an explicit GaussianBeamSet"
                )
            if self.position_unit != "m":
                raise ValueError(
                    "elliptical_gaussian force positions must use position_unit='m'"
                )
        else:
            raise ValueError(f"unsupported beam_mode {self.beam_mode!r}")
        if not self.position_unit:
            raise ValueError("position_unit must be explicit")
        if self.magnetic_gradient_t_m is not None and (
            not np.isfinite(self.magnetic_gradient_t_m)
            or self.magnetic_gradient_t_m == 0.0
        ):
            raise ValueError("magnetic_gradient_t_m must be finite and nonzero")
        if (
            not np.isfinite(self.normalized_gradient_scale)
            or self.normalized_gradient_scale <= 0.0
        ):
            raise ValueError("normalized_gradient_scale must be finite and positive")


@dataclass(frozen=True)
class ForceMapMetadata:
    """Warning metadata attached to every provisional force-map output."""

    track: ProjectTrack
    backend_mode: str
    force_ready: bool
    replication_valid: bool
    label: str
    title: str
    filename: str
    warnings: tuple[str, ...]
    omitted_terms: tuple[str, ...]
    collapsed_terms: tuple[str, ...]
    beam_mode: BeamMode
    position_unit: str
    force_model: str = TOY_HEURISTIC_FORCE_BACKEND.force_model
    physics_valid: bool = TOY_HEURISTIC_FORCE_BACKEND.physics_valid
    physics_scope: str = TOY_HEURISTIC_FORCE_BACKEND.physics_scope
    supersedes_run_outputs: str = TOY_HEURISTIC_FORCE_BACKEND.supersedes_run_outputs


@dataclass(frozen=True)
class ForceGrid1D:
    axis: Axis
    positions: FloatArray
    velocities: FloatArray
    forces: FloatArray
    metadata: ForceMapMetadata


def _axis_index(axis: Axis) -> int:
    return {"x": 0, "y": 1, "z": 2}[axis]


def _require_provisional_backend(
    backend: ApproximateMgFHamiltonian,
    config: ProvisionalForceMapConfig,
) -> BackendProvenance:
    if not config.explicit_provisional_opt_in:
        raise MgFBackendCapabilityError(
            "provisional force-map harness requires explicit_provisional_opt_in=True"
        )
    if not isinstance(backend, ApproximateMgFHamiltonian):
        raise MgFBackendCapabilityError(
            "force maps are available only for the provisional track while the exact backend is blocked"
        )
    provenance = backend.provenance
    if provenance.track is not ProjectTrack.PROVISIONAL:
        raise MgFBackendCapabilityError("backend provenance is not provisional")
    if provenance.replication_valid:
        raise MgFBackendCapabilityError("provisional outputs must not be replication-valid")
    return provenance


def _metadata(
    *,
    backend: ApproximateMgFHamiltonian,
    config: ProvisionalForceMapConfig,
    diagnostic_name: str,
    axis: Axis | None = None,
) -> ForceMapMetadata:
    provenance = _require_provisional_backend(backend, config)
    axis_part = "all_axes" if axis is None else f"{axis}_axis"
    title = f"{FULL_WARNING_LABEL} {diagnostic_name} {axis_part}"
    filename = f"{FULL_WARNING_LABEL}_{diagnostic_name}_{axis_part}.png"
    return ForceMapMetadata(
        track=ProjectTrack.PROVISIONAL,
        backend_mode=provenance.backend_mode,
        force_ready=False,
        replication_valid=False,
        label=FULL_WARNING_LABEL,
        title=title,
        filename=filename,
        warnings=provenance.warnings
        + (
            "Diagnostic normalized force law for plumbing only.",
            f"Output units are normalized {config.units}; not calibrated to MgF.",
            f"Beam mode is explicitly {config.beam_mode}.",
            (
                "Physical magnetic gradient is not source-configured in this force call."
                if config.magnetic_gradient_t_m is None
                else (
                    f"Source magnetic gradient {config.magnetic_gradient_t_m} T/m "
                    f"is represented by normalized scale {config.normalized_gradient_scale}."
                )
            ),
        ),
        omitted_terms=provenance.omitted_terms,
        collapsed_terms=provenance.collapsed_terms,
        beam_mode=config.beam_mode,
        position_unit=config.position_unit,
    )


def force_at(
    position: FloatArray,
    velocity: FloatArray,
    backend: ApproximateMgFHamiltonian,
    config: ProvisionalForceMapConfig,
) -> tuple[FloatArray, ForceMapMetadata]:
    """Return a provisional normalized diagnostic force vector.

    The diagnostic law is intentionally simple:

    ``F = s*(-k*x) - beta*v``, where ``s`` flips when exactly one of
    polarization or magnetic-gradient orientation is flipped.
    """
    metadata = _metadata(backend=backend, config=config, diagnostic_name="force_at")
    r = np.asarray(position, dtype=float)
    v = np.asarray(velocity, dtype=float)
    if r.shape != (3,) or v.shape != (3,):
        raise ValueError("position and velocity must both be 3-vectors")
    restoring_sign = -1.0 if (config.flipped_polarization ^ config.flipped_gradient) else 1.0
    force = (
        restoring_sign * (-config.normalized_spring * r)
        - config.normalized_damping * v
    )
    if config.beam_mode == "elliptical_gaussian":
        if config.gaussian_beam_set is None:  # guarded by config validation
            raise RuntimeError("Gaussian beam set missing after config validation")
        force = force * config.gaussian_beam_set.mean_envelope(r)
    return np.asarray(force, dtype=float), metadata


def force_grid_1d(
    axis: Axis,
    positions: FloatArray,
    velocities: FloatArray,
    backend: ApproximateMgFHamiltonian,
    config: ProvisionalForceMapConfig,
) -> ForceGrid1D:
    """Evaluate the provisional diagnostic force component on a 1D grid."""
    metadata = _metadata(
        backend=backend,
        config=config,
        diagnostic_name="force_grid_1d",
        axis=axis,
    )
    idx = _axis_index(axis)
    xs = np.asarray(positions, dtype=float)
    vs = np.asarray(velocities, dtype=float)
    forces = np.empty((xs.size, vs.size), dtype=float)
    for i, x_value in enumerate(xs):
        for j, v_value in enumerate(vs):
            position = np.zeros(3, dtype=float)
            velocity = np.zeros(3, dtype=float)
            position[idx] = x_value
            velocity[idx] = v_value
            force, _ = force_at(position, velocity, backend, config)
            forces[i, j] = force[idx]
    return ForceGrid1D(axis=axis, positions=xs, velocities=vs, forces=forces, metadata=metadata)


def diagnostic_configs() -> dict[str, ProvisionalForceMapConfig]:
    """Return nominal and sign-flip provisional diagnostic configurations."""
    base = dict(explicit_provisional_opt_in=True)
    return {
        "nominal": ProvisionalForceMapConfig(**base),
        "flipped_polarization": ProvisionalForceMapConfig(
            **base, flipped_polarization=True
        ),
        "flipped_gradient": ProvisionalForceMapConfig(**base, flipped_gradient=True),
        "flipped_both": ProvisionalForceMapConfig(
            **base, flipped_polarization=True, flipped_gradient=True
        ),
    }


def normalized_force_plot_spec(grid: ForceGrid1D) -> dict[str, object]:
    """Return a plotting spec whose title/filename carry mandatory warnings."""
    return {
        "title": grid.metadata.title,
        "filename": grid.metadata.filename,
        "xlabel": f"{grid.axis} position [normalized]",
        "ylabel": f"{grid.axis} velocity [normalized]",
        "zlabel": f"F_{grid.axis} [{grid.metadata.label}; {grid.metadata.replication_valid=}]",
        "warnings": grid.metadata.warnings,
    }


def save_normalized_force_plot(grid: ForceGrid1D, output_dir: str | Path) -> Path:
    """Save a visibly labeled provisional force-grid image using matplotlib."""
    import matplotlib.pyplot as plt

    spec = normalized_force_plot_spec(grid)
    output_path = Path(output_dir) / str(spec["filename"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots()
    mesh = ax.imshow(
        grid.forces.T,
        origin="lower",
        aspect="auto",
        extent=[
            float(grid.positions.min()),
            float(grid.positions.max()),
            float(grid.velocities.min()),
            float(grid.velocities.max()),
        ],
    )
    ax.set_title(str(spec["title"]))
    ax.set_xlabel(str(spec["xlabel"]))
    ax.set_ylabel(str(spec["ylabel"]))
    fig.colorbar(mesh, ax=ax, label=str(spec["zlabel"]))
    fig.savefig(output_path)
    plt.close(fig)
    return output_path
