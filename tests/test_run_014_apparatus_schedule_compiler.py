from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path

import pytest

from mgf_mot.apparatus_constraints import (
    ConstraintProvenance, ConstraintProvenanceClass, ConstraintValue,
    HardwareValidationStatus, KnowledgeState, LatencySpec, RUN014_LABEL,
    apparatus_profile_hash, canonical_apparatus_json, source_incomplete_profile,
    synthetic_identity_profile, synthetic_quantized_profile,
    synthetic_rate_limited_profile, validate_apparatus_profile,
)
from mgf_mot.control_policy_abi import (
    ChannelRelationship, ChannelSignalKind, ChannelTarget, ControlChannelSpec,
    ControlPolicy,
)
from mgf_mot.control_policy_serialization import control_policy_hashes
from mgf_mot.control_schedule_compiler import (
    CompilationMode, CompilationReport, CompilationRequest, CompilationStatus,
    InitialStateMode, ReconstructionMode, canonical_compiled_schedule_json,
    compilation_request_hash, compile_control_schedule,
)
from mgf_mot.legacy_policy_adapter import legacy_policy_to_v2_spec
from mgf_mot.policies import load_policy


ROOT=Path(__file__).resolve().parents[1]
CONFIGS={name:ROOT/"configs"/file for name,file in {"static":"rodriguez_static_3.yaml","chirp":"rodriguez_baseline_linear_chirp.yaml","handoff":"rodriguez_chirp_to_3_plus_1_handoff.yaml"}.items()}
DETAIL=ROOT/"outputs/provisional/apparatus_schedule_compiler/run_014"
METADATA=DETAIL/f"{RUN014_LABEL}_metadata.json";REPORT=ROOT/"outputs/provisional"/f"{RUN014_LABEL}.md"

@pytest.fixture(scope="module")
def specs(): return {name:legacy_policy_to_v2_spec(load_policy(path),source_path=path) for name,path in CONFIGS.items()}
def _fields(spec): return {channel.channel_id:channel.field for channel in spec.control_channels}
def _request(spec,profile,mode=CompilationMode.SAMPLE_AND_HOLD,*,start=0.0,end=.002,pre=None,diagnostic=None,reconstruction=ReconstructionMode.ZERO_ORDER_HOLD):
    return CompilationRequest(control_policy_hashes(spec).full_policy_package,apparatus_profile_hash(profile),mode,start,end,InitialStateMode.POLICY_STATE_AT_START,None,pre,diagnostic,reconstruction)
def _known(value,units): return ConstraintValue(KnowledgeState.KNOWN,value,units,ConstraintProvenance(ConstraintProvenanceClass.SYNTHETIC_TEST_FIXTURE,"test fixture",None,None,"test",False))

def test_unknown_is_not_unbounded_and_known_constraints_need_units_and_provenance(specs):
    profile=source_incomplete_profile(_fields(specs["static"])); result=validate_apparatus_profile(profile)
    assert result.valid and not result.complete
    assert any(issue.code=="UNKNOWN_CAPABILITY" for issue in result.issues)
    strict,_=compile_control_schedule(specs["static"],profile,_request(specs["static"],profile))
    assert strict.status is CompilationStatus.COMPILATION_INVALID
    assert any(issue.code=="INCOMPLETE_STRICT_PROFILE" for issue in strict.violations)
    bad=replace(profile.command_clock.update_period,knowledge=KnowledgeState.KNOWN,value=.001,units=None)
    invalid=replace(profile,command_clock=replace(profile.command_clock,update_period=bad),complete=False)
    assert any(issue.code=="INVALID_KNOWLEDGE_VALUE_COMBINATION" for issue in validate_apparatus_profile(invalid).issues)
    assert all(item.provenance.source_description for cap in synthetic_quantized_profile(_fields(specs["static"])).channel_capabilities for item in (cap.minimum,cap.maximum,cap.update_period,cap.resolution))

def test_horizons_are_mandatory_finite_and_identity_profile_is_exact(specs):
    for spec in specs.values():
        profile=synthetic_identity_profile(_fields(spec));request=_request(spec,profile,CompilationMode.EXACT_ONLY,reconstruction=ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING)
        compiled,realized=compile_control_schedule(spec,profile,request)
        assert compiled.status is CompilationStatus.COMPILED_EXACT and realized is not None
        for time in (0,.0001,.0005,math.nextafter(.001,0),.001,math.nextafter(.001,math.inf),.002):
            a,b=ControlPolicy(spec).sample(time),realized.sample(time)
            assert tuple((x.detuning_gamma,x.saturation,x.enabled,x.active) for x in a.components)==tuple((x.detuning_gamma,x.saturation,x.enabled,x.active) for x in b.components)
            assert b.component_order==(1,2,3,4)
    profile=synthetic_identity_profile(_fields(specs["static"]));bad=_request(specs["static"],profile,CompilationMode.EXACT_ONLY,end=math.inf,reconstruction=ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING)
    compiled,_=compile_control_schedule(specs["static"],profile,bad)
    assert compiled.status is CompilationStatus.COMPILATION_INVALID
    assert any(issue.code=="INVALID_COMPILATION_HORIZON" for issue in compiled.violations)

def test_shared_channel_compiles_once_and_affine_derived_stays_consistent(specs):
    spec=specs["chirp"];profile=synthetic_quantized_profile(_fields(spec));compiled,realized=compile_control_schedule(spec,profile,_request(spec,profile))
    assert compiled.status is CompilationStatus.COMPILED_APPROXIMATE
    shared=next(channel for channel in spec.control_channels if channel.relationship is ChannelRelationship.SHARED)
    assert {command.channel_id for command in compiled.commands if command.channel_id==shared.channel_id}=={shared.channel_id}
    state=realized.sample(.0005);assert state.components[0].detuning_gamma==state.components[1].detuning_gamma==state.components[2].detuning_gamma
    base=specs["static"];old=next(c for c in base.control_channels if c.channel_id=="static_component_2_saturation")
    derived=ControlChannelSpec(old.channel_id,ChannelRelationship.AFFINE_DERIVED,ChannelSignalKind.AFFINE,"saturation",old.targets,source_channel_id="static_component_1_saturation",affine_scale=1.0,affine_offset=0.0)
    affine=replace(base,control_channels=tuple(derived if c.channel_id==old.channel_id else c for c in base.control_channels))
    p=synthetic_quantized_profile(_fields(affine));c,r=compile_control_schedule(affine,p,_request(affine,p))
    assert c.status is CompilationStatus.COMPILED_APPROXIMATE
    assert r.sample(.001).components[0].saturation==r.sample(.001).components[1].saturation

def test_event_clock_latency_and_handoff_boundaries_are_explicit(specs):
    spec=specs["handoff"];profile=synthetic_quantized_profile(_fields(spec));compiled,realized=compile_control_schedule(spec,profile,_request(spec,profile))
    assert len(compiled.events)==1
    event=compiled.events[0];assert event.requested_time_s==.001 and event.realized_time_s==.0009 and event.displacement_s==pytest.approx(-.0001)
    assert tuple(item.component_id for item in event.left_component_states)==(1,2,3,4)
    assert tuple(item.component_id for item in event.right_component_states)==(1,2,3,4)
    assert event.atomic
    assert realized.sample(math.nextafter(event.realized_time_s,0)).segment_id=="pre_handoff"
    assert realized.sample(event.realized_time_s).segment_id=="post_handoff"
    event_commands=[item for item in compiled.commands if item.event_id==event.event_id]
    assert event_commands and all(item.atomic_group_id for item in event_commands)
    assert all(item.requested_effective_time_s==.001 and item.actual_effective_time_s==.0009 for item in event_commands)

    latency_profile=replace(profile,latency=LatencySpec(_known(.0001,"s")))
    no_preroll,_=compile_control_schedule(spec,latency_profile,_request(spec,latency_profile))
    assert no_preroll.status is CompilationStatus.COMPILATION_INFEASIBLE
    assert any(issue.code=="INSUFFICIENT_PRE_ROLL" for issue in no_preroll.violations)
    with_preroll,_=compile_control_schedule(spec,latency_profile,_request(spec,latency_profile,pre=.0001))
    assert with_preroll.status is CompilationStatus.COMPILED_APPROXIMATE
    assert all(command.issued_time_s==pytest.approx(command.actual_effective_time_s-.0001) for command in with_preroll.commands)

def test_quantization_rounding_zoh_and_deduplication_are_deterministic(specs):
    spec=specs["chirp"];profile=synthetic_quantized_profile(_fields(spec));request=_request(spec,profile)
    first,r1=compile_control_schedule(spec,profile,request);second,r2=compile_control_schedule(spec,profile,request)
    assert first.commands==second.commands and first.hashes==second.hashes
    assert all(command.rounding_rule in {"NEAREST_TIES_TO_EVEN","NONE"} for command in first.commands)
    assert all(command.units in {"Gamma","saturation_parameter"} for command in first.commands)
    assert r1.sample(math.nextafter(.0003,0)).components[0].detuning_gamma==-8.0
    assert r1.sample(.0003).components[0].detuning_gamma==-6.0
    static=specs["static"];p=synthetic_quantized_profile(_fields(static));compiled,realized=compile_control_schedule(static,p,_request(static,p))
    assert compiled.total_raw_command_count>compiled.total_command_count
    assert realized.sample(0).components==realized.sample(.002).components

def test_ranges_rates_second_differences_and_dwell_fail_without_repair(specs):
    spec=specs["chirp"]
    rate=synthetic_rate_limited_profile(_fields(spec));compiled,realized=compile_control_schedule(spec,rate,_request(spec,rate))
    assert compiled.status is CompilationStatus.COMPILATION_INFEASIBLE and realized is None
    assert any(issue.code=="RATE_VIOLATION" for issue in compiled.violations)
    base=synthetic_quantized_profile(_fields(spec));caps=list(base.channel_capabilities)
    channel_by_id={channel.channel_id:channel for channel in spec.control_channels}
    index=next(i for i,item in enumerate(caps) if item.field=="detuning_gamma" and channel_by_id[item.channel_id].targets[0].component_id==1)
    caps[index]=replace(caps[index],maximum=_known(-5.0,"Gamma"));range_profile=replace(base,profile_id="range_test",channel_capabilities=tuple(caps))
    c,_=compile_control_schedule(spec,range_profile,_request(spec,range_profile));assert any(x.code=="VALUE_OUTSIDE_RANGE" for x in c.violations)
    caps=list(base.channel_capabilities);caps[index]=replace(caps[index],maximum_second_difference=_known(1.0,"Gamma/s^2"));second_profile=replace(base,profile_id="second_test",channel_capabilities=tuple(caps))
    c,_=compile_control_schedule(spec,second_profile,_request(spec,second_profile));assert any(x.code=="SECOND_DIFFERENCE_VIOLATION" for x in c.violations)
    caps=list(base.channel_capabilities);caps[index]=replace(caps[index],minimum_dwell_time=_known(.0004,"s"));dwell_profile=replace(base,profile_id="dwell_test",channel_capabilities=tuple(caps))
    c,_=compile_control_schedule(spec,dwell_profile,_request(spec,dwell_profile));assert any(x.code=="DWELL_VIOLATION" for x in c.violations)

def test_partial_profiles_hashes_outputs_and_boundaries(specs):
    spec=specs["static"];profile=source_incomplete_profile(_fields(spec));request=_request(spec,profile,CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE,diagnostic=.0005)
    compiled,realized=compile_control_schedule(spec,profile,request)
    assert compiled.status is CompilationStatus.COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE
    assert not compiled.profile_complete and not compiled.hardware_executable_claim_valid
    assert compilation_request_hash(request)==compilation_request_hash(replace(request))
    changed=synthetic_quantized_profile(_fields(spec));changed2=replace(changed,profile_id="changed")
    assert apparatus_profile_hash(changed)!=apparatus_profile_hash(changed2)
    assert canonical_apparatus_json(changed)==canonical_apparatus_json(changed)
    metadata=json.loads(METADATA.read_text(encoding="utf-8"))
    assert metadata["gate"]=="APPARATUS_SCHEDULE_COMPILER_GO"
    assert metadata["abi_policy_hashes_unchanged"] and metadata["protected_artifacts_unchanged"]
    assert metadata["real_apparatus_profile_validated"] is False and metadata["hardware_executable_claim_valid"] is False
    paths=list(DETAIL.iterdir())+[REPORT];stamps=("MODEL_INDEPENDENT","NOT_RODRIGUEZ_REPLICATION","RUN_014","APPARATUS_SCHEDULE_COMPILER_ONLY")
    assert all(all(stamp in path.name for stamp in stamps) for path in paths)
    report=REPORT.read_text(encoding="utf-8");assert "No real apparatus profile has been validated" in report
    source=(ROOT/"scripts/compile_control_policies_run_014.py").read_text(encoding="utf-8")
    for forbidden in ("rateeq","force_at(","load_force_field_cache(","integrate_","capture_velocity(","feedback_policy(","optimizer("):
        assert forbidden not in source

def test_compilation_report_and_serialization_are_deterministic(specs):
    spec=specs["static"];profile=synthetic_quantized_profile(_fields(spec))
    first,_=compile_control_schedule(spec,profile,_request(spec,profile))
    second,_=compile_control_schedule(spec,profile,_request(spec,profile))
    assert canonical_compiled_schedule_json(first)==canonical_compiled_schedule_json(second)
    report=CompilationReport.from_compiled(first)
    assert report.status is first.status
    assert report.compilation_horizon_s==(0.0,.002)
    assert report.hardware_executable_claim_valid is False

def test_allowed_sets_and_abstract_saturation_budget_fail_without_power_claim(specs):
    spec=specs["static"];base=synthetic_quantized_profile(_fields(spec));caps=list(base.channel_capabilities)
    sat_index=next(i for i,item in enumerate(caps) if item.field=="saturation")
    caps[sat_index]=replace(caps[sat_index],allowed_values=_known((0.0,),"saturation_parameter"))
    restricted=replace(base,profile_id="allowed_set_test",channel_capabilities=tuple(caps))
    compiled,_=compile_control_schedule(spec,restricted,_request(spec,restricted))
    assert any(item.code=="VALUE_NOT_IN_ALLOWED_SET" for item in compiled.violations)
    budgeted=replace(base,profile_id="aggregate_saturation_test",aggregate_saturation_budget=_known(0.0,"aggregate_saturation_parameter"))
    compiled,_=compile_control_schedule(spec,budgeted,_request(spec,budgeted))
    assert any(item.code=="AGGREGATE_SATURATION_BUDGET_VIOLATION" for item in compiled.violations)
    assert all("power" not in item.message.lower() for item in compiled.violations)
