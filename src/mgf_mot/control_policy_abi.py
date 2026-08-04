"""Model-independent, declarative control-policy ABI v2.

Only the three existing open-loop policy families execute in Run 013.  The ABI
contains no force, plant, trajectory, feedback, or optimizer dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping


CONTROL_POLICY_SCHEMA_VERSION = "mgf-mot-control-policy-v2"
RUN013_LABEL = "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_013_CONTROL_POLICY_ABI_ONLY"
CONTROL_COMPONENT_ORDER = (1, 2, 3, 4)


class ControlPolicyABIError(ValueError):
    pass


class ControlPolicyFamily(str, Enum):
    STATIC = "STATIC"
    LINEAR_CHIRP = "LINEAR_CHIRP"
    CHIRP_TO_TRAP_HANDOFF = "CHIRP_TO_TRAP_HANDOFF"


class PolicyStatefulness(str, Enum):
    STATELESS_OPEN_LOOP = "STATELESS_OPEN_LOOP"
    STATEFUL_CONTROLLER = "STATEFUL_CONTROLLER"


class DomainBehavior(str, Enum):
    ERROR = "ERROR"
    HOLD_INITIAL = "HOLD_INITIAL"
    HOLD_FINAL = "HOLD_FINAL"


class ChannelRelationship(str, Enum):
    INDEPENDENT = "INDEPENDENT"
    SHARED = "SHARED"
    FIXED = "FIXED"
    AFFINE_DERIVED = "AFFINE_DERIVED"


class ChannelSignalKind(str, Enum):
    FIXED = "FIXED"
    LINEAR_HOLD = "LINEAR_HOLD"
    AFFINE = "AFFINE"


class BoundBasis(str, Enum):
    SOURCE_SUPPORTED = "SOURCE_SUPPORTED"
    APPARATUS_ASSUMPTION = "APPARATUS_ASSUMPTION"
    ENGINEERING_STRESS_TEST = "ENGINEERING_STRESS_TEST"
    UNKNOWN = "UNKNOWN"


class EventBoundaryRule(str, Enum):
    LEFT_OPEN_RIGHT_CLOSED = "t_lt_event_left_t_ge_event_right"


@dataclass(frozen=True)
class PolicyParameterSpec:
    name: str
    description: str
    shape: tuple[int, ...]
    units: str
    data_type: str
    default_value: Any | None
    lower_bound: Any | None
    upper_bound: Any | None
    adjustable: bool
    bound_basis: BoundBasis


@dataclass(frozen=True)
class ChannelTarget:
    segment_id: str
    component_id: int
    field: str


@dataclass(frozen=True)
class ControlChannelSpec:
    channel_id: str
    relationship: ChannelRelationship
    signal_kind: ChannelSignalKind
    field: str
    targets: tuple[ChannelTarget, ...]
    parameter_names: tuple[str, ...] = ()
    fixed_value: float | None = None
    source_channel_id: str | None = None
    affine_scale: float | None = None
    affine_offset: float | None = None
    description: str = ""


@dataclass(frozen=True)
class ComponentControlState:
    component_id: int
    detuning_gamma: float
    saturation: float
    enabled: bool
    active: bool
    off_reason: str | None
    detuning_channel_id: str
    saturation_channel_id: str
    role: str = ""
    polarization: str = ""
    relative_saturation: float | None = None


@dataclass(frozen=True)
class PolicySegment:
    segment_id: str
    semantic_label: str
    components: tuple[ComponentControlState, ...]


@dataclass(frozen=True)
class PolicyDomain:
    minimum_time_s: float
    maximum_time_s: float | None
    unbounded_continuation: bool
    before_minimum: DomainBehavior
    after_maximum: DomainBehavior
    endpoint_semantics: str


@dataclass(frozen=True)
class PolicyEvent:
    event_id: str
    event_time_s: float
    event_type: str
    affected_channel_ids: tuple[str, ...]
    affected_component_ids: tuple[int, ...]
    left_semantic_label: str
    right_semantic_label: str
    boundary_rule: EventBoundaryRule
    provenance: str


@dataclass(frozen=True)
class PolicyProvenance:
    schema_version: str
    policy_family_id: str
    source_configuration_paths: tuple[str, ...]
    source_configuration_hashes: tuple[str, ...]
    implementation_version: str
    parent_policy_ids: tuple[str, ...]
    units: Mapping[str, str]
    generation_method: str
    non_replication_labels: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ControlPolicySpec:
    schema_version: str
    policy_family: ControlPolicyFamily
    policy_name: str
    policy_description: str
    time_unit: str
    detuning_unit: str
    saturation_unit: str
    component_order: tuple[int, ...]
    parameter_specs: tuple[PolicyParameterSpec, ...]
    parameter_values: Mapping[str, Any]
    control_channels: tuple[ControlChannelSpec, ...]
    segments: tuple[PolicySegment, ...]
    events: tuple[PolicyEvent, ...]
    domain: PolicyDomain
    statefulness: PolicyStatefulness
    provenance: PolicyProvenance
    legacy_policy_type: str


@dataclass(frozen=True)
class PolicyState:
    time_s: float
    evaluation_time_s: float
    component_order: tuple[int, ...]
    components: tuple[ComponentControlState, ...]
    segment_id: str
    semantic_label: str
    event_ids_at_time: tuple[str, ...]
    handoff_occurred: bool
    policy_hash: str


def _component_with(component: ComponentControlState, *, detuning: float | None = None, saturation: float | None = None) -> ComponentControlState:
    sat = component.saturation if saturation is None else float(saturation)
    enabled = component.enabled
    active = enabled and sat > 0.0
    return ComponentControlState(
        component_id=component.component_id,
        detuning_gamma=component.detuning_gamma if detuning is None else float(detuning),
        saturation=sat, enabled=enabled, active=active,
        off_reason=None if active else component.off_reason,
        detuning_channel_id=component.detuning_channel_id,
        saturation_channel_id=component.saturation_channel_id,
        role=component.role, polarization=component.polarization,
        relative_saturation=component.relative_saturation,
    )


class ControlPolicy:
    """Executable stateless view of a validated declarative specification."""

    def __init__(self, spec: ControlPolicySpec):
        from .control_policy_validation import validate_control_policy_spec
        result = validate_control_policy_spec(spec)
        if not result.valid:
            raise ControlPolicyABIError("invalid control policy: " + "; ".join(issue.message for issue in result.errors))
        if spec.statefulness is not PolicyStatefulness.STATELESS_OPEN_LOOP:
            raise ControlPolicyABIError("Run 013 cannot instantiate or execute STATEFUL_CONTROLLER specifications")
        self.spec = spec
        from .control_policy_serialization import control_policy_hashes
        self.hashes = control_policy_hashes(spec)

    def _domain_time(self, t: float) -> float:
        if not math.isfinite(t):
            raise ControlPolicyABIError("sample time must be finite")
        domain = self.spec.domain
        if t < domain.minimum_time_s:
            if domain.before_minimum is DomainBehavior.ERROR:
                raise ControlPolicyABIError("sample time is below the policy domain")
            if domain.before_minimum is DomainBehavior.HOLD_INITIAL:
                return domain.minimum_time_s
        if domain.maximum_time_s is not None and t > domain.maximum_time_s:
            if domain.after_maximum is DomainBehavior.ERROR:
                raise ControlPolicyABIError("sample time is above the policy domain")
            if domain.after_maximum is DomainBehavior.HOLD_FINAL:
                return domain.maximum_time_s
        return t

    def _segment(self, t: float) -> PolicySegment:
        if self.spec.policy_family is ControlPolicyFamily.CHIRP_TO_TRAP_HANDOFF:
            event = self.spec.events[0]
            return self.spec.segments[0] if t < event.event_time_s else self.spec.segments[1]
        return self.spec.segments[0]

    def _channel_value(self, channel: ControlChannelSpec, t: float, resolved: dict[str, float]) -> float:
        values = self.spec.parameter_values
        if channel.signal_kind is ChannelSignalKind.FIXED:
            if channel.fixed_value is not None:
                return float(channel.fixed_value)
            return float(values[channel.parameter_names[0]])
        if channel.signal_kind is ChannelSignalKind.LINEAR_HOLD:
            initial, final, duration = (float(values[name]) for name in channel.parameter_names)
            if t <= 0.0: return initial
            if t >= duration: return final
            return initial + (t / duration) * (final - initial)
        if channel.signal_kind is ChannelSignalKind.AFFINE:
            assert channel.source_channel_id is not None
            return float(channel.affine_scale) * resolved[channel.source_channel_id] + float(channel.affine_offset)
        raise ControlPolicyABIError(f"unsupported channel signal kind {channel.signal_kind}")

    def sample(self, t: float) -> PolicyState:
        requested = float(t); evaluation = self._domain_time(requested); segment = self._segment(evaluation)
        components = {component.component_id: component for component in segment.components}
        relevant = [channel for channel in self.spec.control_channels if any(target.segment_id == segment.segment_id for target in channel.targets)]
        resolved: dict[str, float] = {}
        pending = list(relevant)
        while pending:
            progress = False
            for channel in pending[:]:
                if channel.signal_kind is ChannelSignalKind.AFFINE and channel.source_channel_id not in resolved:
                    continue
                resolved[channel.channel_id] = self._channel_value(channel, evaluation, resolved)
                pending.remove(channel); progress = True
            if not progress:
                raise ControlPolicyABIError("unresolved or cyclic channel dependencies")
        for channel in relevant:
            value = resolved[channel.channel_id]
            for target in channel.targets:
                if target.segment_id != segment.segment_id: continue
                component = components[target.component_id]
                if target.field == "detuning_gamma": components[target.component_id] = _component_with(component, detuning=value)
                elif target.field == "saturation": components[target.component_id] = _component_with(component, saturation=value)
                else: raise ControlPolicyABIError(f"unsupported controlled field {target.field!r}")
        ordered = tuple(components[index] for index in CONTROL_COMPONENT_ORDER)
        events = tuple(event.event_id for event in self.spec.events if evaluation == event.event_time_s)
        return PolicyState(
            time_s=requested, evaluation_time_s=evaluation, component_order=CONTROL_COMPONENT_ORDER,
            components=ordered, segment_id=segment.segment_id, semantic_label=segment.semantic_label,
            event_ids_at_time=events,
            handoff_occurred=(self.spec.policy_family is ControlPolicyFamily.CHIRP_TO_TRAP_HANDOFF and segment.segment_id == "post_handoff"),
            policy_hash=self.hashes.full_policy_package,
        )
