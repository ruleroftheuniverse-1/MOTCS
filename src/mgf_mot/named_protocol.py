"""Validated config-backed Track P named finite-beam trajectory protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import math
import yaml

from .outcomes import OutcomeCriteria
from .tracks import ProjectTrack
from .trajectory import TrajectoryConfig, TrajectoryInitialState

REQUIRED_PROTOCOL_LABELS = (
    "PROVISIONAL",
    "NOT_RODRIGUEZ_REPLICATION",
    "NAMED_TRAJECTORY_PROTOCOL_ONLY",
)


@dataclass(frozen=True)
class NamedInitialVelocity:
    """One explicitly named source velocity in both source and SI units."""

    name: str
    gamma_over_k: float
    velocity_m_s: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("named velocity requires a nonempty name")
        if not math.isfinite(self.gamma_over_k) or self.gamma_over_k <= 0.0:
            raise ValueError("gamma_over_k must be finite and positive")
        if not math.isfinite(self.velocity_m_s) or self.velocity_m_s <= 0.0:
            raise ValueError("velocity_m_s must be finite and positive")


@dataclass(frozen=True)
class RodriguezTrajectoryProtocol:
    """Complete data contract for the five deterministic Track P cases."""

    name: str
    labels: tuple[str, str, str]
    initial_position_m: tuple[float, float, float]
    named_velocities: tuple[
        NamedInitialVelocity,
        NamedInitialVelocity,
        NamedInitialVelocity,
        NamedInitialVelocity,
        NamedInitialVelocity,
    ]
    gamma_over_k_velocity_unit_m_s: float
    simulation_duration_s: float
    time_step_s: float
    magnetic_gradient_t_m: float
    gaussian_config_path: str
    handoff_policy_config_path: str
    component_order: tuple[int, int, int, int]
    pre_handoff_saturations: tuple[float, float, float, float]
    post_handoff_saturations: tuple[float, float, float, float]
    total_laser_power_w: float
    power_allocation_status: str
    diagnostic_position_bounds_m: tuple[float, ...]
    outcome_criteria: OutcomeCriteria
    normalized_force_to_acceleration: float
    normalized_gradient_reference_t_m: float
    warnings: tuple[str, ...]
    track: ProjectTrack = ProjectTrack.PROVISIONAL
    replication_valid: bool = False
    force_ready: bool = False

    def __post_init__(self) -> None:
        if self.labels != REQUIRED_PROTOCOL_LABELS:
            raise ValueError(
                f"protocol labels must be exactly {REQUIRED_PROTOCOL_LABELS}"
            )
        if self.track is not ProjectTrack.PROVISIONAL or self.replication_valid:
            raise ValueError("named protocol must remain provisional")
        if self.initial_position_m != (-0.05, 0.0, 0.0):
            raise ValueError("initial position must be exactly (-0.05, 0, 0) m")
        expected_source_values = (2.0, 4.0, 6.0, 7.5, 9.0)
        if tuple(item.gamma_over_k for item in self.named_velocities) != expected_source_values:
            raise ValueError(
                f"named source velocities must be exactly {expected_source_values}"
            )
        if len({item.name for item in self.named_velocities}) != 5:
            raise ValueError("named velocities must have unique names")
        for item in self.named_velocities:
            expected_si = item.gamma_over_k * self.gamma_over_k_velocity_unit_m_s
            if not math.isclose(item.velocity_m_s, expected_si, abs_tol=1e-12):
                raise ValueError(
                    f"{item.name} SI velocity must equal gamma_over_k times 7.53 m/s"
                )
        if self.simulation_duration_s <= self.time_step_s or self.time_step_s <= 0.0:
            raise ValueError("simulation duration and timestep must be positive")
        if self.magnetic_gradient_t_m != 0.2:
            raise ValueError("baseline magnetic gradient must be exactly 0.2 T/m")
        if self.component_order != (1, 2, 3, 4):
            raise ValueError("component order must be exactly (1, 2, 3, 4)")
        if self.pre_handoff_saturations != (1.45, 1.45, 2.89, 0.0):
            raise ValueError("pre-handoff saturation vector is not the baseline")
        if self.post_handoff_saturations != (1.45, 1.45, 2.17, 0.72):
            raise ValueError("post-handoff saturation vector is not the baseline")
        if self.total_laser_power_w != 1.0:
            raise ValueError("reported total laser power metadata must be 1 W")
        if self.power_allocation_status != "unresolved_no_conversion":
            raise ValueError("protocol must not infer a laser-power allocation")
        if not self.diagnostic_position_bounds_m or any(
            not math.isfinite(value) or value <= 0.0
            for value in self.diagnostic_position_bounds_m
        ):
            raise ValueError("diagnostic position bounds must be finite and positive")
        if tuple(sorted(set(self.diagnostic_position_bounds_m))) != (
            self.diagnostic_position_bounds_m
        ):
            raise ValueError("diagnostic position bounds must be unique and sorted")
        if self.outcome_criteria.position_unit != "m":
            raise ValueError("outcome position unit must be m")
        if self.outcome_criteria.speed_unit != "m/s":
            raise ValueError("outcome speed unit must be m/s")
        if self.normalized_force_to_acceleration <= 0.0:
            raise ValueError("normalized force-to-acceleration scale must be positive")
        if self.normalized_gradient_reference_t_m <= 0.0:
            raise ValueError("normalized gradient reference must be positive")
        for required in REQUIRED_PROTOCOL_LABELS:
            if not any(required in warning for warning in self.warnings):
                raise ValueError(f"protocol warnings must include {required}")

    @property
    def label(self) -> str:
        return "_".join(self.labels)

    @property
    def normalized_gradient_scale(self) -> float:
        return self.magnetic_gradient_t_m / self.normalized_gradient_reference_t_m

    def initial_states(self) -> tuple[TrajectoryInitialState, ...]:
        return tuple(
            TrajectoryInitialState(
                position=self.initial_position_m,
                velocity=(item.velocity_m_s, 0.0, 0.0),
            )
            for item in self.named_velocities
        )

    def trajectory_config(self) -> TrajectoryConfig:
        return TrajectoryConfig(
            t_start_s=0.0,
            t_end_s=self.simulation_duration_s,
            time_step_s=self.time_step_s,
            normalized_force_to_acceleration=self.normalized_force_to_acceleration,
            position_unit="m",
            velocity_unit="m/s",
            force_unit="normalized_hbar_k_Gamma",
        )


def _tuple4(values: list[Any], label: str) -> tuple[float, float, float, float]:
    if len(values) != 4:
        raise ValueError(f"{label} must contain exactly four values")
    converted = tuple(float(value) for value in values)
    if not all(math.isfinite(value) and value >= 0.0 for value in converted):
        raise ValueError(f"{label} must contain finite nonnegative values")
    return converted  # type: ignore[return-value]


def load_rodriguez_named_trajectory_protocol(
    path: str | Path,
) -> RodriguezTrajectoryProtocol:
    with Path(path).open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    position = data["initial_state"]["position"]
    if position["unit"] != "mm":
        raise ValueError("initial position must be specified in mm")
    initial_position_m = tuple(float(value) * 1e-3 for value in position["value"])
    velocity_unit = data["initial_state"]["gamma_over_k_velocity_unit"]
    if velocity_unit["unit"] != "m/s":
        raise ValueError("Gamma/k velocity unit must be specified in m/s")
    gamma_over_k_velocity_unit_m_s = float(velocity_unit["value"])
    named_velocities = tuple(
        NamedInitialVelocity(
            name=str(item["name"]),
            gamma_over_k=float(item["gamma_over_k"]),
            velocity_m_s=float(item["velocity_m_s"]),
        )
        for item in data["initial_state"]["named_velocities"]
    )
    simulation = data["simulation"]
    if simulation["duration"]["unit"] != "s" or simulation["time_step"]["unit"] != "s":
        raise ValueError("simulation duration and timestep units must be s")
    gradient = data["magnetic_gradient"]
    if gradient["unit"] != "mT/cm":
        raise ValueError("magnetic gradient must be specified in mT/cm")
    magnetic_gradient_t_m = float(gradient["value"]) * 0.1
    criteria_data = data["provisional_outcome_criteria"]
    if (
        criteria_data["position_unit"] != "m"
        or criteria_data["speed_unit"] != "m/s"
        or criteria_data["time_unit"] != "s"
    ):
        raise ValueError("outcome criteria units must be m, m/s, and s")
    outcome_criteria = OutcomeCriteria(
        max_position=float(criteria_data["max_position"]),
        max_speed=float(criteria_data["max_speed"]),
        final_dwell_window_s=float(criteria_data["final_dwell_window_s"]),
        min_dwell_samples=int(criteria_data["min_dwell_samples"]),
        required_dwell_fraction=float(criteria_data["required_dwell_fraction"]),
        position_measure=str(criteria_data["position_measure"]),  # type: ignore[arg-type]
        hard_escape_position=float(criteria_data["hard_escape_position"]),
        hard_speed=float(criteria_data["hard_speed"]),
        position_unit="m",
        speed_unit="m/s",
    )
    return RodriguezTrajectoryProtocol(
        name=str(data["name"]),
        labels=tuple(str(value) for value in data["artifact_labels"]),  # type: ignore[arg-type]
        initial_position_m=initial_position_m,  # type: ignore[arg-type]
        named_velocities=named_velocities,  # type: ignore[arg-type]
        gamma_over_k_velocity_unit_m_s=gamma_over_k_velocity_unit_m_s,
        simulation_duration_s=float(simulation["duration"]["value"]),
        time_step_s=float(simulation["time_step"]["value"]),
        magnetic_gradient_t_m=magnetic_gradient_t_m,
        gaussian_config_path=str(data["gaussian_beam_config"]),
        handoff_policy_config_path=str(data["handoff_policy_config"]),
        component_order=tuple(int(value) for value in data["component_order"]),  # type: ignore[arg-type]
        pre_handoff_saturations=_tuple4(
            data["operative_peak_saturations"]["pre_handoff"],
            "pre_handoff saturations",
        ),
        post_handoff_saturations=_tuple4(
            data["operative_peak_saturations"]["post_handoff"],
            "post_handoff saturations",
        ),
        total_laser_power_w=float(data["total_laser_power"]["value"]),
        power_allocation_status=str(
            data["total_laser_power"]["allocation_status"]
        ),
        diagnostic_position_bounds_m=tuple(
            float(value) for value in data["diagnostic_position_bounds_m"]
        ),
        outcome_criteria=outcome_criteria,
        normalized_force_to_acceleration=float(
            data["provisional_force_adapter"]["normalized_force_to_acceleration"]
        ),
        normalized_gradient_reference_t_m=float(
            data["provisional_force_adapter"]["normalized_gradient_reference_t_m"]
        ),
        warnings=tuple(str(value) for value in data["warnings"]),
    )
