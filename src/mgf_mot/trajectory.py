"""Track P trajectory-integration scaffold for provisional plumbing checks.

The policy path in this module is gated to the explicit provisional backend.
Its normalized force-to-acceleration conversion has no MgF calibration and
must not be used for capture, loss, loading, or replication claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import math
import numpy as np
from numpy.typing import NDArray

from .mgf_backend import ApproximateMgFHamiltonian, MgFBackendCapabilityError
from .policies import LaserSchedulePolicy
from .policy_force import force_config_for_policy_sample
from .provisional_force import (
    FULL_WARNING_LABEL,
    ProvisionalForceMapConfig,
    force_at,
)
from .tracks import ProjectTrack

FloatArray = NDArray[np.float64]
AccelerationModel = Callable[[float, FloatArray, FloatArray], FloatArray]

TRAJECTORY_SCAFFOLD_LABEL = (
    f"{FULL_WARNING_LABEL}_TRAJECTORY_SCAFFOLD_ONLY"
)
ANALYTIC_TEST_HOOK_LABEL = "ANALYTIC_INTEGRATOR_TEST_HOOK_ONLY"


def _vector3(values: tuple[float, float, float], label: str) -> FloatArray:
    array = np.asarray(values, dtype=float)
    if array.shape != (3,):
        raise ValueError(f"{label} must contain exactly three values")
    if not np.isfinite(array).all():
        raise ValueError(f"{label} must contain only finite values")
    return array


@dataclass(frozen=True)
class TrajectoryInitialState:
    """One three-dimensional initial state for scaffold integration."""

    position: tuple[float, float, float]
    velocity: tuple[float, float, float]

    def __post_init__(self) -> None:
        _vector3(self.position, "position")
        _vector3(self.velocity, "velocity")


@dataclass(frozen=True)
class TrajectoryConfig:
    """Fixed-step RK4 settings with an explicit normalized force conversion."""

    t_start_s: float
    t_end_s: float
    time_step_s: float
    normalized_force_to_acceleration: float = 1.0
    position_unit: str = "normalized_position"
    velocity_unit: str = "normalized_position_per_s"
    force_unit: str = "normalized_hbar_k_Gamma"

    def __post_init__(self) -> None:
        numeric = {
            "t_start_s": self.t_start_s,
            "t_end_s": self.t_end_s,
            "time_step_s": self.time_step_s,
            "normalized_force_to_acceleration": self.normalized_force_to_acceleration,
        }
        for label, value in numeric.items():
            if not math.isfinite(float(value)):
                raise ValueError(f"{label} must be finite")
        if self.t_end_s <= self.t_start_s:
            raise ValueError("t_end_s must be greater than t_start_s")
        if self.time_step_s <= 0.0:
            raise ValueError("time_step_s must be positive")
        if self.normalized_force_to_acceleration <= 0.0:
            raise ValueError("normalized_force_to_acceleration must be positive")
        for label in ("position_unit", "velocity_unit", "force_unit"):
            if not getattr(self, label):
                raise ValueError(f"{label} must be explicit and non-empty")


@dataclass(frozen=True)
class TrajectoryMetadata:
    """Machine-readable warning and backend status for one Track P result."""

    label: str
    title: str
    filename_stem: str
    track: ProjectTrack
    backend_mode: str
    force_ready: bool
    replication_valid: bool
    policy_name: str
    warnings: tuple[str, ...]
    omitted_terms: tuple[str, ...]
    collapsed_terms: tuple[str, ...]
    position_unit: str
    velocity_unit: str
    force_unit: str
    known_event_times_s: tuple[float, ...]
    encountered_event_times_s: tuple[float, ...]
    event_boundary_convention: str


@dataclass(frozen=True)
class TrajectoryResult:
    """Time series from the gated policy-conditioned trajectory scaffold."""

    times_s: FloatArray
    positions: FloatArray
    velocities: FloatArray
    forces: FloatArray
    component_detunings_gamma: FloatArray
    component_saturations: FloatArray
    component_enabled: NDArray[np.bool_]
    component_active: NDArray[np.bool_]
    policy_segments: tuple[str, ...]
    handoff_occurred: NDArray[np.bool_]
    metadata: TrajectoryMetadata


@dataclass(frozen=True)
class AnalyticIntegratorResult:
    """Integrator-only result that never carries or impersonates an MgF backend."""

    label: str
    model_name: str
    times_s: FloatArray
    positions: FloatArray
    velocities: FloatArray
    accelerations: FloatArray
    uses_mgf_backend: bool = False


def _event_times_in_interval(
    config: TrajectoryConfig, event_times_s: tuple[float, ...]
) -> tuple[float, ...]:
    validated = tuple(_finite_event_time(value) for value in event_times_s)
    if tuple(sorted(set(validated))) != validated:
        raise ValueError("policy event times must be unique and sorted")
    return tuple(
        event
        for event in validated
        if config.t_start_s <= event <= config.t_end_s
    )


def _finite_event_time(value: float) -> float:
    event = float(value)
    if not math.isfinite(event):
        raise ValueError("policy event times must be finite")
    return event


def _time_grid(
    config: TrajectoryConfig, event_times_s: tuple[float, ...] = ()
) -> FloatArray:
    """Build a fixed-step grid restarted at every known policy event."""
    events = _event_times_in_interval(config, event_times_s)
    times = [float(config.t_start_s)]
    while times[-1] < config.t_end_s:
        current = times[-1]
        proposed = min(current + config.time_step_s, config.t_end_s)
        crossed_events = [
            event for event in events if current < event <= proposed
        ]
        next_time = crossed_events[0] if crossed_events else proposed
        if next_time <= current:
            raise RuntimeError("trajectory time grid failed to advance")
        times.append(float(next_time))
    times[-1] = float(config.t_end_s)
    return np.asarray(times, dtype=float)


def _validated_acceleration(
    model: AccelerationModel,
    time_s: float,
    position: FloatArray,
    velocity: FloatArray,
) -> FloatArray:
    acceleration = np.asarray(model(time_s, position, velocity), dtype=float)
    if acceleration.shape != (3,):
        raise ValueError("acceleration model must return a 3-vector")
    if not np.isfinite(acceleration).all():
        raise ValueError("acceleration model returned a non-finite value")
    return acceleration


def _integrate_rk4(
    initial_state: TrajectoryInitialState,
    config: TrajectoryConfig,
    acceleration_model: AccelerationModel,
    event_times_s: tuple[float, ...] = (),
) -> tuple[FloatArray, FloatArray, FloatArray, tuple[float, ...]]:
    interval_events = _event_times_in_interval(config, event_times_s)
    times = _time_grid(config, event_times_s)
    positions = np.empty((times.size, 3), dtype=float)
    velocities = np.empty((times.size, 3), dtype=float)
    positions[0] = _vector3(initial_state.position, "position")
    velocities[0] = _vector3(initial_state.velocity, "velocity")

    def derivative(time_s: float, state: FloatArray) -> FloatArray:
        position = state[:3]
        velocity = state[3:]
        acceleration = _validated_acceleration(
            acceleration_model, time_s, position, velocity
        )
        return np.concatenate((velocity, acceleration))

    for index in range(times.size - 1):
        time_s = float(times[index])
        step_s = float(times[index + 1] - times[index])
        state = np.concatenate((positions[index], velocities[index]))
        k1 = derivative(time_s, state)
        k2 = derivative(time_s + step_s / 2.0, state + step_s * k1 / 2.0)
        k3 = derivative(time_s + step_s / 2.0, state + step_s * k2 / 2.0)
        step_end_s = float(times[index + 1])
        # A step ending at a discontinuity integrates up to its left-hand
        # limit. The next step starts at the exact event time and therefore
        # samples the deterministic post-event (t >= event) policy state.
        k4_time_s = (
            float(np.nextafter(step_end_s, time_s))
            if step_end_s in interval_events and time_s < step_end_s
            else step_end_s
        )
        k4 = derivative(k4_time_s, state + step_s * k3)
        next_state = state + step_s * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        if not np.isfinite(next_state).all():
            raise ValueError("trajectory integration produced a non-finite state")
        positions[index + 1] = next_state[:3]
        velocities[index + 1] = next_state[3:]
    encountered_events = tuple(
        event for event in interval_events if np.any(times == event)
    )
    return times, positions, velocities, encountered_events


def integrate_analytic_test_trajectory(
    initial_state: TrajectoryInitialState,
    trajectory_config: TrajectoryConfig,
    acceleration_model: AccelerationModel,
    *,
    model_name: str,
) -> AnalyticIntegratorResult:
    """Validate RK4 using an explicitly analytic, non-MgF acceleration model."""
    if not model_name:
        raise ValueError("analytic test model_name must be explicit")
    times, positions, velocities, _ = _integrate_rk4(
        initial_state, trajectory_config, acceleration_model
    )
    accelerations = np.asarray(
        [
            _validated_acceleration(acceleration_model, time_s, position, velocity)
            for time_s, position, velocity in zip(times, positions, velocities)
        ],
        dtype=float,
    )
    return AnalyticIntegratorResult(
        label=ANALYTIC_TEST_HOOK_LABEL,
        model_name=model_name,
        times_s=times,
        positions=positions,
        velocities=velocities,
        accelerations=accelerations,
    )


def _require_provisional_trajectory_backend(
    backend: ApproximateMgFHamiltonian,
    force_config: ProvisionalForceMapConfig,
) -> None:
    if not force_config.explicit_provisional_opt_in:
        raise MgFBackendCapabilityError(
            "trajectory scaffold requires explicit_provisional_opt_in=True"
        )
    if not isinstance(backend, ApproximateMgFHamiltonian):
        raise MgFBackendCapabilityError(
            "trajectory scaffold requires a Track P provisional backend"
        )
    if backend.provenance.track is not ProjectTrack.PROVISIONAL:
        raise MgFBackendCapabilityError("trajectory backend provenance is not provisional")
    if backend.provenance.replication_valid:
        raise MgFBackendCapabilityError(
            "provisional trajectory backend must have replication_valid=false"
        )


def integrate_policy_trajectory(
    policy: LaserSchedulePolicy,
    initial_state: TrajectoryInitialState,
    backend: ApproximateMgFHamiltonian,
    force_config: ProvisionalForceMapConfig,
    trajectory_config: TrajectoryConfig,
) -> TrajectoryResult:
    """Integrate one policy-conditioned Track P scaffold trajectory.

    The existing provisional normalized force vector is converted to an
    acceleration only through ``normalized_force_to_acceleration``. This is an
    explicit plumbing scale, not an MgF mass or physical unit conversion.
    """
    _require_provisional_trajectory_backend(backend, force_config)
    if force_config.position_unit != trajectory_config.position_unit:
        raise ValueError(
            "force and trajectory position units must match exactly"
        )

    def acceleration_model(
        time_s: float, position: FloatArray, velocity: FloatArray
    ) -> FloatArray:
        sample = policy.sample(time_s)
        derived_force_config = force_config_for_policy_sample(sample, force_config)
        force, _ = force_at(position, velocity, backend, derived_force_config)
        return (
            np.asarray(force, dtype=float)
            * trajectory_config.normalized_force_to_acceleration
        )

    known_event_times = tuple(float(value) for value in policy.event_times_s)
    times, positions, velocities, encountered_event_times = _integrate_rk4(
        initial_state,
        trajectory_config,
        acceleration_model,
        event_times_s=known_event_times,
    )
    forces = np.empty_like(positions)
    component_detunings = np.empty((times.size, 4), dtype=float)
    component_saturations = np.empty((times.size, 4), dtype=float)
    component_enabled = np.empty((times.size, 4), dtype=bool)
    component_active = np.empty((times.size, 4), dtype=bool)
    policy_segments: list[str] = []
    handoff_occurred = np.empty(times.size, dtype=bool)
    for index, (time_s, position, velocity) in enumerate(
        zip(times, positions, velocities)
    ):
        sample = policy.sample(float(time_s))
        derived_force_config = force_config_for_policy_sample(sample, force_config)
        force, _ = force_at(position, velocity, backend, derived_force_config)
        forces[index] = force
        component_detunings[index] = [
            component.detuning_gamma for component in sample.components
        ]
        component_saturations[index] = [
            component.saturation for component in sample.components
        ]
        component_enabled[index] = [
            component.enabled for component in sample.components
        ]
        component_active[index] = [
            component.active for component in sample.components
        ]
        policy_segments.append(sample.segment)
        handoff_occurred[index] = sample.handoff_occurred

    title = f"{TRAJECTORY_SCAFFOLD_LABEL} {policy.name}"
    filename_stem = f"{TRAJECTORY_SCAFFOLD_LABEL}_{policy.name}"
    provenance = backend.provenance
    metadata = TrajectoryMetadata(
        label=TRAJECTORY_SCAFFOLD_LABEL,
        title=title,
        filename_stem=filename_stem,
        track=ProjectTrack.PROVISIONAL,
        backend_mode=provenance.backend_mode,
        force_ready=False,
        replication_valid=False,
        policy_name=policy.name,
        warnings=provenance.warnings
        + (
            "TRAJECTORY_SCAFFOLD_ONLY: validates policy-to-force-to-integrator plumbing.",
            "Normalized force-to-acceleration scaling is not calibrated to MgF.",
            "No capture, loss, loading, source distribution, or physical inference is defined.",
            "Known policy discontinuities split RK4 steps; pre-event steps use the left-hand endpoint limit.",
        ),
        omitted_terms=provenance.omitted_terms,
        collapsed_terms=provenance.collapsed_terms,
        position_unit=trajectory_config.position_unit,
        velocity_unit=trajectory_config.velocity_unit,
        force_unit=trajectory_config.force_unit,
        known_event_times_s=known_event_times,
        encountered_event_times_s=encountered_event_times,
        event_boundary_convention=(
            "pre-event step k4 uses event left limit; next step starts exactly "
            "at event and uses the t>=event policy state"
        ),
    )
    return TrajectoryResult(
        times_s=times,
        positions=positions,
        velocities=velocities,
        forces=forces,
        component_detunings_gamma=component_detunings,
        component_saturations=component_saturations,
        component_enabled=component_enabled,
        component_active=component_active,
        policy_segments=tuple(policy_segments),
        handoff_occurred=handoff_occurred,
        metadata=metadata,
    )
