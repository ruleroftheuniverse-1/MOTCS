"""Deterministic Run 014 compiler from ABI-v2 policy to apparatus commands."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Any, Mapping

import numpy as np

from .apparatus_constraints import (
    COMPILED_SCHEDULE_SCHEMA_VERSION, ActivationRestriction,
    ApparatusConstraintSet, ClockRoundingMode, EventExecutionRule,
    HardwareValidationStatus, KnowledgeState, apparatus_profile_hash,
    validate_apparatus_profile,
)
from .control_policy_abi import (
    ChannelRelationship, ComponentControlState, ControlPolicy, ControlPolicySpec,
    PolicyState,
)
from .control_policy_serialization import control_policy_hashes
from .control_policy_validation import validate_control_policy_spec


class CompilationMode(str, Enum):
    EXACT_ONLY = "EXACT_ONLY"
    SAMPLE_AND_HOLD = "SAMPLE_AND_HOLD"
    DIAGNOSTIC_PARTIAL_PROFILE = "DIAGNOSTIC_PARTIAL_PROFILE"


class InitialStateMode(str, Enum):
    EXPLICIT_INITIAL_STATE = "EXPLICIT_INITIAL_STATE"
    POLICY_STATE_AT_START = "POLICY_STATE_AT_START"
    REQUIRE_PRE_ROLL = "REQUIRE_PRE_ROLL"


class ReconstructionMode(str, Enum):
    ZERO_ORDER_HOLD = "ZERO_ORDER_HOLD"
    SYNTHETIC_CONTINUOUS_IDENTITY_BINDING = "SYNTHETIC_CONTINUOUS_IDENTITY_BINDING"


class CompilationStatus(str, Enum):
    COMPILED_EXACT = "COMPILED_EXACT"
    COMPILED_APPROXIMATE = "COMPILED_APPROXIMATE"
    COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE = "COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE"
    COMPILATION_INFEASIBLE = "COMPILATION_INFEASIBLE"
    COMPILATION_INVALID = "COMPILATION_INVALID"


@dataclass(frozen=True)
class CompilationRequest:
    policy_hash: str
    profile_hash: str
    mode: CompilationMode
    start_time_s: float
    end_time_s: float
    initial_state_mode: InitialStateMode
    explicit_initial_channel_values: Mapping[str, float] | None
    pre_roll_s: float | None
    diagnostic_grid_period_s: float | None
    reconstruction_mode: ReconstructionMode


@dataclass(frozen=True)
class HardwareCommand:
    command_id: str
    channel_id: str
    field: str
    requested_effective_time_s: float
    issued_time_s: float
    actual_effective_time_s: float
    latency_s: float
    clock_displacement_s: float
    ideal_value: float
    quantized_value: float
    units: str
    quantization_step: float | None
    rounding_rule: str
    quantization_error: float
    event_id: str | None
    atomic_group_id: str | None
    continuous_identity_binding: bool


@dataclass(frozen=True)
class CompiledEvent:
    event_id: str
    requested_time_s: float
    realized_time_s: float
    displacement_s: float
    affected_channel_ids: tuple[str, ...]
    affected_component_ids: tuple[int, ...]
    atomic: bool
    left_semantic_label: str
    right_semantic_label: str
    left_component_states: tuple[ComponentControlState, ...]
    right_component_states: tuple[ComponentControlState, ...]


@dataclass(frozen=True)
class ConstraintViolation:
    code: str
    severity: str
    field_path: str
    message: str
    offending_value: Any
    units: str | None
    command_or_event_id: str | None
    suggested_correction: str | None


@dataclass(frozen=True)
class CompilationMetric:
    channel_id: str
    field: str
    maximum_absolute_value_error: float
    rms_value_error: float
    endpoint_error: float
    event_adjacent_error: float
    maximum_measured_first_derivative: float
    maximum_measured_second_difference: float
    maximum_absolute_quantization_error: float
    rms_quantization_error: float
    raw_command_count: int
    deduplicated_command_count: int


@dataclass(frozen=True)
class ScheduleHashes:
    apparatus_profile: str
    compilation_request: str
    source_policy_specification: str
    command_stream: str
    realized_schedule: str
    complete_compiled_package: str


@dataclass(frozen=True)
class CompiledControlSchedule:
    schema_version: str
    compiler_version: str
    compilation_order: tuple[str, ...]
    status: CompilationStatus
    policy_hash: str
    apparatus_profile_hash: str
    request: CompilationRequest
    commands: tuple[HardwareCommand, ...]
    events: tuple[CompiledEvent, ...]
    initial_channel_values: Mapping[str, float]
    violations: tuple[ConstraintViolation, ...]
    metrics: tuple[CompilationMetric, ...]
    total_raw_command_count: int
    total_command_count: int
    simultaneous_command_group_count: int
    maximum_event_displacement_s: float
    profile_complete: bool
    hardware_validation_status: str
    hardware_executable_claim_valid: bool
    hashes: ScheduleHashes


@dataclass(frozen=True)
class CompilationReport:
    """Portable summary view; the compiled package remains the source of truth."""

    status: CompilationStatus
    violations: tuple[ConstraintViolation, ...]
    metrics: tuple[CompilationMetric, ...]
    compilation_horizon_s: tuple[float, float]
    requested_realized_events: tuple[CompiledEvent, ...]
    total_command_count: int
    simultaneous_command_group_count: int
    profile_complete: bool
    hardware_validation_status: str
    hardware_executable_claim_valid: bool

    @classmethod
    def from_compiled(cls, compiled: CompiledControlSchedule) -> "CompilationReport":
        return cls(
            compiled.status, compiled.violations, compiled.metrics,
            (compiled.request.start_time_s, compiled.request.end_time_s),
            compiled.events, compiled.total_command_count,
            compiled.simultaneous_command_group_count, compiled.profile_complete,
            compiled.hardware_validation_status,
            compiled.hardware_executable_claim_valid,
        )


class RealizedControlSchedule:
    """Pure evaluator for effective commands over one finite horizon."""

    def __init__(self, policy_spec: ControlPolicySpec, compiled: CompiledControlSchedule):
        if compiled.request.reconstruction_mode not in {ReconstructionMode.ZERO_ORDER_HOLD, ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING}:
            raise ValueError("unsupported reconstruction mode")
        self.policy = ControlPolicy(policy_spec); self.compiled = compiled
        self.by_channel: dict[str,list[HardwareCommand]] = {}
        for command in compiled.commands: self.by_channel.setdefault(command.channel_id, []).append(command)

    def _mapped_policy_time(self, t: float) -> float:
        if not self.compiled.events: return t
        event = self.compiled.events[0]
        if event.realized_time_s == event.requested_time_s: return t
        if t < event.realized_time_s:
            return min(t, math.nextafter(event.requested_time_s, -math.inf))
        return event.requested_time_s + (t - event.realized_time_s)

    def sample(self, t: float) -> PolicyState:
        if not math.isfinite(t) or t < self.compiled.request.start_time_s or t > self.compiled.request.end_time_s:
            raise ValueError("realized schedule sample time lies outside the finite compilation horizon")
        mapped = self._mapped_policy_time(t); ideal = self.policy.sample(mapped)
        if self.compiled.request.reconstruction_mode is ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING:
            return replace(ideal, time_s=t, evaluation_time_s=mapped, policy_hash=self.compiled.policy_hash)
        components = {item.component_id:item for item in ideal.components}
        values = dict(self.compiled.initial_channel_values)
        for channel_id, commands in self.by_channel.items():
            for command in commands:
                if command.actual_effective_time_s <= t: values[channel_id] = command.quantized_value
                else: break
        channel_by_id = {channel.channel_id:channel for channel in self.policy.spec.control_channels}
        for channel_id, value in values.items():
            channel = channel_by_id[channel_id]
            for target in channel.targets:
                if target.segment_id != ideal.segment_id: continue
                old = components[target.component_id]
                detuning = value if target.field == "detuning_gamma" else old.detuning_gamma
                saturation = value if target.field == "saturation" else old.saturation
                active = old.enabled and saturation > 0
                components[target.component_id] = replace(old, detuning_gamma=detuning, saturation=saturation, active=active, off_reason=None if active else old.off_reason)
        return replace(ideal, time_s=t, evaluation_time_s=mapped, components=tuple(components[index] for index in (1,2,3,4)), policy_hash=self.compiled.policy_hash)


PIPELINE = (
    "validate_policy", "validate_profile", "validate_request", "resolve_channels",
    "establish_horizon", "collect_events", "construct_effective_time_grid",
    "evaluate_ideal_channels", "align_events", "quantize_values",
    "generate_commands", "apply_latency", "reconstruct_realized_schedule",
    "deduplicate_identical_commands", "validate_hard_constraints",
    "calculate_metrics", "serialize_and_hash",
)


def _plain(value: Any) -> Any:
    from dataclasses import is_dataclass
    if isinstance(value, Enum): return value.value
    if is_dataclass(value): return {key:_plain(item) for key,item in asdict(value).items()}
    if isinstance(value, Mapping): return {str(k):_plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_plain(item) for item in value]
    # Invalid requests still need a deterministic diagnostic-package hash.  Encode
    # non-finite sentinels explicitly instead of allowing non-standard JSON.
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_float": "nan" if math.isnan(value) else ("+inf" if value > 0 else "-inf")}
    return value


def _hash(value: Any) -> str:
    return sha256(json.dumps(_plain(value),sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def compilation_request_hash(request: CompilationRequest) -> str: return _hash(request)


def compiled_schedule_to_mapping(compiled: CompiledControlSchedule) -> dict[str, Any]:
    """Return a deterministic, JSON-compatible representation."""
    return _plain(compiled)


def canonical_compiled_schedule_json(compiled: CompiledControlSchedule) -> str:
    return json.dumps(compiled_schedule_to_mapping(compiled),sort_keys=True,separators=(",",":"),allow_nan=False)


def _align(t: float, origin: float, period: float, mode: ClockRoundingMode) -> float:
    q = (Decimal(str(t))-Decimal(str(origin)))/Decimal(str(period))
    if mode is ClockRoundingMode.REQUIRE_EXACT:
        if q != q.to_integral_value(): raise ValueError("time is not exactly aligned to command clock")
        n=q
    elif mode is ClockRoundingMode.FLOOR: n=q.to_integral_value(rounding=ROUND_FLOOR)
    elif mode is ClockRoundingMode.CEIL: n=q.to_integral_value(rounding=ROUND_CEILING)
    else: n=q.to_integral_value(rounding=ROUND_HALF_EVEN)
    return float(Decimal(str(origin))+n*Decimal(str(period)))


def _quantize(value: float, step: float | None) -> float:
    if step is None: return value
    q=Decimal(str(value))/Decimal(str(step)); n=q.to_integral_value(rounding=ROUND_HALF_EVEN)
    return float(n*Decimal(str(step)))


def _channel_value(policy: ControlPolicy, channel: Any, t: float) -> float:
    state=policy.sample(t); target=channel.targets[0]; component=state.components[target.component_id-1]
    return float(getattr(component,target.field))


def _violation(code: str, message: str, value: Any, units: str|None=None, item: str|None=None) -> ConstraintViolation:
    return ConstraintViolation(code,"ERROR","$",message,value,units,item,None)


def compile_control_schedule(spec: ControlPolicySpec, profile: ApparatusConstraintSet, request: CompilationRequest) -> tuple[CompiledControlSchedule,RealizedControlSchedule|None]:
    violations: list[ConstraintViolation]=[]
    policy_validation=validate_control_policy_spec(spec); profile_validation=validate_apparatus_profile(profile)
    policy_hash=control_policy_hashes(spec).full_policy_package; profile_hash=apparatus_profile_hash(profile)
    if not policy_validation.valid: violations.append(_violation("INVALID_POLICY","ABI-v2 policy validation failed",[x.code for x in policy_validation.errors]))
    if not profile_validation.valid: violations.append(_violation("INVALID_APPARATUS_PROFILE","apparatus profile validation failed",[x.code for x in profile_validation.issues if x.severity=="ERROR"]))
    if request.policy_hash!=policy_hash or request.profile_hash!=profile_hash: violations.append(_violation("HASH_MISMATCH","request policy/profile hashes do not match inputs",(request.policy_hash,request.profile_hash)))
    if not math.isfinite(request.start_time_s) or not math.isfinite(request.end_time_s) or request.end_time_s<=request.start_time_s: violations.append(_violation("INVALID_COMPILATION_HORIZON","explicit finite end > start is mandatory",(request.start_time_s,request.end_time_s),"s"))
    if request.start_time_s < spec.domain.minimum_time_s and spec.domain.before_minimum.value=="ERROR": violations.append(_violation("POLICY_DOMAIN_CONFLICT","horizon starts below policy domain",request.start_time_s,"s"))
    unknown=not profile_validation.complete
    if request.mode is not CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE and unknown: violations.append(_violation("INCOMPLETE_STRICT_PROFILE","UNKNOWN capability is not UNBOUNDED and cannot support strict compilation",profile.profile_id))
    if request.mode is CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE and request.diagnostic_grid_period_s is None: violations.append(_violation("MISSING_DIAGNOSTIC_GRID","partial-profile diagnostic requires an explicit request grid",None,"s"))
    channel_ids={channel.channel_id for channel in spec.control_channels}; capabilities={item.channel_id:item for item in profile.channel_capabilities}
    missing=channel_ids-set(capabilities)
    if missing: violations.append(_violation("UNRESOLVED_CHANNEL","apparatus profile lacks ABI channels",sorted(missing)))
    if violations:
        empty_hash=ScheduleHashes(profile_hash,compilation_request_hash(request),control_policy_hashes(spec).policy_specification,_hash([]),_hash({}),_hash({"invalid":True,"request":request}))
        compiled=CompiledControlSchedule(COMPILED_SCHEDULE_SCHEMA_VERSION,"run014-compiler-v1",PIPELINE,CompilationStatus.COMPILATION_INVALID,policy_hash,profile_hash,request,(),(),{},tuple(violations),(),0,0,0,0.0,not unknown,profile.hardware_validation_status.value,False,empty_hash)
        return compiled,None
    policy=ControlPolicy(spec)
    latency=0.0 if profile.latency.fixed_latency.knowledge is not KnowledgeState.KNOWN else float(profile.latency.fixed_latency.value)
    if latency>0 and request.initial_state_mode is InitialStateMode.POLICY_STATE_AT_START and (request.pre_roll_s is None or request.pre_roll_s<latency): violations.append(_violation("INSUFFICIENT_PRE_ROLL","latency requires explicit initial state or sufficient pre-roll",request.pre_roll_s,"s"))
    if request.initial_state_mode is InitialStateMode.REQUIRE_PRE_ROLL and (request.pre_roll_s is None or request.pre_roll_s < latency):
        violations.append(_violation("INSUFFICIENT_PRE_ROLL","REQUIRE_PRE_ROLL requires an explicit interval at least as long as latency",request.pre_roll_s,"s"))
    if request.initial_state_mode is InitialStateMode.EXPLICIT_INITIAL_STATE and request.explicit_initial_channel_values is None: violations.append(_violation("MISSING_INITIAL_STATE","explicit initial-state mode requires every channel value",None))
    if request.initial_state_mode is InitialStateMode.EXPLICIT_INITIAL_STATE and set(request.explicit_initial_channel_values or {})!=channel_ids: violations.append(_violation("MISSING_INITIAL_STATE","explicit initial state must cover every channel",sorted(set(request.explicit_initial_channel_values or {}))))
    initial={channel.channel_id:_channel_value(policy,channel,request.start_time_s) for channel in spec.control_channels} if request.initial_state_mode is not InitialStateMode.EXPLICIT_INITIAL_STATE else dict(request.explicit_initial_channel_values or {})
    for channel_id, value in initial.items():
        if channel_id not in capabilities:
            violations.append(_violation("UNRESOLVED_CHANNEL","initial state contains an unknown channel",channel_id,None,channel_id))
            continue
        if not isinstance(value,(int,float)) or not math.isfinite(float(value)):
            violations.append(_violation("NONFINITE_INITIAL_STATE","initial channel value must be finite",value,None,channel_id))
            continue
        capability=capabilities[channel_id]
        if capability.minimum.knowledge is KnowledgeState.KNOWN and value < float(capability.minimum.value):
            violations.append(_violation("INITIAL_STATE_OUTSIDE_RANGE","initial channel value is below its minimum",value,capability.minimum.units,channel_id))
        if capability.maximum.knowledge is KnowledgeState.KNOWN and value > float(capability.maximum.value):
            violations.append(_violation("INITIAL_STATE_OUTSIDE_RANGE","initial channel value is above its maximum",value,capability.maximum.units,channel_id))
    continuous=profile.command_clock.continuous_identity_binding
    period=None
    if not continuous:
        if request.mode is CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE: period=float(request.diagnostic_grid_period_s)
        elif profile.command_clock.update_period.knowledge is KnowledgeState.KNOWN: period=float(profile.command_clock.update_period.value)
        else: violations.append(_violation("INVALID_UPDATE_PERIOD","finite-clock compilation requires known update period",None,"s"))
    events=[]
    for event in spec.events:
        if not (request.start_time_s<=event.event_time_s<=request.end_time_s): continue
        realized=event.event_time_s
        if not continuous:
            rule=profile.event_execution.rule
            mode={EventExecutionRule.SNAP_FLOOR:ClockRoundingMode.FLOOR,EventExecutionRule.SNAP_CEIL:ClockRoundingMode.CEIL,EventExecutionRule.SNAP_NEAREST:ClockRoundingMode.NEAREST_TIES_TO_EVEN,EventExecutionRule.REQUIRE_EXACT_TIME:ClockRoundingMode.REQUIRE_EXACT,EventExecutionRule.REJECT_IF_UNALIGNED:ClockRoundingMode.REQUIRE_EXACT}[rule]
            try: realized=_align(event.event_time_s,profile.command_clock.clock_origin_s,period,mode)
            except ValueError: violations.append(_violation("EVENT_MISALIGNMENT","event cannot satisfy execution rule",event.event_time_s,"s",event.event_id)); realized=event.event_time_s
        left_state = policy.sample(math.nextafter(event.event_time_s, -math.inf)).components
        right_state = policy.sample(event.event_time_s).components
        events.append(CompiledEvent(event.event_id,event.event_time_s,realized,realized-event.event_time_s,event.affected_channel_ids,event.affected_component_ids,profile.event_execution.atomic_update_required,event.left_semantic_label,event.right_semantic_label,left_state,right_state))
    if continuous: times=sorted(set([request.start_time_s,request.end_time_s]+[event.realized_time_s for event in events]))
    else:
        count=int(math.floor((request.end_time_s-request.start_time_s)/period+1e-12)); times=[request.start_time_s+i*period for i in range(count+1)]
        times=sorted(set(times+[event.realized_time_s for event in events]))
    raw=[]; raw_count=0
    for channel in spec.control_channels:
        capability=capabilities[channel.channel_id]; last=None
        resolution=None if capability.resolution.knowledge is not KnowledgeState.KNOWN else float(capability.resolution.value)
        for t in times:
            associated=next((event for event in events if event.realized_time_s==t and channel.channel_id in event.affected_channel_ids),None)
            requested_t=associated.requested_time_s if associated else t
            ideal_t=associated.requested_time_s if associated else t
            ideal=_channel_value(policy,channel,ideal_t); quantized=_quantize(ideal,resolution); raw_count+=1
            units="Gamma" if channel.field == "detuning_gamma" else "saturation_parameter"
            command=HardwareCommand(f"cmd_{raw_count:05d}",channel.channel_id,channel.field,requested_t,t-latency,t,latency,t-requested_t,ideal,quantized,units,resolution,ClockRoundingMode.NEAREST_TIES_TO_EVEN.value if resolution else "NONE",quantized-ideal,associated.event_id if associated else None,f"atomic_{associated.event_id}" if associated and associated.atomic else None,continuous)
            if last is None or quantized!=last or associated is not None:
                raw.append(command); last=quantized
    commands=tuple(sorted(raw,key=lambda item:(item.actual_effective_time_s,item.channel_id)))
    # Hard constraints are diagnostic only; values are never clipped or stretched.
    for channel_id in sorted(channel_ids):
        capability=capabilities[channel_id]; rows=[item for item in commands if item.channel_id==channel_id]
        for command in rows:
            if not math.isfinite(command.quantized_value): violations.append(_violation("NONFINITE_COMPILED_VALUE","compiled command is nonfinite",command.quantized_value,None,command.command_id))
            if capability.minimum.knowledge is KnowledgeState.KNOWN and command.quantized_value<float(capability.minimum.value)-1e-14: violations.append(_violation("VALUE_OUTSIDE_RANGE","command below minimum",command.quantized_value,capability.minimum.units,command.command_id))
            if capability.maximum.knowledge is KnowledgeState.KNOWN and command.quantized_value>float(capability.maximum.value)+1e-14: violations.append(_violation("VALUE_OUTSIDE_RANGE","command above maximum",command.quantized_value,capability.maximum.units,command.command_id))
            if capability.allowed_values.knowledge is KnowledgeState.KNOWN and command.quantized_value not in tuple(capability.allowed_values.value):
                violations.append(_violation("VALUE_NOT_IN_ALLOWED_SET","command is not in the explicit allowed-value set",command.quantized_value,capability.allowed_values.units,command.command_id))
            if capability.update_period.knowledge is KnowledgeState.KNOWN:
                try:
                    _align(command.actual_effective_time_s,profile.command_clock.clock_origin_s,float(capability.update_period.value),ClockRoundingMode.REQUIRE_EXACT)
                except ValueError:
                    violations.append(_violation("CHANNEL_UPDATE_PERIOD_VIOLATION","command time is not on the channel capability grid",command.actual_effective_time_s,"s",command.command_id))
        for first,second in zip(rows,rows[1:]):
            dt=second.actual_effective_time_s-first.actual_effective_time_s
            if dt<=0: continue
            rate=abs(second.quantized_value-first.quantized_value)/dt
            if capability.maximum_first_derivative.knowledge is KnowledgeState.KNOWN and rate>float(capability.maximum_first_derivative.value)+1e-12: violations.append(_violation("RATE_VIOLATION","realized first derivative exceeds limit",rate,capability.maximum_first_derivative.units,second.command_id))
            if capability.minimum_dwell_time.knowledge is KnowledgeState.KNOWN and dt<float(capability.minimum_dwell_time.value)-1e-15: violations.append(_violation("DWELL_VIOLATION","command dwell is below minimum",dt,"s",second.command_id))
            if capability.update_period.knowledge is KnowledgeState.KNOWN and dt<float(capability.update_period.value)-1e-15:
                violations.append(_violation("CHANNEL_UPDATE_PERIOD_VIOLATION","successive changed commands are closer than the channel update period",dt,"s",second.command_id))
            if profile.command_clock.minimum_command_separation.knowledge is KnowledgeState.KNOWN and dt<float(profile.command_clock.minimum_command_separation.value)-1e-15:
                violations.append(_violation("COMMAND_SEPARATION_VIOLATION","effective commands violate the declared minimum separation",dt,"s",second.command_id))
            if capability.field == "saturation":
                if first.quantized_value <= 0 < second.quantized_value and capability.activation_restriction is ActivationRestriction.FORBIDDEN:
                    violations.append(_violation("ACTIVATION_RESTRICTION_VIOLATION","saturation activation is forbidden",(first.quantized_value,second.quantized_value),"saturation_parameter",second.command_id))
                if first.quantized_value > 0 >= second.quantized_value and capability.deactivation_restriction is ActivationRestriction.FORBIDDEN:
                    violations.append(_violation("DEACTIVATION_RESTRICTION_VIOLATION","saturation deactivation is forbidden",(first.quantized_value,second.quantized_value),"saturation_parameter",second.command_id))
        for a,b,c in zip(rows,rows[1:],rows[2:]):
            dt1=b.actual_effective_time_s-a.actual_effective_time_s; dt2=c.actual_effective_time_s-b.actual_effective_time_s
            if dt1>0 and dt2>0:
                second=abs((c.quantized_value-b.quantized_value)/dt2-(b.quantized_value-a.quantized_value)/dt1)/((dt1+dt2)/2)
                if capability.maximum_second_difference.knowledge is KnowledgeState.KNOWN and second>float(capability.maximum_second_difference.value)+1e-12: violations.append(_violation("SECOND_DIFFERENCE_VIOLATION","realized second finite difference exceeds limit",second,capability.maximum_second_difference.units,c.command_id))
    # ABI affine-derived ownership is checked on the realized command values,
    # after quantization.  A mismatch fails rather than silently turning a
    # derived channel into independent hardware control.
    for channel in spec.control_channels:
        if channel.relationship is not ChannelRelationship.AFFINE_DERIVED:
            continue
        derived_rows=[item for item in commands if item.channel_id == channel.channel_id]
        source_rows=[item for item in commands if item.channel_id == channel.source_channel_id]
        for derived in derived_rows:
            eligible=[item for item in source_rows if item.actual_effective_time_s <= derived.actual_effective_time_s]
            if not eligible:
                violations.append(_violation("DERIVED_CHANNEL_INCONSISTENCY","derived command has no effective source command",derived.quantized_value,derived.units,derived.command_id))
                continue
            source=eligible[-1]
            expected=source.quantized_value*float(channel.affine_scale)+float(channel.affine_offset)
            if not math.isclose(derived.quantized_value,expected,rel_tol=0.0,abs_tol=1e-14):
                violations.append(_violation("DERIVED_CHANNEL_INCONSISTENCY","quantized derived value no longer equals its declared affine source transform",(derived.quantized_value,expected),derived.units,derived.command_id))
    if profile.aggregate_saturation_budget.knowledge is KnowledgeState.KNOWN:
        channel_by_id={channel.channel_id:channel for channel in spec.control_channels}
        for t in sorted({request.start_time_s,request.end_time_s,*[item.actual_effective_time_s for item in commands]}):
            mapped=t
            if events:
                event=events[0]
                if event.realized_time_s != event.requested_time_s:
                    mapped=min(t,math.nextafter(event.requested_time_s,-math.inf)) if t<event.realized_time_s else event.requested_time_s+(t-event.realized_time_s)
            state=policy.sample(mapped); components={item.component_id:item for item in state.components}; values=dict(initial)
            for command in commands:
                if command.actual_effective_time_s<=t: values[command.channel_id]=command.quantized_value
            for channel_id,value in values.items():
                if channel_id not in channel_by_id: continue
                for target in channel_by_id[channel_id].targets:
                    if target.segment_id==state.segment_id and target.field=="saturation": components[target.component_id]=replace(components[target.component_id],saturation=value)
            total=sum(item.saturation for item in components.values())
            if total>float(profile.aggregate_saturation_budget.value)+1e-14:
                violations.append(_violation("AGGREGATE_SATURATION_BUDGET_VIOLATION","abstract aggregate saturation exceeds its declared budget",total,profile.aggregate_saturation_budget.units,None))
    if violations:
        status=CompilationStatus.COMPILATION_INFEASIBLE
    elif request.mode is CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE:
        status=CompilationStatus.COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE
    elif continuous and request.mode is CompilationMode.EXACT_ONLY:
        status=CompilationStatus.COMPILED_EXACT
    elif request.mode is CompilationMode.EXACT_ONLY:
        status=CompilationStatus.COMPILATION_INFEASIBLE; violations.append(_violation("SAMPLING_APPROXIMATION_FORBIDDEN","finite ZOH cannot exactly represent nonconstant continuous channels",period,"s"))
    else: status=CompilationStatus.COMPILED_APPROXIMATE
    # Provisional object first, then use evaluator for deterministic metrics.
    placeholder=ScheduleHashes(profile_hash,compilation_request_hash(request),control_policy_hashes(spec).policy_specification,"","","")
    compiled=CompiledControlSchedule(COMPILED_SCHEDULE_SCHEMA_VERSION,"run014-compiler-v1",PIPELINE,status,policy_hash,profile_hash,request,commands,tuple(events),initial,tuple(violations),(),raw_count,len(commands),len({item.atomic_group_id for item in commands if item.atomic_group_id}),max([abs(event.displacement_s) for event in events] or [0.0]),not unknown,profile.hardware_validation_status.value,False,placeholder)
    realized=RealizedControlSchedule(spec,compiled) if status not in {CompilationStatus.COMPILATION_INVALID,CompilationStatus.COMPILATION_INFEASIBLE} else None
    metrics=[]
    for channel in spec.control_channels:
        rows=[item for item in commands if item.channel_id==channel.channel_id]; errors=[]
        if realized:
            sample_times=sorted(set(times+[(a+b)/2 for a,b in zip(times,times[1:])]))
            for t in sample_times:
                target=channel.targets[0]; ideal=_channel_value(policy,channel,t); state=realized.sample(t); actual=float(getattr(state.components[target.component_id-1],target.field)); errors.append(actual-ideal)
        qerrors=[row.quantization_error for row in rows]; rates=[abs(b.quantized_value-a.quantized_value)/(b.actual_effective_time_s-a.actual_effective_time_s) for a,b in zip(rows,rows[1:]) if b.actual_effective_time_s>a.actual_effective_time_s]
        second=[]
        for a,b,c in zip(rows,rows[1:],rows[2:]):
            d1=b.actual_effective_time_s-a.actual_effective_time_s; d2=c.actual_effective_time_s-b.actual_effective_time_s
            if d1>0 and d2>0: second.append(abs((c.quantized_value-b.quantized_value)/d2-(b.quantized_value-a.quantized_value)/d1)/((d1+d2)/2))
        metrics.append(CompilationMetric(channel.channel_id,channel.field,max(map(abs,errors),default=0.0),float(np.sqrt(np.mean(np.square(errors)))) if errors else 0.0,abs(errors[-1]) if errors else 0.0,max(map(abs,errors),default=0.0),max(rates,default=0.0),max(second,default=0.0),max(map(abs,qerrors),default=0.0),float(np.sqrt(np.mean(np.square(qerrors)))) if qerrors else 0.0,len(times),len(rows)))
    command_hash=_hash(commands); realized_hash=_hash({"mode":request.reconstruction_mode,"commands":commands,"events":events,"initial":initial,"horizon":[request.start_time_s,request.end_time_s]})
    hashes=ScheduleHashes(profile_hash,compilation_request_hash(request),control_policy_hashes(spec).policy_specification,command_hash,realized_hash,"")
    full=_hash({"schema":COMPILED_SCHEDULE_SCHEMA_VERSION,"compiler":"run014-compiler-v1","hashes":hashes,"status":status})
    hashes=replace(hashes,complete_compiled_package=full)
    hardware_claim=status in {CompilationStatus.COMPILED_EXACT,CompilationStatus.COMPILED_APPROXIMATE} and profile.hardware_validation_status is HardwareValidationStatus.HARDWARE_VALIDATED and not unknown
    compiled=replace(compiled,metrics=tuple(metrics),hashes=hashes,hardware_executable_claim_valid=hardware_claim)
    if status is CompilationStatus.COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE and hardware_claim: raise RuntimeError("partial profile escaped hardware-executability boundary")
    realized=RealizedControlSchedule(spec,compiled) if realized else None
    return compiled,realized
