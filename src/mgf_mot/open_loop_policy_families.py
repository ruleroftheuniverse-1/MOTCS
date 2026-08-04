"""Run 015 model-independent, stateless open-loop policy families.

This module contains control mathematics only.  It deliberately has no force,
trajectory, capture, feedback, apparatus-driver, or optimizer dependencies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import yaml

from .control_policy_abi import (
    BoundBasis, ChannelRelationship, ChannelSignalKind, ComponentControlState,
    ControlPolicy, ControlPolicyFamily, ControlPolicySpec, PolicyParameterSpec, PolicyState,
    PolicyStatefulness,
)
from .control_policy_serialization import (
    control_policy_spec_from_mapping, control_policy_spec_to_mapping,
)
from .control_policy_validation import validate_control_policy_spec
from .legacy_policy_adapter import legacy_policy_to_v2_spec
from .policies import load_policy


OPEN_LOOP_FAMILY_SCHEMA_VERSION = "mgf-mot-open-loop-policy-family-v1"
OPEN_LOOP_PARAMETERIZATION_VERSION = "1"
OPEN_LOOP_IMPLEMENTATION_VERSION = "run015-open-loop-v1"
RUN015_LABEL = "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_015_OPEN_LOOP_POLICY_FAMILIES_ONLY"


class OpenLoopFamilyError(ValueError):
    pass


class OpenLoopFamilyId(str, Enum):
    PIECEWISE_LINEAR = "piecewise-linear-open-loop-v1"
    MONOTONE_CUBIC = "monotone-cubic-open-loop-v1"
    FOURIER_CORRECTION = "fourier-correction-open-loop-v1"


class MonotonicityMode(str, Enum):
    UNRESTRICTED = "UNRESTRICTED"
    NONDECREASING = "NONDECREASING"
    NONINCREASING = "NONINCREASING"


class MonotonicityClassification(str, Enum):
    MONOTONE = "MONOTONE"
    NONMONOTONE = "NONMONOTONE"
    MONOTONICITY_NOT_REQUESTED = "MONOTONICITY_NOT_REQUESTED"


@dataclass(frozen=True)
class FamilyProvenance:
    provenance_class: str
    source_description: str
    source_path: str
    source_hash: str
    interpretation_notes: str


@dataclass(frozen=True)
class PiecewiseLinearChannel:
    channel_id: str
    field: str
    knot_u: tuple[float, ...]
    knot_values: tuple[float, ...]
    monotonicity: MonotonicityMode
    adjustable_value_indices: tuple[int, ...]
    fixed_endpoint_values: bool
    minimum_knot_separation: float | None
    algorithm: str = "DETERMINISTIC_LINEAR_INTERPOLATION_V1"


@dataclass(frozen=True)
class MonotoneCubicChannel:
    channel_id: str
    field: str
    knot_u: tuple[float, ...]
    knot_values: tuple[float, ...]
    monotonicity: MonotonicityMode
    adjustable_value_indices: tuple[int, ...]
    fixed_endpoint_values: bool
    minimum_knot_separation: float | None
    algorithm: str = "FRITSCH_CARLSON_PCHIP_V1"


@dataclass(frozen=True)
class FourierCorrectionChannel:
    channel_id: str
    field: str
    baseline_start: float
    baseline_end: float
    harmonic_count: int
    coefficients: tuple[float, ...]
    adjustable_coefficient_indices: tuple[int, ...]
    coefficient_units: str
    basis_id: str = "ENDPOINT_PRESERVING_SIN_N_PI_U_V1"
    correction_amplitude_bound: float | None = None
    monotonicity_requested: bool = False


ChannelFamilySpec = PiecewiseLinearChannel | MonotoneCubicChannel | FourierCorrectionChannel


@dataclass(frozen=True)
class OpenLoopPolicyFamilySpec:
    schema_version: str
    abi_schema_version: str
    family_id: OpenLoopFamilyId
    family_name: str
    parameterization_version: str
    implementation_version: str
    supported_channel_fields: tuple[str, ...]
    supported_event_behavior: str
    statefulness: str
    serialization_contract: str
    t_start_s: float
    t_end_s: float
    abi_spec: ControlPolicySpec
    channel_schedules: tuple[ChannelFamilySpec, ...]
    provenance: FamilyProvenance


@dataclass(frozen=True)
class FamilyValidationIssue:
    code: str
    severity: str
    field_path: str
    message: str
    offending_value: Any
    suggested_correction: str | None


@dataclass(frozen=True)
class FamilyValidationResult:
    issues: tuple[FamilyValidationIssue, ...]

    @property
    def errors(self) -> tuple[FamilyValidationIssue, ...]:
        return tuple(item for item in self.issues if item.severity == "ERROR")

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class FamilyHashes:
    family_specification: str
    parameter_vector_layout: str
    parameter_values: str
    complete_policy_package: str


@dataclass(frozen=True)
class ParameterVectorEntry:
    vector_index: int
    channel_id: str
    parameter_kind: str
    element_index: int
    parameter_name: str
    units: str
    lower_bound: float | None
    upper_bound: float | None
    bound_basis: str


@dataclass(frozen=True)
class ParameterVectorLayout:
    entries: tuple[ParameterVectorEntry, ...]
    layout_hash: str


@dataclass(frozen=True)
class PolicyParameterVector:
    layout_hash: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class SmoothnessLedger:
    family_id: str
    value_continuity: str
    first_derivative_continuity: str
    second_derivative_continuity: str
    structural_knot_times_s: tuple[float, ...]
    semantic_event_times_s: tuple[float, ...]
    known_discontinuities_s: tuple[float, ...]
    endpoint_derivative_behavior: str


@dataclass(frozen=True)
class ChannelStructuralMetric:
    channel_id: str
    field: str
    total_variation: float
    maximum_absolute_first_derivative_per_s: float
    maximum_absolute_second_derivative_per_s2: float | None
    endpoint_displacement: float
    knot_or_harmonic_count: int
    derivative_discontinuity_count: int
    monotonicity: MonotonicityClassification
    minimum_value: float
    maximum_value: float


@dataclass(frozen=True)
class PolicyStructuralMetrics:
    channels: tuple[ChannelStructuralMetric, ...]
    parameter_count: int
    adjustable_parameter_count: int
    event_count: int
    structural_boundary_count: int
    family_complexity: Mapping[str, Any]
    policy_hash: str
    compilation_readiness: str


@dataclass(frozen=True)
class FamilyRegistration:
    family_id: OpenLoopFamilyId
    parameterization_version: str
    algorithm_id: str
    derivative_orders: tuple[int, ...]
    serializer_id: str


FAMILY_REGISTRY: Mapping[tuple[str, str], FamilyRegistration] = {
    (OpenLoopFamilyId.PIECEWISE_LINEAR.value, "1"): FamilyRegistration(OpenLoopFamilyId.PIECEWISE_LINEAR,"1","DETERMINISTIC_LINEAR_INTERPOLATION_V1",(0,1),"CANONICAL_JSON_SORTED_KEYS_V1"),
    (OpenLoopFamilyId.MONOTONE_CUBIC.value, "1"): FamilyRegistration(OpenLoopFamilyId.MONOTONE_CUBIC,"1","FRITSCH_CARLSON_PCHIP_V1",(0,1,2),"CANONICAL_JSON_SORTED_KEYS_V1"),
    (OpenLoopFamilyId.FOURIER_CORRECTION.value, "1"): FamilyRegistration(OpenLoopFamilyId.FOURIER_CORRECTION,"1","ENDPOINT_PRESERVING_SIN_N_PI_U_V1",(0,1,2),"CANONICAL_JSON_SORTED_KEYS_V1"),
}


def family_registration(family_id: str | OpenLoopFamilyId, parameterization_version: str) -> FamilyRegistration:
    key=(family_id.value if isinstance(family_id,OpenLoopFamilyId) else str(family_id),str(parameterization_version))
    try: return FAMILY_REGISTRY[key]
    except KeyError as exc: raise OpenLoopFamilyError(f"unknown policy family/version {key}; registry is closed") from exc


def normalized_policy_time(t: float, t_start_s: float, t_end_s: float) -> float:
    if not all(math.isfinite(item) for item in (t,t_start_s,t_end_s)) or t_end_s <= t_start_s:
        raise OpenLoopFamilyError("normalized time requires finite t and t_end > t_start")
    u=(t-t_start_s)/(t_end_s-t_start_s)
    if u < 0 or u > 1:
        raise OpenLoopFamilyError("time is outside the declared finite family interval; no implicit clamp is permitted")
    return u


def _plain(value: Any) -> Any:
    if isinstance(value,Enum): return value.value
    if isinstance(value,ControlPolicySpec): return control_policy_spec_to_mapping(value)
    if is_dataclass(value): return {key:_plain(item) for key,item in asdict(value).items()}
    if isinstance(value,Mapping): return {str(key):_plain(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)): return [_plain(item) for item in value]
    if callable(value): raise OpenLoopFamilyError("arbitrary executable content is forbidden")
    return value


def _reject_executable_content(value: Any,path: str="$") -> None:
    if callable(value): raise OpenLoopFamilyError(f"ARBITRARY_EXECUTABLE_CONTENT at {path}")
    if isinstance(value,Mapping):
        for key,item in value.items():
            if str(key).lower() in {"callable","expression","lambda","exec","eval","python_code","module_path"}:
                raise OpenLoopFamilyError(f"ARBITRARY_EXECUTABLE_CONTENT at {path}.{key}")
            _reject_executable_content(item,f"{path}.{key}")
    elif isinstance(value,(tuple,list)):
        for index,item in enumerate(value):_reject_executable_content(item,f"{path}[{index}]")


def family_spec_to_mapping(spec: OpenLoopPolicyFamilySpec) -> dict[str,Any]:
    mapping=_plain(spec)
    mapping["abi_spec"]=control_policy_spec_to_mapping(spec.abi_spec)
    mapping["channel_schedules"]=[{"schedule_type":type(item).__name__,**_plain(item)} for item in spec.channel_schedules]
    return mapping


def canonical_family_json(spec_or_mapping: OpenLoopPolicyFamilySpec | Mapping[str,Any]) -> str:
    mapping=family_spec_to_mapping(spec_or_mapping) if isinstance(spec_or_mapping,OpenLoopPolicyFamilySpec) else _plain(spec_or_mapping)
    return json.dumps(mapping,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)


def serialize_family_spec(spec: OpenLoopPolicyFamilySpec, *, pretty: bool=False) -> str:
    mapping=family_spec_to_mapping(spec)
    return json.dumps(mapping,sort_keys=True,indent=2 if pretty else None,separators=None if pretty else (",",":"),ensure_ascii=False,allow_nan=False)+("\n" if pretty else "")


def _schedule_from_mapping(row: Mapping[str,Any]) -> ChannelFamilySpec:
    kind=row["schedule_type"]
    if kind=="PiecewiseLinearChannel":
        expected={"schedule_type","channel_id","field","knot_u","knot_values","monotonicity","adjustable_value_indices","fixed_endpoint_values","minimum_knot_separation","algorithm"}
        if set(row)!=expected: raise OpenLoopFamilyError(f"piecewise schedule fields must be exactly {sorted(expected)}")
        return PiecewiseLinearChannel(row["channel_id"],row["field"],tuple(row["knot_u"]),tuple(row["knot_values"]),MonotonicityMode(row["monotonicity"]),tuple(row["adjustable_value_indices"]),row["fixed_endpoint_values"],row["minimum_knot_separation"],row["algorithm"])
    if kind=="MonotoneCubicChannel":
        expected={"schedule_type","channel_id","field","knot_u","knot_values","monotonicity","adjustable_value_indices","fixed_endpoint_values","minimum_knot_separation","algorithm"}
        if set(row)!=expected: raise OpenLoopFamilyError(f"cubic schedule fields must be exactly {sorted(expected)}")
        return MonotoneCubicChannel(row["channel_id"],row["field"],tuple(row["knot_u"]),tuple(row["knot_values"]),MonotonicityMode(row["monotonicity"]),tuple(row["adjustable_value_indices"]),row["fixed_endpoint_values"],row["minimum_knot_separation"],row["algorithm"])
    if kind=="FourierCorrectionChannel":
        expected={"schedule_type","channel_id","field","baseline_start","baseline_end","harmonic_count","coefficients","adjustable_coefficient_indices","coefficient_units","basis_id","correction_amplitude_bound","monotonicity_requested"}
        if set(row)!=expected: raise OpenLoopFamilyError(f"Fourier schedule fields must be exactly {sorted(expected)}")
        return FourierCorrectionChannel(row["channel_id"],row["field"],row["baseline_start"],row["baseline_end"],row["harmonic_count"],tuple(row["coefficients"]),tuple(row["adjustable_coefficient_indices"]),row["coefficient_units"],row["basis_id"],row["correction_amplitude_bound"],row["monotonicity_requested"])
    raise OpenLoopFamilyError(f"unknown schedule type {kind!r}")


def validate_family_mapping(data: Mapping[str,Any]) -> FamilyValidationResult:
    issues=[]
    try:_reject_executable_content(data)
    except OpenLoopFamilyError as exc:issues.append(_issue("ARBITRARY_EXECUTABLE_CONTENT","$",str(exc),None))
    required={"schema_version","abi_schema_version","family_id","family_name","parameterization_version","implementation_version","supported_channel_fields","supported_event_behavior","statefulness","serialization_contract","t_start_s","t_end_s","abi_spec","channel_schedules","provenance"}
    for key in sorted(required-set(data)):issues.append(_issue("MISSING_REQUIRED_FIELD",f"$.{key}","required family field is missing; no default is used",None))
    for key in sorted(set(data)-required):issues.append(_issue("UNKNOWN_FAMILY_FIELD",f"$.{key}","unknown family field fails closed",data[key]))
    if data.get("schema_version")!=OPEN_LOOP_FAMILY_SCHEMA_VERSION:issues.append(_issue("UNKNOWN_FAMILY_VERSION","$.schema_version","unknown family schema version",data.get("schema_version")))
    try:family_registration(str(data.get("family_id")),str(data.get("parameterization_version")))
    except OpenLoopFamilyError as exc:issues.append(_issue("UNKNOWN_POLICY_FAMILY","$.family_id",str(exc),data.get("family_id")))
    return FamilyValidationResult(tuple(issues))


def family_spec_from_mapping(data: Mapping[str,Any]) -> OpenLoopPolicyFamilySpec:
    mapping_validation=validate_family_mapping(data)
    if not mapping_validation.valid:raise OpenLoopFamilyError("invalid family mapping: "+"; ".join(item.message for item in mapping_validation.errors))
    required=("schema_version","abi_schema_version","family_id","family_name","parameterization_version","implementation_version","supported_channel_fields","supported_event_behavior","statefulness","serialization_contract","t_start_s","t_end_s","abi_spec","channel_schedules","provenance")
    missing=[key for key in required if key not in data]
    if missing: raise OpenLoopFamilyError(f"family specification missing {missing}; no fallback defaults are permitted")
    if set(data)!=set(required): raise OpenLoopFamilyError(f"family specification contains unknown fields {sorted(set(data)-set(required))}")
    p=data["provenance"]
    provenance=FamilyProvenance(p["provenance_class"],p["source_description"],p["source_path"],p["source_hash"],p["interpretation_notes"])
    spec=OpenLoopPolicyFamilySpec(data["schema_version"],data["abi_schema_version"],OpenLoopFamilyId(data["family_id"]),data["family_name"],str(data["parameterization_version"]),data["implementation_version"],tuple(data["supported_channel_fields"]),data["supported_event_behavior"],data["statefulness"],data["serialization_contract"],float(data["t_start_s"]),float(data["t_end_s"]),control_policy_spec_from_mapping(data["abi_spec"]),tuple(_schedule_from_mapping(row) for row in data["channel_schedules"]),provenance)
    result=validate_family_spec(spec)
    if not result.valid: raise OpenLoopFamilyError("invalid deserialized family: "+"; ".join(item.message for item in result.errors))
    return spec


def deserialize_family_spec(text: str) -> OpenLoopPolicyFamilySpec:
    data=json.loads(text,parse_constant=lambda value: (_ for _ in ()).throw(OpenLoopFamilyError(f"nonfinite JSON value {value} is forbidden")))
    if not isinstance(data,dict): raise OpenLoopFamilyError("family JSON root must be an object")
    return family_spec_from_mapping(data)


def family_hashes(spec: OpenLoopPolicyFamilySpec) -> FamilyHashes:
    mapping=family_spec_to_mapping(spec)
    schedules=mapping["channel_schedules"]
    parameter_values=[]
    for row in schedules:
        parameter_values.append({"channel_id":row["channel_id"],"knot_values":row.get("knot_values"),"coefficients":row.get("coefficients")})
    family_hash=sha256(canonical_family_json({key:value for key,value in mapping.items() if key!="provenance"}).encode()).hexdigest()
    parameter_hash=sha256(canonical_family_json(parameter_values).encode()).hexdigest()
    complete=sha256(canonical_family_json(mapping).encode()).hexdigest()
    return FamilyHashes(family_hash,parameter_vector_layout(spec).layout_hash,parameter_hash,complete)


def _issue(code: str,path: str,message: str,value: Any,correction: str|None=None) -> FamilyValidationIssue:
    return FamilyValidationIssue(code,"ERROR",path,message,value,correction)


def _validate_knots(item: PiecewiseLinearChannel|MonotoneCubicChannel,path: str,issues: list[FamilyValidationIssue]) -> None:
    x,y=item.knot_u,item.knot_values
    if len(x)!=len(y): issues.append(_issue("MALFORMED_KNOT_ARRAY",path,"knot position and value counts must match",(len(x),len(y))))
    if len(x)<2 or len(y)<2: issues.append(_issue("INSUFFICIENT_KNOT_COUNT",path,"at least two knots are required",(len(x),len(y))))
    if x and (x[0]!=0.0 or x[-1]!=1.0): issues.append(_issue("MISSING_ENDPOINT_KNOT",path+".knot_u","canonical knots must begin at 0 and end at 1",x))
    if any(not math.isfinite(float(value)) for value in (*x,*y)): issues.append(_issue("NONFINITE_KNOT_VALUE",path,"all knot positions and values must be finite",(x,y)))
    if len(set(x))!=len(x): issues.append(_issue("DUPLICATE_KNOTS",path+".knot_u","duplicate knots are forbidden",x))
    if any(b<=a for a,b in zip(x,x[1:])): issues.append(_issue("NON_INCREASING_KNOT_POSITIONS",path+".knot_u","knot positions must be strictly increasing; duplicates are forbidden",x))
    if item.minimum_knot_separation is not None and (not math.isfinite(item.minimum_knot_separation) or item.minimum_knot_separation<=0 or any(b-a<item.minimum_knot_separation for a,b in zip(x,x[1:]))): issues.append(_issue("MINIMUM_KNOT_SEPARATION_VIOLATION",path+".minimum_knot_separation","declared minimum knot separation is invalid or violated",item.minimum_knot_separation))
    if item.monotonicity is MonotonicityMode.NONDECREASING and any(b<a for a,b in zip(y,y[1:])): issues.append(_issue("MONOTONICITY_VIOLATION",path+".knot_values","values are not nondecreasing",y))
    if item.monotonicity is MonotonicityMode.NONINCREASING and any(b>a for a,b in zip(y,y[1:])): issues.append(_issue("MONOTONICITY_VIOLATION",path+".knot_values","values are not nonincreasing",y))
    if isinstance(item,MonotoneCubicChannel) and item.monotonicity is MonotonicityMode.UNRESTRICTED: issues.append(_issue("MONOTONICITY_REQUIRED",path+".monotonicity","Run 015 monotone cubic requires a monotonicity direction",item.monotonicity.value))
    if isinstance(item,MonotoneCubicChannel) and len(x)==len(y) and len(x)>=2 and all(b>a for a,b in zip(x,x[1:])) and all(math.isfinite(float(value)) for value in (*x,*y)):
        for segment,(a,b) in enumerate(zip(y,y[1:])):
            samples=[_pchip_eval(item,x[segment]+(x[segment+1]-x[segment])*fraction,0) for fraction in (0,.125,.25,.5,.75,.875,1)]
            if min(samples)<min(a,b)-1e-12 or max(samples)>max(a,b)+1e-12: issues.append(_issue("SPLINE_OVERSHOOT_INVARIANT_FAILURE",path,"shape-preserving cubic escaped neighboring knot bounds",samples));break
    if any(index<0 or index>=len(y) for index in item.adjustable_value_indices) or len(set(item.adjustable_value_indices))!=len(item.adjustable_value_indices): issues.append(_issue("INVALID_ADJUSTABLE_INDEX",path+".adjustable_value_indices","adjustable indices must be unique valid knot indices",item.adjustable_value_indices))
    if item.fixed_endpoint_values and any(index in {0,len(y)-1} for index in item.adjustable_value_indices): issues.append(_issue("FIXED_ENDPOINT_MARKED_ADJUSTABLE",path,"fixed endpoints cannot be adjustable",item.adjustable_value_indices))


def validate_family_spec(spec: OpenLoopPolicyFamilySpec) -> FamilyValidationResult:
    issues:list[FamilyValidationIssue]=[]
    if spec.schema_version!=OPEN_LOOP_FAMILY_SCHEMA_VERSION: issues.append(_issue("UNKNOWN_FAMILY_VERSION","$.schema_version","unknown family schema version",spec.schema_version))
    try: registration=family_registration(spec.family_id,spec.parameterization_version)
    except OpenLoopFamilyError as exc: issues.append(_issue("UNKNOWN_POLICY_FAMILY","$.family_id",str(exc),spec.family_id)); registration=None
    if spec.abi_schema_version!=spec.abi_spec.schema_version: issues.append(_issue("ABI_SCHEMA_MISMATCH","$.abi_schema_version","declared ABI schema differs from embedded ABI specification",spec.abi_schema_version))
    abi_validation=validate_control_policy_spec(spec.abi_spec)
    for item in abi_validation.errors: issues.append(_issue("ABI_"+item.code,"$.abi_spec"+item.field_path[1:],item.message,item.relevant_value,item.suggested_correction))
    if spec.statefulness!=PolicyStatefulness.STATELESS_OPEN_LOOP.value: issues.append(_issue("INVALID_STATEFULNESS","$.statefulness","families must be stateless open loop",spec.statefulness))
    if not all(math.isfinite(item) for item in (spec.t_start_s,spec.t_end_s)) or spec.t_end_s<=spec.t_start_s: issues.append(_issue("INVALID_NORMALIZED_TIME_INTERVAL","$.t_end_s","finite t_end > t_start is required",(spec.t_start_s,spec.t_end_s)))
    channels={item.channel_id:item for item in spec.abi_spec.control_channels}
    seen=set()
    for index,item in enumerate(spec.channel_schedules):
        path=f"$.channel_schedules[{index}]"
        if item.channel_id in seen: issues.append(_issue("AMBIGUOUS_CHANNEL_OWNERSHIP",path+".channel_id","a channel has multiple family schedules",item.channel_id))
        seen.add(item.channel_id)
        if item.channel_id not in channels: issues.append(_issue("UNRESOLVED_CHANNEL",path+".channel_id","family channel does not exist in ABI ownership",item.channel_id)); continue
        if item.field not in {"detuning_gamma","saturation"} or item.field not in spec.supported_channel_fields: issues.append(_issue("UNSUPPORTED_CHANNEL_FIELD",path+".field","unsupported family channel field",item.field))
        if channels[item.channel_id].field!=item.field: issues.append(_issue("AMBIGUOUS_CHANNEL_OWNERSHIP",path+".field","family field differs from ABI channel field",(item.field,channels[item.channel_id].field)))
        expected={OpenLoopFamilyId.PIECEWISE_LINEAR:PiecewiseLinearChannel,OpenLoopFamilyId.MONOTONE_CUBIC:MonotoneCubicChannel,OpenLoopFamilyId.FOURIER_CORRECTION:FourierCorrectionChannel}[spec.family_id]
        if not isinstance(item,expected): issues.append(_issue("FAMILY_SCHEDULE_TYPE_MISMATCH",path,"channel schedule type does not match family",type(item).__name__)); continue
        if isinstance(item,(PiecewiseLinearChannel,MonotoneCubicChannel)):
            _validate_knots(item,path,issues)
            if item.field=="saturation" and any(value<0 for value in item.knot_values): issues.append(_issue("NEGATIVE_SATURATION",path+".knot_values","saturation knots cannot be negative",item.knot_values))
        else:
            if item.basis_id!="ENDPOINT_PRESERVING_SIN_N_PI_U_V1": issues.append(_issue("UNKNOWN_FOURIER_BASIS",path+".basis_id","unknown basis identifier",item.basis_id))
            if not isinstance(item.harmonic_count,int) or item.harmonic_count<=0: issues.append(_issue("INVALID_HARMONIC_COUNT",path+".harmonic_count","positive finite harmonic count is required",item.harmonic_count))
            if len(item.coefficients)!=item.harmonic_count: issues.append(_issue("COEFFICIENT_COUNT_MISMATCH",path+".coefficients","coefficient count must equal harmonic count",len(item.coefficients)))
            if any(not math.isfinite(value) for value in (item.baseline_start,item.baseline_end,*item.coefficients)): issues.append(_issue("NONFINITE_FOURIER_COEFFICIENT",path,"baseline and coefficients must be finite",item.coefficients))
            if any(i<0 or i>=len(item.coefficients) for i in item.adjustable_coefficient_indices) or len(set(item.adjustable_coefficient_indices))!=len(item.adjustable_coefficient_indices): issues.append(_issue("INVALID_ADJUSTABLE_INDEX",path+".adjustable_coefficient_indices","coefficient indices must be unique and valid",item.adjustable_coefficient_indices))
            if item.correction_amplitude_bound is not None and (item.correction_amplitude_bound<0 or sum(abs(value) for value in item.coefficients)>item.correction_amplitude_bound+1e-15): issues.append(_issue("CORRECTION_AMPLITUDE_BOUND_VIOLATION",path,"coefficient absolute-sum exceeds the declared correction bound",item.correction_amplitude_bound))
            if item.field=="saturation" and min(item.baseline_start,item.baseline_end)-sum(abs(value) for value in item.coefficients)<0: issues.append(_issue("NEGATIVE_SATURATION",path,"Fourier saturation correction cannot prove nonnegative values",item.coefficients))
    if not spec.channel_schedules: issues.append(_issue("MISSING_CHANNEL_SCHEDULES","$.channel_schedules","at least one explicitly owned schedule is required",()))
    if registration and any(getattr(item,"algorithm",getattr(item,"basis_id",None))!=registration.algorithm_id for item in spec.channel_schedules): issues.append(_issue("ALGORITHM_VERSION_MISMATCH","$.channel_schedules","serialized algorithm does not match closed registry",registration.algorithm_id))
    return FamilyValidationResult(tuple(issues))


def _interval(x: Sequence[float],u: float) -> int:
    if u==1.0: return len(x)-2
    return max(0,min(len(x)-2,int(np.searchsorted(x,u,side="right")-1)))


def _linear_eval(item: PiecewiseLinearChannel,u: float,order: int) -> float:
    if order not in {0,1}: raise OpenLoopFamilyError("piecewise-linear second derivative is not classically defined at knots")
    if order==1 and any(u==k for k in item.knot_u[1:-1]): raise OpenLoopFamilyError("piecewise-linear first derivative is discontinuous at this interior knot")
    i=_interval(item.knot_u,u); x0,x1=item.knot_u[i:i+2]; y0,y1=item.knot_values[i:i+2]; slope=(y1-y0)/(x1-x0)
    return y0+(u-x0)*slope if order==0 else slope


def _pchip_tangents(x: Sequence[float],y: Sequence[float]) -> tuple[float,...]:
    n=len(x); h=np.diff(np.asarray(x,float)); d=np.diff(np.asarray(y,float))/h
    if n==2: return (float(d[0]),float(d[0]))
    m=np.zeros(n,float)
    for k in range(1,n-1):
        if d[k-1]==0 or d[k]==0 or np.sign(d[k-1])!=np.sign(d[k]): m[k]=0.0
        else:
            w1=2*h[k]+h[k-1]; w2=h[k]+2*h[k-1]; m[k]=(w1+w2)/(w1/d[k-1]+w2/d[k])
    def endpoint(h0,h1,d0,d1):
        value=((2*h0+h1)*d0-h0*d1)/(h0+h1)
        if np.sign(value)!=np.sign(d0): return 0.0
        if np.sign(d0)!=np.sign(d1) and abs(value)>abs(3*d0): return float(3*d0)
        return float(value)
    m[0]=endpoint(h[0],h[1],d[0],d[1]);m[-1]=endpoint(h[-1],h[-2],d[-1],d[-2])
    return tuple(float(value) for value in m)


def _pchip_eval(item: MonotoneCubicChannel,u: float,order: int) -> float:
    if order not in {0,1,2}: raise OpenLoopFamilyError("unsupported derivative request")
    if len(item.knot_u)==2:
        slope=item.knot_values[1]-item.knot_values[0]
        return item.knot_values[0]+u*slope if order==0 else (slope if order==1 else 0.0)
    i=_interval(item.knot_u,u); x0,x1=item.knot_u[i:i+2]; h=x1-x0; s=(u-x0)/h; y0,y1=item.knot_values[i:i+2]; m=_pchip_tangents(item.knot_u,item.knot_values); m0,m1=m[i],m[i+1]
    if order==0: return (2*s**3-3*s**2+1)*y0+(s**3-2*s**2+s)*h*m0+(-2*s**3+3*s**2)*y1+(s**3-s**2)*h*m1
    if order==1: return ((6*s**2-6*s)*y0+(3*s**2-4*s+1)*h*m0+(-6*s**2+6*s)*y1+(3*s**2-2*s)*h*m1)/h
    return ((12*s-6)*y0+(6*s-4)*h*m0+(-12*s+6)*y1+(6*s-2)*h*m1)/(h*h)


def _fourier_eval(item: FourierCorrectionChannel,u: float,order: int) -> float:
    if order not in {0,1,2}: raise OpenLoopFamilyError("unsupported derivative request")
    base=item.baseline_start+(item.baseline_end-item.baseline_start)*u
    if order==0:
        if u==0.0:return item.baseline_start
        if u==1.0:return item.baseline_end
        return base+sum(a*math.sin((n+1)*math.pi*u) for n,a in enumerate(item.coefficients))
    if order==1: return item.baseline_end-item.baseline_start+sum(a*(n+1)*math.pi*math.cos((n+1)*math.pi*u) for n,a in enumerate(item.coefficients))
    return sum(-a*((n+1)*math.pi)**2*math.sin((n+1)*math.pi*u) for n,a in enumerate(item.coefficients))


def evaluate_channel(schedule: ChannelFamilySpec,u: float,derivative_order: int=0) -> float:
    if not math.isfinite(u) or u<0 or u>1: raise OpenLoopFamilyError("normalized channel evaluation requires 0 <= u <= 1")
    if isinstance(schedule,PiecewiseLinearChannel): return float(_linear_eval(schedule,u,derivative_order))
    if isinstance(schedule,MonotoneCubicChannel): return float(_pchip_eval(schedule,u,derivative_order))
    return float(_fourier_eval(schedule,u,derivative_order))


def _with_value(component: ComponentControlState,field: str,value: float) -> ComponentControlState:
    if field=="detuning_gamma": return replace(component,detuning_gamma=float(value))
    if value<0: raise OpenLoopFamilyError("NEGATIVE_SATURATION: evaluation produced a negative saturation; no clipping is permitted")
    active=component.enabled and value>0
    return replace(component,saturation=float(value),active=active,off_reason=None if active else (component.off_reason or "explicit zero saturation"))


class OpenLoopFamilyPolicy:
    """Executable ABI-v2 policy backed only by a closed registered family."""
    def __init__(self,spec: OpenLoopPolicyFamilySpec):
        result=validate_family_spec(spec)
        if not result.valid: raise OpenLoopFamilyError("invalid open-loop family: "+"; ".join(item.message for item in result.errors))
        self.family_spec=spec; self.spec=spec.abi_spec; self.base=ControlPolicy(spec.abi_spec); self.hashes=family_hashes(spec)
        self.schedules={item.channel_id:item for item in spec.channel_schedules}
        self.channels={item.channel_id:item for item in spec.abi_spec.control_channels}

    def _evaluation_time(self,t: float) -> float:
        return self.base.sample(t).evaluation_time_s

    def _normalized_or_declared_hold(self,evaluation: float) -> float:
        if self.family_spec.t_start_s<=evaluation<=self.family_spec.t_end_s:
            return normalized_policy_time(evaluation,self.family_spec.t_start_s,self.family_spec.t_end_s)
        # The embedded ABI-v2 LINEAR_HOLD channel is the explicit endpoint-hold
        # declaration.  Other channel kinds do not acquire a hidden clamp.
        if not all(self.channels[channel_id].signal_kind is ChannelSignalKind.LINEAR_HOLD for channel_id in self.schedules):
            raise OpenLoopFamilyError("family evaluation lies outside its interval without an ABI endpoint-hold declaration")
        return 0.0 if evaluation<self.family_spec.t_start_s else 1.0

    def sample(self,t: float) -> PolicyState:
        base_state=self.base.sample(t); evaluation=base_state.evaluation_time_s
        is_handoff=self.spec.policy_family is ControlPolicyFamily.CHIRP_TO_TRAP_HANDOFF
        if is_handoff and evaluation>=self.family_spec.t_end_s: return replace(base_state,policy_hash=self.hashes.complete_policy_package)
        u=self._normalized_or_declared_hold(evaluation)
        values={channel_id:evaluate_channel(schedule,u) for channel_id,schedule in self.schedules.items()}
        pending=[channel for channel in self.spec.control_channels if channel.relationship is ChannelRelationship.AFFINE_DERIVED and channel.source_channel_id in values]
        while pending:
            progress=False
            for channel in pending[:]:
                if channel.source_channel_id not in values: continue
                values[channel.channel_id]=float(channel.affine_scale)*values[channel.source_channel_id]+float(channel.affine_offset);pending.remove(channel);progress=True
            if not progress: raise OpenLoopFamilyError("unresolved affine-derived family channel")
        components={item.component_id:item for item in base_state.components}
        for channel_id,value in values.items():
            channel=self.channels[channel_id]
            for target in channel.targets:
                if target.segment_id==base_state.segment_id: components[target.component_id]=_with_value(components[target.component_id],target.field,value)
        return replace(base_state,components=tuple(components[index] for index in (1,2,3,4)),policy_hash=self.hashes.complete_policy_package)

    def channel_derivative(self,channel_id: str,t: float,order: int=1) -> float:
        if order not in {1,2}: raise OpenLoopFamilyError("unsupported derivative request")
        evaluation=self._evaluation_time(t)
        if evaluation<self.family_spec.t_start_s or evaluation>self.family_spec.t_end_s: return 0.0
        duration=self.family_spec.t_end_s-self.family_spec.t_start_s;u=normalized_policy_time(evaluation,self.family_spec.t_start_s,self.family_spec.t_end_s)
        if channel_id in self.schedules: return evaluate_channel(self.schedules[channel_id],u,order)/(duration**order)
        channel=self.channels[channel_id]
        if channel.relationship is ChannelRelationship.AFFINE_DERIVED: return float(channel.affine_scale)*self.channel_derivative(channel.source_channel_id,t,order)
        if channel.signal_kind is ChannelSignalKind.FIXED: return 0.0
        if channel.signal_kind is ChannelSignalKind.LINEAR_HOLD:
            values=self.spec.parameter_values; initial,final,duration_s=(float(values[name]) for name in channel.parameter_names)
            return (final-initial)/duration_s if order==1 and 0<evaluation<duration_s else 0.0
        raise OpenLoopFamilyError("unsupported derivative request for channel")


def parameter_vector_layout(spec: OpenLoopPolicyFamilySpec) -> ParameterVectorLayout:
    rows=[]
    for schedule in sorted(spec.channel_schedules,key=lambda item:item.channel_id):
        units="Gamma" if schedule.field=="detuning_gamma" else "saturation_parameter"
        if isinstance(schedule,(PiecewiseLinearChannel,MonotoneCubicChannel)):
            iterable=((index,"knot_value") for index in schedule.adjustable_value_indices)
        else: iterable=((index,"fourier_coefficient") for index in schedule.adjustable_coefficient_indices)
        for element,kind in iterable:
            rows.append(ParameterVectorEntry(len(rows),schedule.channel_id,kind,element,f"{schedule.channel_id}.{kind}[{element}]",units,None,None,BoundBasis.UNKNOWN.value))
    payload=[_plain(item) for item in rows];digest=sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return ParameterVectorLayout(tuple(rows),digest)


def flatten_parameter_vector(spec: OpenLoopPolicyFamilySpec) -> PolicyParameterVector:
    layout=parameter_vector_layout(spec); schedules={item.channel_id:item for item in spec.channel_schedules};values=[]
    for entry in layout.entries:
        item=schedules[entry.channel_id]; source=item.knot_values if entry.parameter_kind=="knot_value" else item.coefficients;values.append(float(source[entry.element_index]))
    return PolicyParameterVector(layout.layout_hash,tuple(values))


def _embed_adjustable_parameters(spec: OpenLoopPolicyFamilySpec) -> OpenLoopPolicyFamilySpec:
    base=spec.abi_spec; kept_specs=tuple(item for item in base.parameter_specs if not item.name.startswith("run015__"));kept_values={key:value for key,value in base.parameter_values.items() if not key.startswith("run015__")};new_specs=list(kept_specs);new_values=dict(kept_values)
    for entry,value in zip(parameter_vector_layout(spec).entries,flatten_parameter_vector(spec).values):
        name="run015__"+entry.parameter_name.replace(".","__").replace("[","_").replace("]","")
        new_specs.append(PolicyParameterSpec(name,"Run 015 model-independent adjustable family parameter",(),entry.units,"float64",value,entry.lower_bound,entry.upper_bound,True,BoundBasis.UNKNOWN));new_values[name]=value
    notes=tuple(item for item in base.provenance.notes if not item.startswith("family_parameterization="))+(f"family_parameterization={spec.parameterization_version}",)
    provenance=replace(base.provenance,policy_family_id=spec.family_id.value,implementation_version=spec.implementation_version,generation_method="Run 015 closed-registry open-loop family",notes=notes)
    return replace(spec,abi_spec=replace(base,parameter_specs=tuple(new_specs),parameter_values=new_values,provenance=provenance,legacy_policy_type=spec.family_id.value))


def reconstruct_from_parameter_vector(spec: OpenLoopPolicyFamilySpec, vector: PolicyParameterVector) -> OpenLoopPolicyFamilySpec:
    layout=parameter_vector_layout(spec)
    if vector.layout_hash!=layout.layout_hash: raise OpenLoopFamilyError("PARAMETER_LAYOUT_MISMATCH: vector layout hash differs")
    if len(vector.values)!=len(layout.entries): raise OpenLoopFamilyError("PARAMETER_VECTOR_LENGTH_MISMATCH")
    if any(not math.isfinite(value) for value in vector.values): raise OpenLoopFamilyError("nonfinite parameter-vector value")
    by_channel={item.channel_id:item for item in spec.channel_schedules}
    for entry,value in zip(layout.entries,vector.values):
        item=by_channel[entry.channel_id]
        if entry.parameter_kind=="knot_value":
            values=list(item.knot_values);values[entry.element_index]=float(value);by_channel[entry.channel_id]=replace(item,knot_values=tuple(values))
        else:
            values=list(item.coefficients);values[entry.element_index]=float(value);by_channel[entry.channel_id]=replace(item,coefficients=tuple(values))
    rebuilt=replace(spec,channel_schedules=tuple(by_channel[item.channel_id] for item in spec.channel_schedules))
    rebuilt=_embed_adjustable_parameters(rebuilt);result=validate_family_spec(rebuilt)
    if not result.valid: raise OpenLoopFamilyError("reconstructed policy is invalid: "+"; ".join(item.message for item in result.errors))
    return rebuilt


def smoothness_ledger(spec: OpenLoopPolicyFamilySpec) -> SmoothnessLedger:
    duration=spec.t_end_s-spec.t_start_s; knots=sorted({spec.t_start_s+u*duration for item in spec.channel_schedules if isinstance(item,(PiecewiseLinearChannel,MonotoneCubicChannel)) for u in item.knot_u[1:-1]});events=tuple(sorted(item.event_time_s for item in spec.abi_spec.events))
    if spec.family_id is OpenLoopFamilyId.PIECEWISE_LINEAR: first="piecewise constant; discontinuous at interior knots";second="not classically defined at interior knots";endpoint="one-sided slopes"
    elif spec.family_id is OpenLoopFamilyId.MONOTONE_CUBIC: first="continuous within family interval";second="piecewise continuous and generally discontinuous at knots";endpoint="deterministic one-sided Fritsch-Carlson tangents"
    else: first="continuous within family interval";second="continuous within family interval";endpoint="analytic finite-basis derivatives; values, not derivatives, are endpoint-preserved"
    discontinuities=tuple(sorted(set(events if spec.family_id is OpenLoopFamilyId.FOURIER_CORRECTION else (*events,*knots))))
    return SmoothnessLedger(spec.family_id.value,"continuous within family interval",first,second,tuple(knots),events,discontinuities,endpoint)


def _monotonicity(values: np.ndarray,requested: bool) -> MonotonicityClassification:
    if not requested:return MonotonicityClassification.MONOTONICITY_NOT_REQUESTED
    diff=np.diff(values);return MonotonicityClassification.MONOTONE if (np.all(diff>=-1e-12) or np.all(diff<=1e-12)) else MonotonicityClassification.NONMONOTONE


def structural_metrics(spec: OpenLoopPolicyFamilySpec) -> PolicyStructuralMetrics:
    policy=OpenLoopFamilyPolicy(spec);duration=spec.t_end_s-spec.t_start_s;grid=np.linspace(0,1,4097);rows=[]
    for item in spec.channel_schedules:
        values=np.array([evaluate_channel(item,float(u),0) for u in grid]); first=np.array([evaluate_channel(item,float(u),1) for u in grid if not (isinstance(item,PiecewiseLinearChannel) and any(float(u)==k for k in item.knot_u[1:-1]))])/duration
        second=None if isinstance(item,PiecewiseLinearChannel) else max(abs(evaluate_channel(item,float(u),2))/duration**2 for u in grid)
        requested=(not isinstance(item,FourierCorrectionChannel) and item.monotonicity is not MonotonicityMode.UNRESTRICTED) or (isinstance(item,FourierCorrectionChannel) and item.monotonicity_requested)
        count=len(item.knot_u) if not isinstance(item,FourierCorrectionChannel) else item.harmonic_count;discontinuities=max(0,len(item.knot_u)-2) if isinstance(item,PiecewiseLinearChannel) else 0
        rows.append(ChannelStructuralMetric(item.channel_id,item.field,float(np.sum(np.abs(np.diff(values)))),float(np.max(np.abs(first))),None if second is None else float(second),float(values[-1]-values[0]),count,discontinuities,_monotonicity(values,requested),float(values.min()),float(values.max())))
    layout=parameter_vector_layout(spec);boundaries=len(smoothness_ledger(spec).structural_knot_times_s)
    return PolicyStructuralMetrics(tuple(rows),sum((len(item.knot_values) if not isinstance(item,FourierCorrectionChannel) else len(item.coefficients)) for item in spec.channel_schedules),len(layout.entries),len(spec.abi_spec.events),boundaries,{"family_id":spec.family_id.value,"channel_schedule_count":len(spec.channel_schedules)},policy.hashes.complete_policy_package,"READY_FOR_RUN014_SYNTHETIC_COMPILATION")


def compose_with_handoff(spec: OpenLoopPolicyFamilySpec, handoff_abi_spec: ControlPolicySpec, channel_id_mapping: Mapping[str,str]) -> OpenLoopPolicyFamilySpec:
    matches=[event for event in handoff_abi_spec.events if event.event_time_s==spec.t_end_s and event.event_id=="chirp_to_trap_handoff"]
    if len(matches)!=1: raise OpenLoopFamilyError("EVENT_FAMILY_BOUNDARY_CONFLICT: exactly one handoff event must equal t_end")
    if set(channel_id_mapping)!=set(item.channel_id for item in spec.channel_schedules): raise OpenLoopFamilyError("ambiguous baseline reference: every family channel requires an explicit handoff mapping")
    target_ids={item.channel_id for item in handoff_abi_spec.control_channels}
    if any(value not in target_ids for value in channel_id_mapping.values()): raise OpenLoopFamilyError("handoff mapping contains an unresolved target channel")
    schedules=tuple(replace(item,channel_id=channel_id_mapping[item.channel_id]) for item in spec.channel_schedules)
    composed=replace(spec,abi_spec=handoff_abi_spec,channel_schedules=schedules,supported_event_behavior="EXPLICIT_T_LT_TAU_PRE_T_GE_TAU_POST")
    return _embed_adjustable_parameters(composed)


def load_family_config(path: str|Path) -> OpenLoopPolicyFamilySpec:
    source=Path(path);data=yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data,dict): raise OpenLoopFamilyError("family YAML root must be a mapping")
    _reject_executable_content(data)
    required=("schema_version","family_id","family_name","parameterization_version","implementation_version","abi_source_config","t_start_s","t_end_s","supported_channel_fields","supported_event_behavior","statefulness","serialization_contract","channel_schedules","provenance")
    missing=[key for key in required if key not in data]
    if missing: raise OpenLoopFamilyError(f"family config missing {missing}; hidden defaults are forbidden")
    abi_path=(source.parent/str(data["abi_source_config"])).resolve();base=legacy_policy_to_v2_spec(load_policy(abi_path),source_path=abi_path)
    schedules=[]
    for row in data["channel_schedules"]:
        kind=row["schedule_type"]
        if kind=="PIECEWISE_LINEAR": schedules.append(PiecewiseLinearChannel(row["channel_id"],row["field"],tuple(row["knot_u"]),tuple(row["knot_values"]),MonotonicityMode(row["monotonicity"]),tuple(row["adjustable_value_indices"]),row["fixed_endpoint_values"],row["minimum_knot_separation"]))
        elif kind=="MONOTONE_CUBIC": schedules.append(MonotoneCubicChannel(row["channel_id"],row["field"],tuple(row["knot_u"]),tuple(row["knot_values"]),MonotonicityMode(row["monotonicity"]),tuple(row["adjustable_value_indices"]),row["fixed_endpoint_values"],row["minimum_knot_separation"]))
        elif kind=="FOURIER_CORRECTION": schedules.append(FourierCorrectionChannel(row["channel_id"],row["field"],row["baseline_start"],row["baseline_end"],row["harmonic_count"],tuple(row["coefficients"]),tuple(row["adjustable_coefficient_indices"]),row["coefficient_units"],row["basis_id"],row["correction_amplitude_bound"],row["monotonicity_requested"]))
        else: raise OpenLoopFamilyError(f"unknown schedule_type {kind!r}")
    p=data["provenance"];source_hash=sha256(source.read_bytes()).hexdigest();provenance=FamilyProvenance(p["provenance_class"],p["source_description"],str(source),source_hash,p["interpretation_notes"])
    spec=OpenLoopPolicyFamilySpec(data["schema_version"],base.schema_version,OpenLoopFamilyId(data["family_id"]),data["family_name"],str(data["parameterization_version"]),data["implementation_version"],tuple(data["supported_channel_fields"]),data["supported_event_behavior"],data["statefulness"],data["serialization_contract"],float(data["t_start_s"]),float(data["t_end_s"]),base,tuple(schedules),provenance)
    spec=_embed_adjustable_parameters(spec);result=validate_family_spec(spec)
    if not result.valid: raise OpenLoopFamilyError("invalid family config: "+"; ".join(item.message for item in result.errors))
    return spec


def compile_family_policy(spec: OpenLoopPolicyFamilySpec,profile: Any,request: Any):
    """Route a registered family through the Run 014 compiler, without a fork."""
    from .control_schedule_compiler import compile_control_schedule
    policy=OpenLoopFamilyPolicy(spec);hashes=family_hashes(spec)
    return compile_control_schedule(spec.abi_spec,profile,request,policy_evaluator=policy,policy_hash_override=hashes.complete_policy_package,source_policy_specification_hash_override=hashes.family_specification)
