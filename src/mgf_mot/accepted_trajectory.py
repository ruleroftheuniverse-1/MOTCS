"""Accepted Run 010 force-field adapter and event-aware Run 011 integrator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
import math

import numpy as np
from numpy.typing import NDArray

from .accepted_backend import (
    AcceptedProvisionalBackendSelection,
    build_accepted_force_field_provenance,
    build_accepted_provisional_rateeq_backend,
)
from .force_field import (
    FORCE_FIELD_LABEL,
    ForceFieldDomain,
    ForceFieldDomainError,
    InterpolatedForceField,
    load_force_field_cache,
)
from .force_units import (
    MgFForceUnitAudit,
    normalized_force_to_acceleration_m_s2,
    normalized_force_to_newtons,
)
from .gaussian_beams import build_rodriguez_gaussian_beam_set, load_gaussian_envelope_config
from .mgf_backend import MgFBackendCapabilityError
from .policies import ChirpToTrapHandoffPolicy
from .tracks import ProjectTrack
from .trajectory import TrajectoryInitialState


FloatArray = NDArray[np.float64]
RUN011_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_"
    "ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011"
)


class IntegrationTerminationStatus(str, Enum):
    COMPLETED_TIME_INTERVAL = "COMPLETED_TIME_INTERVAL"
    FORCE_FIELD_DOMAIN_EXIT = "FORCE_FIELD_DOMAIN_EXIT"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


@dataclass(frozen=True)
class ForceFieldDomainExitRecord:
    time_s: float
    position_m: float
    velocity_m_s: float
    detuning_gamma: float | None
    policy_segment: str
    field_selection: str
    violated_coordinate: str
    attempted_value: float
    lower_boundary: float
    upper_boundary: float
    message: str


@dataclass(frozen=True)
class AcceptedForceEvaluation:
    normalized_force_x: float
    force_x_n: float
    acceleration_x_m_s2: float
    policy_segment: str
    detuning_gamma: float
    component_detunings_gamma: tuple[float, float, float, float]
    component_saturations: tuple[float, float, float, float]
    component_active: tuple[bool, bool, bool, bool]
    field_selection: str
    gaussian_envelope_mean: float
    gaussian_envelope_minimum: float
    gaussian_envelope_maximum: float
    interpolation_cell_indices: tuple[int, ...]
    interpolation_fractions: tuple[float, ...]


@dataclass(frozen=True)
class AcceptedTrajectoryMetadata:
    label: str
    title: str
    track: ProjectTrack
    replication_valid: bool
    accepted_backend_selection: dict
    pre_cache_key: str
    post_cache_key: str
    force_conversion_count: int
    handoff_time_s: float
    handoff_boundary_convention: str
    timestep_s: float
    duration_s: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AcceptedTrajectoryResult:
    times_s: FloatArray
    positions: FloatArray
    velocities: FloatArray
    normalized_forces_x: FloatArray
    forces_x_n: FloatArray
    accelerations_x_m_s2: FloatArray
    cumulative_impulse_x_n_s: FloatArray
    cumulative_integrated_acceleration_x_m_s: FloatArray
    policy_segments: tuple[str, ...]
    chirp_detunings_gamma: FloatArray
    component_detunings_gamma: FloatArray
    component_saturations: FloatArray
    component_active: NDArray[np.bool_]
    field_selections: tuple[str, ...]
    gaussian_envelope_mean: FloatArray
    gaussian_envelope_minimum: FloatArray
    gaussian_envelope_maximum: FloatArray
    interpolation_cell_indices: tuple[tuple[int, ...], ...]
    interpolation_fractions: tuple[tuple[float, ...], ...]
    handoff_event_times_s: tuple[float, ...]
    termination_status: IntegrationTerminationStatus
    domain_exit: ForceFieldDomainExitRecord | None
    numerical_failure_reason: str | None
    metadata: AcceptedTrajectoryMetadata


class _DomainExitSignal(RuntimeError):
    def __init__(self, record: ForceFieldDomainExitRecord):
        super().__init__(record.message)
        self.record = record


def _cache_paths(repo_root: Path, kind: str) -> tuple[Path, Path]:
    stem = f"{FORCE_FIELD_LABEL}_{kind}_run_010"
    base = repo_root / "outputs" / "provisional" / "force_fields"
    return base / f"{stem}.npz", base / f"{stem}_metadata.json"


def _bracket_metadata(axis: FloatArray, value: float) -> tuple[int, float]:
    if value == axis[-1]:
        return len(axis) - 2, 1.0
    index = int(np.searchsorted(axis, value, side="right") - 1)
    index = max(0, min(index, len(axis) - 2))
    return index, float((value - axis[index]) / (axis[index + 1] - axis[index]))


class InterpolatedRateEquationTrajectoryForce:
    """The only accepted force adapter for Run 011 named trajectories."""

    def __init__(
        self,
        *,
        repo_root: Path,
        explicit_provisional_opt_in: bool,
        acknowledge_midpoint_not_measured: bool,
        track: ProjectTrack = ProjectTrack.PROVISIONAL,
    ):
        if not explicit_provisional_opt_in:
            raise MgFBackendCapabilityError("Run 011 requires explicit provisional opt-in")
        if not acknowledge_midpoint_not_measured:
            raise MgFBackendCapabilityError(
                "Run 011 requires acknowledgment that 0.5 MHz is an interval midpoint, not measured"
            )
        if track is not ProjectTrack.PROVISIONAL:
            raise MgFBackendCapabilityError("Run 011 force adapter is unavailable on Track E")
        self.repo_root = Path(repo_root).resolve()
        self.selection = AcceptedProvisionalBackendSelection()
        self.backend = build_accepted_provisional_rateeq_backend(
            explicit_provisional_opt_in=True, selection=self.selection
        )
        pre_provenance = build_accepted_force_field_provenance(
            repo_root=self.repo_root,
            backend=self.backend,
            selection=self.selection,
            field_kind="pre_handoff_chirp_3",
        )
        post_provenance = build_accepted_force_field_provenance(
            repo_root=self.repo_root,
            backend=self.backend,
            selection=self.selection,
            field_kind="post_handoff_trap_3_plus_1",
        )
        self.pre = InterpolatedForceField(
            load_force_field_cache(*_cache_paths(self.repo_root, "pre_handoff_chirp_3"), pre_provenance)
        )
        self.post = InterpolatedForceField(
            load_force_field_cache(*_cache_paths(self.repo_root, "post_handoff_trap_3_plus_1"), post_provenance)
        )
        self.pre_cache_key = pre_provenance.cache_key
        self.post_cache_key = post_provenance.cache_key
        self.force_units: MgFForceUnitAudit = self.backend.force_units
        if self.force_units.conversion_count != 1:
            raise MgFBackendCapabilityError("accepted force conversion must be applied exactly once")
        gaussian_config = load_gaussian_envelope_config(
            self.repo_root / "configs" / "rodriguez_gaussian_baseline.yaml"
        )
        self.gaussian3 = build_rodriguez_gaussian_beam_set(
            gaussian_config, (1.45, 1.45, 2.89, 0.0)
        )
        self.gaussian31 = build_rodriguez_gaussian_beam_set(
            gaussian_config, (1.45, 1.45, 2.17, 0.72)
        )

    @staticmethod
    def _violation(
        domain: ForceFieldDomain, x: float, v: float, detuning: float | None
    ) -> tuple[str, float, float, float] | None:
        checks = [("position_m", x, domain.positions_m[0], domain.positions_m[-1]),
                  ("velocity_m_s", v, domain.velocities_m_s[0], domain.velocities_m_s[-1])]
        if domain.detunings_gamma is not None and detuning is not None:
            checks.append(("detuning_gamma", detuning, domain.detunings_gamma[0], domain.detunings_gamma[-1]))
        for name, value, lower, upper in checks:
            if value < lower or value > upper:
                return name, float(value), float(lower), float(upper)
        return None

    def evaluate(
        self,
        policy: ChirpToTrapHandoffPolicy,
        time_s: float,
        position_m: float,
        velocity_m_s: float,
    ) -> AcceptedForceEvaluation:
        sample = policy.sample(float(time_s))
        pre = time_s < policy.handoff_time_s
        detunings = tuple(float(c.detuning_gamma) for c in sample.components)
        saturations = tuple(float(c.saturation) for c in sample.components)
        active = tuple(bool(c.active) for c in sample.components)
        detuning = detunings[0]
        if pre:
            if detunings[:3] != (detuning, detuning, detuning) or active != (True, True, True, False):
                raise MgFBackendCapabilityError("Run 011 pre-handoff policy state changed")
            field, selection, beams = self.pre, "pre_handoff_chirp_3", self.gaussian3
            query_detuning: float | None = detuning
        else:
            if detunings != (-1.0, -1.0, -1.0, 2.0) or active != (True, True, True, True):
                raise MgFBackendCapabilityError("Run 011 post-handoff policy state changed")
            field, selection, beams = self.post, "post_handoff_trap_3_plus_1", self.gaussian31
            query_detuning = None
        violation = self._violation(field.grid.domain, position_m, velocity_m_s, query_detuning)
        if violation is not None:
            coordinate, value, lower, upper = violation
            record = ForceFieldDomainExitRecord(
                time_s=float(time_s), position_m=float(position_m), velocity_m_s=float(velocity_m_s),
                detuning_gamma=query_detuning, policy_segment=sample.segment,
                field_selection=selection, violated_coordinate=coordinate,
                attempted_value=value, lower_boundary=lower, upper_boundary=upper,
                message=f"{coordinate}={value} outside [{lower},{upper}]; no clamping/extrapolation",
            )
            raise _DomainExitSignal(record)
        try:
            normalized = field.force_normalized(position_m, velocity_m_s, query_detuning)
        except ForceFieldDomainError as exc:
            raise RuntimeError("domain precheck and interpolation domain check disagree") from exc
        force_n = float(normalized_force_to_newtons(normalized, self.force_units))
        acceleration = float(normalized_force_to_acceleration_m_s2(normalized, self.force_units))
        envelope_values = tuple(beams.envelopes(np.array([position_m, 0.0, 0.0])).values())
        ix, tx = _bracket_metadata(field.grid.domain.positions_m, position_m)
        iv, tv = _bracket_metadata(field.grid.domain.velocities_m_s, velocity_m_s)
        indices, fractions = (ix, iv), (tx, tv)
        if query_detuning is not None:
            idelta, td = _bracket_metadata(field.grid.domain.detunings_gamma, query_detuning)
            indices, fractions = indices + (idelta,), fractions + (td,)
        return AcceptedForceEvaluation(
            normalized_force_x=normalized, force_x_n=force_n,
            acceleration_x_m_s2=acceleration, policy_segment=sample.segment,
            detuning_gamma=detuning, component_detunings_gamma=detunings,  # type: ignore[arg-type]
            component_saturations=saturations, component_active=active,  # type: ignore[arg-type]
            field_selection=selection, gaussian_envelope_mean=float(np.mean(envelope_values)),
            gaussian_envelope_minimum=float(np.min(envelope_values)),
            gaussian_envelope_maximum=float(np.max(envelope_values)),
            interpolation_cell_indices=indices, interpolation_fractions=fractions,
        )


def _next_time(current: float, end: float, step: float, event: float) -> float:
    proposed = min(current + step, end)
    return event if current < event <= proposed else proposed


def integrate_accepted_force_field_trajectory(
    *,
    adapter: InterpolatedRateEquationTrajectoryForce,
    policy: ChirpToTrapHandoffPolicy,
    initial_state: TrajectoryInitialState,
    duration_s: float,
    timestep_s: float,
) -> AcceptedTrajectoryResult:
    """Integrate one named 1D trajectory, stopping cleanly on domain exit."""

    if duration_s <= 0 or timestep_s <= 0 or timestep_s >= duration_s:
        raise ValueError("duration and timestep must be finite, positive, and ordered")
    if tuple(initial_state.position[1:]) != (0.0, 0.0) or tuple(initial_state.velocity[1:]) != (0.0, 0.0):
        raise ValueError("Run 011 permits motion only along lab x")
    times = [0.0]
    positions = [np.asarray(initial_state.position, dtype=float)]
    velocities = [np.asarray(initial_state.velocity, dtype=float)]
    cumulative_impulses = [0.0]
    cumulative_accelerations = [0.0]
    termination = IntegrationTerminationStatus.COMPLETED_TIME_INTERVAL
    domain_exit = None
    numerical_failure = None

    def derivative(t: float, state: FloatArray) -> FloatArray:
        evaluation = adapter.evaluate(policy, t, float(state[0]), float(state[3]))
        return np.array([state[3], 0.0, 0.0, evaluation.acceleration_x_m_s2, 0.0, 0.0])

    while times[-1] < duration_s:
        t = times[-1]
        next_t = _next_time(t, duration_s, timestep_s, policy.handoff_time_s)
        dt = next_t - t
        state = np.concatenate((positions[-1], velocities[-1]))
        try:
            k1 = derivative(t, state)
            k2 = derivative(t + dt / 2, state + dt * k1 / 2)
            k3 = derivative(t + dt / 2, state + dt * k2 / 2)
            k4_t = float(np.nextafter(next_t, t)) if next_t == policy.handoff_time_s and t < next_t else next_t
            k4 = derivative(k4_t, state + dt * k3)
            next_state = state + dt * (k1 + 2*k2 + 2*k3 + k4) / 6
            integrated_acceleration = dt * (k1[3] + 2*k2[3] + 2*k3[3] + k4[3]) / 6
            if not np.isfinite(next_state).all():
                raise FloatingPointError("RK4 produced a nonfinite state")
        except _DomainExitSignal as exc:
            termination = IntegrationTerminationStatus.FORCE_FIELD_DOMAIN_EXIT
            record = exc.record
            coordinate_current = state[0] if record.violated_coordinate == "position_m" else state[3]
            coordinate_attempted = record.position_m if record.violated_coordinate == "position_m" else record.velocity_m_s
            boundary = record.upper_boundary if coordinate_attempted > record.upper_boundary else record.lower_boundary
            denominator = coordinate_attempted - coordinate_current
            fraction = 0.0 if denominator == 0 else float(np.clip((boundary - coordinate_current) / denominator, 0.0, 1.0))
            exit_time = t + fraction * (record.time_s - t)
            exit_position = float(state[0] + fraction * (record.position_m - state[0]))
            exit_velocity = float(state[3] + fraction * (record.velocity_m_s - state[3]))
            if record.violated_coordinate == "position_m":
                exit_position = boundary
            else:
                exit_velocity = boundary
            domain_exit = replace(
                record, time_s=exit_time, position_m=exit_position,
                velocity_m_s=exit_velocity,
                message=record.message + "; termination localized to exact boundary",
            )
            if exit_time > t:
                times.append(float(exit_time))
                exit_state = state.copy()
                exit_state[0], exit_state[3] = exit_position, exit_velocity
                positions.append(exit_state[:3])
                velocities.append(exit_state[3:])
                delta_v = exit_velocity - float(state[3])
                cumulative_accelerations.append(cumulative_accelerations[-1] + delta_v)
                cumulative_impulses.append(
                    cumulative_impulses[-1] + adapter.force_units.mass.value_kg * delta_v
                )
            break
        except (ArithmeticError, FloatingPointError, ValueError) as exc:
            termination, numerical_failure = IntegrationTerminationStatus.NUMERICAL_FAILURE, str(exc)
            break
        times.append(float(next_t))
        positions.append(next_state[:3])
        velocities.append(next_state[3:])
        cumulative_accelerations.append(cumulative_accelerations[-1] + integrated_acceleration)
        cumulative_impulses.append(
            cumulative_impulses[-1]
            + adapter.force_units.mass.value_kg * integrated_acceleration
        )

    time_array = np.asarray(times, dtype=float)
    position_array = np.asarray(positions, dtype=float)
    velocity_array = np.asarray(velocities, dtype=float)
    evaluations = [
        adapter.evaluate(policy, float(t), float(r[0]), float(v[0]))
        for t, r, v in zip(time_array, position_array, velocity_array)
    ]
    normalized = np.array([e.normalized_force_x for e in evaluations])
    force_n = np.array([e.force_x_n for e in evaluations])
    acceleration = np.array([e.acceleration_x_m_s2 for e in evaluations])
    impulse = np.asarray(cumulative_impulses, dtype=float)
    integrated_acceleration_array = np.asarray(cumulative_accelerations, dtype=float)
    encountered = (policy.handoff_time_s,) if np.any(time_array == policy.handoff_time_s) else ()
    metadata = AcceptedTrajectoryMetadata(
        label=RUN011_LABEL, title=f"{RUN011_LABEL} accepted interpolated trajectory",
        track=ProjectTrack.PROVISIONAL, replication_valid=False,
        accepted_backend_selection=asdict(adapter.selection),
        pre_cache_key=adapter.pre_cache_key, post_cache_key=adapter.post_cache_key,
        force_conversion_count=adapter.force_units.conversion_count,
        handoff_time_s=policy.handoff_time_s,
        handoff_boundary_convention="t < tau pre; t >= tau post; event-aware RK4; no smoothing",
        timestep_s=timestep_s, duration_s=duration_s,
        warnings=(
            "PROVISIONAL accepted-force-field named trajectory only.",
            "NOT_RODRIGUEZ_REPLICATION; exact Track E remains blocked.",
            "BOUNDED_FINAL_STATE is an engineering outcome and is not CAPTURED.",
        ),
    )
    return AcceptedTrajectoryResult(
        times_s=time_array, positions=position_array, velocities=velocity_array,
        normalized_forces_x=normalized, forces_x_n=force_n,
        accelerations_x_m_s2=acceleration, cumulative_impulse_x_n_s=impulse,
        cumulative_integrated_acceleration_x_m_s=integrated_acceleration_array,
        policy_segments=tuple(e.policy_segment for e in evaluations),
        chirp_detunings_gamma=np.array([e.detuning_gamma for e in evaluations]),
        component_detunings_gamma=np.array([e.component_detunings_gamma for e in evaluations]),
        component_saturations=np.array([e.component_saturations for e in evaluations]),
        component_active=np.array([e.component_active for e in evaluations], dtype=bool),
        field_selections=tuple(e.field_selection for e in evaluations),
        gaussian_envelope_mean=np.array([e.gaussian_envelope_mean for e in evaluations]),
        gaussian_envelope_minimum=np.array([e.gaussian_envelope_minimum for e in evaluations]),
        gaussian_envelope_maximum=np.array([e.gaussian_envelope_maximum for e in evaluations]),
        interpolation_cell_indices=tuple(e.interpolation_cell_indices for e in evaluations),
        interpolation_fractions=tuple(e.interpolation_fractions for e in evaluations),
        handoff_event_times_s=encountered, termination_status=termination,
        domain_exit=domain_exit, numerical_failure_reason=numerical_failure, metadata=metadata,
    )
