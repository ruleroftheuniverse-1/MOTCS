"""Run 015 audit for model-independent open-loop policy families only."""

from __future__ import annotations

from dataclasses import asdict, replace
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/"src"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))

from mgf_mot.apparatus_constraints import (  # noqa: E402
    ConstraintProvenance, ConstraintProvenanceClass, ConstraintValue,
    KnowledgeState, apparatus_profile_hash, source_incomplete_profile,
    synthetic_identity_profile, synthetic_quantized_profile,
    synthetic_rate_limited_profile,
)
from mgf_mot.control_policy_abi import ControlPolicy  # noqa: E402
from mgf_mot.control_policy_serialization import control_policy_hashes  # noqa: E402
from mgf_mot.control_schedule_compiler import (  # noqa: E402
    CompilationMode, CompilationRequest, InitialStateMode, ReconstructionMode,
)
from mgf_mot.legacy_policy_adapter import legacy_policy_to_v2_spec  # noqa: E402
from mgf_mot.open_loop_policy_families import (  # noqa: E402
    RUN015_LABEL, OpenLoopFamilyPolicy, compile_family_policy,
    compose_with_handoff,
    deserialize_family_spec, family_hashes, flatten_parameter_vector,
    load_family_config, parameter_vector_layout,
    reconstruct_from_parameter_vector, serialize_family_spec,
    smoothness_ledger, structural_metrics, validate_family_spec,
)
from mgf_mot.policies import load_policy  # noqa: E402


CONFIG_DIR=ROOT/"configs/run_015";OUT=ROOT/"outputs/provisional";DETAIL=OUT/"open_loop_policy_families/run_015"
REPORT=OUT/f"{RUN015_LABEL}.md";METADATA=DETAIL/f"{RUN015_LABEL}_metadata.json"
LEGACY_CONFIGS=(ROOT/"configs/rodriguez_static_3.yaml",ROOT/"configs/rodriguez_static_3_plus_1.yaml",ROOT/"configs/rodriguez_baseline_linear_chirp.yaml",ROOT/"configs/rodriguez_chirp_to_3_plus_1_handoff.yaml")


def _digest(path:Path)->str:return sha256(path.read_bytes()).hexdigest()
def _manifest(paths):return {str(path.relative_to(ROOT)):_digest(path) for path in sorted(set(paths))}
def _protected()->tuple[Path,...]:
    patterns=("outputs/provisional/*RUN_010*","outputs/provisional/*RUN_011*","outputs/provisional/*RUN_012*","outputs/provisional/*RUN_013*","outputs/provisional/*RUN_014*","outputs/provisional/molecular_model_packages/run_012/*","outputs/provisional/control_policy_abi/run_013/*","outputs/provisional/apparatus_schedule_compiler/run_014/*","outputs/provisional/force_fields/*","outputs/provisional/molecular_model_audit/run_011*/*","outputs/provisional/paper_digitization/run_011b/*","configs/*.yaml")
    paths=set()
    for pattern in patterns:paths.update(path for path in ROOT.glob(pattern) if path.is_file())
    paths.update(ROOT/"src/mgf_mot"/name for name in ("control_policy_abi.py","control_policy_serialization.py","control_policy_validation.py","legacy_policy_adapter.py","apparatus_constraints.py"))
    return tuple(sorted(paths))
def _plain(value:Any)->Any:
    if isinstance(value,Enum):return value.value
    if hasattr(value,"__dataclass_fields__"):return {key:_plain(item) for key,item in asdict(value).items()}
    if isinstance(value,dict):return {str(key):_plain(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):return [_plain(item) for item in value]
    return value
def _fields(spec):return {channel.channel_id:channel.field for channel in spec.abi_spec.control_channels}
def _request(spec,profile,mode=CompilationMode.SAMPLE_AND_HOLD,reconstruction=ReconstructionMode.ZERO_ORDER_HOLD,diagnostic=None):return CompilationRequest(family_hashes(spec).complete_policy_package,apparatus_profile_hash(profile),mode,0.0,.002,InitialStateMode.POLICY_STATE_AT_START,None,None,diagnostic,reconstruction)
def _known(value,units):return ConstraintValue(KnowledgeState.KNOWN,value,units,ConstraintProvenance(ConstraintProvenanceClass.ENGINEERING_STRESS_TEST,"Run 015 explicit synthetic constraint",None,None,"not apparatus evidence",False))


def _baseline_audit(spec,baseline):
    policy=OpenLoopFamilyPolicy(spec);channel=spec.channel_schedules[0].channel_id;times=(0.0,.00005,.00025,.0005,.00075,math.nextafter(.001,0.0),.001,.000137,.000619,.000883)
    states=all(policy.sample(t).components==baseline.sample(t).components for t in times)
    derivatives=all(policy.channel_derivative(channel,t,1)==7000.0 for t in (0.0,.0002,.0005,.0008,.001))
    return {"outcome":"BASELINE_EXACT" if states and derivatives else "BASELINE_NOT_REPRODUCED","state_equality":states,"derivative_equality":derivatives,"sample_times_s":list(times)}


def _current_run014_profile_hashes():
    identity=[]
    for path in LEGACY_CONFIGS:
        abi=legacy_policy_to_v2_spec(load_policy(path),source_path=path);fields={channel.channel_id:channel.field for channel in abi.control_channels};identity.append((abi.policy_name,apparatus_profile_hash(synthetic_identity_profile(fields))))
    path=LEGACY_CONFIGS[2];abi=legacy_policy_to_v2_spec(load_policy(path),source_path=path);fields={channel.channel_id:channel.field for channel in abi.control_channels}
    demonstrations=[("quantized",apparatus_profile_hash(synthetic_quantized_profile(fields))),("rate_limited",apparatus_profile_hash(synthetic_rate_limited_profile(fields))),("source_incomplete",apparatus_profile_hash(source_incomplete_profile(fields)))]
    return {"identity":identity,"demonstrations":demonstrations}


def run()->dict[str,Any]:
    protected=_protected();before=_manifest(protected);DETAIL.mkdir(parents=True,exist_ok=True)
    run013=json.loads(next((ROOT/"outputs/provisional/control_policy_abi/run_013").glob("*metadata.json")).read_text(encoding="utf-8"));run014=json.loads(next((ROOT/"outputs/provisional/apparatus_schedule_compiler/run_014").glob("*metadata.json")).read_text(encoding="utf-8"))
    current_policy_hashes=[control_policy_hashes(legacy_policy_to_v2_spec(load_policy(path),source_path=path)).full_policy_package for path in LEGACY_CONFIGS];accepted_policy_hashes=[row["hashes"]["full_policy_package"] for row in run013["policies"]]
    expected_profiles={"identity":[(row["policy_name"],row["profile_hash"]) for row in run014["identity_compilations"]],"demonstrations":[(row["name"],row["profile_hash"]) for row in run014["demonstrations"]]};current_profiles=_current_run014_profile_hashes()
    baseline_path=LEGACY_CONFIGS[2];baseline=ControlPolicy(legacy_policy_to_v2_spec(load_policy(baseline_path),source_path=baseline_path))
    handoff_path=LEGACY_CONFIGS[3];handoff_spec=legacy_policy_to_v2_spec(load_policy(handoff_path),source_path=handoff_path);handoff_baseline=ControlPolicy(handoff_spec)
    family_rows=[]
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        spec=load_family_config(path);validation=validate_family_spec(spec);serialized=serialize_family_spec(spec);round_trip=deserialize_family_spec(serialized);vector=flatten_parameter_vector(spec);rebuilt=reconstruct_from_parameter_vector(spec,vector);policy=OpenLoopFamilyPolicy(spec);fields=_fields(spec)
        identity=synthetic_identity_profile(fields);identity_compiled,identity_realized=compile_family_policy(spec,identity,_request(spec,identity,CompilationMode.EXACT_ONLY,ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING))
        quantized=synthetic_quantized_profile(fields);quantized_compiled,_=compile_family_policy(spec,quantized,_request(spec,quantized))
        baseline_result=_baseline_audit(spec,baseline) if any(token in path.stem for token in ("piecewise_baseline","cubic_baseline","fourier_zero")) else None
        if baseline_result is not None:
            composed=compose_with_handoff(spec,handoff_spec,{spec.channel_schedules[0].channel_id:"pre_shared_linear_detuning_123"});composed_policy=OpenLoopFamilyPolicy(composed)
            handoff_times=(0.0,.00025,.0005,math.nextafter(.001,0.0),.001,math.nextafter(.001,math.inf),.002)
            baseline_result["handoff_state_equality"]=all(composed_policy.sample(t).components==handoff_baseline.sample(t).components for t in handoff_times)
            if not baseline_result["handoff_state_equality"]:baseline_result["outcome"]="BASELINE_NOT_REPRODUCED"
        samples=[{"time_s":t,"components":_plain(policy.sample(t).components)} for t in (0.0,.00025,.0005,.00075,.001,.002)]
        package={"label":RUN015_LABEL,"source_config":str(path.relative_to(ROOT)),"family_spec":json.loads(serialize_family_spec(spec)),"hashes":_plain(family_hashes(spec)),"validation":_plain(validation),"parameter_layout":_plain(parameter_vector_layout(spec)),"parameter_vector":_plain(vector),"round_trip_equal":round_trip==spec,"vector_round_trip_equal":rebuilt==spec,"smoothness":_plain(smoothness_ledger(spec)),"structural_metrics":_plain(structural_metrics(spec)),"baseline_equivalence":baseline_result,"samples":samples,"identity_compilation":_plain(identity_compiled),"quantized_compilation":_plain(quantized_compiled)}
        suffix=path.stem.removeprefix(RUN015_LABEL+"_")
        output=DETAIL/f"{RUN015_LABEL}_{suffix}_family_package.json";output.write_text(json.dumps(package,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
        row={"name":spec.family_name,"family_id":spec.family_id.value,"config":str(path.relative_to(ROOT)),"output":output.name,"valid":validation.valid,"serialization_round_trip":round_trip==spec,"vector_round_trip":rebuilt==spec,"hashes":_plain(family_hashes(spec)),"baseline_equivalence":baseline_result,"identity_status":identity_compiled.status.value,"identity_exact_samples":all(identity_realized.sample(t).components==policy.sample(t).components for t in (0,.0002,.0005,.001,.002)),"quantized_status":quantized_compiled.status.value,"quantized_command_count":quantized_compiled.total_command_count,"hardware_executable_claim_valid":quantized_compiled.hardware_executable_claim_valid}
        family_rows.append(row);print(row["family_id"],row["name"],row["identity_status"],row["quantized_status"],baseline_result["outcome"] if baseline_result else "SYNTHETIC")
    multi=load_family_config(next(CONFIG_DIR.glob("*piecewise_multiknot.yaml")));fields=_fields(multi)
    high=load_family_config(next(CONFIG_DIR.glob("*fourier_high_bandwidth.yaml")));limited=synthetic_rate_limited_profile(_fields(high));rate_failure,_=compile_family_policy(high,limited,_request(high,limited))
    quantized=synthetic_quantized_profile(fields);caps=list(quantized.channel_capabilities);target=multi.channel_schedules[0].channel_id;index=next(i for i,item in enumerate(caps) if item.channel_id==target)
    pass_caps=[replace(item,maximum_first_derivative=_known(1e9,"Gamma/s" if item.field=="detuning_gamma" else "saturation_parameter/s")) for item in caps];pass_profile=replace(quantized,profile_id="run015_synthetic_rate_pass",profile_name="Run 015 synthetic permissive rate fixture",channel_capabilities=tuple(pass_caps));rate_pass,_=compile_family_policy(multi,pass_profile,_request(multi,pass_profile))
    second_caps=list(caps);second_caps[index]=replace(second_caps[index],maximum_second_difference=_known(1.0,"Gamma/s^2"));second_profile=replace(quantized,profile_id="run015_synthetic_second_failure",channel_capabilities=tuple(second_caps));second_failure,_=compile_family_policy(multi,second_profile,_request(multi,second_profile))
    dwell_caps=list(caps);dwell_caps[index]=replace(dwell_caps[index],minimum_dwell_time=_known(.0004,"s"));dwell_profile=replace(quantized,profile_id="run015_synthetic_dwell_failure",channel_capabilities=tuple(dwell_caps));dwell_failure,_=compile_family_policy(multi,dwell_profile,_request(multi,dwell_profile))
    incomplete=source_incomplete_profile(fields);diagnostic,_=compile_family_policy(multi,incomplete,_request(multi,incomplete,CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE,diagnostic=.0005))
    constraint_audit={"rate_pass":rate_pass.status.value,"rate_failure":rate_failure.status.value,"rate_failure_codes":sorted({item.code for item in rate_failure.violations}),"second_failure":second_failure.status.value,"second_failure_codes":sorted({item.code for item in second_failure.violations}),"dwell_failure":dwell_failure.status.value,"dwell_failure_codes":sorted({item.code for item in dwell_failure.violations}),"source_incomplete":diagnostic.status.value,"source_incomplete_hardware_claim":diagnostic.hardware_executable_claim_valid}
    after=_manifest(protected);baselines=[row for row in family_rows if row["baseline_equivalence"] is not None]
    ready=(run013["gate"]=="CONTROL_POLICY_ABI_GO" and run014["gate"]=="APPARATUS_SCHEDULE_COMPILER_GO" and current_policy_hashes==accepted_policy_hashes and current_profiles==expected_profiles and before==after and len(baselines)==3 and all(row["baseline_equivalence"]["outcome"]=="BASELINE_EXACT" for row in baselines) and all(row["valid"] and row["serialization_round_trip"] and row["vector_round_trip"] and row["identity_status"]=="COMPILED_EXACT" and row["identity_exact_samples"] and row["quantized_status"]=="COMPILED_APPROXIMATE" and not row["hardware_executable_claim_valid"] for row in family_rows) and constraint_audit["rate_pass"]=="COMPILED_APPROXIMATE" and "RATE_VIOLATION" in constraint_audit["rate_failure_codes"] and "SECOND_DIFFERENCE_VIOLATION" in constraint_audit["second_failure_codes"] and "DWELL_VIOLATION" in constraint_audit["dwell_failure_codes"] and constraint_audit["source_incomplete"]=="COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE" and not constraint_audit["source_incomplete_hardware_claim"])
    gate="OPEN_LOOP_POLICY_FAMILIES_GO" if ready else "OPEN_LOOP_POLICY_FAMILIES_REFINEMENT_REQUIRED"
    metadata={"label":RUN015_LABEL,"gate":gate,"family_schema_version":"mgf-mot-open-loop-policy-family-v1","abi_schema_version":"mgf-mot-control-policy-v2","compiled_schedule_schema_version":"mgf-mot-compiled-control-schedule-v1","families":family_rows,"constraint_compilation_audit":constraint_audit,"run013_policy_hashes_unchanged":current_policy_hashes==accepted_policy_hashes,"run013_policy_hashes":accepted_policy_hashes,"current_run013_policy_hashes":current_policy_hashes,"run014_profile_hashes_unchanged":current_profiles==expected_profiles,"run014_profile_hashes":expected_profiles,"current_run014_profile_hashes":current_profiles,"protected_hashes_before":before,"protected_hashes_after":after,"protected_artifacts_unchanged":before==after,"molecular_force_evaluations":0,"force_field_queries":0,"trajectory_integrations":0,"capture_metrics":0,"feedback_executions":0,"optimization_runs":0,"control_policy_abi_authorized":True,"apparatus_schedule_compiler_authorized":True,"open_loop_policy_families_authorized":gate=="OPEN_LOOP_POLICY_FAMILIES_GO","real_apparatus_profile_validated":False,"hardware_executable_claim_valid":False,"feedback_policy_authorized":False,"optimizer_interface_authorized":False,"optimization_run_authorized":False,"capture_authorized":False,"exact_replication_valid":False}
    METADATA.write_text(json.dumps(metadata,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    baseline_lines=[f"- `{row['family_id']}`: `{row['baseline_equivalence']['outcome']}`" for row in baselines]
    REPORT.write_text("\n".join([f"# {RUN015_LABEL}","","**No molecular force was evaluated. No trajectory was integrated. No capture metric was calculated. No optimizer was invoked. No policy was shown to improve physical performance. Synthetic feasibility is not a real-apparatus claim.**","","## Baseline equivalence","",*baseline_lines,"","## Compiler diagnostics","",f"- permissive synthetic rate case: `{constraint_audit['rate_pass']}`",f"- deliberately rate-limited case: `{constraint_audit['rate_failure']}`",f"- deliberately second-difference-limited case: `{constraint_audit['second_failure']}`",f"- deliberately dwell-limited case: `{constraint_audit['dwell_failure']}`",f"- source-incomplete case: `{constraint_audit['source_incomplete']}`; hardware claim `false`","","## Authorization boundaries","","`control_policy_abi_authorized=true`; `apparatus_schedule_compiler_authorized=true`; `real_apparatus_profile_validated=false`; `hardware_executable_claim_valid=false`; `feedback_policy_authorized=false`; `optimizer_interface_authorized=false`; `optimization_run_authorized=false`; `capture_authorized=false`; `exact_replication_valid=false`.","",gate])+"\n",encoding="utf-8")
    if before!=after:raise RuntimeError("Run 015 modified a protected artifact")
    print(RUN015_LABEL,gate);return metadata


if __name__=="__main__":run()
