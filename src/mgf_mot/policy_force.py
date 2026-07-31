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
class ComponentSnapshotState:
    """Per-component optical state, separating parked detuning from activity."""

    component_id: int
    detuning_gamma: float
    saturation: float
    enabled: bool
    active: bool
    off_reason: str | None
    role: str


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
    component_active: tuple[bool, bool, bool, bool]
    component_off_reasons: tuple[str | None, str | None, str | None, str | None]
    component_states: tuple[
        ComponentSnapshotState,
        ComponentSnapshotState,
        ComponentSnapshotState,
        ComponentSnapshotState,
    ]
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


def force_config_for_policy_sample(
    sample: PolicySample, force_config: ProvisionalForceMapConfig
) -> ProvisionalForceMapConfig:
    """Map one policy sample onto the normalized Track P force-law scale.

    This is an engineering conversion only. Active optical saturation sets the
    diagnostic spring scale; detunings remain metadata and are not interpreted
    as a physical MgF force model.
    """
    if not force_config.explicit_provisional_opt_in:
        raise MgFBackendCapabilityError(
            "policy force snapshots require explicit_provisional_opt_in=True"
        )
    active_saturation = sum(
        component.saturation for component in sample.components if component.active
    )
    return replace(
        force_config,
        normalized_spring=float(active_saturation),
    )


def _off_reason(enabled: bool, saturation: float, configured_reason: str | None) -> str | None:
    if enabled and saturation > 0.0:
        return None
    if configured_reason:
        return configured_reason
    if not enabled and saturation == 0.0:
        return "disabled_zero_saturation"
    if not enabled:
        return "disabled"
    return "zero_saturation"


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
    derived_config = force_config_for_policy_sample(sample, force_config)
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
    active = tuple(bool(component.active) for component in sample.components)
    off_reasons = tuple(
        _off_reason(component.enabled, component.saturation, component.off_reason)
        for component in sample.components
    )
    component_states = tuple(
        ComponentSnapshotState(
            component_id=int(component.component_id),
            detuning_gamma=float(component.detuning_gamma),
            saturation=float(component.saturation),
            enabled=bool(component.enabled),
            active=bool(component.active),
            off_reason=off_reason,
            role=component.role,
        )
        for component, off_reason in zip(sample.components, off_reasons)
    )
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
        component_active=active,  # type: ignore[arg-type]
        component_off_reasons=off_reasons,  # type: ignore[arg-type]
        component_states=component_states,  # type: ignore[arg-type]
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
        beam_mode=grid.metadata.beam_mode,
        position_unit=grid.metadata.position_unit,
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
