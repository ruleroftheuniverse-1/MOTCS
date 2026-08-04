"""Run 014 deterministic model-independent apparatus compilation audit."""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))

from mgf_mot.apparatus_constraints import (  # noqa: E402
    RUN014_LABEL, apparatus_profile_hash, source_incomplete_profile,
    synthetic_identity_profile, synthetic_quantized_profile,
    synthetic_rate_limited_profile, validate_apparatus_profile,
)
from mgf_mot.control_schedule_compiler import (  # noqa: E402
    CompilationMode, CompilationRequest, CompilationStatus, InitialStateMode,
    ReconstructionMode, compile_control_schedule,
)
from mgf_mot.control_policy_abi import ControlPolicy  # noqa: E402
from mgf_mot.control_policy_serialization import control_policy_hashes  # noqa: E402
from mgf_mot.legacy_policy_adapter import legacy_policy_to_v2_spec  # noqa: E402
from mgf_mot.policies import load_policy  # noqa: E402

CONFIGS=(ROOT/"configs/rodriguez_static_3.yaml",ROOT/"configs/rodriguez_static_3_plus_1.yaml",ROOT/"configs/rodriguez_baseline_linear_chirp.yaml",ROOT/"configs/rodriguez_chirp_to_3_plus_1_handoff.yaml")
OUT=ROOT/"outputs/provisional"; DETAIL=OUT/"apparatus_schedule_compiler/run_014"
METADATA=DETAIL/f"{RUN014_LABEL}_metadata.json"; REPORT=OUT/f"{RUN014_LABEL}.md"

def _hash(path:Path)->str:return sha256(path.read_bytes()).hexdigest()
def _protected()->tuple[Path,...]:
    patterns=("outputs/provisional/molecular_model_packages/run_012/*","outputs/provisional/control_policy_abi/run_013/*","outputs/provisional/*RUN_010*","outputs/provisional/*RUN_011*","outputs/provisional/*RUN_012*","outputs/provisional/*RUN_013*","outputs/provisional/force_fields/*","outputs/provisional/molecular_model_audit/run_011*/*","outputs/provisional/paper_digitization/run_011b/*","configs/*.yaml")
    paths:set[Path]={ROOT/"src/mgf_mot/control_policy_abi.py",ROOT/"src/mgf_mot/control_policy_serialization.py",ROOT/"src/mgf_mot/control_policy_validation.py",ROOT/"src/mgf_mot/legacy_policy_adapter.py"}
    for pattern in patterns:paths.update(path for path in ROOT.glob(pattern) if path.is_file())
    return tuple(sorted(paths))
def _manifest(paths):return {str(path.relative_to(ROOT)):_hash(path) for path in paths}
def _plain(value:Any)->Any:
    if isinstance(value,Enum):return value.value
    if hasattr(value,"__dataclass_fields__"):return {key:_plain(item) for key,item in asdict(value).items()}
    if isinstance(value,dict):return {str(k):_plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_plain(item) for item in value]
    return value
def _request(spec,profile,mode,reconstruction,*,diagnostic=None):
    return CompilationRequest(control_policy_hashes(spec).full_policy_package,apparatus_profile_hash(profile),mode,0.0,0.002,InitialStateMode.POLICY_STATE_AT_START,None,None,diagnostic,reconstruction)
def _exact_samples(spec,realized):
    ideal=ControlPolicy(spec); times=(0.0,0.0001,0.0005,math.nextafter(0.001,0.0),0.001,math.nextafter(0.001,math.inf),0.002)
    rows=[]
    for t in times:
        a,b=ideal.sample(t),realized.sample(t)
        equal=tuple((x.detuning_gamma,x.saturation,x.enabled,x.active,x.off_reason) for x in a.components)==tuple((x.detuning_gamma,x.saturation,x.enabled,x.active,x.off_reason) for x in b.components)
        rows.append({"time_s":t,"exact":equal,"component_order":list(b.component_order),"segment":b.segment_id})
    return rows

def run()->dict[str,Any]:
    run013_path=next((ROOT/"outputs/provisional/control_policy_abi/run_013").glob("*metadata.json"))
    run013=json.loads(run013_path.read_text(encoding="utf-8"))
    accepted_manifest=run013["protected_hashes_after"]
    accepted_current={relative:_hash(ROOT/relative) if (ROOT/relative).is_file() else None for relative in accepted_manifest}
    accepted_unchanged=accepted_current==accepted_manifest
    protected=_protected();before=_manifest(protected);DETAIL.mkdir(parents=True,exist_ok=True)
    identity=[]; demonstrations=[]; current_hashes=[]
    for path in CONFIGS:
        spec=legacy_policy_to_v2_spec(load_policy(path),source_path=path); policy_hash=control_policy_hashes(spec).full_policy_package;current_hashes.append(policy_hash)
        fields={channel.channel_id:channel.field for channel in spec.control_channels};profile=synthetic_identity_profile(fields)
        request=_request(spec,profile,CompilationMode.EXACT_ONLY,ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING)
        compiled,realized=compile_control_schedule(spec,profile,request);samples=_exact_samples(spec,realized) if realized else []
        package_path=DETAIL/f"{RUN014_LABEL}_{spec.policy_name}_synthetic_identity_compiled_schedule.json";package_path.write_text(json.dumps({"label":RUN014_LABEL,"profile":_plain(profile),"compiled":_plain(compiled),"sample_audit":samples},indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
        identity.append({"policy_name":spec.policy_name,"policy_hash":policy_hash,"profile_hash":apparatus_profile_hash(profile),"profile_validation":validate_apparatus_profile(profile).valid,"status":compiled.status.value,"all_samples_exact":all(row["exact"] for row in samples),"event_table":_plain(compiled.events),"command_count":compiled.total_command_count,"hashes":_plain(compiled.hashes),"output":package_path.name})
        print(spec.policy_name,compiled.status.value,"commands",compiled.total_command_count,"events",len(compiled.events))
    # Deterministic constrained demonstrations use the existing linear chirp.
    path=CONFIGS[2];spec=legacy_policy_to_v2_spec(load_policy(path),source_path=path);fields={channel.channel_id:channel.field for channel in spec.control_channels}
    for label,profile,mode,diagnostic in (("quantized",synthetic_quantized_profile(fields),CompilationMode.SAMPLE_AND_HOLD,None),("rate_limited",synthetic_rate_limited_profile(fields),CompilationMode.SAMPLE_AND_HOLD,None),("source_incomplete",source_incomplete_profile(fields),CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE,0.0005)):
        request=_request(spec,profile,mode,ReconstructionMode.ZERO_ORDER_HOLD,diagnostic=diagnostic);compiled,realized=compile_control_schedule(spec,profile,request)
        samples=[] if realized is None else [{"time_s":t,"components":[{"id":c.component_id,"detuning_gamma":c.detuning_gamma,"saturation":c.saturation,"active":c.active} for c in realized.sample(t).components]} for t in (0.0,0.0005,0.001,0.002)]
        output=DETAIL/f"{RUN014_LABEL}_{label}_demonstration_compiled_schedule.json";output.write_text(json.dumps({"label":RUN014_LABEL,"profile":_plain(profile),"compiled":_plain(compiled),"realized_samples":samples},indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
        demonstrations.append({"name":label,"profile_hash":apparatus_profile_hash(profile),"status":compiled.status.value,"violation_codes":sorted({item.code for item in compiled.violations}),"hardware_executable_claim_valid":compiled.hardware_executable_claim_valid,"maximum_event_displacement_s":compiled.maximum_event_displacement_s,"metrics":_plain(compiled.metrics),"hashes":_plain(compiled.hashes),"output":output.name})
        print(label,compiled.status.value,"violations",demonstrations[-1]["violation_codes"])
    run013_hashes=[row["hashes"]["full_policy_package"] for row in run013["policies"]]
    after=_manifest(protected);ready=(all(row["status"]=="COMPILED_EXACT" and row["all_samples_exact"] for row in identity) and demonstrations[0]["status"]=="COMPILED_APPROXIMATE" and demonstrations[1]["status"]=="COMPILATION_INFEASIBLE" and "RATE_VIOLATION" in demonstrations[1]["violation_codes"] and demonstrations[2]["status"]=="COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE" and not demonstrations[2]["hardware_executable_claim_valid"] and current_hashes==run013_hashes and accepted_unchanged and before==after)
    gate="APPARATUS_SCHEDULE_COMPILER_GO" if ready else "APPARATUS_SCHEDULE_COMPILER_REFINEMENT_REQUIRED"
    metadata={"label":RUN014_LABEL,"apparatus_schema_version":"mgf-mot-apparatus-constraints-v1","compiled_schedule_schema_version":"mgf-mot-compiled-control-schedule-v1","identity_compilations":identity,"demonstrations":demonstrations,"run013_policy_hashes":run013_hashes,"current_policy_hashes":current_hashes,"abi_policy_hashes_unchanged":current_hashes==run013_hashes,"accepted_protected_hashes":accepted_manifest,"accepted_protected_hashes_current":accepted_current,"accepted_protected_artifacts_unchanged":accepted_unchanged,"protected_hashes_before":before,"protected_hashes_after":after,"protected_artifacts_unchanged":before==after,"formal_identity_note":"Exact linear-chirp identity uses an explicitly synthetic continuous channel binding. Finite-clock profiles reconstruct by ZERO_ORDER_HOLD and cannot claim exact continuous realization.","molecular_force_calculations":0,"force_field_queries":0,"trajectory_integrations":0,"capture_calculations":0,"feedback_executions":0,"optimization_runs":0,"control_policy_abi_authorized":True,"apparatus_schedule_compiler_authorized":gate=="APPARATUS_SCHEDULE_COMPILER_GO","real_apparatus_profile_validated":False,"hardware_executable_claim_valid":False,"open_loop_policy_families_authorized":False,"feedback_policy_authorized":False,"optimizer_interface_authorized":False,"optimization_run_authorized":False,"capture_authorized":False,"exact_replication_valid":False,"gate":gate}
    METADATA.write_text(json.dumps(metadata,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    REPORT.write_text("\n".join([f"# {RUN014_LABEL}","","**No real apparatus profile has been validated. Synthetic compilation is not evidence of hardware executability. No molecular-force, force-field, trajectory, capture, feedback, or optimization calculation occurred.**","",f"## {RUN014_LABEL} Result","",f"All four ABI-v2 legacy policies compiled under the formal synthetic identity profile with `COMPILED_EXACT` and exact sampled states/events. The finite-clock synthetic profile returned `{demonstrations[0]['status']}` with deterministic zero-order-hold and quantization metrics. The deliberate rate limit returned `{demonstrations[1]['status']}` with `{demonstrations[1]['violation_codes']}`; no repair was applied. The source-incomplete profile returned `{demonstrations[2]['status']}` and cannot make a hardware claim.","",f"## {RUN014_LABEL} Time and event semantics","","Commands separately record requested effective, issued, and actual effective times, latency, clock displacement, ideal/quantized values, and event/atomic group IDs. Finite clocks use explicit decimal rounding and zero-order hold. The exact linear-chirp identity is an explicitly synthetic continuous binding—not a finite command clock or real-device claim.","",f"## {RUN014_LABEL} Boundaries","","`control_policy_abi_authorized=true`; `real_apparatus_profile_validated=false`; `hardware_executable_claim_valid=false`; `open_loop_policy_families_authorized=false`; `feedback_policy_authorized=false`; `optimizer_interface_authorized=false`; `optimization_run_authorized=false`; `capture_authorized=false`; `exact_replication_valid=false`.","",gate])+"\n",encoding="utf-8")
    if before!=after:raise RuntimeError("Run 014 modified a protected artifact")
    print(RUN014_LABEL,gate);return metadata
if __name__=="__main__":run()
