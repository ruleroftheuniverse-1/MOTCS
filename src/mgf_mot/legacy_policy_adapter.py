"""Explicit v1-policy to control-policy ABI v2 compatibility adapter."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

from .control_policy_abi import (
    BoundBasis, ChannelRelationship, ChannelSignalKind, ChannelTarget,
    ComponentControlState, ControlChannelSpec, ControlPolicyFamily,
    ControlPolicySpec, DomainBehavior, EventBoundaryRule, PolicyDomain,
    PolicyEvent, PolicyParameterSpec, PolicyProvenance, PolicySegment,
    PolicyState, PolicyStatefulness, CONTROL_POLICY_SCHEMA_VERSION,
    RUN013_LABEL,
)
from .policies import (
    ChirpToTrapHandoffPolicy, ComponentState, LinearChirpPolicy, PolicySample,
    StaticPolicy,
)


LEGACY_UNSPECIFIED_OFF_REASON = "legacy_v1_explicit_disabled_no_text_reason"


def _source(path: Path | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if path is None:
        return (), ()
    return (path.as_posix(),), (sha256(path.read_bytes()).hexdigest(),)


def _bounds(policy: Any, field: str) -> tuple[float | None, float | None, BoundBasis]:
    bounds = policy.apparatus_bounds
    if bounds is None: return None, None, BoundBasis.UNKNOWN
    pair = bounds.detuning_range_gamma if field == "detuning_gamma" else bounds.saturation_range
    return (None, None, BoundBasis.UNKNOWN) if pair is None else (float(pair[0]), float(pair[1]), BoundBasis.APPARATUS_ASSUMPTION)


def _parameter(name: str, value: float, description: str, units: str, policy: Any, field: str | None = None) -> tuple[PolicyParameterSpec, tuple[str, float]]:
    lower, upper, basis = _bounds(policy, field) if field else (None, None, BoundBasis.UNKNOWN)
    return PolicyParameterSpec(name, description, (), units, "float64", None, lower, upper, False, basis), (name, float(value))


def _abi_component(component: ComponentState, detuning_channel: str, saturation_channel: str) -> ComponentControlState:
    active = component.enabled and component.saturation > 0.0
    reason = None if active else (component.off_reason or LEGACY_UNSPECIFIED_OFF_REASON)
    return ComponentControlState(
        component_id=component.component_id, detuning_gamma=float(component.detuning_gamma), saturation=float(component.saturation),
        enabled=bool(component.enabled), active=active, off_reason=reason,
        detuning_channel_id=detuning_channel, saturation_channel_id=saturation_channel,
        role=component.role, polarization=component.polarization,
        relative_saturation=component.relative_saturation,
    )


def _fixed_segment(policy: Any, components: tuple[ComponentState, ...], segment_id: str, semantic: str, prefix: str) -> tuple[PolicySegment, list[ControlChannelSpec], list[PolicyParameterSpec], dict[str, float]]:
    channels: list[ControlChannelSpec] = []; specs: list[PolicyParameterSpec] = []; values: dict[str, float] = {}
    detuning_ids: dict[int, str] = {}
    if components[0].detuning_gamma == components[1].detuning_gamma == components[2].detuning_gamma:
        channel_id = f"{prefix}_shared_detuning_123"; parameter_name = f"{prefix}_detuning_123_gamma"
        item, value = _parameter(parameter_name, components[0].detuning_gamma, "Shared fixed detuning for components 1,2,3", "Gamma", policy, "detuning_gamma"); specs.append(item); values.update([value])
        targets = tuple(ChannelTarget(segment_id, index, "detuning_gamma") for index in (1,2,3))
        channels.append(ControlChannelSpec(channel_id, ChannelRelationship.SHARED, ChannelSignalKind.FIXED, "detuning_gamma", targets, (parameter_name,), description="One shared fixed detuning channel"))
        detuning_ids.update({index: channel_id for index in (1,2,3)})
    for component in components:
        if component.component_id not in detuning_ids:
            channel_id = f"{prefix}_component_{component.component_id}_detuning"; parameter_name = f"{prefix}_component_{component.component_id}_detuning_gamma"
            item, value = _parameter(parameter_name, component.detuning_gamma, f"Fixed detuning of component {component.component_id}", "Gamma", policy, "detuning_gamma"); specs.append(item); values.update([value])
            channels.append(ControlChannelSpec(channel_id, ChannelRelationship.FIXED, ChannelSignalKind.FIXED, "detuning_gamma", (ChannelTarget(segment_id, component.component_id, "detuning_gamma"),), (parameter_name,), description="Explicit fixed/parked detuning")); detuning_ids[component.component_id] = channel_id
    saturation_ids = {}
    for component in components:
        channel_id = f"{prefix}_component_{component.component_id}_saturation"; parameter_name = f"{prefix}_component_{component.component_id}_saturation"
        item, value = _parameter(parameter_name, component.saturation, f"Fixed saturation of component {component.component_id}", "saturation_parameter", policy, "saturation"); specs.append(item); values.update([value])
        channels.append(ControlChannelSpec(channel_id, ChannelRelationship.FIXED, ChannelSignalKind.FIXED, "saturation", (ChannelTarget(segment_id, component.component_id, "saturation"),), (parameter_name,), description="Explicit fixed optical power")); saturation_ids[component.component_id] = channel_id
    state = tuple(_abi_component(component, detuning_ids[component.component_id], saturation_ids[component.component_id]) for component in components)
    return PolicySegment(segment_id, semantic, state), channels, specs, values


def _chirp_segment(policy: LinearChirpPolicy, segment_id: str, semantic: str, prefix: str) -> tuple[PolicySegment, list[ControlChannelSpec], list[PolicyParameterSpec], dict[str, float]]:
    channels: list[ControlChannelSpec] = []; specs: list[PolicyParameterSpec] = []; values: dict[str, float] = {}
    names_values = (
        _parameter(f"{prefix}_initial_detuning_gamma", policy.initial_detuning_gamma, "Common initial chirp detuning", "Gamma", policy, "detuning_gamma"),
        _parameter(f"{prefix}_final_detuning_gamma", policy.final_detuning_gamma, "Common final chirp detuning", "Gamma", policy, "detuning_gamma"),
        _parameter(f"{prefix}_duration_s", policy.duration_s, "Linear chirp duration", "s", policy),
    )
    for item, value in names_values: specs.append(item); values.update([value])
    chirp_id = f"{prefix}_shared_linear_detuning_123"
    parameter_names = tuple(item.name for item, _ in names_values)
    channels.append(ControlChannelSpec(chirp_id, ChannelRelationship.SHARED, ChannelSignalKind.LINEAR_HOLD, "detuning_gamma", tuple(ChannelTarget(segment_id, index, "detuning_gamma") for index in (1,2,3)), parameter_names, description="Rodriguez common linear detuning channel for components 1,2,3"))
    component4 = policy.components[3]; parked_id = f"{prefix}_component_4_parked_detuning"; parked_name = f"{prefix}_component_4_detuning_gamma"
    item, value = _parameter(parked_name, component4.detuning_gamma, "Parked detuning of inactive component 4", "Gamma", policy, "detuning_gamma"); specs.append(item); values.update([value])
    channels.append(ControlChannelSpec(parked_id, ChannelRelationship.FIXED, ChannelSignalKind.FIXED, "detuning_gamma", (ChannelTarget(segment_id, 4, "detuning_gamma"),), (parked_name,), description="Parked component 4 frequency, not optical activity"))
    saturation_ids = {}
    for component in policy.components:
        channel_id = f"{prefix}_component_{component.component_id}_saturation"; name = f"{prefix}_component_{component.component_id}_saturation"
        item, value = _parameter(name, component.saturation, f"Fixed saturation of component {component.component_id}", "saturation_parameter", policy, "saturation"); specs.append(item); values.update([value])
        channels.append(ControlChannelSpec(channel_id, ChannelRelationship.FIXED, ChannelSignalKind.FIXED, "saturation", (ChannelTarget(segment_id, component.component_id, "saturation"),), (name,), description="Fixed chirp-stage optical power")); saturation_ids[component.component_id] = channel_id
    states = tuple(_abi_component(component, chirp_id if component.component_id in (1,2,3) else parked_id, saturation_ids[component.component_id]) for component in policy.components)
    return PolicySegment(segment_id, semantic, states), channels, specs, values


def legacy_policy_to_v2_spec(policy: StaticPolicy | LinearChirpPolicy | ChirpToTrapHandoffPolicy, *, source_path: Path | None) -> ControlPolicySpec:
    source_paths, source_hashes = _source(source_path)
    segments: list[PolicySegment] = []; channels: list[ControlChannelSpec] = []; parameters: list[PolicyParameterSpec] = []; values: dict[str, float] = {}; events: list[PolicyEvent] = []
    parents: tuple[str, ...] = (); notes = ["Converted declaratively from the existing v1 policy object; source YAML was not rewritten."]
    if isinstance(policy, StaticPolicy):
        family = ControlPolicyFamily.STATIC
        segment, c, p, v = _fixed_segment(policy, policy.components, "static", "static", "static")
        segments.append(segment); channels += c; parameters += p; values.update(v)
        description = "Legacy-compatible static four-component schedule"
    elif isinstance(policy, LinearChirpPolicy):
        family = ControlPolicyFamily.LINEAR_CHIRP
        segment, c, p, v = _chirp_segment(policy, "linear_chirp", "linear_chirp", "chirp")
        segments.append(segment); channels += c; parameters += p; values.update(v)
        events.append(PolicyEvent("chirp_endpoint", policy.duration_s, "CONTINUOUS_CHIRP_TO_HOLD", ("chirp_shared_linear_detuning_123",), (1,2,3), "linear_chirp", "final_detuning_hold", EventBoundaryRule.LEFT_OPEN_RIGHT_CLOSED, policy.source))
        description = "Legacy-compatible common linear chirp with final hold"
    else:
        family = ControlPolicyFamily.CHIRP_TO_TRAP_HANDOFF
        pre, c, p, v = _chirp_segment(policy.chirp_policy, "pre_handoff", "chirp_3", "pre")
        post, c2, p2, v2 = _fixed_segment(policy.trap_policy, policy.trap_policy.components, "post_handoff", "trap_3_plus_1", "post")
        segments += [pre, post]; channels += c + c2; parameters += p + p2; values.update(v); values.update(v2)
        events.append(PolicyEvent("chirp_to_trap_handoff", policy.handoff_time_s, "DISCONTINUOUS_POLICY_HANDOFF", tuple(channel.channel_id for channel in channels), (1,2,3,4), "chirp_3", "trap_3_plus_1", EventBoundaryRule.LEFT_OPEN_RIGHT_CLOSED, policy.source))
        parents = (policy.chirp_policy.name, policy.trap_policy.name); description = "Legacy-compatible t<tau chirped [3], t>=tau static [3+1] handoff"
    if any(component.off_reason is None and not component.active for segment in segments for component in segment.components):
        raise AssertionError("ABI adapter left an inactive component without a reason")
    if any(component.off_reason == LEGACY_UNSPECIFIED_OFF_REASON for segment in segments for component in segment.components):
        notes.append("ABI v2 labels a legacy explicit-disabled/null-reason component with a sentinel; compatibility projection restores null exactly.")
    provenance = PolicyProvenance(
        schema_version=CONTROL_POLICY_SCHEMA_VERSION, policy_family_id=family.value,
        source_configuration_paths=source_paths, source_configuration_hashes=source_hashes,
        implementation_version="run013-control-policy-abi-v2.0", parent_policy_ids=parents,
        units={"time": policy.time_unit, "detuning": policy.detuning_unit, "saturation": policy.saturation_unit},
        generation_method="legacy_v1_to_declarative_v2_adapter",
        non_replication_labels=("MODEL_INDEPENDENT", "NOT_RODRIGUEZ_REPLICATION", "CONTROL_POLICY_ABI_ONLY"), notes=tuple(notes),
    )
    return ControlPolicySpec(
        schema_version=CONTROL_POLICY_SCHEMA_VERSION, policy_family=family, policy_name=policy.name,
        policy_description=description, time_unit=policy.time_unit, detuning_unit=policy.detuning_unit,
        saturation_unit=policy.saturation_unit, component_order=tuple(policy.component_order),
        parameter_specs=tuple(parameters), parameter_values=values, control_channels=tuple(channels),
        segments=tuple(segments), events=tuple(events),
        domain=PolicyDomain(0.0, None, True, DomainBehavior.HOLD_INITIAL, DomainBehavior.HOLD_FINAL, "t=0 included; finite endpoints use exact values; unbounded final hold"),
        statefulness=PolicyStatefulness.STATELESS_OPEN_LOOP, provenance=provenance,
        legacy_policy_type=policy.policy_type,
    )


def v2_state_to_legacy_sample(state: PolicyState, policy: StaticPolicy | LinearChirpPolicy | ChirpToTrapHandoffPolicy) -> PolicySample:
    components = tuple(ComponentState(
        component_id=component.component_id, detuning_gamma=component.detuning_gamma,
        saturation=component.saturation, enabled=component.enabled, role=component.role,
        polarization=component.polarization, relative_saturation=component.relative_saturation,
        off_reason=None if component.off_reason == LEGACY_UNSPECIFIED_OFF_REASON else component.off_reason,
    ) for component in state.components)
    segment = "static" if isinstance(policy, StaticPolicy) else "linear_chirp" if isinstance(policy, LinearChirpPolicy) else state.semantic_label
    return PolicySample(
        time_s=state.time_s, component_order=tuple(state.component_order), detuning_unit=policy.detuning_unit,
        saturation_unit=policy.saturation_unit, components=components, segment=segment,
        handoff_occurred=state.handoff_occurred,
    )
