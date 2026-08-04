"""Structured, non-executing validation for control-policy ABI v2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping

from .control_policy_abi import (
    CONTROL_COMPONENT_ORDER, CONTROL_POLICY_SCHEMA_VERSION, ChannelRelationship,
    ChannelSignalKind, ControlPolicyFamily, ControlPolicySpec, DomainBehavior,
    PolicyStatefulness,
)


class PolicyIssueSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class PolicyValidationIssue:
    code: str
    severity: PolicyIssueSeverity
    field_path: str
    message: str
    relevant_value: Any
    suggested_correction: str | None


@dataclass(frozen=True)
class PolicyValidationResult:
    issues: tuple[PolicyValidationIssue, ...]

    @property
    def errors(self) -> tuple[PolicyValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is PolicyIssueSeverity.ERROR)

    @property
    def warnings(self) -> tuple[PolicyValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is PolicyIssueSeverity.WARNING)

    @property
    def valid(self) -> bool:
        return not self.errors


def _issue(code: str, path: str, message: str, value: Any, correction: str | None = None, severity: PolicyIssueSeverity = PolicyIssueSeverity.ERROR) -> PolicyValidationIssue:
    return PolicyValidationIssue(code, severity, path, message, value, correction)


def _contains_executable(value: Any, path: str = "$") -> list[PolicyValidationIssue]:
    issues = []
    if callable(value):
        issues.append(_issue("ARBITRARY_EXECUTABLE_CONTENT", path, "callables and executable content are forbidden", repr(value), "use FIXED, SHARED, LINEAR_HOLD, or declared affine channels"))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in {"callable", "expression", "lambda", "exec", "eval", "python_code"}:
                issues.append(_issue("ARBITRARY_EXECUTABLE_CONTENT", f"{path}.{key}", "executable expression fields are forbidden", item, "use a declared affine transform"))
            issues.extend(_contains_executable(item, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value): issues.extend(_contains_executable(item, f"{path}[{index}]"))
    return issues


def validate_control_policy_mapping(data: Mapping[str, Any]) -> PolicyValidationResult:
    issues = _contains_executable(data)
    required = {"schema_version", "policy_family", "policy_name", "time_unit", "detuning_unit", "saturation_unit", "component_order", "parameter_specs", "parameter_values", "control_channels", "segments", "events", "domain", "statefulness", "provenance"}
    for field in sorted(required - set(data)):
        issues.append(_issue("MISSING_REQUIRED_FIELD", f"$.{field}", "required field is missing; no default will be used", None, f"supply {field}"))
    if data.get("schema_version") != CONTROL_POLICY_SCHEMA_VERSION:
        issues.append(_issue("UNKNOWN_SCHEMA_VERSION", "$.schema_version", f"schema version must be {CONTROL_POLICY_SCHEMA_VERSION}", data.get("schema_version"), "convert explicitly to ABI v2"))
    return PolicyValidationResult(tuple(issues))


def validate_control_policy_spec(spec: ControlPolicySpec) -> PolicyValidationResult:
    issues: list[PolicyValidationIssue] = []
    if spec.schema_version != CONTROL_POLICY_SCHEMA_VERSION:
        issues.append(_issue("UNKNOWN_SCHEMA_VERSION", "$.schema_version", f"schema version must be {CONTROL_POLICY_SCHEMA_VERSION}", spec.schema_version, "convert explicitly to ABI v2"))
    if (spec.time_unit, spec.detuning_unit, spec.saturation_unit) != ("s", "Gamma", "saturation_parameter"):
        issues.append(_issue("INVALID_UNITS", "$.units", "supported units are s, Gamma, and saturation_parameter", (spec.time_unit, spec.detuning_unit, spec.saturation_unit), "convert units before constructing the specification"))
    if tuple(spec.component_order) != CONTROL_COMPONENT_ORDER:
        issues.append(_issue("INVALID_COMPONENT_ORDER", "$.component_order", f"component order must be exactly {CONTROL_COMPONENT_ORDER}", spec.component_order, "supply all four ordered component IDs"))
    parameter_names = [item.name for item in spec.parameter_specs]
    if len(parameter_names) != len(set(parameter_names)):
        issues.append(_issue("DUPLICATE_PARAMETER", "$.parameter_specs", "parameter names must be unique", parameter_names, "rename duplicate parameters"))
    for index, parameter in enumerate(spec.parameter_specs):
        path = f"$.parameter_specs[{index}]"
        if parameter.data_type not in {"float64", "int64", "bool", "string"}:
            issues.append(_issue("INVALID_PARAMETER_TYPE", path + ".data_type", "unsupported parameter data type", parameter.data_type, "use a declared scalar ABI data type"))
        if parameter.lower_bound is not None and parameter.upper_bound is not None:
            try:
                if parameter.lower_bound > parameter.upper_bound: issues.append(_issue("MALFORMED_PARAMETER_BOUNDS", path, "lower bound exceeds upper bound", (parameter.lower_bound, parameter.upper_bound), "correct or mark unknown bounds as null"))
            except TypeError:
                issues.append(_issue("MALFORMED_PARAMETER_BOUNDS", path, "bounds cannot be compared", (parameter.lower_bound, parameter.upper_bound), "match bounds to the parameter data type"))
        if parameter.name not in spec.parameter_values:
            issues.append(_issue("UNRESOLVED_PARAMETER", "$.parameter_values", "parameter has no explicit value; defaults are not substituted", parameter.name, "supply an explicit parameter value"))
    for name, value in spec.parameter_values.items():
        if name not in parameter_names: issues.append(_issue("UNDECLARED_PARAMETER_VALUE", f"$.parameter_values.{name}", "value has no parameter specification", value, "add a parameter specification or remove the value"))
        if isinstance(value, float) and not math.isfinite(value): issues.append(_issue("NONFINITE_VALUE", f"$.parameter_values.{name}", "parameter values must be finite", value, "supply a finite value"))
    segment_ids = [segment.segment_id for segment in spec.segments]
    if len(segment_ids) != len(set(segment_ids)): issues.append(_issue("DUPLICATE_SEGMENT", "$.segments", "segment IDs must be unique", segment_ids, "rename duplicate segments"))
    for sindex, segment in enumerate(spec.segments):
        path = f"$.segments[{sindex}]"
        ids = [component.component_id for component in segment.components]
        if len(ids) != len(set(ids)): issues.append(_issue("DUPLICATE_COMPONENT", path + ".components", "component IDs must be unique", ids, "supply each component once"))
        if tuple(ids) != CONTROL_COMPONENT_ORDER: issues.append(_issue("MISSING_OR_UNORDERED_COMPONENTS", path + ".components", f"exactly ordered components {CONTROL_COMPONENT_ORDER} are required", ids, "supply all four explicit records"))
        for cindex, component in enumerate(segment.components):
            cpath = f"{path}.components[{cindex}]"
            for field, value in (("detuning_gamma", component.detuning_gamma), ("saturation", component.saturation)):
                if not isinstance(value, (int, float)) or not math.isfinite(float(value)): issues.append(_issue("NONFINITE_VALUE", cpath + "." + field, f"{field} must be finite", value, "supply a finite scalar"))
            if component.saturation < 0: issues.append(_issue("NEGATIVE_SATURATION", cpath + ".saturation", "saturation must be nonnegative", component.saturation, "use zero for an optically off component"))
            expected_active = bool(component.enabled and component.saturation > 0)
            if component.active != expected_active: issues.append(_issue("INCONSISTENT_ACTIVE_STATE", cpath + ".active", "active must equal enabled and saturation > 0", component.active, f"set active to {expected_active}"))
            if not component.active and not component.off_reason: issues.append(_issue("MISSING_OFF_REASON", cpath + ".off_reason", "inactive components require an explicit reason", component.off_reason, "supply a nonempty reason; parked detuning may remain"))
    channel_ids = [channel.channel_id for channel in spec.control_channels]
    if len(channel_ids) != len(set(channel_ids)): issues.append(_issue("DUPLICATE_CHANNEL_ID", "$.control_channels", "control-channel IDs must be unique", channel_ids, "rename duplicate channels"))
    ownership: dict[tuple[str, int, str], str] = {}
    dependencies: dict[str, str] = {}
    components_by_segment = {segment.segment_id: {component.component_id: component for component in segment.components} for segment in spec.segments}
    for index, channel in enumerate(spec.control_channels):
        path = f"$.control_channels[{index}]"
        if channel.relationship not in set(ChannelRelationship) or channel.signal_kind not in set(ChannelSignalKind):
            issues.append(_issue("UNKNOWN_CHANNEL_TYPE", path, "unknown channel types fail closed", (channel.relationship, channel.signal_kind), "use a v2 channel type"))
        if channel.relationship is ChannelRelationship.SHARED and len(channel.targets) < 2: issues.append(_issue("INVALID_SHARED_CHANNEL", path + ".targets", "SHARED channels require multiple targets", len(channel.targets), "add targets or use INDEPENDENT"))
        if channel.relationship is ChannelRelationship.AFFINE_DERIVED:
            if not channel.source_channel_id or channel.affine_scale is None or channel.affine_offset is None: issues.append(_issue("MALFORMED_AFFINE_CHANNEL", path, "affine channels require source, scale, and offset", channel.source_channel_id, "supply the complete affine transform"))
            else: dependencies[channel.channel_id] = channel.source_channel_id
        for target in channel.targets:
            key = (target.segment_id, target.component_id, target.field)
            if key in ownership: issues.append(_issue("DUPLICATE_CHANNEL_OWNERSHIP", path + ".targets", "controlled field has overlapping channel ownership", key, f"remove overlap with {ownership[key]}"))
            ownership[key] = channel.channel_id
            if target.segment_id not in components_by_segment or target.component_id not in components_by_segment.get(target.segment_id, {}): issues.append(_issue("UNRESOLVED_CHANNEL_TARGET", path + ".targets", "channel target does not resolve to a component", key, "correct segment/component membership"))
        if channel.signal_kind is ChannelSignalKind.FIXED:
            declared = channel.fixed_value
            if declared is None and len(channel.parameter_names) == 1:
                declared = spec.parameter_values.get(channel.parameter_names[0])
            if declared is None:
                issues.append(_issue("UNRESOLVED_FIXED_CHANNEL", path, "fixed channel has no fixed value or resolved parameter", channel.parameter_names, "supply exactly one explicit fixed value"))
            else:
                for target in channel.targets:
                    component = components_by_segment.get(target.segment_id, {}).get(target.component_id)
                    if component and getattr(component, target.field) != declared:
                        issues.append(_issue("FIXED_CHANNEL_VALUE_MISMATCH", path, "fixed channel value differs from declared component state", (declared, getattr(component, target.field)), "make the state and channel value identical"))
        if channel.signal_kind is ChannelSignalKind.LINEAR_HOLD:
            if len(channel.parameter_names) != 3 or any(name not in spec.parameter_values for name in channel.parameter_names):
                issues.append(_issue("UNRESOLVED_LINEAR_CHANNEL", path + ".parameter_names", "linear-hold channels require explicit initial, final, and duration parameters", channel.parameter_names, "supply three declared parameter names"))
            else:
                initial = spec.parameter_values[channel.parameter_names[0]]
                duration = spec.parameter_values[channel.parameter_names[2]]
                if not isinstance(duration, (int, float)) or duration <= 0:
                    issues.append(_issue("INVALID_LINEAR_DURATION", path, "linear-hold duration must be positive", duration, "supply a positive duration"))
                for target in channel.targets:
                    component = components_by_segment.get(target.segment_id, {}).get(target.component_id)
                    if component and getattr(component, target.field) != initial:
                        issues.append(_issue("LINEAR_INITIAL_VALUE_MISMATCH", path, "linear channel initial value differs from declared segment state", (initial, getattr(component, target.field)), "make the state equal the initial parameter"))
        if channel.relationship is ChannelRelationship.SHARED:
            endpoint_values = []
            for target in channel.targets:
                component = components_by_segment.get(target.segment_id, {}).get(target.component_id)
                if component: endpoint_values.append(getattr(component, target.field))
            if endpoint_values and any(value != endpoint_values[0] for value in endpoint_values[1:]): issues.append(_issue("SHARED_CHANNEL_VALUE_MISMATCH", path, "shared-channel target values must be equal at the declared state", endpoint_values, "make shared target values identical"))
    for segment in spec.segments:
        for component in segment.components:
            for field in ("detuning_gamma", "saturation"):
                key = (segment.segment_id, component.component_id, field)
                if key not in ownership: issues.append(_issue("UNRESOLVED_CONTROLLED_FIELD", f"$.segments.{segment.segment_id}.component[{component.component_id}].{field}", "every controlled field needs exactly one channel", key, "add an explicit channel"))
                else:
                    declared_id = component.detuning_channel_id if field == "detuning_gamma" else component.saturation_channel_id
                    if declared_id != ownership[key]: issues.append(_issue("CHANNEL_IDENTIFIER_MISMATCH", f"$.segments.{segment.segment_id}.component[{component.component_id}].{field}", "component channel identifier does not match the owning channel", (declared_id, ownership[key]), "use the unique owner channel ID"))
    for start in dependencies:
        seen = set(); current = start
        while current in dependencies:
            if current in seen:
                issues.append(_issue("CYCLIC_DERIVED_CHANNEL", "$.control_channels", "affine-derived channel dependencies must be acyclic", start, "break the dependency cycle")); break
            seen.add(current); current = dependencies[current]
        if current not in channel_ids: issues.append(_issue("UNRESOLVED_DERIVED_CHANNEL", "$.control_channels", "affine source channel is unknown", current, "reference an existing channel"))
    domain = spec.domain
    if not math.isfinite(domain.minimum_time_s) or (domain.maximum_time_s is not None and (not math.isfinite(domain.maximum_time_s) or domain.maximum_time_s < domain.minimum_time_s)):
        issues.append(_issue("INVALID_DOMAIN", "$.domain", "time domain is invalid", domain, "supply finite ordered domain bounds"))
    if domain.maximum_time_s is None and not domain.unbounded_continuation: issues.append(_issue("INVALID_DOMAIN", "$.domain.unbounded_continuation", "an absent maximum requires explicit unbounded continuation", False, "set unbounded_continuation true or supply a maximum"))
    event_times = [event.event_time_s for event in spec.events]
    if event_times != sorted(event_times): issues.append(_issue("UNSORTED_EVENTS", "$.events", "event records must be sorted by time", event_times, "sort events without changing semantic ordering"))
    event_ids = [event.event_id for event in spec.events]
    if len(event_ids) != len(set(event_ids)): issues.append(_issue("DUPLICATE_EVENT_ID", "$.events", "event IDs must be unique", event_ids, "use distinct IDs for simultaneous distinct events"))
    for index, event in enumerate(spec.events):
        if not math.isfinite(event.event_time_s): issues.append(_issue("NONFINITE_EVENT_TIME", f"$.events[{index}].event_time_s", "event time must be finite", event.event_time_s, "supply a finite time"))
        if event.event_time_s < domain.minimum_time_s or (domain.maximum_time_s is not None and event.event_time_s > domain.maximum_time_s): issues.append(_issue("EVENT_DOMAIN_CONFLICT", f"$.events[{index}]", "event lies outside the declared domain", event.event_time_s, "adjust the domain or event"))
    if spec.policy_family is ControlPolicyFamily.CHIRP_TO_TRAP_HANDOFF and len(spec.events) != 1: issues.append(_issue("IMPLICIT_OR_MISSING_DISCONTINUITY", "$.events", "handoff requires one explicit event", len(spec.events), "declare the handoff event"))
    if spec.policy_family is ControlPolicyFamily.CHIRP_TO_TRAP_HANDOFF and len(spec.events) == 1 and len(spec.segments) == 2:
        event = spec.events[0]
        if (event.left_semantic_label, event.right_semantic_label) != (spec.segments[0].semantic_label, spec.segments[1].semantic_label):
            issues.append(_issue("EVENT_SEGMENT_CONFLICT", "$.events[0]", "handoff event labels must match left/right segment semantics", (event.left_semantic_label, event.right_semantic_label), "match the ordered segment labels"))
    if spec.policy_family is ControlPolicyFamily.LINEAR_CHIRP and len(spec.events) == 1:
        linear = next((channel for channel in spec.control_channels if channel.signal_kind is ChannelSignalKind.LINEAR_HOLD), None)
        if linear and len(linear.parameter_names) == 3 and spec.events[0].event_time_s != spec.parameter_values.get(linear.parameter_names[2]):
            issues.append(_issue("EVENT_ENDPOINT_CONFLICT", "$.events[0].event_time_s", "chirp endpoint event must equal the linear duration", spec.events[0].event_time_s, "set the event to the duration parameter"))
    if spec.statefulness is PolicyStatefulness.STATEFUL_CONTROLLER: issues.append(_issue("STATEFUL_EXECUTION_UNSUPPORTED", "$.statefulness", "stateful controllers are reserved but cannot execute in Run 013", spec.statefulness.value, "use STATELESS_OPEN_LOOP for Run 013 execution", PolicyIssueSeverity.WARNING))
    return PolicyValidationResult(tuple(issues))
