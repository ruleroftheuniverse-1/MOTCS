"""Versioned model-independent apparatus constraint profiles for Run 014."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Any, Mapping


APPARATUS_SCHEMA_VERSION = "mgf-mot-apparatus-constraints-v1"
COMPILED_SCHEDULE_SCHEMA_VERSION = "mgf-mot-compiled-control-schedule-v1"
RUN014_LABEL = "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_014_APPARATUS_SCHEDULE_COMPILER_ONLY"


class KnowledgeState(str, Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    UNBOUNDED = "UNBOUNDED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConstraintProvenanceClass(str, Enum):
    SOURCE_SUPPORTED = "SOURCE_SUPPORTED"
    APPARATUS_ASSUMPTION = "APPARATUS_ASSUMPTION"
    ENGINEERING_STRESS_TEST = "ENGINEERING_STRESS_TEST"
    SYNTHETIC_TEST_FIXTURE = "SYNTHETIC_TEST_FIXTURE"
    UNKNOWN = "UNKNOWN"


class HardwareValidationStatus(str, Enum):
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    SOURCE_INCOMPLETE = "SOURCE_INCOMPLETE"
    SOURCE_SUPPORTED_NOT_HARDWARE_VALIDATED = "SOURCE_SUPPORTED_NOT_HARDWARE_VALIDATED"
    HARDWARE_VALIDATED = "HARDWARE_VALIDATED"


class ClockRoundingMode(str, Enum):
    REQUIRE_EXACT = "REQUIRE_EXACT"
    FLOOR = "FLOOR"
    CEIL = "CEIL"
    NEAREST_TIES_TO_EVEN = "NEAREST_TIES_TO_EVEN"


class EventExecutionRule(str, Enum):
    REQUIRE_EXACT_TIME = "REQUIRE_EXACT_TIME"
    SNAP_FLOOR = "SNAP_FLOOR"
    SNAP_CEIL = "SNAP_CEIL"
    SNAP_NEAREST = "SNAP_NEAREST"
    REJECT_IF_UNALIGNED = "REJECT_IF_UNALIGNED"


class ActivationRestriction(str, Enum):
    ALLOWED = "ALLOWED"
    FORBIDDEN = "FORBIDDEN"
    UNKNOWN = "UNKNOWN"


class CouplingRuleKind(str, Enum):
    AFFINE_DERIVATION = "AFFINE_DERIVATION"
    SIMULTANEOUS_UPDATE = "SIMULTANEOUS_UPDATE"
    ABSTRACT_AGGREGATE = "ABSTRACT_AGGREGATE"


@dataclass(frozen=True)
class ConstraintProvenance:
    provenance_class: ConstraintProvenanceClass
    source_description: str
    source_path_or_citation: str | None
    source_hash: str | None
    interpretation_notes: str
    directly_reported: bool


@dataclass(frozen=True)
class ConstraintValue:
    knowledge: KnowledgeState
    value: Any | None
    units: str | None
    provenance: ConstraintProvenance
    not_applicable_reason: str | None = None


@dataclass(frozen=True)
class ChannelCapabilitySpec:
    channel_id: str
    field: str
    minimum: ConstraintValue
    maximum: ConstraintValue
    update_period: ConstraintValue
    resolution: ConstraintValue
    maximum_first_derivative: ConstraintValue
    maximum_second_difference: ConstraintValue
    minimum_dwell_time: ConstraintValue
    allowed_values: ConstraintValue
    activation_restriction: ActivationRestriction = ActivationRestriction.ALLOWED
    deactivation_restriction: ActivationRestriction = ActivationRestriction.ALLOWED


@dataclass(frozen=True)
class CommandClockSpec:
    clock_origin_s: float
    update_period: ConstraintValue
    shared_clock: bool
    rounding_mode: ClockRoundingMode
    minimum_command_separation: ConstraintValue
    simultaneous_updates_atomic: bool
    continuous_identity_binding: bool = False
    allowed_time_rule: str = "clock_origin_plus_integer_update_period"


@dataclass(frozen=True)
class LatencySpec:
    fixed_latency: ConstraintValue


@dataclass(frozen=True)
class EventExecutionSpec:
    rule: EventExecutionRule
    atomic_update_required: bool


@dataclass(frozen=True)
class ApparatusCouplingRule:
    rule_id: str
    kind: CouplingRuleKind
    channel_ids: tuple[str, ...]
    description: str
    provenance: ConstraintProvenance


@dataclass(frozen=True)
class ApparatusConstraintSet:
    schema_version: str
    profile_id: str
    profile_name: str
    profile_description: str
    channel_capabilities: tuple[ChannelCapabilitySpec, ...]
    command_clock: CommandClockSpec
    latency: LatencySpec
    event_execution: EventExecutionSpec
    aggregate_saturation_budget: ConstraintValue
    provenance: ConstraintProvenance
    complete: bool
    hardware_validation_status: HardwareValidationStatus
    coupling_rules: tuple[ApparatusCouplingRule, ...] = ()


@dataclass(frozen=True)
class ApparatusValidationIssue:
    code: str
    severity: str
    field_path: str
    message: str
    offending_value: Any
    units: str | None
    suggested_correction: str | None


@dataclass(frozen=True)
class ApparatusValidationResult:
    issues: tuple[ApparatusValidationIssue, ...]

    @property
    def valid(self) -> bool: return not any(item.severity == "ERROR" for item in self.issues)

    @property
    def complete(self) -> bool: return self.valid and not any(item.code == "UNKNOWN_CAPABILITY" for item in self.issues)


def _issue(code: str, path: str, message: str, value: Any, units: str | None = None, correction: str | None = None, severity: str = "ERROR") -> ApparatusValidationIssue:
    return ApparatusValidationIssue(code, severity, path, message, value, units, correction)


def _validate_value(value: ConstraintValue, path: str, *, positive: bool = False) -> list[ApparatusValidationIssue]:
    issues = []
    if value.knowledge is KnowledgeState.KNOWN:
        if value.value is None or not value.units:
            issues.append(_issue("INVALID_KNOWLEDGE_VALUE_COMBINATION", path, "KNOWN requires a value and units", value.value, value.units, "supply both"))
        elif isinstance(value.value, (int, float)) and (not math.isfinite(float(value.value)) or (positive and float(value.value) <= 0)):
            issues.append(_issue("INVALID_NUMERICAL_CONSTRAINT", path, "known numerical constraint is nonfinite or nonpositive", value.value, value.units, "supply a finite positive value"))
    elif value.knowledge is KnowledgeState.UNKNOWN:
        if value.value is not None:
            issues.append(_issue("UNKNOWN_INTERPRETED_AS_VALUE", path, "UNKNOWN cannot carry or imply a capability value", value.value, value.units, "use null value"))
        issues.append(_issue("UNKNOWN_CAPABILITY", path, "capability remains explicitly unknown", None, value.units, "supply source-supported capability before strict compilation", "WARNING"))
    elif value.knowledge is KnowledgeState.UNBOUNDED:
        if value.value is not None:
            issues.append(_issue("INVALID_KNOWLEDGE_VALUE_COMBINATION", path, "UNBOUNDED must not carry a finite value", value.value, value.units, "set value null"))
    elif value.knowledge is KnowledgeState.NOT_APPLICABLE:
        if value.value is not None or not value.not_applicable_reason:
            issues.append(_issue("INVALID_KNOWLEDGE_VALUE_COMBINATION", path, "NOT_APPLICABLE requires null value and an explicit reason", value.value, value.units, "add the reason"))
    if not value.provenance.source_description:
        issues.append(_issue("MISSING_CONSTRAINT_PROVENANCE", path + ".provenance", "constraint provenance requires a source description", "", value.units, "describe source or synthetic fixture"))
    return issues


def validate_apparatus_profile(profile: ApparatusConstraintSet) -> ApparatusValidationResult:
    issues: list[ApparatusValidationIssue] = []
    if profile.schema_version != APPARATUS_SCHEMA_VERSION: issues.append(_issue("UNKNOWN_SCHEMA_VERSION", "$.schema_version", "unknown apparatus schema", profile.schema_version, None, f"use {APPARATUS_SCHEMA_VERSION}"))
    if profile.hardware_validation_status is HardwareValidationStatus.HARDWARE_VALIDATED: issues.append(_issue("HARDWARE_VALIDATION_NOT_AUTHORIZED", "$.hardware_validation_status", "Run 014 cannot emit HARDWARE_VALIDATED", profile.hardware_validation_status.value, None, "use a nonvalidated status"))
    ids = [item.channel_id for item in profile.channel_capabilities]
    if len(ids) != len(set(ids)): issues.append(_issue("CONFLICTING_CHANNEL_CAPABILITY_OWNERSHIP", "$.channel_capabilities", "channel capability IDs must be unique", ids))
    if profile.command_clock.allowed_time_rule != "clock_origin_plus_integer_update_period": issues.append(_issue("UNKNOWN_ALLOWED_TIME_RULE","$.command_clock.allowed_time_rule","unknown allowed-command-time rule fails closed",profile.command_clock.allowed_time_rule))
    coupling_ids=[item.rule_id for item in profile.coupling_rules]
    if len(coupling_ids)!=len(set(coupling_ids)): issues.append(_issue("DUPLICATE_COUPLING_RULE_ID","$.coupling_rules","coupling rule IDs must be unique",coupling_ids))
    for index,rule in enumerate(profile.coupling_rules):
        missing=sorted(set(rule.channel_ids)-set(ids))
        if missing: issues.append(_issue("UNRESOLVED_COUPLING_CHANNEL",f"$.coupling_rules[{index}].channel_ids","coupling references unresolved channels",missing))
        if not rule.description or not rule.provenance.source_description: issues.append(_issue("MISSING_CONSTRAINT_PROVENANCE",f"$.coupling_rules[{index}]","coupling rules require description and provenance",rule.rule_id))
    for index, capability in enumerate(profile.channel_capabilities):
        path = f"$.channel_capabilities[{index}]"
        if capability.field not in {"detuning_gamma", "saturation"}: issues.append(_issue("UNKNOWN_CAPABILITY_TYPE", path + ".field", "unknown capability field fails closed", capability.field))
        for name in ("minimum", "maximum", "update_period", "resolution", "maximum_first_derivative", "maximum_second_difference", "minimum_dwell_time", "allowed_values"):
            positive = name in {"update_period", "resolution", "minimum_dwell_time"}
            issues.extend(_validate_value(getattr(capability, name), f"{path}.{name}", positive=positive))
        if capability.allowed_values.knowledge is KnowledgeState.KNOWN:
            allowed=capability.allowed_values.value
            if not isinstance(allowed,(tuple,list)) or not allowed or any(not isinstance(item,(int,float)) or not math.isfinite(float(item)) for item in allowed):
                issues.append(_issue("INVALID_ALLOWED_VALUE_SET",path+".allowed_values","allowed values must be a nonempty finite numerical sequence",allowed,capability.allowed_values.units))
        for name in ("maximum_first_derivative","maximum_second_difference"):
            item=getattr(capability,name)
            if item.knowledge is KnowledgeState.KNOWN and float(item.value)<0:
                issues.append(_issue("INVALID_NUMERICAL_CONSTRAINT",f"{path}.{name}","a maximum derivative cannot be negative",item.value,item.units))
        if ActivationRestriction.UNKNOWN in {capability.activation_restriction,capability.deactivation_restriction}:
            issues.append(_issue("UNKNOWN_CAPABILITY",path+".activation_restriction","activation/deactivation behavior remains explicitly unknown",None,None,"declare the apparatus behavior","WARNING"))
        if capability.minimum.knowledge is KnowledgeState.KNOWN and capability.maximum.knowledge is KnowledgeState.KNOWN and capability.minimum.value > capability.maximum.value:
            issues.append(_issue("INVALID_RANGE", path, "minimum exceeds maximum", (capability.minimum.value, capability.maximum.value), capability.minimum.units))
    issues.extend(_validate_value(profile.command_clock.update_period, "$.command_clock.update_period", positive=not profile.command_clock.continuous_identity_binding))
    issues.extend(_validate_value(profile.command_clock.minimum_command_separation, "$.command_clock.minimum_command_separation"))
    issues.extend(_validate_value(profile.latency.fixed_latency, "$.latency.fixed_latency"))
    issues.extend(_validate_value(profile.aggregate_saturation_budget, "$.aggregate_saturation_budget"))
    has_unknown = any(item.code == "UNKNOWN_CAPABILITY" for item in issues)
    if not math.isfinite(profile.command_clock.clock_origin_s): issues.append(_issue("INVALID_CLOCK_ORIGIN","$.command_clock.clock_origin_s","clock origin must be finite",profile.command_clock.clock_origin_s,"s"))
    if profile.command_clock.minimum_command_separation.knowledge is KnowledgeState.KNOWN and float(profile.command_clock.minimum_command_separation.value)<0: issues.append(_issue("INVALID_NUMERICAL_CONSTRAINT","$.command_clock.minimum_command_separation","minimum separation cannot be negative",profile.command_clock.minimum_command_separation.value,"s"))
    if profile.latency.fixed_latency.knowledge is KnowledgeState.KNOWN and float(profile.latency.fixed_latency.value)<0: issues.append(_issue("INVALID_NUMERICAL_CONSTRAINT","$.latency.fixed_latency","latency cannot be negative",profile.latency.fixed_latency.value,"s"))
    if profile.complete and has_unknown: issues.append(_issue("FALSE_COMPLETENESS_DECLARATION", "$.complete", "profile with unknown capabilities cannot be complete", True))
    return ApparatusValidationResult(tuple(issues))


def _plain(value: Any) -> Any:
    from dataclasses import is_dataclass
    if isinstance(value, Enum): return value.value
    if is_dataclass(value): return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping): return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(item) for item in value]
    return value


def canonical_apparatus_json(profile: ApparatusConstraintSet) -> str:
    return json.dumps(_plain(profile), sort_keys=True, separators=(",", ":"), allow_nan=False)


def apparatus_profile_hash(profile: ApparatusConstraintSet) -> str:
    return sha256(canonical_apparatus_json(profile).encode()).hexdigest()


def _provenance(kind: ConstraintProvenanceClass, description: str) -> ConstraintProvenance:
    return ConstraintProvenance(kind, description, None, None, description, False)


def _known(value: Any, units: str, description: str = "synthetic Run 014 test fixture") -> ConstraintValue:
    return ConstraintValue(KnowledgeState.KNOWN, value, units, _provenance(ConstraintProvenanceClass.SYNTHETIC_TEST_FIXTURE, description))


def _unbounded(units: str | None, description: str = "explicit idealized unbounded synthetic capability") -> ConstraintValue:
    return ConstraintValue(KnowledgeState.UNBOUNDED, None, units, _provenance(ConstraintProvenanceClass.SYNTHETIC_TEST_FIXTURE, description))


def _na(reason: str) -> ConstraintValue:
    return ConstraintValue(KnowledgeState.NOT_APPLICABLE, None, None, _provenance(ConstraintProvenanceClass.SYNTHETIC_TEST_FIXTURE, reason), reason)


def _unknown(units: str | None, note: str) -> ConstraintValue:
    return ConstraintValue(KnowledgeState.UNKNOWN, None, units, _provenance(ConstraintProvenanceClass.UNKNOWN, note))


def _capability(channel_id: str, field: str, *, period: float | None, resolution: float | None, rate: float | None = None, second: float | None = None, dwell: float | None = None, range_: tuple[float,float] | None = None) -> ChannelCapabilitySpec:
    units = "Gamma" if field == "detuning_gamma" else "saturation_parameter"
    derivative_units = "Gamma/s" if field == "detuning_gamma" else "saturation_parameter/s"
    return ChannelCapabilitySpec(
        channel_id, field,
        _unbounded(units) if range_ is None else _known(range_[0], units), _unbounded(units) if range_ is None else _known(range_[1], units),
        _unbounded("s") if period is None else _known(period, "s"),
        _na("continuous values") if resolution is None else _known(resolution, units),
        _unbounded(derivative_units) if rate is None else _known(rate, derivative_units),
        _unbounded(f"{derivative_units}/s") if second is None else _known(second, f"{derivative_units}/s"),
        _na("no minimum dwell") if dwell is None else _known(dwell, "s"), _na("no discrete allowed-value set"),
    )


def synthetic_identity_profile(channel_fields: Mapping[str,str]) -> ApparatusConstraintSet:
    provenance = _provenance(ConstraintProvenanceClass.SYNTHETIC_TEST_FIXTURE, "formal continuous identity profile; not hardware")
    return ApparatusConstraintSet(
        APPARATUS_SCHEMA_VERSION, "synthetic_identity", "Synthetic identity profile", "Formal exact continuous binding with zero latency and no quantization; not a finite-clock device",
        tuple(_capability(channel, field, period=None, resolution=None) for channel, field in sorted(channel_fields.items())),
        CommandClockSpec(0.0, _unbounded("s"), True, ClockRoundingMode.REQUIRE_EXACT, _na("continuous binding"), True, True),
        LatencySpec(_known(0.0, "s")), EventExecutionSpec(EventExecutionRule.REQUIRE_EXACT_TIME, True), _unbounded("aggregate_saturation_parameter"), provenance, True, HardwareValidationStatus.SYNTHETIC_ONLY,
    )


def synthetic_quantized_profile(channel_fields: Mapping[str,str]) -> ApparatusConstraintSet:
    provenance = _provenance(ConstraintProvenanceClass.SYNTHETIC_TEST_FIXTURE, "synthetic quantization fixture; not hardware")
    return ApparatusConstraintSet(
        APPARATUS_SCHEMA_VERSION, "synthetic_quantized", "Synthetic quantized profile", "Deterministic finite-clock fixture",
        tuple(_capability(channel, field, period=0.0003, resolution=0.25 if field == "detuning_gamma" else 0.05, range_=(-10,3) if field == "detuning_gamma" else (0,4)) for channel, field in sorted(channel_fields.items())),
        CommandClockSpec(0.0, _known(0.0003,"s"), True, ClockRoundingMode.NEAREST_TIES_TO_EVEN, _known(0.0003,"s"), True),
        LatencySpec(_known(0.0,"s")), EventExecutionSpec(EventExecutionRule.SNAP_NEAREST, True), _unbounded("aggregate_saturation_parameter"), provenance, True, HardwareValidationStatus.SYNTHETIC_ONLY,
    )


def synthetic_rate_limited_profile(channel_fields: Mapping[str,str]) -> ApparatusConstraintSet:
    base = synthetic_quantized_profile(channel_fields)
    capabilities = tuple(_capability(item.channel_id, item.field, period=0.0003, resolution=0.25 if item.field=="detuning_gamma" else 0.05, rate=10.0, range_=(-10,3) if item.field=="detuning_gamma" else (0,4)) for item in base.channel_capabilities)
    return ApparatusConstraintSet(**{**asdict(base), "profile_id":"synthetic_rate_limited", "profile_name":"Synthetic deliberately rate-limited profile", "channel_capabilities":capabilities, "command_clock":base.command_clock, "latency":base.latency, "event_execution":base.event_execution, "aggregate_saturation_budget":base.aggregate_saturation_budget, "provenance":base.provenance, "hardware_validation_status":base.hardware_validation_status})


def source_incomplete_profile(channel_fields: Mapping[str,str]) -> ApparatusConstraintSet:
    provenance = _provenance(ConstraintProvenanceClass.UNKNOWN, "No source-supported apparatus capability table is currently available")
    capabilities = tuple(ChannelCapabilitySpec(channel, field, *([_unknown("Gamma" if field=="detuning_gamma" else "saturation_parameter", "unknown source capability")]*2), _unknown("s","unknown update period"), _unknown("Gamma" if field=="detuning_gamma" else "saturation_parameter","unknown resolution"), _unknown("Gamma/s" if field=="detuning_gamma" else "saturation_parameter/s","unknown rate"), _unknown(None,"unknown second difference"), _unknown("s","unknown dwell"), _unknown(None,"unknown allowed values"), ActivationRestriction.UNKNOWN, ActivationRestriction.UNKNOWN) for channel,field in sorted(channel_fields.items()))
    return ApparatusConstraintSet(APPARATUS_SCHEMA_VERSION,"source_incomplete","Source-incomplete profile","Explicit unknowns; cannot support hardware claims",capabilities,CommandClockSpec(0.0,_unknown("s","unknown clock"),True,ClockRoundingMode.REQUIRE_EXACT,_unknown("s","unknown separation"),False),LatencySpec(_unknown("s","unknown latency")),EventExecutionSpec(EventExecutionRule.REJECT_IF_UNALIGNED,False),_unknown("aggregate_saturation_parameter","unknown abstract budget"),provenance,False,HardwareValidationStatus.SOURCE_INCOMPLETE)
