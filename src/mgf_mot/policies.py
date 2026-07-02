"""Pure laser schedule policies for Track P control-interface plumbing.

These policies describe detuning and saturation as a function of time. They do
not integrate trajectories, estimate capture, model Gaussian beams, optimize
parameters, or make exact Rodriguez/MgF replication claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import math
import yaml

ComponentId = Literal[1, 2, 3, 4]
PolicyType = Literal["static", "linear_chirp"]

COMPONENT_ORDER: tuple[ComponentId, ComponentId, ComponentId, ComponentId] = (1, 2, 3, 4)
DETUNING_UNIT = "Gamma"
SATURATION_UNIT = "saturation_parameter"
TIME_UNIT = "s"


class PolicyValidationError(ValueError):
    """Raised when a policy would rely on ambiguous schedule data."""


@dataclass(frozen=True)
class ApparatusBounds:
    """Optional apparatus-realism bounds, stored as data only."""

    max_chirp_rate_gamma_per_s: float | None = None
    detuning_range_gamma: tuple[float, float] | None = None
    saturation_range: tuple[float, float] | None = None
    frequency_update_granularity_s: float | None = None
    intensity_update_granularity_s: float | None = None


@dataclass(frozen=True)
class ComponentState:
    """Detuning/intensity state for one frequency component."""

    component_id: ComponentId
    detuning_gamma: float
    saturation: float
    enabled: bool
    role: str = ""
    relative_saturation: float | None = None


@dataclass(frozen=True)
class PolicySample:
    """A policy state sampled at a time."""

    time_s: float
    component_order: tuple[ComponentId, ComponentId, ComponentId, ComponentId]
    detuning_unit: str
    saturation_unit: str
    components: tuple[ComponentState, ComponentState, ComponentState, ComponentState]


class LaserSchedulePolicy(Protocol):
    name: str
    policy_type: PolicyType
    component_order: tuple[ComponentId, ComponentId, ComponentId, ComponentId]
    detuning_unit: str
    saturation_unit: str
    time_unit: str

    def sample(self, t: float) -> PolicySample:
        """Return per-component detuning and saturation state at time ``t``."""


def _finite(value: float, label: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise PolicyValidationError(f"{label} must be finite")
    return value


def _component_id(value: Any) -> ComponentId:
    if value not in COMPONENT_ORDER:
        raise PolicyValidationError(f"component id must be one of {COMPONENT_ORDER}, got {value!r}")
    return value


def _validate_units(detuning_unit: str, saturation_unit: str, time_unit: str = TIME_UNIT) -> None:
    if detuning_unit != DETUNING_UNIT:
        raise PolicyValidationError(f"detuning_unit must be {DETUNING_UNIT!r}")
    if saturation_unit != SATURATION_UNIT:
        raise PolicyValidationError(f"saturation_unit must be {SATURATION_UNIT!r}")
    if time_unit != TIME_UNIT:
        raise PolicyValidationError(f"time_unit must be {TIME_UNIT!r}")


def _validate_component_order(component_order: tuple[int, ...]) -> None:
    if tuple(component_order) != COMPONENT_ORDER:
        raise PolicyValidationError(f"component_order must be exactly {COMPONENT_ORDER}")


def _component_state_from_mapping(data: dict[str, Any]) -> ComponentState:
    saturation = _finite(data["saturation"], f"component {data.get('id')} saturation")
    if saturation < 0:
        raise PolicyValidationError("negative saturation is not allowed")
    relative = data.get("relative_saturation")
    if relative is not None:
        relative = _finite(relative, f"component {data.get('id')} relative_saturation")
        if relative < 0:
            raise PolicyValidationError("negative relative_saturation is not allowed")
    return ComponentState(
        component_id=_component_id(data["id"]),
        detuning_gamma=_finite(data["detuning_gamma"], f"component {data.get('id')} detuning"),
        saturation=saturation,
        enabled=bool(data.get("enabled", True)),
        role=str(data.get("role", "")),
        relative_saturation=relative,
    )


def _validate_components(
    components: tuple[ComponentState, ...],
) -> tuple[ComponentState, ComponentState, ComponentState, ComponentState]:
    if tuple(component.component_id for component in components) != COMPONENT_ORDER:
        raise PolicyValidationError(
            f"components must be explicit and ordered as {COMPONENT_ORDER}"
        )
    for component in components:
        _finite(component.detuning_gamma, f"component {component.component_id} detuning")
        _finite(component.saturation, f"component {component.component_id} saturation")
        if component.saturation < 0:
            raise PolicyValidationError("negative saturation is not allowed")
    return components  # type: ignore[return-value]


def _bounds_from_mapping(data: dict[str, Any] | None) -> ApparatusBounds | None:
    if data is None:
        return None
    detuning_range = data.get("detuning_range_gamma")
    saturation_range = data.get("saturation_range")
    return ApparatusBounds(
        max_chirp_rate_gamma_per_s=(
            None if data.get("max_chirp_rate_gamma_per_s") is None else _finite(
                data["max_chirp_rate_gamma_per_s"], "max_chirp_rate_gamma_per_s"
            )
        ),
        detuning_range_gamma=(
            None if detuning_range is None else (
                _finite(detuning_range[0], "detuning_range_gamma min"),
                _finite(detuning_range[1], "detuning_range_gamma max"),
            )
        ),
        saturation_range=(
            None if saturation_range is None else (
                _finite(saturation_range[0], "saturation_range min"),
                _finite(saturation_range[1], "saturation_range max"),
            )
        ),
        frequency_update_granularity_s=(
            None if data.get("frequency_update_granularity_s") is None else _finite(
                data["frequency_update_granularity_s"], "frequency_update_granularity_s"
            )
        ),
        intensity_update_granularity_s=(
            None if data.get("intensity_update_granularity_s") is None else _finite(
                data["intensity_update_granularity_s"], "intensity_update_granularity_s"
            )
        ),
    )


@dataclass(frozen=True)
class StaticPolicy:
    """Static per-component detuning and saturation schedule."""

    name: str
    components: tuple[ComponentState, ComponentState, ComponentState, ComponentState]
    source: str = ""
    policy_type: PolicyType = "static"
    component_order: tuple[ComponentId, ComponentId, ComponentId, ComponentId] = COMPONENT_ORDER
    detuning_unit: str = DETUNING_UNIT
    saturation_unit: str = SATURATION_UNIT
    time_unit: str = TIME_UNIT
    apparatus_bounds: ApparatusBounds | None = None

    def __post_init__(self) -> None:
        _validate_units(self.detuning_unit, self.saturation_unit, self.time_unit)
        _validate_component_order(self.component_order)
        _validate_components(self.components)

    def sample(self, t: float) -> PolicySample:
        return PolicySample(
            time_s=_finite(t, "sample time"),
            component_order=self.component_order,
            detuning_unit=self.detuning_unit,
            saturation_unit=self.saturation_unit,
            components=self.components,
        )

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "StaticPolicy":
        detuning_unit = config.get("detuning_unit", DETUNING_UNIT)
        saturation_unit = config.get("saturation_unit", SATURATION_UNIT)
        time_unit = config.get("time_unit", TIME_UNIT)
        _validate_units(detuning_unit, saturation_unit, time_unit)
        _validate_component_order(tuple(config.get("component_order", COMPONENT_ORDER)))
        components = tuple(_component_state_from_mapping(item) for item in config["frequency_components"])
        return cls(
            name=str(config["name"]),
            source=str(config.get("source", "")),
            components=_validate_components(components),
            detuning_unit=detuning_unit,
            saturation_unit=saturation_unit,
            time_unit=time_unit,
            apparatus_bounds=_bounds_from_mapping(config.get("apparatus_bounds")),
        )


@dataclass(frozen=True)
class LinearChirpPolicy:
    """Linear detuning schedule for explicit chirped components."""

    name: str
    components: tuple[ComponentState, ComponentState, ComponentState, ComponentState]
    chirped_components: tuple[ComponentId, ...]
    initial_detuning_gamma: float
    final_detuning_gamma: float
    duration_s: float
    source: str = ""
    policy_type: PolicyType = "linear_chirp"
    component_order: tuple[ComponentId, ComponentId, ComponentId, ComponentId] = COMPONENT_ORDER
    detuning_unit: str = DETUNING_UNIT
    saturation_unit: str = SATURATION_UNIT
    time_unit: str = TIME_UNIT
    apparatus_bounds: ApparatusBounds | None = None
    component_4_behavior: str = "explicit_off_during_chirp"

    def __post_init__(self) -> None:
        _validate_units(self.detuning_unit, self.saturation_unit, self.time_unit)
        _validate_component_order(self.component_order)
        _validate_components(self.components)
        if tuple(self.chirped_components) != (1, 2, 3):
            raise PolicyValidationError("Rodriguez baseline chirped components must be exactly (1, 2, 3)")
        _finite(self.initial_detuning_gamma, "initial_detuning_gamma")
        _finite(self.final_detuning_gamma, "final_detuning_gamma")
        if _finite(self.duration_s, "duration_s") <= 0:
            raise PolicyValidationError("chirp duration must be positive")
        component_4 = self.components[3]
        if component_4.component_id != 4:
            raise PolicyValidationError("component 4 must be explicit")

    def _detuning_at(self, t: float) -> float:
        t = _finite(t, "sample time")
        if t <= 0:
            return self.initial_detuning_gamma
        if t >= self.duration_s:
            return self.final_detuning_gamma
        fraction = t / self.duration_s
        return self.initial_detuning_gamma + fraction * (
            self.final_detuning_gamma - self.initial_detuning_gamma
        )

    def sample(self, t: float) -> PolicySample:
        detuning = self._detuning_at(t)
        chirped = set(self.chirped_components)
        components = tuple(
            ComponentState(
                component_id=component.component_id,
                detuning_gamma=detuning if component.component_id in chirped else component.detuning_gamma,
                saturation=component.saturation,
                enabled=component.enabled,
                role=component.role,
                relative_saturation=component.relative_saturation,
            )
            for component in self.components
        )
        return PolicySample(
            time_s=_finite(t, "sample time"),
            component_order=self.component_order,
            detuning_unit=self.detuning_unit,
            saturation_unit=self.saturation_unit,
            components=_validate_components(components),
        )

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "LinearChirpPolicy":
        detuning_unit = config.get("detuning_unit", DETUNING_UNIT)
        saturation_unit = config.get("saturation_unit", SATURATION_UNIT)
        time_unit = config.get("time_unit", TIME_UNIT)
        _validate_units(detuning_unit, saturation_unit, time_unit)
        _validate_component_order(tuple(config.get("component_order", COMPONENT_ORDER)))
        components = tuple(_component_state_from_mapping(item) for item in config["frequency_components"])
        chirp = config["chirp"]
        return cls(
            name=str(config["name"]),
            source=str(config.get("source", "")),
            components=_validate_components(components),
            chirped_components=tuple(_component_id(item) for item in chirp["components"]),
            initial_detuning_gamma=_finite(chirp["initial_detuning_gamma"], "initial_detuning_gamma"),
            final_detuning_gamma=_finite(chirp["final_detuning_gamma"], "final_detuning_gamma"),
            duration_s=_finite(chirp["duration_s"], "duration_s"),
            component_4_behavior=str(chirp["component_4_behavior"]),
            detuning_unit=detuning_unit,
            saturation_unit=saturation_unit,
            time_unit=time_unit,
            apparatus_bounds=_bounds_from_mapping(config.get("apparatus_bounds")),
        )


def load_policy_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def policy_from_config(config: dict[str, Any]) -> StaticPolicy | LinearChirpPolicy:
    policy_type = config.get("policy_type", "static")
    if policy_type == "static":
        return StaticPolicy.from_config(config)
    if policy_type == "linear_chirp":
        return LinearChirpPolicy.from_config(config)
    raise PolicyValidationError(f"unsupported policy_type {policy_type!r}")


def load_policy(path: str | Path) -> StaticPolicy | LinearChirpPolicy:
    return policy_from_config(load_policy_config(path))
