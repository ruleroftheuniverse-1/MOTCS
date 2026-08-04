from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from mgf_mot.apparatus_constraints import source_incomplete_profile
from mgf_mot.control_policy_abi import ChannelRelationship
from mgf_mot.feedback_examples import load_feedback_example
from mgf_mot.feedback_policy import (
    ORACLE_LABELS, REPLAY_SCHEMA_VERSION, RUN016_LABEL, ActionChannelValue,
    ActionUpdateMode, ActionValidity, ControlAction, ControllerFamily,
    ControllerMemory, ControllerStatefulness, FeedbackController, FeedbackError,
    FeedbackReplay, HiddenPlantState, InfeasibleActionStrategy, MemoryFieldSpec,
    MissingStrategy, NoiseModelId, ObservationAccessClass, ObservationModel,
    ObservationStatus, PlantFamily, PolicyState, TransformId,
    canonical_feedback_json, compile_action_sequence, feedback_hash,
    initial_controller_memory, replay_apparatus_from_actions,
    replay_controller_from_packets, replay_full_session, run_feedback_session,
    serialize_feedback, validate_action, validate_controller_spec,
    validate_observation_spec, validate_session_spec,
)
from mgf_mot.open_loop_policy_families import OpenLoopFamilyPolicy, compile_family_policy, family_hashes
from mgf_mot.control_schedule_compiler import CompilationMode, CompilationRequest, InitialStateMode, ReconstructionMode
from mgf_mot.apparatus_constraints import apparatus_profile_hash


ROOT=Path(__file__).resolve().parents[1];CONFIG_DIR=ROOT/"configs/run_016";DETAIL=ROOT/"outputs/provisional/feedback_policy_interface/run_016";REPORT=ROOT/"outputs/provisional"/f"{RUN016_LABEL}.md"
def _load(name):return load_feedback_example(next(CONFIG_DIR.glob(f"*_{name}.yaml")),ROOT)


def test_hidden_state_cannot_be_passed_to_controller_and_only_declared_observations_are_exposed():
    spec=_load("oracle_affine");controller=FeedbackController(spec.controller_spec,spec.abi_spec);memory=initial_controller_memory(spec.controller_spec)
    with pytest.raises(TypeError,match="ObservationPacket only"):controller.step(HiddenPlantState(0,{"x":1}),memory,"step",0,0)
    packet=ObservationModel(spec.observation_spec).sample(HiddenPlantState(0,{"x":1,"undeclared":99}),0,0,(HiddenPlantState(0,{"x":1,"undeclared":99}),))
    assert [item.channel_id for item in packet.observations]==["obs_x"] and packet.observations[0].value==(1.0,)


def test_oracle_labels_are_mandatory_and_propagate_to_artifacts():
    spec=_load("oracle_affine");assert set(ORACLE_LABELS).issubset(spec.observation_spec.labels)
    result=run_feedback_session(spec);assert set(ORACLE_LABELS).issubset(result.labels)
    invalid=replace(spec.observation_spec,labels=());validation=validate_observation_spec(invalid)
    assert any(item.code=="MISSING_ORACLE_LABELS" for item in validation.errors)


def test_transform_graph_cycles_and_arbitrary_callables_fail_closed():
    spec=_load("oracle_affine").observation_spec;channel=spec.channels[0]
    cyclic=replace(channel,input_channel_ids=(channel.channel_id,),transformation_id=TransformId.AFFINE_TRANSFORM,transformation_parameters={"scale":[1],"offset":[0]})
    assert any(item.code=="CYCLIC_TRANSFORMATION_GRAPH" for item in validate_observation_spec(replace(spec,channels=(cyclic,))).errors)
    executable=replace(channel,transformation_parameters={"callable":lambda x:x})
    assert any(item.code=="ARBITRARY_EXECUTABLE_CONTENT" for item in validate_observation_spec(replace(spec,channels=(executable,))).errors)


def test_seeded_noise_is_exact_and_does_not_touch_global_rng_state():
    spec=_load("deterministic_noise");model=ObservationModel(spec.observation_spec);state=HiddenPlantState(0,{"x":1});history=(state,)
    np.random.seed(123);before=np.random.get_state();a=model.sample(state,0,0,history);after=np.random.get_state();b=model.sample(state,0,0,history)
    assert a==b and all(np.array_equal(x,y) for x,y in zip(before[1:],after[1:]))
    changed=replace(spec.observation_spec.channels[0].noise_model,seed=99);other=ObservationModel(replace(spec.observation_spec,channels=(replace(spec.observation_spec.channels[0],noise_model=changed),))).sample(state,0,0,history)
    assert other.observations[0].value!=a.observations[0].value


def test_missing_observations_are_none_not_zero_and_timestamps_are_distinct():
    spec=_load("partial_delayed");model=ObservationModel(spec.observation_spec);state=HiddenPlantState(.0003,{"x":1});packet=model.sample(state,.0003,1,(state,))
    assert packet.status is ObservationStatus.MISSING and packet.observations[0].value is None
    assert packet.source_state_timestamp_s==packet.sensor_sample_time_s
    assert packet.sensor_sample_time_s<packet.observation_availability_time_s<packet.controller_receive_time_s


def test_stale_and_missing_packets_follow_declared_hold_behavior():
    spec=_load("partial_delayed");timing=replace(spec.timing_spec,max_observation_age_s=0.0);result=run_feedback_session(replace(spec,timing_spec=timing))
    assert any(step.observation_packet.status is ObservationStatus.STALE for step in result.steps)
    assert all(step.action is None or step.action.update_mode is ActionUpdateMode.HOLD_NO_CHANGE for step in result.steps if step.observation_packet.status in {ObservationStatus.MISSING,ObservationStatus.STALE})


def test_memory_is_explicit_serializable_and_stateless_memory_is_empty():
    spec=_load("deterministic_noise").controller_spec;memory=initial_controller_memory(spec);assert memory.values=={"step_index":0,"last_action_hash":""}
    assert json.loads(serialize_feedback(memory))==json.loads(canonical_feedback_json(memory))
    stateless=replace(spec,statefulness=ControllerStatefulness.STATELESS,memory_schema=());assert initial_controller_memory(stateless).values=={}


def test_invalid_actions_fail_before_compilation_with_units_channels_shared_and_derived_checks():
    session=_load("oracle_affine");prov=session.provenance;packet=run_feedback_session(session).steps[0].observation_packet
    bad=ControlAction("bad",packet.controller_receive_time_s,packet.controller_receive_time_s,(ActionChannelValue("unknown",1,"Gamma"),),ActionUpdateMode.PARTIAL_HOLD_UNSPECIFIED,"test","step",ActionValidity.VALID,None,prov)
    assert any(item.code=="UNKNOWN_ACTION_CHANNEL" for item in validate_action(bad,session.abi_spec,packet).errors)
    shared=session.abi_spec.control_channels[0].channel_id;diverge=replace(bad,channel_values=(ActionChannelValue(shared,-1,"wrong"),ActionChannelValue(shared,-2,"Gamma")))
    codes={item.code for item in validate_action(diverge,session.abi_spec,packet).errors};assert "ACTION_UNIT_MISMATCH" in codes and "SHARED_CHANNEL_DIVERGENCE" in codes
    channels=list(session.abi_spec.control_channels);channels[1]=replace(channels[1],relationship=ChannelRelationship.AFFINE_DERIVED,source_channel_id=channels[0].channel_id,affine_scale=1,affine_offset=0);abi=replace(session.abi_spec,control_channels=tuple(channels));derived=replace(bad,channel_values=(ActionChannelValue(channels[1].channel_id,0,"Gamma"),))
    assert any(item.code=="INVALID_DERIVED_CHANNEL_UPDATE" for item in validate_action(derived,abi).errors)


def test_action_compilation_uses_run014_constraints_and_rejects_without_repair():
    session=_load("infeasible_action");result=run_feedback_session(session)
    assert any(step.compilation_status=="COMPILATION_INFEASIBLE" for step in result.steps)
    assert any(step.fallback_decision==InfeasibleActionStrategy.REJECT_AND_HOLD_PREVIOUS.value for step in result.steps)
    assert len(result.accepted_actions)<sum(step.action is not None for step in result.steps)
    rejected=next(step for step in result.steps if step.compilation_status=="COMPILATION_INFEASIBLE");assert rejected.action.channel_values[0].value==2.0


def test_event_order_is_deterministic_and_matches_declared_priority():
    spec=_load("deterministic_noise");a=run_feedback_session(spec);b=run_feedback_session(spec);assert a.event_order==b.event_order
    at_zero=[item.split(":",1)[1] for item in a.event_order if item.startswith("0:")]
    assert at_zero==["EFFECTIVE_COMMANDS","SENSOR_SAMPLE","OBSERVATION_ARRIVAL","CONTROLLER_EVALUATION","COMMAND_ISSUE_RECORD"]


def test_baseline_feedback_replay_is_exact_including_handoff_and_realized_states():
    spec=_load("baseline_replay");result=run_feedback_session(spec);family=spec.baseline_family_spec;h=family_hashes(family);request=CompilationRequest(h.complete_policy_package,apparatus_profile_hash(spec.apparatus_profile),CompilationMode.EXACT_ONLY,0,.002,InitialStateMode.POLICY_STATE_AT_START,None,None,None,ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING);compiled,realized=compile_family_policy(family,spec.apparatus_profile,request)
    assert result.final_compilation.commands==compiled.commands and result.final_compilation.events==compiled.events
    assert result.final_compilation.status.value=="COMPILED_EXACT" and compiled.events[0].event_id=="chirp_to_trap_handoff"
    policy=OpenLoopFamilyPolicy(family)
    for step in result.steps:assert step.realized_control_state.components==policy.sample(step.action.requested_effective_time_s).components


@pytest.mark.parametrize("name",["baseline_replay","oracle_affine","partial_delayed","infeasible_action","deterministic_noise"])
def test_full_controller_and_apparatus_replays_are_exact(name):
    spec=_load(name);recorded=run_feedback_session(spec)
    assert replay_full_session(spec,recorded).replay_equal
    assert replay_controller_from_packets(spec,recorded).replay_equal
    assert replay_apparatus_from_actions(spec,recorded).replay_equal


def test_replay_hash_mismatch_fails_visibly():
    spec=_load("deterministic_noise");recorded=run_feedback_session(spec);changed_controller=replace(spec.controller_spec,controller_version="changed");changed=replace(spec,controller_spec=changed_controller)
    with pytest.raises(FeedbackError,match="REPLAY_HASH_MISMATCH"):replay_full_session(changed,recorded)


def test_partial_profile_is_diagnostic_and_never_hardware_executable():
    spec=_load("deterministic_noise");profile=source_incomplete_profile({item.channel_id:item.field for item in spec.abi_spec.control_channels});result=run_feedback_session(replace(spec,apparatus_profile=profile))
    assert not result.hardware_executable_claim_valid
    assert result.final_compilation.status.value=="COMPILED_DIAGNOSTIC_INCOMPLETE_PROFILE"
    assert not result.final_compilation.hardware_executable_claim_valid


def test_outputs_labels_protected_hashes_and_authorization_boundaries():
    metadata=json.loads(next(DETAIL.glob("*metadata.json")).read_text(encoding="utf-8"));assert metadata["gate"]=="FEEDBACK_POLICY_INTERFACE_GO"
    assert metadata["protected_artifacts_unchanged"] and metadata["run013_hashes_unchanged"] and metadata["run014_profile_hashes_unchanged"] and metadata["run015_family_hashes_unchanged"]
    assert not metadata["real_sensor_model_validated"] and not metadata["hardware_executable_claim_valid"] and not metadata["reinforcement_learning_authorized"]
    stamps=("MODEL_INDEPENDENT","NOT_RODRIGUEZ_REPLICATION","RUN_016","FEEDBACK_POLICY_INTERFACE_ONLY");assert all(all(stamp in path.name for stamp in stamps) for path in [REPORT,*DETAIL.iterdir()])
    oracle=next(path for path in DETAIL.iterdir() if "oracle_affine" in path.name);assert all(label in oracle.name for label in ORACLE_LABELS)
    source=(ROOT/"scripts/validate_feedback_policy_interface_run_016.py").read_text(encoding="utf-8")
    for forbidden in ("rateeq","force_at(","load_force_field_cache(","integrate_policy_trajectory","capture_velocity(","optimizer(","import gym","import torch"):
        assert forbidden not in source
