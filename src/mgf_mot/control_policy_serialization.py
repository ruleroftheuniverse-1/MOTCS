"""Canonical JSON serialization and deterministic hashes for policy ABI v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping

from .control_policy_abi import (
    BoundBasis, ChannelRelationship, ChannelSignalKind, ChannelTarget,
    ControlChannelSpec, ControlPolicyFamily, ControlPolicySpec, DomainBehavior,
    EventBoundaryRule, PolicyDomain, PolicyEvent, PolicyParameterSpec,
    PolicyProvenance, PolicySegment, PolicyStatefulness, ComponentControlState,
)


@dataclass(frozen=True)
class ControlPolicyHashes:
    parameter_specification: str
    channel_specification: str
    policy_specification: str
    full_policy_package: str


def _plain(value: Any) -> Any:
    if isinstance(value, Enum): return value.value
    if is_dataclass(value): return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping): return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(item) for item in value]
    if callable(value): raise ValueError("arbitrary executable content cannot be serialized")
    return value


def control_policy_spec_to_mapping(spec: ControlPolicySpec) -> dict[str, Any]:
    return _plain(spec)


def canonical_control_policy_json(spec_or_mapping: ControlPolicySpec | Mapping[str, Any]) -> str:
    value = control_policy_spec_to_mapping(spec_or_mapping) if isinstance(spec_or_mapping, ControlPolicySpec) else _plain(spec_or_mapping)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def serialize_control_policy_spec(spec: ControlPolicySpec, *, pretty: bool = False) -> str:
    mapping = control_policy_spec_to_mapping(spec)
    if pretty: return json.dumps(mapping, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    return canonical_control_policy_json(mapping)


def _required(mapping: Mapping[str, Any], fields: tuple[str, ...], path: str) -> None:
    missing = [field for field in fields if field not in mapping]
    if missing: raise ValueError(f"{path} missing required fields: {missing}; no defaults are permitted")


def _component(data: Mapping[str, Any]) -> ComponentControlState:
    fields = ("component_id", "detuning_gamma", "saturation", "enabled", "active", "off_reason", "detuning_channel_id", "saturation_channel_id", "role", "polarization", "relative_saturation")
    _required(data, fields, "component")
    return ComponentControlState(**{field: data[field] for field in fields})


def control_policy_spec_from_mapping(data: Mapping[str, Any]) -> ControlPolicySpec:
    required = ("schema_version", "policy_family", "policy_name", "policy_description", "time_unit", "detuning_unit", "saturation_unit", "component_order", "parameter_specs", "parameter_values", "control_channels", "segments", "events", "domain", "statefulness", "provenance", "legacy_policy_type")
    _required(data, required, "control policy specification")
    parameters = []
    for row in data["parameter_specs"]:
        _required(row, ("name", "description", "shape", "units", "data_type", "default_value", "lower_bound", "upper_bound", "adjustable", "bound_basis"), "parameter")
        parameters.append(PolicyParameterSpec(
            name=row["name"], description=row["description"], shape=tuple(row["shape"]), units=row["units"], data_type=row["data_type"],
            default_value=row["default_value"], lower_bound=row["lower_bound"], upper_bound=row["upper_bound"], adjustable=row["adjustable"], bound_basis=BoundBasis(row["bound_basis"]),
        ))
    channels = []
    for row in data["control_channels"]:
        _required(row, ("channel_id", "relationship", "signal_kind", "field", "targets", "parameter_names", "fixed_value", "source_channel_id", "affine_scale", "affine_offset", "description"), "channel")
        channels.append(ControlChannelSpec(
            channel_id=row["channel_id"], relationship=ChannelRelationship(row["relationship"]), signal_kind=ChannelSignalKind(row["signal_kind"]), field=row["field"],
            targets=tuple(ChannelTarget(**target) for target in row["targets"]), parameter_names=tuple(row["parameter_names"]), fixed_value=row["fixed_value"], source_channel_id=row["source_channel_id"], affine_scale=row["affine_scale"], affine_offset=row["affine_offset"], description=row["description"],
        ))
    segments = tuple(PolicySegment(segment_id=row["segment_id"], semantic_label=row["semantic_label"], components=tuple(_component(item) for item in row["components"])) for row in data["segments"])
    events = tuple(PolicyEvent(
        event_id=row["event_id"], event_time_s=row["event_time_s"], event_type=row["event_type"], affected_channel_ids=tuple(row["affected_channel_ids"]), affected_component_ids=tuple(row["affected_component_ids"]), left_semantic_label=row["left_semantic_label"], right_semantic_label=row["right_semantic_label"], boundary_rule=EventBoundaryRule(row["boundary_rule"]), provenance=row["provenance"],
    ) for row in data["events"])
    domain_data = data["domain"]; provenance_data = data["provenance"]
    domain = PolicyDomain(
        minimum_time_s=domain_data["minimum_time_s"], maximum_time_s=domain_data["maximum_time_s"], unbounded_continuation=domain_data["unbounded_continuation"], before_minimum=DomainBehavior(domain_data["before_minimum"]), after_maximum=DomainBehavior(domain_data["after_maximum"]), endpoint_semantics=domain_data["endpoint_semantics"],
    )
    provenance = PolicyProvenance(
        schema_version=provenance_data["schema_version"], policy_family_id=provenance_data["policy_family_id"], source_configuration_paths=tuple(provenance_data["source_configuration_paths"]), source_configuration_hashes=tuple(provenance_data["source_configuration_hashes"]), implementation_version=provenance_data["implementation_version"], parent_policy_ids=tuple(provenance_data["parent_policy_ids"]), units=dict(provenance_data["units"]), generation_method=provenance_data["generation_method"], non_replication_labels=tuple(provenance_data["non_replication_labels"]), notes=tuple(provenance_data["notes"]),
    )
    return ControlPolicySpec(
        schema_version=data["schema_version"], policy_family=ControlPolicyFamily(data["policy_family"]), policy_name=data["policy_name"], policy_description=data["policy_description"], time_unit=data["time_unit"], detuning_unit=data["detuning_unit"], saturation_unit=data["saturation_unit"], component_order=tuple(data["component_order"]), parameter_specs=tuple(parameters), parameter_values=dict(data["parameter_values"]), control_channels=tuple(channels), segments=segments, events=events, domain=domain, statefulness=PolicyStatefulness(data["statefulness"]), provenance=provenance, legacy_policy_type=data["legacy_policy_type"],
    )


def deserialize_control_policy_spec(text: str) -> ControlPolicySpec:
    data = json.loads(text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite JSON value {value} is forbidden")))
    if not isinstance(data, dict): raise ValueError("control policy JSON root must be an object")
    return control_policy_spec_from_mapping(data)


def _digest(value: Any) -> str:
    return sha256(canonical_control_policy_json(value).encode("utf-8")).hexdigest()


def control_policy_hashes(spec: ControlPolicySpec) -> ControlPolicyHashes:
    mapping = control_policy_spec_to_mapping(spec)
    parameter = {"parameter_specs": mapping["parameter_specs"], "parameter_values": mapping["parameter_values"]}
    channel = {"control_channels": mapping["control_channels"]}
    policy = {key: value for key, value in mapping.items() if key != "provenance"}
    return ControlPolicyHashes(_digest(parameter), _digest(channel), _digest(policy), _digest(mapping))
