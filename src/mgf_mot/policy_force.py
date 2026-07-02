"""Bridge Track P laser policies to provisional frozen-time force grids.

This module evaluates policy samples and static provisional force grids at fixed
times only. It does not integrate trajectories, estimate capture, model
Gaussian beams, optimize parameters, or open exact force-map paths.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from .mgf_backend import ApproximateMgFHamiltonian, MgFBackendCapabilityError
from .policies import LaserSchedulePolicy, PolicySample
from .provisional_force import (
    FULL_WARNING_LABEL,
    Axis,
    ForceGrid1D,
    ForceMapMetadata,
    ProvisionalForceMapConfig,
    force_grid_1d,
)
from .tracks import ProjectTrack

FloatArray = NDArray[np.float64]
POLICY_FORCE_SNAPSHOT_LABEL = f"{FULL_WARNING_LABEL}_POLICY_FORCE_SNAPSHOT_ONLY"


@dataclass(frozen=True)
class PolicyForceGridConfig:
    """Small static grid specification for one frozen-time policy snapshot."""

    axis: Axis = "z"
    positions: tuple[float, ...] = (-0.4, -0.2, 0.0, 0.2, 0.4)
    velocities: tuple[float, ...] = (-0.2, 0.0, 0.2)


@dataclass(frozen=True)
class PolicyForceSnapshotMetadata:
    """Metadata proving the snapshot is provisional and non-replication-valid."""

    label: str
    title: str
    filename_stem: str
    track: ProjectTrack
    backend_mode: str
    replication_valid: bool
    force_ready: bool
    policy_name: str
    policy_type: str
    time_s: float
    component_detunings_gamma: tuple[float, float, float, float]
    component_saturations: tuple[float, float, float, float]
    component_enabled: tuple[bool, bool, bool, bool]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PolicyForceSnapshot:
    """Frozen-time policy sample plus provisional force grid."""

    policy_sample: PolicySample
    derived_force_config: ProvisionalForceMapConfig
    grid: ForceGrid1D
    metadata: PolicyForceSnapshotMetadata


def _require_provisional_backend(backend: ApproximateMgFHamiltonian) -> None:
    if not isinstance(backend, ApproximateMgFHamiltonian):
        raise MgFBackendCapabilityError(
            "policy force snapshots require a Track P provisional backend"
        )
    if backend.provenance.track is not ProjectTrack.PROVISIONAL:
        raise MgFBackendCapabilityError("backend provenance is not provisional")
    if backend.provenance.replication_valid:
        raise MgFBackendCapabilityError("provisional snapshot backend must not be replication-valid")


def _derive_force_config(
    sample: PolicySample, force_config: ProvisionalForceMapConfig
) -> ProvisionalForceMapConfig:
    if not force_config.explicit_provisional_opt_in:
        raise MgFBackendCapabilityError(
            "policy force snapshots require explicit_provisional_opt_in=True"
        )
    enabled_saturation = sum(
        component.saturation for component in sample.components if component.enabled
    )
    # This is a plumbing conversion, not a physical force model. Detunings remain
    # attached to metadata; enabled saturation controls only the diagnostic scale.
    return replace(
        force_config,
        normalized_spring=float(enabled_saturation),
    )


def force_grid_for_policy_snapshot(
    policy: LaserSchedulePolicy,
    t: float,
    backend: ApproximateMgFHamiltonian,
    force_config: ProvisionalForceMapConfig,
    grid_config: PolicyForceGridConfig,
) -> PolicyForceSnapshot:
    """Evaluate one frozen-time policy-conditioned provisional force grid."""
    _require_provisional_backend(backend)
    sample = policy.sample(t)
    derived_config = _derive_force_config(sample, force_config)
    grid = force_grid_1d(
        grid_config.axis,
        np.asarray(grid_config.positions, dtype=float),
        np.asarray(grid_config.velocities, dtype=float),
        backend,
        derived_config,
    )
    detunings = tuple(float(component.detuning_gamma) for component in sample.components)
    saturations = tuple(float(component.saturation) for component in sample.components)
    enabled = tuple(bool(component.enabled) for component in sample.components)
    title = (
        f"{POLICY_FORCE_SNAPSHOT_LABEL} {policy.name} "
        f"t={sample.time_s:.6g}s"
    )
    time_label = f"t_{sample.time_s:.6g}s".replace(".", "p").replace("-", "m")
    filename_stem = f"{POLICY_FORCE_SNAPSHOT_LABEL}_{policy.name}_{time_label}"
    metadata = PolicyForceSnapshotMetadata(
        label=POLICY_FORCE_SNAPSHOT_LABEL,
        title=title,
        filename_stem=filename_stem,
        track=ProjectTrack.PROVISIONAL,
        backend_mode=backend.provenance.backend_mode,
        replication_valid=False,
        force_ready=False,
        policy_name=policy.name,
        policy_type=policy.policy_type,
        time_s=sample.time_s,
        component_detunings_gamma=detunings,  # type: ignore[arg-type]
        component_saturations=saturations,  # type: ignore[arg-type]
        component_enabled=enabled,  # type: ignore[arg-type]
        warnings=backend.provenance.warnings
        + (
            "POLICY_FORCE_SNAPSHOT_ONLY: frozen-time static grid; no dynamics.",
            "No physical conclusions should be drawn from provisional force magnitudes or topology.",
        ),
    )
    grid_metadata = ForceMapMetadata(
        track=grid.metadata.track,
        backend_mode=grid.metadata.backend_mode,
        force_ready=False,
        replication_valid=False,
        label=POLICY_FORCE_SNAPSHOT_LABEL,
        title=title,
        filename=f"{filename_stem}_grid.png",
        warnings=grid.metadata.warnings + metadata.warnings,
        omitted_terms=grid.metadata.omitted_terms,
        collapsed_terms=grid.metadata.collapsed_terms,
    )
    labeled_grid = ForceGrid1D(
        axis=grid.axis,
        positions=grid.positions,
        velocities=grid.velocities,
        forces=grid.forces,
        metadata=grid_metadata,
    )
    return PolicyForceSnapshot(
        policy_sample=sample,
        derived_force_config=derived_config,
        grid=labeled_grid,
        metadata=metadata,
    )
