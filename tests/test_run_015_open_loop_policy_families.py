from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.apparatus_constraints import (
    ConstraintProvenance, ConstraintProvenanceClass, ConstraintValue,
    KnowledgeState, RUN014_LABEL, apparatus_profile_hash,
    source_incomplete_profile, synthetic_identity_profile,
    synthetic_quantized_profile, synthetic_rate_limited_profile,
)
from mgf_mot.control_policy_abi import ControlPolicy
from mgf_mot.control_schedule_compiler import (
    CompilationMode, CompilationRequest, CompilationStatus, InitialStateMode,
    ReconstructionMode,
)
from mgf_mot.legacy_policy_adapter import legacy_policy_to_v2_spec
from mgf_mot.open_loop_policy_families import (
    RUN015_LABEL, FourierCorrectionChannel, MonotoneCubicChannel,
    MonotonicityClassification, MonotonicityMode, OpenLoopFamilyError,
    OpenLoopFamilyId, OpenLoopFamilyPolicy, PiecewiseLinearChannel,
    PolicyParameterVector, canonical_family_json, compile_family_policy,
    compose_with_handoff, deserialize_family_spec, evaluate_channel,
    family_hashes, family_registration, flatten_parameter_vector,
    load_family_config, normalized_policy_time, parameter_vector_layout,
    reconstruct_from_parameter_vector, serialize_family_spec,
    smoothness_ledger, structural_metrics, validate_family_spec,
    validate_family_mapping,
)
from mgf_mot.policies import load_policy


ROOT=Path(__file__).resolve().parents[1]
CONFIG_DIR=ROOT/"configs/run_015"
FILES={path.stem.rsplit("_",1)[-1]:path for path in CONFIG_DIR.glob("*.yaml")}
REPORT=ROOT/"outputs/provisional"/f"{RUN015_LABEL}.md"
DETAIL=ROOT/"outputs/provisional/open_loop_policy_families/run_015"


def _path(suffix): return next(path for path in CONFIG_DIR.glob(f"*_{suffix}.yaml"))
def _load(suffix): return load_family_config(_path(suffix))
def _fields(spec): return {channel.channel_id:channel.field for channel in spec.abi_spec.control_channels}
def _request(spec,profile,mode=CompilationMode.SAMPLE_AND_HOLD,reconstruction=ReconstructionMode.ZERO_ORDER_HOLD,diagnostic=None):
    return CompilationRequest(family_hashes(spec).complete_policy_package,apparatus_profile_hash(profile),mode,0.0,.002,InitialStateMode.POLICY_STATE_AT_START,None,None,diagnostic,reconstruction)
def _known(value,units): return ConstraintValue(KnowledgeState.KNOWN,value,units,ConstraintProvenance(ConstraintProvenanceClass.SYNTHETIC_TEST_FIXTURE,"Run 015 test fixture",None,None,"synthetic only",False))


def test_family_registry_versions_are_closed_and_normalized_time_is_explicit():
    assert {item.family_id for item in (family_registration(value,"1") for value in OpenLoopFamilyId)}==set(OpenLoopFamilyId)
    with pytest.raises(OpenLoopFamilyError,match="unknown policy family/version"): family_registration("made-up-family","1")
    with pytest.raises(OpenLoopFamilyError): family_registration(OpenLoopFamilyId.PIECEWISE_LINEAR,"2")
    assert normalized_policy_time(.00025,0,.001)==.25
    with pytest.raises(OpenLoopFamilyError,match="no implicit clamp"): normalized_policy_time(-1e-6,0,.001)


def test_piecewise_knots_endpoints_monotonicity_and_derivatives():
    spec=_load("piecewise_multiknot");item=spec.channel_schedules[0]
    assert evaluate_channel(item,0)==-8 and evaluate_channel(item,1)==-1
    assert evaluate_channel(item,.25)==-6.4
    assert evaluate_channel(item,.1,1)==pytest.approx(6.4)
    with pytest.raises(OpenLoopFamilyError,match="discontinuous"): evaluate_channel(item,.25,1)
    duplicate=replace(item,knot_u=(0,.25,.25,1));result=validate_family_spec(replace(spec,channel_schedules=(duplicate,)))
    assert any(issue.code=="NON_INCREASING_KNOT_POSITIONS" for issue in result.errors)
    decreasing=replace(item,knot_values=(-8,-6,-7,-1));result=validate_family_spec(replace(spec,channel_schedules=(decreasing,)))
    assert any(issue.code=="MONOTONICITY_VIOLATION" for issue in result.errors)


def test_monotone_cubic_is_shape_preserving_and_two_knots_are_exactly_linear():
    multi=_load("cubic_multiknot").channel_schedules[0]
    grid=np.linspace(0,1,2001);values=np.array([evaluate_channel(multi,float(u)) for u in grid])
    assert np.all(np.diff(values)>=-1e-13)
    for a,b,x0,x1 in zip(multi.knot_values,multi.knot_values[1:],multi.knot_u,multi.knot_u[1:]):
        local=values[(grid>=x0)&(grid<=x1)];assert local.min()>=min(a,b)-1e-12 and local.max()<=max(a,b)+1e-12
    baseline=_load("cubic_baseline").channel_schedules[0]
    for u in np.linspace(0,1,41):
        assert evaluate_channel(baseline,float(u))==-8+7*u
        assert evaluate_channel(baseline,float(u),1)==7
        assert evaluate_channel(baseline,float(u),2)==0


def test_fourier_endpoints_zero_baseline_and_analytic_derivatives():
    zero=_load("fourier_zero");item=zero.channel_schedules[0]
    assert evaluate_channel(item,0)==-8 and evaluate_channel(item,1)==pytest.approx(-1,abs=1e-15)
    baseline=_load("piecewise_baseline");a=OpenLoopFamilyPolicy(zero);b=OpenLoopFamilyPolicy(baseline)
    for t in np.linspace(0,.001,29): assert a.sample(float(t)).components==b.sample(float(t)).components
    nonzero=_load("fourier_nonzero").channel_schedules[0];assert evaluate_channel(nonzero,0)==nonzero.baseline_start and evaluate_channel(nonzero,1)==nonzero.baseline_end
    u=.413;h=1e-5
    first=(evaluate_channel(nonzero,u+h)-evaluate_channel(nonzero,u-h))/(2*h)
    second=(evaluate_channel(nonzero,u+h)-2*evaluate_channel(nonzero,u)+evaluate_channel(nonzero,u-h))/h**2
    assert evaluate_channel(nonzero,u,1)==pytest.approx(first,rel=2e-8)
    assert evaluate_channel(nonzero,u,2)==pytest.approx(second,rel=2e-5)
    bad=replace(nonzero,harmonic_count=4);spec=_load("fourier_nonzero");result=validate_family_spec(replace(spec,channel_schedules=(bad,)))
    assert any(issue.code=="COEFFICIENT_COUNT_MISMATCH" for issue in result.errors)


def test_all_three_distinguished_families_reproduce_baseline_states_and_derivative():
    path=ROOT/"configs/rodriguez_baseline_linear_chirp.yaml";legacy=ControlPolicy(legacy_policy_to_v2_spec(load_policy(path),source_path=path))
    rng=np.random.default_rng(15015);times=[0,.00005,.00025,.0005,.00075,math.nextafter(.001,0),.001,*sorted(rng.uniform(0,.001,12))]
    for suffix in ("piecewise_baseline","cubic_baseline","fourier_zero"):
        policy=OpenLoopFamilyPolicy(_load(suffix));channel=policy.family_spec.channel_schedules[0].channel_id
        for t in times: assert policy.sample(float(t)).components==legacy.sample(float(t)).components
        for t in (0,.0002,.0005,.0008,.001): assert policy.channel_derivative(channel,t,1)==pytest.approx(7000.0,abs=1e-9)


def test_four_components_shared_ownership_saturation_and_no_clipping():
    spec=_load("piecewise_baseline");policy=OpenLoopFamilyPolicy(spec);state=policy.sample(.0004)
    assert state.component_order==(1,2,3,4) and len(state.components)==4
    assert len({state.components[index].detuning_gamma for index in (0,1,2)})==1
    source=spec.channel_schedules[0];bad=PiecewiseLinearChannel("chirp_component_1_saturation","saturation",source.knot_u,(1.0,-.1),MonotonicityMode.UNRESTRICTED,(),False,None)
    result=validate_family_spec(replace(spec,channel_schedules=(bad,)))
    assert any(issue.code=="NEGATIVE_SATURATION" for issue in result.errors)


def test_parameter_vector_order_round_trip_fixed_values_and_hashes():
    spec=_load("piecewise_multiknot");layout=parameter_vector_layout(spec);vector=flatten_parameter_vector(spec)
    assert [entry.vector_index for entry in layout.entries]==list(range(len(layout.entries)))
    assert all(entry.bound_basis=="UNKNOWN" and entry.lower_bound is None and entry.upper_bound is None for entry in layout.entries)
    rebuilt=reconstruct_from_parameter_vector(spec,vector);assert rebuilt==spec
    changed=PolicyParameterVector(vector.layout_hash,(vector.values[0]+.1,*vector.values[1:]));modified=reconstruct_from_parameter_vector(spec,changed)
    assert family_hashes(modified)!=family_hashes(spec)
    assert modified.channel_schedules[0].knot_values[0]==spec.channel_schedules[0].knot_values[0]
    with pytest.raises(OpenLoopFamilyError,match="LENGTH"): reconstruct_from_parameter_vector(spec,PolicyParameterVector(vector.layout_hash,()))


def test_canonical_serialization_round_trip_and_mapping_order_independence():
    spec=_load("fourier_nonzero");text=serialize_family_spec(spec);assert deserialize_family_spec(text)==spec
    mapping=json.loads(text);reversed_mapping=dict(reversed(list(mapping.items())))
    assert canonical_family_json(mapping)==canonical_family_json(reversed_mapping)
    assert family_hashes(spec)==family_hashes(deserialize_family_spec(text))
    arbitrary=dict(mapping);arbitrary["expression"]="do_not_execute"
    assert any(issue.code=="ARBITRARY_EXECUTABLE_CONTENT" for issue in validate_family_mapping(arbitrary).errors)
    unknown=dict(mapping);unknown["family_id"]="unknown-family-v1"
    assert any(issue.code=="UNKNOWN_POLICY_FAMILY" for issue in validate_family_mapping(unknown).errors)


def test_handoff_composition_preserves_strict_boundary_and_event():
    pre=_load("cubic_baseline");path=ROOT/"configs/rodriguez_chirp_to_3_plus_1_handoff.yaml";handoff=legacy_policy_to_v2_spec(load_policy(path),source_path=path)
    composed=compose_with_handoff(pre,handoff,{"chirp_shared_linear_detuning_123":"pre_shared_linear_detuning_123"});policy=OpenLoopFamilyPolicy(composed)
    left=policy.sample(math.nextafter(.001,0));right=policy.sample(.001)
    assert left.segment_id=="pre_handoff" and not left.handoff_occurred
    assert right.segment_id=="post_handoff" and right.handoff_occurred
    assert len(composed.abi_spec.events)==1 and composed.abi_spec.events[0].event_time_s==.001
    with pytest.raises(OpenLoopFamilyError,match="EVENT_FAMILY_BOUNDARY_CONFLICT"): compose_with_handoff(replace(pre,t_end_s=.0009),handoff,{"chirp_shared_linear_detuning_123":"pre_shared_linear_detuning_123"})


def test_smoothness_ledgers_and_structural_metrics_are_model_independent():
    for suffix in ("piecewise_multiknot","cubic_multiknot","fourier_nonzero"):
        spec=_load(suffix);ledger=smoothness_ledger(spec);metrics=structural_metrics(spec)
        assert ledger.family_id==spec.family_id.value and metrics.policy_hash==family_hashes(spec).complete_policy_package
        assert metrics.channels and all(item.field in {"detuning_gamma","saturation"} for item in metrics.channels)
    assert "discontinuous" in smoothness_ledger(_load("piecewise_multiknot")).first_derivative_continuity
    assert structural_metrics(_load("fourier_high_bandwidth")).channels[0].monotonicity is MonotonicityClassification.NONMONOTONE


def test_run014_compiler_identity_quantized_rate_and_incomplete_paths():
    spec=_load("piecewise_multiknot");fields=_fields(spec)
    identity=synthetic_identity_profile(fields);compiled,realized=compile_family_policy(spec,identity,_request(spec,identity,CompilationMode.EXACT_ONLY,ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING))
    assert compiled.status is CompilationStatus.COMPILED_EXACT and realized is not None
    assert realized.sample(.0005).components==OpenLoopFamilyPolicy(spec).sample(.0005).components
    quantized=synthetic_quantized_profile(fields);a,_=compile_family_policy(spec,quantized,_request(spec,quantized));b,_=compile_family_policy(spec,quantized,_request(spec,quantized))
    assert a.status is CompilationStatus.COMPILED_APPROXIMATE and a.commands==b.commands and a.hashes==b.hashes
    high=_load("fourier_high_bandwidth");limited=synthetic_rate_limited_profile(_fields(high));failed,realized=compile_family_policy(high,limited,_request(high,limited))
    assert failed.status is CompilationStatus.COMPILATION_INFEASIBLE and realized is None
    assert any(issue.code=="RATE_VIOLATION" for issue in failed.violations)
    incomplete=source_incomplete_profile(fields);diagnostic,_=compile_family_policy(spec,incomplete,_request(spec,incomplete,CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE,diagnostic=.0005))
    assert diagnostic.status is CompilationStatus.COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE and not diagnostic.hardware_executable_claim_valid


def test_second_difference_and_dwell_fail_without_family_repair():
    spec=_load("piecewise_multiknot");base=synthetic_quantized_profile(_fields(spec));caps=list(base.channel_capabilities);target=spec.channel_schedules[0].channel_id;index=next(i for i,item in enumerate(caps) if item.channel_id==target)
    caps[index]=replace(caps[index],maximum_second_difference=_known(1.0,"Gamma/s^2"));profile=replace(base,profile_id="run015_second_difference",channel_capabilities=tuple(caps));compiled,_=compile_family_policy(spec,profile,_request(spec,profile))
    assert any(issue.code=="SECOND_DIFFERENCE_VIOLATION" for issue in compiled.violations)
    caps=list(base.channel_capabilities);caps[index]=replace(caps[index],minimum_dwell_time=_known(.0004,"s"));profile=replace(base,profile_id="run015_dwell",channel_capabilities=tuple(caps));compiled,_=compile_family_policy(spec,profile,_request(spec,profile))
    assert any(issue.code=="DWELL_VIOLATION" for issue in compiled.violations)


def test_run015_outputs_and_script_authorization_boundaries():
    metadata=json.loads(next(DETAIL.glob("*metadata.json")).read_text(encoding="utf-8"))
    assert metadata["gate"]=="OPEN_LOOP_POLICY_FAMILIES_GO"
    assert metadata["protected_artifacts_unchanged"] and metadata["run013_policy_hashes_unchanged"] and metadata["run014_profile_hashes_unchanged"]
    assert not metadata["real_apparatus_profile_validated"] and not metadata["hardware_executable_claim_valid"]
    stamps=("MODEL_INDEPENDENT","NOT_RODRIGUEZ_REPLICATION","RUN_015","OPEN_LOOP_POLICY_FAMILIES_ONLY")
    assert all(all(stamp in path.name for stamp in stamps) for path in [REPORT,*DETAIL.iterdir()])
    source=(ROOT/"scripts/validate_open_loop_policy_families_run_015.py").read_text(encoding="utf-8")
    for forbidden in ("rateeq","force_at(","load_force_field_cache(","integrate_","capture_velocity(","feedback_policy(","optimizer("):
        assert forbidden not in source
