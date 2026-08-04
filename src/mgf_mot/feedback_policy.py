"""Run 016 model-independent feedback, observation, session, and replay layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np

from .apparatus_constraints import ApparatusConstraintSet, KnowledgeState, apparatus_profile_hash
from .control_policy_abi import (
    ChannelRelationship, ComponentControlState, ControlPolicy,
    ControlPolicySpec, EventBoundaryRule, PolicyEvent, PolicyState,
)
from .control_schedule_compiler import (
    CompilationMode, CompilationRequest, CompilationStatus,
    CompiledControlSchedule, InitialStateMode, ReconstructionMode,
    compile_control_schedule,
)
from .open_loop_policy_families import (
    OpenLoopFamilyPolicy, OpenLoopPolicyFamilySpec, compile_family_policy,
    family_hashes,
)


OBSERVATION_SCHEMA_VERSION="mgf-mot-observation-spec-v1"
CONTROLLER_SCHEMA_VERSION="mgf-mot-feedback-controller-v1"
ACTION_SCHEMA_VERSION="mgf-mot-feedback-action-spec-v1"
SESSION_SCHEMA_VERSION="mgf-mot-feedback-session-v1"
REPLAY_SCHEMA_VERSION="mgf-mot-feedback-replay-v1"
FEEDBACK_IMPLEMENTATION_VERSION="run016-feedback-v1"
EVENT_ORDERING_VERSION="run016-effective_plant_sample_arrival_controller_issue_checkpoint-v1"
RUN016_LABEL="MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_016_FEEDBACK_POLICY_INTERFACE_ONLY"
ORACLE_LABELS=("FULL_STATE_ORACLE","SIMULATION_ONLY","NOT_APPARATUS_REALIZABLE")
SYNTHETIC_PLANT_LABELS=("SYNTHETIC_TEST_FIXTURE","MODEL_INDEPENDENT","NOT_MGF_PHYSICS")


class FeedbackError(ValueError):pass
class ObservationAccessClass(str,Enum):
    FULL_STATE_ORACLE="FULL_STATE_ORACLE";PARTIAL_STATE_SYNTHETIC="PARTIAL_STATE_SYNTHETIC";SENSOR_MODEL_SYNTHETIC="SENSOR_MODEL_SYNTHETIC";SOURCE_SUPPORTED_SENSOR_MODEL="SOURCE_SUPPORTED_SENSOR_MODEL"
class ObservationStatus(str,Enum):VALID="VALID";MISSING="MISSING";STALE="STALE";INVALID="INVALID";SATURATED="SATURATED"
class TransformId(str,Enum):
    IDENTITY_FIELD="IDENTITY_FIELD";SELECT_FIELDS="SELECT_FIELDS";AFFINE_TRANSFORM="AFFINE_TRANSFORM";LINEAR_PROJECTION="LINEAR_PROJECTION";NORM="NORM";WINDOWED_MEAN="WINDOWED_MEAN";WINDOWED_SUM="WINDOWED_SUM";FINITE_DIFFERENCE="FINITE_DIFFERENCE";QUANTIZE="QUANTIZE";CLIP="CLIP";DELAYED_SAMPLE="DELAYED_SAMPLE";CONSTANT_CHANNEL="CONSTANT_CHANNEL"
class NoiseModelId(str,Enum):NONE="NONE";ADDITIVE_GAUSSIAN="ADDITIVE_GAUSSIAN";UNIFORM_QUANTIZATION="UNIFORM_QUANTIZATION";DETERMINISTIC_BIAS="DETERMINISTIC_BIAS";DROPOUT_PATTERN="DROPOUT_PATTERN"
class MissingStrategy(str,Enum):REJECT_STEP="REJECT_STEP";HOLD_LAST_ACTION="HOLD_LAST_ACTION";USE_LAST_VALID_OBSERVATION="USE_LAST_VALID_OBSERVATION";USE_DECLARED_FALLBACK_ACTION="USE_DECLARED_FALLBACK_ACTION"
class ControllerFamily(str,Enum):NO_OP_CONTROLLER="NO_OP_CONTROLLER";BASELINE_REPLAY_CONTROLLER="BASELINE_REPLAY_CONTROLLER";SCRIPTED_SEQUENCE_CONTROLLER="SCRIPTED_SEQUENCE_CONTROLLER";BOUNDED_AFFINE_CONTROLLER="BOUNDED_AFFINE_CONTROLLER";HOLD_LAST_CONTROLLER="HOLD_LAST_CONTROLLER"
class ControllerStatefulness(str,Enum):STATELESS="STATELESS";EXPLICIT_MEMORY="EXPLICIT_MEMORY"
class ActionUpdateMode(str,Enum):COMPLETE="COMPLETE";PARTIAL_HOLD_UNSPECIFIED="PARTIAL_HOLD_UNSPECIFIED";HOLD_NO_CHANGE="HOLD_NO_CHANGE"
class ActionValidity(str,Enum):VALID="VALID";INVALID="INVALID"
class SchedulingMode(str,Enum):OBSERVATION_DRIVEN="OBSERVATION_DRIVEN";FIXED_CONTROL_CLOCK="FIXED_CONTROL_CLOCK";SCRIPTED_CONTROLLER_TIMES="SCRIPTED_CONTROLLER_TIMES"
class InfeasibleActionStrategy(str,Enum):TERMINATE_SESSION="TERMINATE_SESSION";REJECT_AND_HOLD_PREVIOUS="REJECT_AND_HOLD_PREVIOUS";USE_DECLARED_SAFE_ACTION="USE_DECLARED_SAFE_ACTION";RECORD_ONLY_DIAGNOSTIC="RECORD_ONLY_DIAGNOSTIC"
class PlantFamily(str,Enum):STATIC_PLANT="STATIC_PLANT";DISCRETE_INTEGRATOR_PLANT="DISCRETE_INTEGRATOR_PLANT";FIRST_ORDER_LAG_PLANT="FIRST_ORDER_LAG_PLANT"


@dataclass(frozen=True)
class FeedbackProvenance:
    provenance_class:str;source_description:str;source_path_or_citation:str|None;source_hash:str|None;interpretation_notes:str;labels:tuple[str,...]
@dataclass(frozen=True)
class HiddenPlantState:
    timestamp_s:float;values:Mapping[str,float];synthetic_fixture_labels:tuple[str,...]=SYNTHETIC_PLANT_LABELS
@dataclass(frozen=True)
class NoiseModelSpec:
    model_id:NoiseModelId;version:str;parameters:Mapping[str,Any];units:str;seed:int|None;generator_algorithm:str;provenance:FeedbackProvenance;stream_sharing_id:str|None=None
@dataclass(frozen=True)
class ObservationChannelSpec:
    channel_id:str;name:str;description:str;units:str;shape:tuple[int,...];dtype:str;meaning:str;access_class:ObservationAccessClass;source_hidden_state_fields:tuple[str,...];input_channel_ids:tuple[str,...];transformation_id:TransformId;transformation_version:str;transformation_parameters:Mapping[str,Any];sampling_period_s:float;sensor_latency_s:float;noise_model:NoiseModelSpec;missing_data_model:Mapping[str,Any];quantization_step:float|None;clip_min:float|None;clip_max:float|None;provenance:FeedbackProvenance
@dataclass(frozen=True)
class ObservationSpec:
    schema_version:str;spec_id:str;access_class:ObservationAccessClass;channels:tuple[ObservationChannelSpec,...];fixed_period_s:float|None;explicit_sample_times_s:tuple[float,...];communication_latency_s:float;deterministic_jitter_s:tuple[float,...];labels:tuple[str,...];provenance:FeedbackProvenance
@dataclass(frozen=True)
class Observation:
    channel_id:str;value:tuple[float,...]|None;units:str;status:ObservationStatus;source_state_timestamp_s:float;sensor_sample_time_s:float;availability_time_s:float;noise_realization:tuple[float,...]|None;missing_reason:str|None;saturated:bool
@dataclass(frozen=True)
class ObservationPacket:
    packet_id:str;observation_spec_hash:str;source_state_timestamp_s:float;sensor_sample_time_s:float;observation_availability_time_s:float;controller_receive_time_s:float;observations:tuple[Observation,...];status:ObservationStatus;labels:tuple[str,...]
@dataclass(frozen=True)
class MemoryFieldSpec:
    name:str;dtype:str;shape:tuple[int,...];units:str|None;initial_value:Any;update_semantics:str
@dataclass(frozen=True)
class ControllerMemory:
    schema_hash:str;values:Mapping[str,Any]
@dataclass(frozen=True)
class ActionChannelValue:
    channel_id:str;value:float;units:str
@dataclass(frozen=True)
class ActionChannelSpec:
    channel_id:str;units:str;required_in_complete_action:bool;minimum:float|None;maximum:float|None;ownership:str
@dataclass(frozen=True)
class ActionSpec:
    schema_version:str;action_spec_id:str;channels:tuple[ActionChannelSpec,...];allow_partial_updates:bool;unspecified_channel_behavior:str;allow_hold_instruction:bool;provenance:FeedbackProvenance
@dataclass(frozen=True)
class ControlAction:
    action_id:str;action_timestamp_s:float;requested_effective_time_s:float;channel_values:tuple[ActionChannelValue,...];update_mode:ActionUpdateMode;action_source:str;controller_step_id:str;validity:ActionValidity;fallback_origin:str|None;provenance:FeedbackProvenance
@dataclass(frozen=True)
class ControllerSpec:
    schema_version:str;controller_id:str;controller_family:ControllerFamily;controller_version:str;statefulness:ControllerStatefulness;observation_spec_hash:str;action_spec_hash:str;memory_schema:tuple[MemoryFieldSpec,...];timing_assumptions:Mapping[str,Any];fallback_rules:Mapping[str,MissingStrategy];parameters:Mapping[str,Any];provenance:FeedbackProvenance;simulation_only:bool;apparatus_eligible:bool
@dataclass(frozen=True)
class FeedbackTimingSpec:
    observation_period_s:float;control_period_s:float;controller_compute_latency_s:float;sensor_latency_s:float;communication_latency_s:float;apparatus_command_latency_s:float;synchronous_clocks:bool;clock_alignment_rule:str;initial_time_s:float;end_time_s:float;pre_roll_s:float;max_observation_age_s:float;scheduling_mode:SchedulingMode;scripted_controller_times_s:tuple[float,...];event_ordering_version:str=EVENT_ORDERING_VERSION
@dataclass(frozen=True)
class SyntheticPlantSpec:
    schema_version:str;plant_id:str;family:PlantFamily;state_fields:tuple[str,...];input_channel_ids:tuple[str,...];initial_values:tuple[float,...];update_period_s:float;parameters:Mapping[str,Any];provenance:FeedbackProvenance;labels:tuple[str,...]=SYNTHETIC_PLANT_LABELS
@dataclass(frozen=True)
class FeedbackSessionSpec:
    schema_version:str;session_id:str;observation_spec:ObservationSpec;action_spec:ActionSpec;controller_spec:ControllerSpec;timing_spec:FeedbackTimingSpec;plant_spec:SyntheticPlantSpec;abi_spec:ControlPolicySpec;apparatus_profile:ApparatusConstraintSet;infeasible_action_strategy:InfeasibleActionStrategy;safe_action:ControlAction|None;baseline_family_spec:OpenLoopPolicyFamilySpec|None;provenance:FeedbackProvenance
@dataclass(frozen=True)
class FeedbackValidationIssue:
    code:str;severity:str;field_path:str;message:str;offending_value:Any;suggested_correction:str|None
@dataclass(frozen=True)
class FeedbackValidationResult:
    issues:tuple[FeedbackValidationIssue,...]
    @property
    def errors(self):return tuple(item for item in self.issues if item.severity=="ERROR")
    @property
    def valid(self):return not self.errors
@dataclass(frozen=True)
class FeedbackStepRecord:
    step_id:str;event_index:int;plant_state_hash:str;synthetic_hidden_state:HiddenPlantState|None;observation_packet:ObservationPacket;controller_receive_time_s:float;memory_before:ControllerMemory;action:ControlAction|None;memory_after:ControllerMemory;action_validation:FeedbackValidationResult;compilation_status:str|None;issued_commands:tuple[Any,...];effective_commands:tuple[Any,...];realized_control_state:PolicyState|None;fallback_decision:str|None;validation_issues:tuple[FeedbackValidationIssue,...];record_hash:str
@dataclass(frozen=True)
class FeedbackMetrics:
    packet_count:int;valid_count:int;missing_count:int;stale_count:int;latency_min_s:float;latency_max_s:float;channel_saturation_count:int;controller_step_count:int;action_count:int;fallback_count:int;invalid_action_count:int;memory_state_size:int;deterministic_replay_status:str;exact_compilation_count:int;approximate_compilation_count:int;infeasible_action_count:int;command_count:int;maximum_action_to_effect_latency_s:float;quantization_by_channel:Mapping[str,Mapping[str,float]]
@dataclass(frozen=True)
class FeedbackSessionResult:
    schema_version:str;session_hash:str;spec_hashes:Mapping[str,str];event_order:tuple[str,...];steps:tuple[FeedbackStepRecord,...];accepted_actions:tuple[ControlAction,...];observation_stream_hash:str;action_stream_hash:str;command_stream_hash:str;final_plant_state:HiddenPlantState;final_memory:ControllerMemory;final_compilation:CompiledControlSchedule|None;metrics:FeedbackMetrics;hardware_executable_claim_valid:bool;labels:tuple[str,...];replay_hash:str
@dataclass(frozen=True)
class FeedbackReplay:
    schema_version:str;mode:str;source_session_hash:str;spec_hashes:Mapping[str,str];observation_stream_hash:str;action_stream_hash:str;command_stream_hash:str;replay_equal:bool;replay_package_hash:str;labels:tuple[str,...]


TRANSFORM_REGISTRY={item.value:"1" for item in TransformId};NOISE_REGISTRY={item.value:"1" for item in NoiseModelId};CONTROLLER_REGISTRY={item.value:"1" for item in ControllerFamily}


def _plain(value:Any)->Any:
    if isinstance(value,Enum):return value.value
    if is_dataclass(value):return {key:_plain(item) for key,item in asdict(value).items()}
    if isinstance(value,Mapping):return {str(key):_plain(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):return [_plain(item) for item in value]
    if callable(value):raise FeedbackError("ARBITRARY_EXECUTABLE_CONTENT")
    return value
def canonical_feedback_json(value:Any)->str:return json.dumps(_plain(value),sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
def feedback_hash(value:Any)->str:return sha256(canonical_feedback_json(value).encode()).hexdigest()
def serialize_feedback(value:Any,pretty:bool=False)->str:return json.dumps(_plain(value),sort_keys=True,indent=2 if pretty else None,separators=None if pretty else (",",":"),ensure_ascii=False,allow_nan=False)+("\n" if pretty else "")
def _issue(code,path,message,value=None,correction=None):return FeedbackValidationIssue(code,"ERROR",path,message,value,correction)
def _finite(value):return isinstance(value,(int,float)) and math.isfinite(float(value))
def _reject_executable(value,path="$",issues=None):
    issues=[] if issues is None else issues
    if callable(value):issues.append(_issue("ARBITRARY_EXECUTABLE_CONTENT",path,"callables are forbidden",repr(value)))
    elif is_dataclass(value):
        for name in value.__dataclass_fields__:_reject_executable(getattr(value,name),f"{path}.{name}",issues)
    elif isinstance(value,Mapping):
        for key,item in value.items():
            if str(key).lower() in {"callable","expression","lambda","exec","eval","python_code","module_path"}:issues.append(_issue("ARBITRARY_EXECUTABLE_CONTENT",f"{path}.{key}","executable payload fields are forbidden",item))
            _reject_executable(item,f"{path}.{key}",issues)
    elif isinstance(value,(tuple,list)):
        for i,item in enumerate(value):_reject_executable(item,f"{path}[{i}]",issues)
    return issues


def validate_observation_spec(spec:ObservationSpec)->FeedbackValidationResult:
    issues=_reject_executable(spec)
    if spec.schema_version!=OBSERVATION_SCHEMA_VERSION:issues.append(_issue("UNKNOWN_OBSERVATION_SCHEMA","$.schema_version","unknown observation schema",spec.schema_version))
    if spec.access_class is ObservationAccessClass.SOURCE_SUPPORTED_SENSOR_MODEL:issues.append(_issue("SOURCE_SUPPORTED_SENSOR_MODEL_UNAVAILABLE","$.access_class","Run 016 has no source-supported sensor model",spec.access_class.value))
    if spec.access_class is ObservationAccessClass.FULL_STATE_ORACLE and not set(ORACLE_LABELS).issubset(spec.labels):issues.append(_issue("MISSING_ORACLE_LABELS","$.labels","oracle observations require all mandatory labels",spec.labels))
    ids=[item.channel_id for item in spec.channels]
    if len(ids)!=len(set(ids)):issues.append(_issue("DUPLICATE_OBSERVATION_CHANNEL","$.channels","observation channel IDs must be unique",ids))
    graph={item.channel_id:set(item.input_channel_ids) for item in spec.channels}
    for index,item in enumerate(spec.channels):
        path=f"$.channels[{index}]"
        if not item.units:issues.append(_issue("MISSING_UNITS",path+".units","observation units are mandatory",item.units))
        if item.transformation_id.value not in TRANSFORM_REGISTRY or item.transformation_version!=TRANSFORM_REGISTRY.get(item.transformation_id.value):issues.append(_issue("INVALID_OBSERVATION_TRANSFORMATION",path,"unknown transform/version",(item.transformation_id,item.transformation_version)))
        if item.noise_model.model_id.value not in NOISE_REGISTRY:issues.append(_issue("INVALID_NOISE_PARAMETER",path+".noise_model","unknown noise model",item.noise_model.model_id))
        if item.noise_model.model_id is NoiseModelId.ADDITIVE_GAUSSIAN and (not _finite(item.noise_model.parameters.get("standard_deviation")) or item.noise_model.parameters["standard_deviation"]<0 or item.noise_model.seed is None):issues.append(_issue("INVALID_NOISE_PARAMETER",path+".noise_model","Gaussian noise requires nonnegative standard deviation and explicit seed",item.noise_model.parameters))
        if item.noise_model.model_id is NoiseModelId.UNIFORM_QUANTIZATION and (not _finite(item.noise_model.parameters.get("resolution")) or item.noise_model.parameters["resolution"]<=0):issues.append(_issue("INVALID_NOISE_PARAMETER",path+".noise_model","quantization resolution must be positive",item.noise_model.parameters))
        if item.noise_model.generator_algorithm not in {"NONE","NUMPY_PCG64_V1","DETERMINISTIC_ALGEBRA_V1"}:issues.append(_issue("UNCONTROLLED_GLOBAL_RNG_USE",path+".noise_model.generator_algorithm","generator must be closed and local",item.noise_model.generator_algorithm))
        if item.sampling_period_s<=0 or item.sensor_latency_s<0:issues.append(_issue("INVALID_OBSERVATION_TIMING",path,"sampling period must be positive and latency nonnegative",(item.sampling_period_s,item.sensor_latency_s)))
        if any(dep not in graph for dep in item.input_channel_ids):issues.append(_issue("INVALID_OBSERVATION_TRANSFORMATION",path+".input_channel_ids","transform input channel is undeclared",item.input_channel_ids))
    visiting=set();visited=set()
    def visit(node):
        if node in visiting:issues.append(_issue("CYCLIC_TRANSFORMATION_GRAPH","$.channels","observation transform graph is cyclic",node));return
        if node in visited:return
        visiting.add(node)
        for dep in graph.get(node,()):visit(dep)
        visiting.remove(node);visited.add(node)
    for node in graph:visit(node)
    if spec.communication_latency_s<0:issues.append(_issue("INVALID_OBSERVATION_TIMING","$.communication_latency_s","communication latency cannot be negative",spec.communication_latency_s))
    if spec.explicit_sample_times_s and (any(not _finite(value) for value in spec.explicit_sample_times_s) or any(b<=a for a,b in zip(spec.explicit_sample_times_s,spec.explicit_sample_times_s[1:]))):issues.append(_issue("INVALID_OBSERVATION_TIMING","$.explicit_sample_times_s","explicit sample times must be finite and strictly increasing",spec.explicit_sample_times_s))
    return FeedbackValidationResult(tuple(issues))


def _as_array(value:Any)->np.ndarray:return np.asarray(value,dtype=float).reshape(-1)
def _transform(channel:ObservationChannelSpec,state:HiddenPlantState,resolved:Mapping[str,np.ndarray],history:Sequence[HiddenPlantState])->np.ndarray:
    p=channel.transformation_parameters;tid=channel.transformation_id
    if tid is TransformId.IDENTITY_FIELD:return _as_array([state.values[channel.source_hidden_state_fields[0]]])
    if tid is TransformId.SELECT_FIELDS:return _as_array([state.values[name] for name in channel.source_hidden_state_fields])
    inputs=np.concatenate([resolved[name] for name in channel.input_channel_ids]) if channel.input_channel_ids else np.array([],float)
    if tid is TransformId.AFFINE_TRANSFORM:return _as_array(p["scale"])*inputs+_as_array(p["offset"])
    if tid is TransformId.LINEAR_PROJECTION:return np.asarray(p["matrix"],float)@inputs+_as_array(p["offset"])
    if tid is TransformId.NORM:return _as_array([float(np.linalg.norm(inputs,ord=p.get("order",2)))])
    if tid in {TransformId.WINDOWED_MEAN,TransformId.WINDOWED_SUM}:
        fields=channel.source_hidden_state_fields;window=int(p["window_length"]);rows=np.array([[item.values[name] for name in fields] for item in history[-window:]],float)
        return rows.mean(axis=0) if tid is TransformId.WINDOWED_MEAN else rows.sum(axis=0)
    if tid is TransformId.FINITE_DIFFERENCE:
        if len(history)<2:return np.full(len(channel.source_hidden_state_fields),np.nan)
        a,b=history[-2:];return np.array([(b.values[name]-a.values[name])/(b.timestamp_s-a.timestamp_s) for name in channel.source_hidden_state_fields])
    if tid is TransformId.QUANTIZE:
        step=float(p["resolution"]);return np.round(inputs/step)*step
    if tid is TransformId.CLIP:return np.clip(inputs,float(p["minimum"]),float(p["maximum"]))
    if tid is TransformId.DELAYED_SAMPLE:
        index=max(0,len(history)-1-int(p["delay_samples"]));sample=history[index];return np.array([sample.values[name] for name in channel.source_hidden_state_fields])
    if tid is TransformId.CONSTANT_CHANNEL:return _as_array(p["value"])
    raise FeedbackError("INVALID_OBSERVATION_TRANSFORMATION")


def _noise(channel:ObservationChannelSpec,value:np.ndarray,sample_index:int)->tuple[np.ndarray|None,np.ndarray|None,str|None]:
    model=channel.noise_model;mid=model.model_id
    if mid is NoiseModelId.NONE:return value,np.zeros_like(value),None
    if mid is NoiseModelId.DROPOUT_PATTERN:
        if sample_index in tuple(model.parameters["missing_indices"]):return None,None,"declared deterministic dropout pattern"
        return value,np.zeros_like(value),None
    if mid is NoiseModelId.DETERMINISTIC_BIAS:
        realization=np.broadcast_to(_as_array(model.parameters["bias"]),value.shape);return value+realization,realization,None
    if mid is NoiseModelId.UNIFORM_QUANTIZATION:
        step=float(model.parameters["resolution"]);noisy=np.round(value/step)*step;return noisy,noisy-value,None
    if mid is NoiseModelId.ADDITIVE_GAUSSIAN:
        stream=model.stream_sharing_id or channel.channel_id;seed_bytes=sha256(f"{model.seed}|{stream}|{sample_index}|NUMPY_PCG64_V1".encode()).digest();seed=int.from_bytes(seed_bytes[:16],"big");rng=np.random.Generator(np.random.PCG64(seed));realization=rng.normal(0,float(model.parameters["standard_deviation"]),size=value.shape);return value+realization,realization,None
    raise FeedbackError("INVALID_NOISE_PARAMETER")


class ObservationModel:
    def __init__(self,spec:ObservationSpec):
        result=validate_observation_spec(spec)
        if not result.valid:raise FeedbackError("invalid observation specification: "+"; ".join(item.message for item in result.errors))
        self.spec=spec;self.hash=feedback_hash(spec)
    def sample(self,state:HiddenPlantState,sample_time_s:float,sample_index:int,history:Sequence[HiddenPlantState])->ObservationPacket:
        if not isinstance(state,HiddenPlantState):raise TypeError("observation model accepts HiddenPlantState only")
        if sample_time_s<state.timestamp_s-1e-15:raise FeedbackError("INVALID_PACKET_TIMESTAMP: sample precedes supplied state")
        resolved={};missing_resolved=set();rows=[];pending=list(self.spec.channels)
        while pending:
            progress=False
            for channel in pending[:]:
                if any(dep not in resolved for dep in channel.input_channel_ids):continue
                if any(dep in missing_resolved for dep in channel.input_channel_ids):value=None;realization=None;missing="upstream observation is explicitly missing"
                else:
                    raw=_transform(channel,state,resolved,history);value,realization,missing=_noise(channel,raw,sample_index)
                status=ObservationStatus.MISSING if value is None else (ObservationStatus.INVALID if not np.all(np.isfinite(value)) else ObservationStatus.VALID);saturated=False
                if value is not None and channel.quantization_step is not None:value=np.round(value/channel.quantization_step)*channel.quantization_step
                if value is not None and (channel.clip_min is not None or channel.clip_max is not None):
                    clipped=np.clip(value,-np.inf if channel.clip_min is None else channel.clip_min,np.inf if channel.clip_max is None else channel.clip_max);saturated=not np.array_equal(clipped,value);value=clipped;status=ObservationStatus.SATURATED if saturated else status
                availability=sample_time_s+channel.sensor_latency_s;resolved[channel.channel_id]=np.array([]) if value is None else value
                if value is None:missing_resolved.add(channel.channel_id)
                rows.append(Observation(channel.channel_id,None if value is None else tuple(float(x) for x in value),channel.units,status,state.timestamp_s,sample_time_s,availability,None if realization is None else tuple(float(x) for x in realization),missing,saturated));pending.remove(channel);progress=True
            if not progress:raise FeedbackError("CYCLIC_TRANSFORMATION_GRAPH")
        availability=max((item.availability_time_s for item in rows),default=sample_time_s);receive=availability+self.spec.communication_latency_s+(self.spec.deterministic_jitter_s[sample_index%len(self.spec.deterministic_jitter_s)] if self.spec.deterministic_jitter_s else 0.0)
        status=ObservationStatus.MISSING if any(item.status is ObservationStatus.MISSING for item in rows) else (ObservationStatus.INVALID if any(item.status is ObservationStatus.INVALID for item in rows) else (ObservationStatus.SATURATED if any(item.saturated for item in rows) else ObservationStatus.VALID))
        labels=tuple(dict.fromkeys((*self.spec.labels,*(ORACLE_LABELS if self.spec.access_class is ObservationAccessClass.FULL_STATE_ORACLE else ()))))
        return ObservationPacket(f"packet_{sample_index:05d}",self.hash,state.timestamp_s,sample_time_s,availability,receive,tuple(rows),status,labels)


def validate_controller_spec(spec:ControllerSpec)->FeedbackValidationResult:
    issues=_reject_executable(spec)
    if spec.schema_version!=CONTROLLER_SCHEMA_VERSION:issues.append(_issue("UNKNOWN_CONTROLLER_SCHEMA","$.schema_version","unknown controller schema",spec.schema_version))
    if spec.controller_family.value not in CONTROLLER_REGISTRY:issues.append(_issue("UNKNOWN_CONTROLLER_FAMILY","$.controller_family","unknown controller family",spec.controller_family))
    names=[item.name for item in spec.memory_schema]
    if len(names)!=len(set(names)):issues.append(_issue("INVALID_MEMORY_SCHEMA","$.memory_schema","memory field names must be unique",names))
    for item in spec.memory_schema:
        try:canonical_feedback_json(item.initial_value)
        except Exception:issues.append(_issue("NONSERIALIZABLE_MEMORY","$.memory_schema","memory initial value is not serializable",item.name))
    if spec.statefulness is ControllerStatefulness.STATELESS and spec.memory_schema:issues.append(_issue("INVALID_MEMORY_SCHEMA","$.memory_schema","stateless controllers require an explicitly empty memory schema",names))
    required={status.value for status in ObservationStatus}
    if set(spec.fallback_rules)!=required:issues.append(_issue("MISSING_FALLBACK_RULE","$.fallback_rules","every observation status requires an explicit behavior",sorted(required-set(spec.fallback_rules))))
    if spec.apparatus_eligible:issues.append(_issue("APPARATUS_ELIGIBILITY_NOT_AUTHORIZED","$.apparatus_eligible","Run 016 cannot mark a controller apparatus eligible",True))
    return FeedbackValidationResult(tuple(issues))
def initial_controller_memory(spec:ControllerSpec)->ControllerMemory:
    schema_hash=feedback_hash(spec.memory_schema);return ControllerMemory(schema_hash,{item.name:item.initial_value for item in spec.memory_schema})


class FeedbackController:
    def __init__(self,spec:ControllerSpec,abi_spec:ControlPolicySpec,baseline_policy:OpenLoopFamilyPolicy|None=None):
        result=validate_controller_spec(spec)
        if not result.valid:raise FeedbackError("invalid controller specification: "+"; ".join(item.message for item in result.errors))
        self.spec=spec;self.abi_spec=abi_spec;self.baseline_policy=baseline_policy;self.channels={item.channel_id:item for item in abi_spec.control_channels}
    def step(self,packet:ObservationPacket,memory:ControllerMemory,step_id:str,execution_time_s:float,requested_time_s:float)->tuple[ControlAction,ControllerMemory]:
        if not isinstance(packet,ObservationPacket):raise TypeError("controller.step accepts ObservationPacket only; hidden plant state is structurally forbidden")
        if not isinstance(memory,ControllerMemory):raise TypeError("controller memory must be passed explicitly")
        index=int(memory.values.get("step_index",0));family=self.spec.controller_family;values=[]
        if family is ControllerFamily.BASELINE_REPLAY_CONTROLLER:
            if self.baseline_policy is None:raise FeedbackError("ambiguous baseline reference")
            state=self.baseline_policy.sample(requested_time_s)
            for channel in self.abi_spec.control_channels:
                if channel.relationship is ChannelRelationship.AFFINE_DERIVED:continue
                if not any(target.segment_id==state.segment_id for target in channel.targets):continue
                target=channel.targets[0];component=state.components[target.component_id-1];values.append(ActionChannelValue(channel.channel_id,float(getattr(component,target.field)),"Gamma" if target.field=="detuning_gamma" else "saturation_parameter"))
        elif family in {ControllerFamily.NO_OP_CONTROLLER,ControllerFamily.HOLD_LAST_CONTROLLER}:
            values=[ActionChannelValue(row["channel_id"],float(row["value"]),row["units"]) for row in self.spec.parameters.get("fixed_action",())]
        elif family is ControllerFamily.SCRIPTED_SEQUENCE_CONTROLLER:
            sequence=self.spec.parameters["actions"];row=sequence[min(index,len(sequence)-1)];values=[ActionChannelValue(item["channel_id"],float(item["value"]),item["units"]) for item in row]
        elif family is ControllerFamily.BOUNDED_AFFINE_CONTROLLER:
            observed={item.channel_id:item for item in packet.observations};vector=np.concatenate([_as_array(observed[channel_id].value) for channel_id in self.spec.parameters["observation_channel_ids"]]);raw=np.asarray(self.spec.parameters["matrix"],float)@vector+np.asarray(self.spec.parameters["offset"],float);lower=np.asarray(self.spec.parameters["lower"],float);upper=np.asarray(self.spec.parameters["upper"],float)
            if self.spec.parameters["bound_behavior"]=="REJECT" and (np.any(raw<lower) or np.any(raw>upper)):raise FeedbackError("controller action outside declared abstract bounds")
            if self.spec.parameters["bound_behavior"]=="EXPLICIT_CLIP":raw=np.clip(raw,lower,upper)
            for channel_id,value in zip(self.spec.parameters["action_channel_ids"],raw):values.append(ActionChannelValue(channel_id,float(value),"Gamma" if self.channels[channel_id].field=="detuning_gamma" else "saturation_parameter"))
        else:raise FeedbackError("UNKNOWN_CONTROLLER_FAMILY")
        provenance=self.spec.provenance;action=ControlAction(f"action_{step_id}",execution_time_s,requested_time_s,tuple(values),ActionUpdateMode(self.spec.parameters["update_mode"]),family.value,step_id,ActionValidity.VALID,None,provenance)
        new_values=dict(memory.values)
        if "step_index" in new_values:new_values["step_index"]=index+1
        if "last_action_hash" in new_values:new_values["last_action_hash"]=feedback_hash(action)
        return action,ControllerMemory(memory.schema_hash,new_values)


def validate_action_spec(spec:ActionSpec,abi_spec:ControlPolicySpec)->FeedbackValidationResult:
    issues=_reject_executable(spec);abi_channels={item.channel_id:item for item in abi_spec.control_channels};ids=[item.channel_id for item in spec.channels]
    if spec.schema_version!=ACTION_SCHEMA_VERSION:issues.append(_issue("UNKNOWN_ACTION_SCHEMA","$.schema_version","unknown action schema",spec.schema_version))
    if len(ids)!=len(set(ids)):issues.append(_issue("DUPLICATE_CONTROL_OWNERSHIP","$.channels","action channel specifications must be unique",ids))
    for index,item in enumerate(spec.channels):
        if item.channel_id not in abi_channels:issues.append(_issue("UNKNOWN_ACTION_CHANNEL",f"$.channels[{index}]","action specification references an unknown ABI channel",item.channel_id));continue
        expected="Gamma" if abi_channels[item.channel_id].field=="detuning_gamma" else "saturation_parameter"
        if item.units!=expected:issues.append(_issue("ACTION_UNIT_MISMATCH",f"$.channels[{index}].units","action specification units differ from ABI units",(item.units,expected)))
        if item.minimum is not None and item.maximum is not None and item.minimum>item.maximum:issues.append(_issue("INVALID_ACTION_BOUNDS",f"$.channels[{index}]","action minimum exceeds maximum",(item.minimum,item.maximum)))
        if abi_channels[item.channel_id].relationship is ChannelRelationship.AFFINE_DERIVED:issues.append(_issue("INVALID_DERIVED_CHANNEL_UPDATE",f"$.channels[{index}]","derived ABI channels cannot be independently actionable",item.channel_id))
    if spec.unspecified_channel_behavior!="HOLD_PREVIOUS_VALUE":issues.append(_issue("INVALID_PARTIAL_ACTION_SEMANTICS","$.unspecified_channel_behavior","only explicit hold-previous semantics are supported",spec.unspecified_channel_behavior))
    return FeedbackValidationResult(tuple(issues))


def validate_action(action:ControlAction,abi_spec:ControlPolicySpec,observation_packet:ObservationPacket|None=None,action_spec:ActionSpec|None=None)->FeedbackValidationResult:
    issues=_reject_executable(action);channels={item.channel_id:item for item in abi_spec.control_channels};seen={}
    if observation_packet and action.action_timestamp_s<observation_packet.controller_receive_time_s-1e-15:issues.append(_issue("ACTION_BEFORE_OBSERVATION_AVAILABILITY","$.action_timestamp_s","action precedes packet receipt",action.action_timestamp_s))
    for index,row in enumerate(action.channel_values):
        path=f"$.channel_values[{index}]"
        if row.channel_id not in channels:issues.append(_issue("UNKNOWN_ACTION_CHANNEL",path+".channel_id","action channel is undeclared",row.channel_id));continue
        channel=channels[row.channel_id];expected="Gamma" if channel.field=="detuning_gamma" else "saturation_parameter"
        if row.units!=expected:issues.append(_issue("ACTION_UNIT_MISMATCH",path+".units","action units do not match ABI channel",(row.units,expected)))
        if not _finite(row.value):issues.append(_issue("NONFINITE_ACTION_VALUE",path+".value","action value must be finite",row.value))
        if channel.relationship is ChannelRelationship.AFFINE_DERIVED:issues.append(_issue("INVALID_DERIVED_CHANNEL_UPDATE",path,"derived channels cannot be directly controlled",row.channel_id))
        if row.channel_id in seen and seen[row.channel_id]!=row.value:issues.append(_issue("SHARED_CHANNEL_DIVERGENCE",path,"duplicate shared channel requests diverge",(seen[row.channel_id],row.value)))
        elif row.channel_id in seen:issues.append(_issue("DUPLICATE_CONTROL_OWNERSHIP",path,"channel is requested more than once",row.channel_id))
        seen[row.channel_id]=row.value
    required={item.channel_id for item in abi_spec.control_channels if item.relationship is not ChannelRelationship.AFFINE_DERIVED}
    if action.update_mode is ActionUpdateMode.COMPLETE and set(seen)!=required:issues.append(_issue("MISSING_REQUIRED_CHANNEL","$.channel_values","complete action must cover all nonderived ABI channels",sorted(required-set(seen))))
    if action_spec is not None:
        declared={item.channel_id:item for item in action_spec.channels}
        if action.update_mode is ActionUpdateMode.PARTIAL_HOLD_UNSPECIFIED and not action_spec.allow_partial_updates:issues.append(_issue("INVALID_PARTIAL_ACTION_SEMANTICS","$.update_mode","partial updates are forbidden by the action specification",action.update_mode.value))
        if action.update_mode is ActionUpdateMode.HOLD_NO_CHANGE and not action_spec.allow_hold_instruction:issues.append(_issue("INVALID_PARTIAL_ACTION_SEMANTICS","$.update_mode","hold instructions are forbidden by the action specification",action.update_mode.value))
        for row in action.channel_values:
            if row.channel_id not in declared:issues.append(_issue("UNKNOWN_ACTION_CHANNEL","$.channel_values","channel is absent from the action specification",row.channel_id));continue
            capability=declared[row.channel_id]
            if capability.minimum is not None and row.value<capability.minimum or capability.maximum is not None and row.value>capability.maximum:issues.append(_issue("ACTION_OUTSIDE_DECLARED_ABSTRACT_BOUNDS","$.channel_values","action value violates declared abstract bounds",row.value))
    return FeedbackValidationResult(tuple(issues))


class _ActionSequencePolicy:
    def __init__(self,base_spec:ControlPolicySpec,actions:Sequence[ControlAction],start_time_s:float):
        events=[]
        for action in actions:
            affected=tuple(row.channel_id for row in action.channel_values);components=sorted({target.component_id for channel in base_spec.control_channels if channel.channel_id in affected for target in channel.targets})
            events.append(PolicyEvent(action.action_id,action.requested_effective_time_s,"FEEDBACK_ACTION_UPDATE",affected,tuple(components),"previous_requested_action","updated_requested_action",EventBoundaryRule.LEFT_OPEN_RIGHT_CLOSED,"Run 016 deterministic feedback action"))
        self.spec=replace(base_spec,events=tuple(events));self.base=ControlPolicy(base_spec);self.actions=tuple(actions);self.start_time_s=start_time_s;self.hash=feedback_hash(actions);self.channels={item.channel_id:item for item in base_spec.control_channels}
        initial=self.base.sample(start_time_s);self.initial_components=initial.components
    def sample(self,t:float)->PolicyState:
        if not math.isfinite(t):raise FeedbackError("nonfinite action-policy time")
        components={item.component_id:item for item in self.initial_components};values={}
        for action in self.actions:
            if action.requested_effective_time_s<=t:
                if action.update_mode is ActionUpdateMode.HOLD_NO_CHANGE:continue
                for row in action.channel_values:values[row.channel_id]=row.value
        for channel_id,value in values.items():
            channel=self.channels[channel_id]
            for target in channel.targets:
                component=components[target.component_id]
                if target.field=="detuning_gamma":component=replace(component,detuning_gamma=value)
                else:
                    active=component.enabled and value>0;component=replace(component,saturation=value,active=active,off_reason=None if active else (component.off_reason or "explicit feedback zero saturation"))
                components[target.component_id]=component
        event_ids=tuple(action.action_id for action in self.actions if action.requested_effective_time_s==t)
        return PolicyState(t,t,(1,2,3,4),tuple(components[i] for i in (1,2,3,4)),self.base.spec.segments[0].segment_id,self.base.spec.segments[0].semantic_label,event_ids,False,self.hash)


def compile_action_sequence(actions:Sequence[ControlAction],abi_spec:ControlPolicySpec,profile:ApparatusConstraintSet,start_time_s:float,end_time_s:float,mode:CompilationMode=CompilationMode.SAMPLE_AND_HOLD,diagnostic_grid_period_s:float|None=None,pre_roll_s:float|None=None):
    policy=_ActionSequencePolicy(abi_spec,actions,start_time_s);request=CompilationRequest(policy.hash,apparatus_profile_hash(profile),mode,start_time_s,end_time_s,InitialStateMode.POLICY_STATE_AT_START,None,pre_roll_s,diagnostic_grid_period_s,ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING if profile.command_clock.continuous_identity_binding else ReconstructionMode.ZERO_ORDER_HOLD)
    return compile_control_schedule(policy.spec,profile,request,policy_evaluator=policy,policy_hash_override=policy.hash,source_policy_specification_hash_override=feedback_hash({"base_abi":abi_spec,"actions":actions}))


def validate_plant_spec(spec:SyntheticPlantSpec)->FeedbackValidationResult:
    issues=_reject_executable(spec)
    if spec.schema_version!="mgf-mot-synthetic-plant-v1":issues.append(_issue("UNKNOWN_SYNTHETIC_PLANT_SCHEMA","$.schema_version","unknown synthetic plant schema",spec.schema_version))
    if not set(SYNTHETIC_PLANT_LABELS).issubset(spec.labels):issues.append(_issue("MISSING_SYNTHETIC_PLANT_LABELS","$.labels","synthetic plants require all labels",spec.labels))
    if len(spec.state_fields)!=len(spec.initial_values) or any(not _finite(value) for value in spec.initial_values):issues.append(_issue("INVALID_SYNTHETIC_PLANT_STATE","$.initial_values","state field/value shape mismatch or nonfinite value",spec.initial_values))
    if spec.update_period_s<=0:issues.append(_issue("INVALID_SYNTHETIC_PLANT_TIMING","$.update_period_s","plant update period must be positive",spec.update_period_s))
    return FeedbackValidationResult(tuple(issues))
def update_synthetic_plant(spec:SyntheticPlantSpec,state:HiddenPlantState,action:ControlAction|None,timestamp_s:float)->HiddenPlantState:
    dt=timestamp_s-state.timestamp_s;x=np.array([state.values[name] for name in spec.state_fields],float);u=np.zeros(len(spec.input_channel_ids));mapping={} if action is None else {row.channel_id:row.value for row in action.channel_values};u=np.array([mapping.get(name,0.0) for name in spec.input_channel_ids])
    if spec.family is PlantFamily.STATIC_PLANT:new=x
    elif spec.family is PlantFamily.DISCRETE_INTEGRATOR_PLANT:new=x+np.asarray(spec.parameters["input_matrix"],float)@u*dt/spec.update_period_s
    elif spec.family is PlantFamily.FIRST_ORDER_LAG_PLANT:
        target=np.asarray(spec.parameters["input_matrix"],float)@u;alpha=float(spec.parameters["alpha"]);new=x+alpha*(target-x)*dt/spec.update_period_s
    else:raise FeedbackError("unknown synthetic plant")
    return HiddenPlantState(timestamp_s,{name:float(value) for name,value in zip(spec.state_fields,new)})


def _sample_times(timing:FeedbackTimingSpec,observation_spec:ObservationSpec):
    if observation_spec.explicit_sample_times_s:return observation_spec.explicit_sample_times_s
    n=int(math.floor((timing.end_time_s-timing.initial_time_s)/timing.observation_period_s+1e-12));return tuple(timing.initial_time_s+i*timing.observation_period_s for i in range(n+1))
def _control_times(timing:FeedbackTimingSpec):
    if timing.scheduling_mode is SchedulingMode.SCRIPTED_CONTROLLER_TIMES:return timing.scripted_controller_times_s
    n=int(math.floor((timing.end_time_s-timing.initial_time_s)/timing.control_period_s+1e-12));return tuple(timing.initial_time_s+i*timing.control_period_s for i in range(n+1))


def validate_session_spec(spec:FeedbackSessionSpec)->FeedbackValidationResult:
    issues=_reject_executable(spec)
    if spec.schema_version!=SESSION_SCHEMA_VERSION:issues.append(_issue("UNKNOWN_FEEDBACK_SESSION_SCHEMA","$.schema_version","unknown session schema",spec.schema_version))
    issues.extend(validate_observation_spec(spec.observation_spec).issues);issues.extend(validate_action_spec(spec.action_spec,spec.abi_spec).issues);issues.extend(validate_controller_spec(spec.controller_spec).issues);issues.extend(validate_plant_spec(spec.plant_spec).issues)
    t=spec.timing_spec
    if any(not _finite(value) for value in (t.observation_period_s,t.control_period_s,t.controller_compute_latency_s,t.sensor_latency_s,t.communication_latency_s,t.apparatus_command_latency_s,t.initial_time_s,t.end_time_s,t.pre_roll_s,t.max_observation_age_s)) or min(t.observation_period_s,t.control_period_s)<=0 or t.end_time_s<=t.initial_time_s:issues.append(_issue("INVALID_FEEDBACK_TIMING","$.timing_spec","timing layers require finite valid values",t))
    if spec.controller_spec.observation_spec_hash!=feedback_hash(spec.observation_spec):issues.append(_issue("OBSERVATION_SPEC_HASH_MISMATCH","$.controller_spec.observation_spec_hash","controller observation hash differs",spec.controller_spec.observation_spec_hash))
    if spec.controller_spec.action_spec_hash!=feedback_hash(spec.action_spec):issues.append(_issue("ACTION_SPEC_HASH_MISMATCH","$.controller_spec.action_spec_hash","controller action hash differs",spec.controller_spec.action_spec_hash))
    plant_fields=set(spec.plant_spec.state_fields);declared_fields={field for channel in spec.observation_spec.channels for field in channel.source_hidden_state_fields}
    if not declared_fields.issubset(plant_fields):issues.append(_issue("UNDECLARED_HIDDEN_STATE_ACCESS","$.observation_spec.channels","observation requests hidden fields absent from the declared plant schema",sorted(declared_fields-plant_fields)))
    if spec.observation_spec.access_class is ObservationAccessClass.FULL_STATE_ORACLE and declared_fields!=plant_fields:issues.append(_issue("UNDECLARED_HIDDEN_STATE_ACCESS","$.observation_spec","FULL_STATE_ORACLE must explicitly declare the complete hidden-state representation",(sorted(declared_fields),sorted(plant_fields))))
    if any(channel.sensor_latency_s!=t.sensor_latency_s for channel in spec.observation_spec.channels) or spec.observation_spec.communication_latency_s!=t.communication_latency_s:issues.append(_issue("FEEDBACK_TIMING_MISMATCH","$.timing_spec","observation timing and session timing declarations differ",None))
    latency=spec.apparatus_profile.latency.fixed_latency
    if latency.knowledge is KnowledgeState.KNOWN and float(latency.value)!=t.apparatus_command_latency_s:issues.append(_issue("FEEDBACK_TIMING_MISMATCH","$.timing_spec.apparatus_command_latency_s","timing declaration differs from apparatus profile latency",(t.apparatus_command_latency_s,latency.value)))
    if spec.infeasible_action_strategy is InfeasibleActionStrategy.USE_DECLARED_SAFE_ACTION and spec.safe_action is None:issues.append(_issue("INFEASIBLE_ACTION_WITHOUT_DECLARED_RESPONSE","$.safe_action","safe-action strategy requires an explicit action",None))
    if spec.apparatus_profile.hardware_validation_status.value=="SOURCE_INCOMPLETE" and False:issues.append(_issue("PARTIAL_PROFILE_HARDWARE_CLAIM","$.apparatus_profile","partial profile cannot claim hardware execution",None))
    return FeedbackValidationResult(tuple(issues))


def _missing_packet(spec:ObservationSpec,time_s:float,index:int)->ObservationPacket:
    return ObservationPacket(f"missing_{index:05d}",feedback_hash(spec),time_s,time_s,time_s,time_s,(),ObservationStatus.MISSING,tuple(spec.labels))


def run_feedback_session(spec:FeedbackSessionSpec)->FeedbackSessionResult:
    validation=validate_session_spec(spec)
    if not validation.valid:raise FeedbackError("invalid feedback session: "+"; ".join(item.message for item in validation.errors))
    observation_model=ObservationModel(spec.observation_spec);baseline=OpenLoopFamilyPolicy(spec.baseline_family_spec) if spec.baseline_family_spec else None;controller=FeedbackController(spec.controller_spec,spec.abi_spec,baseline)
    state=HiddenPlantState(spec.timing_spec.initial_time_s,{name:value for name,value in zip(spec.plant_spec.state_fields,spec.plant_spec.initial_values)});history=[state];memory=initial_controller_memory(spec.controller_spec);packets=[];pending=[];steps=[];accepted=[];last_action=None;last_valid=None;final_compilation=None;terminated=False;event_order=[]
    sample_times=_sample_times(spec.timing_spec,spec.observation_spec);control_times=_control_times(spec.timing_spec);all_times=sorted(set((*sample_times,*control_times,*[time+spec.timing_spec.sensor_latency_s+spec.timing_spec.communication_latency_s for time in sample_times])))
    sample_index=0;step_index=0
    if spec.controller_spec.controller_family is ControllerFamily.BASELINE_REPLAY_CONTROLLER and spec.baseline_family_spec is not None:
        profile=spec.apparatus_profile;h=family_hashes(spec.baseline_family_spec);request=CompilationRequest(h.complete_policy_package,apparatus_profile_hash(profile),CompilationMode.EXACT_ONLY if profile.command_clock.continuous_identity_binding else CompilationMode.SAMPLE_AND_HOLD,spec.timing_spec.initial_time_s,spec.timing_spec.end_time_s,InitialStateMode.POLICY_STATE_AT_START,None,spec.timing_spec.pre_roll_s,None,ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING if profile.command_clock.continuous_identity_binding else ReconstructionMode.ZERO_ORDER_HOLD);final_compilation,_=compile_family_policy(spec.baseline_family_spec,profile,request)
    for now in all_times:
        if terminated:break
        event_order.append(f"{now:.12g}:EFFECTIVE_COMMANDS")
        if now>state.timestamp_s and any(math.isclose(now,t,abs_tol=1e-15) for t in control_times):state=update_synthetic_plant(spec.plant_spec,state,last_action,now);history.append(state);event_order.append(f"{now:.12g}:PLANT_UPDATE")
        if any(math.isclose(now,t,abs_tol=1e-15) for t in sample_times):
            packet=observation_model.sample(state,now,sample_index,tuple(history));pending.append(packet);sample_index+=1;event_order.append(f"{now:.12g}:SENSOR_SAMPLE")
        arrived=[packet for packet in pending if packet.controller_receive_time_s<=now+1e-15]
        for packet in arrived:
            packets.append(packet);pending.remove(packet);event_order.append(f"{now:.12g}:OBSERVATION_ARRIVAL")
        execute=any(math.isclose(now,t,abs_tol=1e-15) for t in control_times)
        if spec.timing_spec.scheduling_mode is SchedulingMode.OBSERVATION_DRIVEN:execute=bool(arrived)
        if not execute:continue
        packet=packets[-1] if packets else _missing_packet(spec.observation_spec,now,step_index)
        age=now-packet.source_state_timestamp_s
        if age>spec.timing_spec.max_observation_age_s and packet.status is not ObservationStatus.MISSING:packet=replace(packet,status=ObservationStatus.STALE,observations=tuple(replace(item,status=ObservationStatus.STALE) for item in packet.observations))
        use_packet=packet;fallback=None;strategy=spec.controller_spec.fallback_rules[packet.status.value]
        if packet.status in {ObservationStatus.MISSING,ObservationStatus.STALE,ObservationStatus.INVALID}:
            if strategy is MissingStrategy.REJECT_STEP:
                record=FeedbackStepRecord(f"step_{step_index:05d}",step_index,feedback_hash(state),state,packet,now,memory,None,memory,FeedbackValidationResult(()),None,(),(),None,strategy.value,(),"");record=replace(record,record_hash=feedback_hash(replace(record,record_hash="")));steps.append(record);step_index+=1;continue
            if strategy is MissingStrategy.USE_LAST_VALID_OBSERVATION:
                if last_valid is None:raise FeedbackError("missing packet has no last valid observation");use_packet=last_valid;fallback=strategy.value
            elif strategy is MissingStrategy.HOLD_LAST_ACTION:
                action=ControlAction(f"action_step_{step_index:05d}",now,now+spec.timing_spec.controller_compute_latency_s,(),ActionUpdateMode.HOLD_NO_CHANGE,spec.controller_spec.controller_family.value,f"step_{step_index:05d}",ActionValidity.VALID,strategy.value,spec.controller_spec.provenance);new_memory=memory;fallback=strategy.value
            elif strategy is MissingStrategy.USE_DECLARED_FALLBACK_ACTION:
                if spec.safe_action is None:raise FeedbackError("missing declared fallback action");action=replace(spec.safe_action,action_id=f"fallback_{step_index:05d}",action_timestamp_s=now,requested_effective_time_s=now+spec.timing_spec.controller_compute_latency_s,controller_step_id=f"step_{step_index:05d}",fallback_origin=strategy.value);new_memory=memory;fallback=strategy.value
        if packet.status in {ObservationStatus.VALID,ObservationStatus.SATURATED}:last_valid=packet
        if "action" not in locals() or getattr(action,"controller_step_id",None)!=f"step_{step_index:05d}":action,new_memory=controller.step(use_packet,memory,f"step_{step_index:05d}",now,now+spec.timing_spec.controller_compute_latency_s)
        action_validation=validate_action(action,spec.abi_spec,packet,spec.action_spec);compilation=None;realized=None;issues=list(action_validation.issues);accepted_candidate=False
        if action_validation.valid:
            if spec.controller_spec.controller_family is ControllerFamily.BASELINE_REPLAY_CONTROLLER:
                accepted.append(action);accepted_candidate=True;compilation=final_compilation;last_action=action
            else:
                candidate=tuple((*accepted,action));compilation,realized=compile_action_sequence(candidate,spec.abi_spec,spec.apparatus_profile,spec.timing_spec.initial_time_s,spec.timing_spec.end_time_s,CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE if not spec.apparatus_profile.complete else CompilationMode.SAMPLE_AND_HOLD,spec.timing_spec.control_period_s if not spec.apparatus_profile.complete else None,spec.timing_spec.pre_roll_s)
                success=compilation.status in {CompilationStatus.COMPILED_EXACT,CompilationStatus.COMPILED_APPROXIMATE,CompilationStatus.COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE}
                if success:accepted.append(action);accepted_candidate=True;final_compilation=compilation;last_action=action
                else:
                    fallback=spec.infeasible_action_strategy.value
                    if spec.infeasible_action_strategy is InfeasibleActionStrategy.TERMINATE_SESSION:terminated=True
                    elif spec.infeasible_action_strategy is InfeasibleActionStrategy.RECORD_ONLY_DIAGNOSTIC:pass
                    elif spec.infeasible_action_strategy is InfeasibleActionStrategy.USE_DECLARED_SAFE_ACTION:
                        safe_validation=validate_action(spec.safe_action,spec.abi_spec,packet,spec.action_spec)
                        if not safe_validation.valid:raise FeedbackError("declared safe action is invalid")
        status=None if compilation is None else compilation.status.value;issued=() if compilation is None else compilation.commands;effective=issued
        if spec.controller_spec.controller_family is ControllerFamily.BASELINE_REPLAY_CONTROLLER and final_compilation is not None:compilation=final_compilation;status=compilation.status.value;issued=compilation.commands;effective=issued;realized_policy=OpenLoopFamilyPolicy(spec.baseline_family_spec);realized_state=realized_policy.sample(min(action.requested_effective_time_s,spec.timing_spec.end_time_s))
        else:realized_state=None if realized is None else realized.sample(min(action.requested_effective_time_s,spec.timing_spec.end_time_s))
        record=FeedbackStepRecord(f"step_{step_index:05d}",step_index,feedback_hash(state),state if spec.observation_spec.access_class is ObservationAccessClass.FULL_STATE_ORACLE else None,packet,now,memory,action,new_memory,action_validation,status,issued,effective,realized_state,fallback,tuple(issues),"");record=replace(record,record_hash=feedback_hash(replace(record,record_hash="")));steps.append(record);memory=new_memory;event_order.append(f"{now:.12g}:CONTROLLER_EVALUATION");event_order.append(f"{now:.12g}:COMMAND_ISSUE_RECORD");step_index+=1
        if 'action' in locals():del action
    observation_hash=feedback_hash(tuple(step.observation_packet for step in steps));action_hash=feedback_hash(tuple(step.action for step in steps));command_hash=feedback_hash(() if final_compilation is None else final_compilation.commands);spec_hashes={"observation":feedback_hash(spec.observation_spec),"controller":feedback_hash(spec.controller_spec),"controller_parameters":feedback_hash(spec.controller_spec.parameters),"timing":feedback_hash(spec.timing_spec),"plant":feedback_hash(spec.plant_spec),"apparatus":apparatus_profile_hash(spec.apparatus_profile),"session":feedback_hash(spec)}
    exact=sum(step.compilation_status==CompilationStatus.COMPILED_EXACT.value for step in steps);approx=sum(step.compilation_status==CompilationStatus.COMPILED_APPROXIMATE.value for step in steps);infeasible=sum(step.compilation_status==CompilationStatus.COMPILATION_INFEASIBLE.value for step in steps);commands=() if final_compilation is None else final_compilation.commands;quant={}
    for channel_id in sorted({item.channel_id for item in commands}):
        errors=[item.quantization_error for item in commands if item.channel_id==channel_id];quant[channel_id]={"maximum_absolute":max(map(abs,errors),default=0.0),"rms":float(np.sqrt(np.mean(np.square(errors)))) if errors else 0.0}
    latencies=[step.observation_packet.controller_receive_time_s-step.observation_packet.sensor_sample_time_s for step in steps];action_latencies=[item.actual_effective_time_s-item.requested_effective_time_s for item in commands]
    metrics=FeedbackMetrics(len(steps),sum(step.observation_packet.status in {ObservationStatus.VALID,ObservationStatus.SATURATED} for step in steps),sum(step.observation_packet.status is ObservationStatus.MISSING for step in steps),sum(step.observation_packet.status is ObservationStatus.STALE for step in steps),min(latencies,default=0.0),max(latencies,default=0.0),sum(any(item.saturated for item in step.observation_packet.observations) for step in steps),len(steps),sum(step.action is not None for step in steps),sum(step.fallback_decision is not None for step in steps),sum(not step.action_validation.valid for step in steps),len(memory.values),"PENDING_REPLAY_AUDIT",exact,approx,infeasible,len(commands),max(action_latencies,default=0.0),quant)
    labels=tuple(dict.fromkeys((RUN016_LABEL,*spec.observation_spec.labels,*(ORACLE_LABELS if spec.observation_spec.access_class is ObservationAccessClass.FULL_STATE_ORACLE else ()))))
    provisional=FeedbackSessionResult(REPLAY_SCHEMA_VERSION,feedback_hash(spec),spec_hashes,tuple(event_order),tuple(steps),tuple(accepted),observation_hash,action_hash,command_hash,state,memory,final_compilation,metrics,False,labels,"");replay_hash=feedback_hash(replace(provisional,replay_hash=""));return replace(provisional,replay_hash=replay_hash)


def replay_full_session(spec:FeedbackSessionSpec,recorded:FeedbackSessionResult)->FeedbackReplay:
    if feedback_hash(spec)!=recorded.session_hash:raise FeedbackError("REPLAY_HASH_MISMATCH: session specification changed")
    rerun=run_feedback_session(spec);equal=replace(rerun,metrics=replace(rerun.metrics,deterministic_replay_status="PENDING_REPLAY_AUDIT"))==recorded
    replay=FeedbackReplay(REPLAY_SCHEMA_VERSION,"FULL_REPLAY_FROM_SPECS_AND_SEEDS",recorded.session_hash,recorded.spec_hashes,rerun.observation_stream_hash,rerun.action_stream_hash,rerun.command_stream_hash,equal,"",recorded.labels);return replace(replay,replay_package_hash=feedback_hash(replace(replay,replay_package_hash="")))
def replay_controller_from_packets(spec:FeedbackSessionSpec,recorded:FeedbackSessionResult)->FeedbackReplay:
    controller=FeedbackController(spec.controller_spec,spec.abi_spec,OpenLoopFamilyPolicy(spec.baseline_family_spec) if spec.baseline_family_spec else None);memory=initial_controller_memory(spec.controller_spec);actions=[];last_valid=None
    for step in recorded.steps:
        if step.action is None:continue
        packet=step.observation_packet;strategy=spec.controller_spec.fallback_rules[packet.status.value]
        if packet.status in {ObservationStatus.VALID,ObservationStatus.SATURATED}:last_valid=packet
        if step.action.fallback_origin==MissingStrategy.HOLD_LAST_ACTION.value:
            action=ControlAction(f"action_{step.step_id}",step.controller_receive_time_s,step.action.requested_effective_time_s,(),ActionUpdateMode.HOLD_NO_CHANGE,spec.controller_spec.controller_family.value,step.step_id,ActionValidity.VALID,MissingStrategy.HOLD_LAST_ACTION.value,spec.controller_spec.provenance)
        elif step.action.fallback_origin==MissingStrategy.USE_DECLARED_FALLBACK_ACTION.value:
            action=replace(spec.safe_action,action_id=step.action.action_id,action_timestamp_s=step.controller_receive_time_s,requested_effective_time_s=step.action.requested_effective_time_s,controller_step_id=step.step_id,fallback_origin=MissingStrategy.USE_DECLARED_FALLBACK_ACTION.value)
        else:
            use_packet=last_valid if strategy is MissingStrategy.USE_LAST_VALID_OBSERVATION and packet.status not in {ObservationStatus.VALID,ObservationStatus.SATURATED} else packet
            action,memory=controller.step(use_packet,memory,step.step_id,step.controller_receive_time_s,step.action.requested_effective_time_s)
        actions.append(action)
    stream=feedback_hash(tuple(actions));equal=stream==feedback_hash(tuple(step.action for step in recorded.steps if step.action is not None));replay=FeedbackReplay(REPLAY_SCHEMA_VERSION,"CONTROLLER_ONLY_FROM_RECORDED_PACKETS",recorded.session_hash,recorded.spec_hashes,recorded.observation_stream_hash,stream,"",equal,"",recorded.labels);return replace(replay,replay_package_hash=feedback_hash(replace(replay,replay_package_hash="")))
def replay_apparatus_from_actions(spec:FeedbackSessionSpec,recorded:FeedbackSessionResult)->FeedbackReplay:
    if spec.controller_spec.controller_family is ControllerFamily.BASELINE_REPLAY_CONTROLLER and spec.baseline_family_spec is not None:
        h=family_hashes(spec.baseline_family_spec);request=CompilationRequest(h.complete_policy_package,apparatus_profile_hash(spec.apparatus_profile),CompilationMode.EXACT_ONLY if spec.apparatus_profile.command_clock.continuous_identity_binding else CompilationMode.SAMPLE_AND_HOLD,spec.timing_spec.initial_time_s,spec.timing_spec.end_time_s,InitialStateMode.POLICY_STATE_AT_START,None,spec.timing_spec.pre_roll_s,None,ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING if spec.apparatus_profile.command_clock.continuous_identity_binding else ReconstructionMode.ZERO_ORDER_HOLD);compiled,_=compile_family_policy(spec.baseline_family_spec,spec.apparatus_profile,request)
    else:compiled,_=compile_action_sequence(recorded.accepted_actions,spec.abi_spec,spec.apparatus_profile,spec.timing_spec.initial_time_s,spec.timing_spec.end_time_s,CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE if not spec.apparatus_profile.complete else CompilationMode.SAMPLE_AND_HOLD,spec.timing_spec.control_period_s if not spec.apparatus_profile.complete else None,spec.timing_spec.pre_roll_s)
    stream=feedback_hash(compiled.commands);equal=stream==recorded.command_stream_hash;replay=FeedbackReplay(REPLAY_SCHEMA_VERSION,"APPARATUS_ONLY_FROM_RECORDED_ACTIONS",recorded.session_hash,recorded.spec_hashes,recorded.observation_stream_hash,recorded.action_stream_hash,stream,equal,"",recorded.labels);return replace(replay,replay_package_hash=feedback_hash(replace(replay,replay_package_hash="")))
