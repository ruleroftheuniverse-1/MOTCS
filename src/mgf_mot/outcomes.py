"""Provisional trajectory outcome classification and ordered ensemble plumbing.

The labels in this module are engineering outcomes, not physical MOT capture
claims. The ensemble path is restricted to the explicit Track P backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol

import math
import numpy as np
from numpy.typing import NDArray

from .mgf_backend import ApproximateMgFHamiltonian, MgFBackendCapabilityError
from .policies import LaserSchedulePolicy
from .provisional_force import FULL_WARNING_LABEL, ProvisionalForceMapConfig
from .tracks import ProjectTrack
from .trajectory import (
    TrajectoryConfig,
    TrajectoryInitialState,
    TrajectoryResult,
    integrate_policy_trajectory,
)

FloatArray = NDArray[np.float64]
PositionMeasure = Literal["radius", "max_abs_coordinate"]

OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL = (
    f"{FULL_WARNING_LABEL}_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY"
)


class OutcomeLabel(str, Enum):
    """Explicit provisional outcome categories."""

    BOUNDED_FINAL_STATE = "BOUNDED_FINAL_STATE"
    ESCAPED = "ESCAPED"
    UNRESOLVED = "UNRESOLVED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class OutcomeCriteria:
    """Engineering-defined bounds applied over a final dwell window."""

    max_position: float
    max_speed: float
    final_dwell_window_s: float
    min_dwell_samples: int = 3
    required_dwell_fraction: float = 1.0
    position_measure: PositionMeasure = "radius"
    hard_escape_position: float | None = None
    hard_speed: float | None = None
    position_unit: str = "normalized_position"
    speed_unit: str = "normalized_position_per_s"

    def __post_init__(self) -> None:
        finite_positive = {
            "max_position": self.max_position,
            "max_speed": self.max_speed,
            "final_dwell_window_s": self.final_dwell_window_s,
        }
        for name, value in finite_positive.items():
            if not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.min_dwell_samples < 2:
            raise ValueError("min_dwell_samples must be at least 2")
        if (
            not math.isfinite(float(self.required_dwell_fraction))
            or not 0.0 < self.required_dwell_fraction <= 1.0
        ):
            raise ValueError("required_dwell_fraction must be in (0, 1]")
        if self.position_measure not in ("radius", "max_abs_coordinate"):
            raise ValueError(
                "position_measure must be 'radius' or 'max_abs_coordinate'"
            )
        for name in ("hard_escape_position", "hard_speed"):
            value = getattr(self, name)
            if value is not None and (
                not math.isfinite(float(value)) or float(value) <= 0.0
            ):
                raise ValueError(f"{name} must be finite and positive when set")
        if (
            self.hard_escape_position is not None
            and self.hard_escape_position < self.max_position
        ):
            raise ValueError("hard_escape_position must not be below max_position")
        if self.hard_speed is not None and self.hard_speed < self.max_speed:
            raise ValueError("hard_speed must not be below max_speed")
        if not self.position_unit or not self.speed_unit:
            raise ValueError("outcome units must be explicit and non-empty")


@dataclass(frozen=True)
class TrajectoryOutcome:
    """One explicit label plus the numerical reason supporting it."""

    label: OutcomeLabel
    numerical_reason: str
    dwell_start_s: float | None
    dwell_end_s: float | None
    dwell_sample_count: int
    dwell_in_bounds_count: int
    dwell_in_bounds_fraction: float | None
    max_position_overall: float | None
    max_speed_overall: float | None
    max_position_dwell: float | None
    max_speed_dwell: float | None


class ClassifiableTrajectory(Protocol):
    times_s: FloatArray
    positions: FloatArray
    velocities: FloatArray


@dataclass(frozen=True)
class EnsembleMemberProvenance:
    """Full Track P status attached to every ordered ensemble member."""

    label: str
    title: str
    track: ProjectTrack
    backend_mode: str
    replication_valid: bool
    force_ready: bool
    omitted_terms: tuple[str, ...]
    collapsed_terms: tuple[str, ...]
    policy_name: str
    initial_state: TrajectoryInitialState
    integration_status: str
    outcome_label: OutcomeLabel
    numerical_reason: str


@dataclass(frozen=True)
class TrajectoryEnsembleMember:
    """One input state, optional result, outcome, and complete provenance."""

    initial_state: TrajectoryInitialState
    trajectory: TrajectoryResult | None
    outcome: TrajectoryOutcome
    integration_status: str
    provenance: EnsembleMemberProvenance


@dataclass(frozen=True)
class TrajectoryEnsembleMetadata:
    """Shared non-replication status for an ordered provisional ensemble."""

    label: str
    title: str
    track: ProjectTrack
    backend_mode: str
    replication_valid: bool
    force_ready: bool
    policy_name: str
    warnings: tuple[str, ...]
    omitted_terms: tuple[str, ...]
    collapsed_terms: tuple[str, ...]


@dataclass(frozen=True)
class TrajectoryEnsembleResult:
    """Ordered provisional trajectories and their explicit outcomes."""

    members: tuple[TrajectoryEnsembleMember, ...]
    criteria: OutcomeCriteria
    metadata: TrajectoryEnsembleMetadata


def _position_values(positions: FloatArray, measure: PositionMeasure) -> FloatArray:
    if measure == "radius":
        return np.linalg.norm(positions, axis=1)
    return np.max(np.abs(positions), axis=1)


def _invalid_outcome(reason: str) -> TrajectoryOutcome:
    return TrajectoryOutcome(
        label=OutcomeLabel.INVALID,
        numerical_reason=reason,
        dwell_start_s=None,
        dwell_end_s=None,
        dwell_sample_count=0,
        dwell_in_bounds_count=0,
        dwell_in_bounds_fraction=None,
        max_position_overall=None,
        max_speed_overall=None,
        max_position_dwell=None,
        max_speed_dwell=None,
    )


def classify_trajectory(
    result: ClassifiableTrajectory,
    criteria: OutcomeCriteria,
) -> TrajectoryOutcome:
    """Classify a trajectory using hard bounds and a final dwell window."""
    times = np.asarray(result.times_s, dtype=float)
    positions = np.asarray(result.positions, dtype=float)
    velocities = np.asarray(result.velocities, dtype=float)
    if times.ndim != 1 or times.size == 0:
        return _invalid_outcome("time array must be nonempty and one-dimensional")
    expected_shape = (times.size, 3)
    if positions.shape != expected_shape or velocities.shape != expected_shape:
        return _invalid_outcome(
            f"position and velocity arrays must both have shape {expected_shape}"
        )
    if (
        not np.isfinite(times).all()
        or not np.isfinite(positions).all()
        or not np.isfinite(velocities).all()
    ):
        return _invalid_outcome("trajectory contains NaN or nonfinite values")
    if times.size > 1 and not np.all(np.diff(times) > 0.0):
        return _invalid_outcome("trajectory times must be strictly increasing")

    position_values = _position_values(positions, criteria.position_measure)
    speeds = np.linalg.norm(velocities, axis=1)
    max_position_overall = float(np.max(position_values))
    max_speed_overall = float(np.max(speeds))
    if (
        criteria.hard_escape_position is not None
        and max_position_overall > criteria.hard_escape_position
    ):
        return TrajectoryOutcome(
            label=OutcomeLabel.ESCAPED,
            numerical_reason=(
                f"maximum {criteria.position_measure} {max_position_overall:.9g} "
                f"exceeded hard escape bound {criteria.hard_escape_position:.9g}"
            ),
            dwell_start_s=None,
            dwell_end_s=float(times[-1]),
            dwell_sample_count=0,
            dwell_in_bounds_count=0,
            dwell_in_bounds_fraction=None,
            max_position_overall=max_position_overall,
            max_speed_overall=max_speed_overall,
            max_position_dwell=None,
            max_speed_dwell=None,
        )
    if criteria.hard_speed is not None and max_speed_overall > criteria.hard_speed:
        return TrajectoryOutcome(
            label=OutcomeLabel.ESCAPED,
            numerical_reason=(
                f"maximum speed {max_speed_overall:.9g} exceeded hard speed "
                f"bound {criteria.hard_speed:.9g}"
            ),
            dwell_start_s=None,
            dwell_end_s=float(times[-1]),
            dwell_sample_count=0,
            dwell_in_bounds_count=0,
            dwell_in_bounds_fraction=None,
            max_position_overall=max_position_overall,
            max_speed_overall=max_speed_overall,
            max_position_dwell=None,
            max_speed_dwell=None,
        )

    total_duration_s = float(times[-1] - times[0])
    if total_duration_s < criteria.final_dwell_window_s:
        return TrajectoryOutcome(
            label=OutcomeLabel.UNRESOLVED,
            numerical_reason=(
                f"trajectory duration {total_duration_s:.9g} s is shorter than "
                f"required dwell window {criteria.final_dwell_window_s:.9g} s"
            ),
            dwell_start_s=None,
            dwell_end_s=float(times[-1]),
            dwell_sample_count=0,
            dwell_in_bounds_count=0,
            dwell_in_bounds_fraction=None,
            max_position_overall=max_position_overall,
            max_speed_overall=max_speed_overall,
            max_position_dwell=None,
            max_speed_dwell=None,
        )

    dwell_end_s = float(times[-1])
    dwell_start_s = dwell_end_s - criteria.final_dwell_window_s
    dwell_mask = times >= dwell_start_s
    dwell_count = int(np.count_nonzero(dwell_mask))
    if dwell_count < criteria.min_dwell_samples:
        return TrajectoryOutcome(
            label=OutcomeLabel.UNRESOLVED,
            numerical_reason=(
                f"dwell window contains {dwell_count} samples, fewer than "
                f"required minimum {criteria.min_dwell_samples}"
            ),
            dwell_start_s=dwell_start_s,
            dwell_end_s=dwell_end_s,
            dwell_sample_count=dwell_count,
            dwell_in_bounds_count=0,
            dwell_in_bounds_fraction=None,
            max_position_overall=max_position_overall,
            max_speed_overall=max_speed_overall,
            max_position_dwell=(
                None if dwell_count == 0 else float(np.max(position_values[dwell_mask]))
            ),
            max_speed_dwell=(
                None if dwell_count == 0 else float(np.max(speeds[dwell_mask]))
            ),
        )

    dwell_positions = position_values[dwell_mask]
    dwell_speeds = speeds[dwell_mask]
    in_bounds = (
        (dwell_positions <= criteria.max_position)
        & (dwell_speeds <= criteria.max_speed)
    )
    in_bounds_count = int(np.count_nonzero(in_bounds))
    in_bounds_fraction = in_bounds_count / dwell_count
    max_position_dwell = float(np.max(dwell_positions))
    max_speed_dwell = float(np.max(dwell_speeds))
    if in_bounds_fraction >= criteria.required_dwell_fraction:
        return TrajectoryOutcome(
            label=OutcomeLabel.BOUNDED_FINAL_STATE,
            numerical_reason=(
                f"{in_bounds_count}/{dwell_count} dwell samples satisfied "
                f"{criteria.position_measure}<={criteria.max_position:.9g} and "
                f"speed<={criteria.max_speed:.9g}"
            ),
            dwell_start_s=dwell_start_s,
            dwell_end_s=dwell_end_s,
            dwell_sample_count=dwell_count,
            dwell_in_bounds_count=in_bounds_count,
            dwell_in_bounds_fraction=in_bounds_fraction,
            max_position_overall=max_position_overall,
            max_speed_overall=max_speed_overall,
            max_position_dwell=max_position_dwell,
            max_speed_dwell=max_speed_dwell,
        )
    return TrajectoryOutcome(
        label=OutcomeLabel.UNRESOLVED,
        numerical_reason=(
            f"only {in_bounds_count}/{dwell_count} dwell samples satisfied "
            f"the engineering bounds; required fraction is "
            f"{criteria.required_dwell_fraction:.9g}"
        ),
        dwell_start_s=dwell_start_s,
        dwell_end_s=dwell_end_s,
        dwell_sample_count=dwell_count,
        dwell_in_bounds_count=in_bounds_count,
        dwell_in_bounds_fraction=in_bounds_fraction,
        max_position_overall=max_position_overall,
        max_speed_overall=max_speed_overall,
        max_position_dwell=max_position_dwell,
        max_speed_dwell=max_speed_dwell,
    )


def _require_provisional_ensemble_backend(
    backend: ApproximateMgFHamiltonian,
    force_config: ProvisionalForceMapConfig,
) -> None:
    if not force_config.explicit_provisional_opt_in:
        raise MgFBackendCapabilityError(
            "trajectory ensemble requires explicit_provisional_opt_in=True"
        )
    if not isinstance(backend, ApproximateMgFHamiltonian):
        raise MgFBackendCapabilityError(
            "trajectory ensemble requires a Track P provisional backend"
        )
    provenance = backend.provenance
    if provenance.track is not ProjectTrack.PROVISIONAL:
        raise MgFBackendCapabilityError("ensemble backend provenance is not provisional")
    if provenance.replication_valid:
        raise MgFBackendCapabilityError(
            "provisional ensemble backend must have replication_valid=false"
        )


def run_trajectory_ensemble(
    initial_states: tuple[TrajectoryInitialState, ...]
    | list[TrajectoryInitialState],
    policy: LaserSchedulePolicy,
    backend: ApproximateMgFHamiltonian,
    force_config: ProvisionalForceMapConfig,
    trajectory_config: TrajectoryConfig,
    outcome_criteria: OutcomeCriteria,
) -> TrajectoryEnsembleResult:
    """Integrate and classify an ordered, explicitly provisional state list."""
    _require_provisional_ensemble_backend(backend, force_config)
    ordered_states = tuple(initial_states)
    provenance = backend.provenance
    members: list[TrajectoryEnsembleMember] = []
    for index, initial_state in enumerate(ordered_states):
        try:
            trajectory = integrate_policy_trajectory(
                policy,
                initial_state,
                backend,
                force_config,
                trajectory_config,
            )
            outcome = classify_trajectory(trajectory, outcome_criteria)
            integration_status = "completed"
        except ValueError as exc:
            trajectory = None
            outcome = _invalid_outcome(f"integration failed: {exc}")
            integration_status = "numerical_failure"
        member_provenance = EnsembleMemberProvenance(
            label=OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
            title=(
                f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} ensemble member "
                f"{index}"
            ),
            track=ProjectTrack.PROVISIONAL,
            backend_mode=provenance.backend_mode,
            replication_valid=False,
            force_ready=False,
            omitted_terms=provenance.omitted_terms,
            collapsed_terms=provenance.collapsed_terms,
            policy_name=policy.name,
            initial_state=initial_state,
            integration_status=integration_status,
            outcome_label=outcome.label,
            numerical_reason=outcome.numerical_reason,
        )
        members.append(
            TrajectoryEnsembleMember(
                initial_state=initial_state,
                trajectory=trajectory,
                outcome=outcome,
                integration_status=integration_status,
                provenance=member_provenance,
            )
        )

    metadata = TrajectoryEnsembleMetadata(
        label=OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
        title=f"{OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL} ordered ensemble",
        track=ProjectTrack.PROVISIONAL,
        backend_mode=provenance.backend_mode,
        replication_valid=False,
        force_ready=False,
        policy_name=policy.name,
        warnings=provenance.warnings
        + (
            "OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY: engineering labels only.",
            "BOUNDED_FINAL_STATE is not equivalent to physical MOT capture.",
            "No threshold search or physical inference is performed.",
        ),
        omitted_terms=provenance.omitted_terms,
        collapsed_terms=provenance.collapsed_terms,
    )
    return TrajectoryEnsembleResult(
        members=tuple(members),
        criteria=outcome_criteria,
        metadata=metadata,
    )
