"""Run 016 model-independent feedback interface and replay audit."""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/"src"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))

from mgf_mot.apparatus_constraints import (  # noqa: E402
    apparatus_profile_hash, source_incomplete_profile,
    synthetic_identity_profile, synthetic_quantized_profile,
    synthetic_rate_limited_profile,
)
from mgf_mot.control_policy_serialization import control_policy_hashes  # noqa: E402
from mgf_mot.feedback_examples import load_feedback_example  # noqa: E402
from mgf_mot.feedback_policy import (  # noqa: E402
    ORACLE_LABELS, RUN016_LABEL, ObservationStatus, feedback_hash,
    replay_apparatus_from_actions, replay_controller_from_packets,
    replay_full_session, run_feedback_session, validate_session_spec,
)
from mgf_mot.legacy_policy_adapter import legacy_policy_to_v2_spec  # noqa: E402
from mgf_mot.open_loop_policy_families import family_hashes, load_family_config  # noqa: E402
from mgf_mot.policies import load_policy  # noqa: E402


CONFIG_DIR=ROOT/"configs/run_016";OUT=ROOT/"outputs/provisional";DETAIL=OUT/"feedback_policy_interface/run_016";REPORT=OUT/f"{RUN016_LABEL}.md";METADATA=DETAIL/f"{RUN016_LABEL}_metadata.json"
LEGACY_CONFIGS=(ROOT/"configs/rodriguez_static_3.yaml",ROOT/"configs/rodriguez_static_3_plus_1.yaml",ROOT/"configs/rodriguez_baseline_linear_chirp.yaml",ROOT/"configs/rodriguez_chirp_to_3_plus_1_handoff.yaml")


def _digest(path:Path):return sha256(path.read_bytes()).hexdigest()
def _manifest(paths):return {str(path.relative_to(ROOT)):_digest(path) for path in sorted(set(paths))}
def _protected():
    patterns=("outputs/provisional/*RUN_01[0-5]*","outputs/provisional/molecular_model_packages/run_012/*","outputs/provisional/control_policy_abi/run_013/*","outputs/provisional/apparatus_schedule_compiler/run_014/*","outputs/provisional/open_loop_policy_families/run_015/*","outputs/provisional/force_fields/*","outputs/provisional/molecular_model_audit/run_011*/*","outputs/provisional/paper_digitization/run_011b/*","configs/*.yaml","configs/run_015/*.yaml","docs/control-policy-abi-v2.md","docs/apparatus-constraint-and-schedule-compiler.md","docs/open-loop-policy-families.md")
    paths=set()
    for pattern in patterns:paths.update(path for path in ROOT.glob(pattern) if path.is_file())
    paths.update(ROOT/"src/mgf_mot"/name for name in ("control_policy_abi.py","control_policy_serialization.py","control_policy_validation.py","legacy_policy_adapter.py","apparatus_constraints.py","open_loop_policy_families.py"))
    return tuple(sorted(paths))
def _plain(value:Any)->Any:
    if isinstance(value,Enum):return value.value
    if hasattr(value,"__dataclass_fields__"):return {key:_plain(item) for key,item in asdict(value).items()}
    if isinstance(value,dict):return {str(key):_plain(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):return [_plain(item) for item in value]
    return value
def _current_run014_profiles():
    identity=[]
    for path in LEGACY_CONFIGS:
        abi=legacy_policy_to_v2_spec(load_policy(path),source_path=path);fields={item.channel_id:item.field for item in abi.control_channels};identity.append((abi.policy_name,apparatus_profile_hash(synthetic_identity_profile(fields))))
    abi=legacy_policy_to_v2_spec(load_policy(LEGACY_CONFIGS[2]),source_path=LEGACY_CONFIGS[2]);fields={item.channel_id:item.field for item in abi.control_channels}
    return {"identity":identity,"demonstrations":[("quantized",apparatus_profile_hash(synthetic_quantized_profile(fields))),("rate_limited",apparatus_profile_hash(synthetic_rate_limited_profile(fields))),("source_incomplete",apparatus_profile_hash(source_incomplete_profile(fields)))]}


def run():
    protected=_protected();before=_manifest(protected);DETAIL.mkdir(parents=True,exist_ok=True)
    run013=json.loads(next((ROOT/"outputs/provisional/control_policy_abi/run_013").glob("*metadata.json")).read_text(encoding="utf-8"));run014=json.loads(next((ROOT/"outputs/provisional/apparatus_schedule_compiler/run_014").glob("*metadata.json")).read_text(encoding="utf-8"));run015=json.loads(next((ROOT/"outputs/provisional/open_loop_policy_families/run_015").glob("*metadata.json")).read_text(encoding="utf-8"))
    run013_expected=[row["hashes"]["full_policy_package"] for row in run013["policies"]];run013_current=[control_policy_hashes(legacy_policy_to_v2_spec(load_policy(path),source_path=path)).full_policy_package for path in LEGACY_CONFIGS]
    run014_expected={"identity":[(row["policy_name"],row["profile_hash"]) for row in run014["identity_compilations"]],"demonstrations":[(row["name"],row["profile_hash"]) for row in run014["demonstrations"]]};run014_current=_current_run014_profiles()
    run015_expected={row["config"]:row["hashes"] for row in run015["families"]};run015_current={str(path.relative_to(ROOT)):_plain(family_hashes(load_family_config(path))) for path in sorted((ROOT/"configs/run_015").glob("*.yaml"))}
    sessions=[]
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        spec=load_feedback_example(path,ROOT);validation=validate_session_spec(spec);result=run_feedback_session(spec);full=replay_full_session(spec,result);controller=replay_controller_from_packets(spec,result);apparatus=replay_apparatus_from_actions(spec,result)
        oracle=spec.observation_spec.access_class.value=="FULL_STATE_ORACLE";suffix=path.stem.removeprefix(RUN016_LABEL+"_");oracle_stamp="_FULL_STATE_ORACLE_SIMULATION_ONLY_NOT_APPARATUS_REALIZABLE" if oracle else "";output=DETAIL/f"{RUN016_LABEL}_{suffix}{oracle_stamp}_replay_package.json"
        package={"label":RUN016_LABEL,"source_config":str(path.relative_to(ROOT)),"session_spec":_plain(spec),"validation":_plain(validation),"session_result":_plain(result),"full_replay":_plain(full),"controller_only_replay":_plain(controller),"apparatus_only_replay":_plain(apparatus),"oracle_labels":list(ORACLE_LABELS) if oracle else [],"no_physics_or_training_claim":True};output.write_text(json.dumps(package,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
        row={"session_id":spec.session_id,"config":str(path.relative_to(ROOT)),"output":output.name,"valid":validation.valid,"session_hash":feedback_hash(spec),"observation_hash":result.spec_hashes["observation"],"controller_hash":result.spec_hashes["controller"],"timing_hash":result.spec_hashes["timing"],"plant_hash":result.spec_hashes["plant"],"observation_stream_hash":result.observation_stream_hash,"action_stream_hash":result.action_stream_hash,"command_stream_hash":result.command_stream_hash,"replay_package_hash":result.replay_hash,"full_replay_equal":full.replay_equal,"controller_only_replay_equal":controller.replay_equal,"apparatus_only_replay_equal":apparatus.replay_equal,"oracle_labels_present":not oracle or set(ORACLE_LABELS).issubset(result.labels),"hardware_executable_claim_valid":result.hardware_executable_claim_valid,"metrics":_plain(result.metrics),"compilation_status":None if result.final_compilation is None else result.final_compilation.status.value,"handoff_event_ids":[] if result.final_compilation is None else [event.event_id for event in result.final_compilation.events]}
        if spec.session_id=="baseline_replay":row["open_loop_equivalence"]="OPEN_LOOP_FEEDBACK_REPLAY_EXACT" if result.final_compilation and result.final_compilation.status.value=="COMPILED_EXACT" and "chirp_to_trap_handoff" in row["handoff_event_ids"] and apparatus.replay_equal else "OPEN_LOOP_FEEDBACK_REPLAY_CHANGED"
        sessions.append(row);print(spec.session_id,row["compilation_status"],full.replay_equal,controller.replay_equal,apparatus.replay_equal,row.get("open_loop_equivalence","SYNTHETIC"))
    after=_manifest(protected);baseline=next(row for row in sessions if row["session_id"]=="baseline_replay");oracle=next(row for row in sessions if row["session_id"]=="oracle_affine");partial=next(row for row in sessions if row["session_id"]=="partial_delayed");infeasible=next(row for row in sessions if row["session_id"]=="infeasible_action");noise=next(row for row in sessions if row["session_id"]=="deterministic_noise")
    ready=(run013["gate"]=="CONTROL_POLICY_ABI_GO" and run014["gate"]=="APPARATUS_SCHEDULE_COMPILER_GO" and run015["gate"]=="OPEN_LOOP_POLICY_FAMILIES_GO" and run013_current==run013_expected and run014_current==run014_expected and run015_current==run015_expected and before==after and all(row["valid"] and row["full_replay_equal"] and row["controller_only_replay_equal"] and row["apparatus_only_replay_equal"] and not row["hardware_executable_claim_valid"] for row in sessions) and baseline["open_loop_equivalence"]=="OPEN_LOOP_FEEDBACK_REPLAY_EXACT" and oracle["oracle_labels_present"] and partial["metrics"]["missing_count"]>0 and infeasible["metrics"]["infeasible_action_count"]>0 and noise["full_replay_equal"])
    gate="FEEDBACK_POLICY_INTERFACE_GO" if ready else "FEEDBACK_POLICY_INTERFACE_REFINEMENT_REQUIRED"
    metadata={"label":RUN016_LABEL,"gate":gate,"observation_schema_version":"mgf-mot-observation-spec-v1","controller_schema_version":"mgf-mot-feedback-controller-v1","session_schema_version":"mgf-mot-feedback-session-v1","replay_schema_version":"mgf-mot-feedback-replay-v1","event_ordering_version":"run016-effective_plant_sample_arrival_controller_issue_checkpoint-v1","sessions":sessions,"run013_hashes_unchanged":run013_current==run013_expected,"run014_profile_hashes_unchanged":run014_current==run014_expected,"run015_family_hashes_unchanged":run015_current==run015_expected,"protected_hashes_before":before,"protected_hashes_after":after,"protected_artifacts_unchanged":before==after,"molecular_force_evaluations":0,"force_field_queries":0,"molecular_trajectory_integrations":0,"capture_metrics":0,"controller_training_runs":0,"optimization_runs":0,"control_policy_abi_authorized":True,"apparatus_schedule_compiler_authorized":True,"open_loop_policy_families_authorized":True,"feedback_policy_interface_authorized":gate=="FEEDBACK_POLICY_INTERFACE_GO","real_sensor_model_validated":False,"real_apparatus_profile_validated":False,"hardware_executable_claim_valid":False,"state_estimator_authorized":False,"optimizer_interface_authorized":False,"optimization_run_authorized":False,"reinforcement_learning_authorized":False,"capture_authorized":False,"exact_replication_valid":False}
    METADATA.write_text(json.dumps(metadata,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    REPORT.write_text("\n".join([f"# {RUN016_LABEL}","","**No molecular force was evaluated. No molecular trajectory was integrated. No capture metric was calculated. No controller was optimized or trained. No real sensor or apparatus model was validated. Synthetic feedback success is not physical evidence.**","","## Deterministic sessions","",*[f"- `{row['session_id']}`: full/controller/apparatus replay = `{row['full_replay_equal']}`/`{row['controller_only_replay_equal']}`/`{row['apparatus_only_replay_equal']}`; compilation `{row['compilation_status']}`" for row in sessions],"",f"Baseline audit: `{baseline['open_loop_equivalence']}`.","","## Authorization boundaries","","`control_policy_abi_authorized=true`; `apparatus_schedule_compiler_authorized=true`; `open_loop_policy_families_authorized=true`; `real_sensor_model_validated=false`; `real_apparatus_profile_validated=false`; `hardware_executable_claim_valid=false`; `state_estimator_authorized=false`; `optimizer_interface_authorized=false`; `optimization_run_authorized=false`; `reinforcement_learning_authorized=false`; `capture_authorized=false`; `exact_replication_valid=false`.","",gate])+"\n",encoding="utf-8")
    if before!=after:raise RuntimeError("Run 016 modified a protected artifact")
    print(RUN016_LABEL,gate);return metadata


if __name__=="__main__":run()
