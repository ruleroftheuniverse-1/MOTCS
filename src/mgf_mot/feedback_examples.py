"""Closed Run 016 model-independent feedback example builders."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import yaml

from .apparatus_constraints import synthetic_identity_profile, synthetic_quantized_profile, synthetic_rate_limited_profile
from .feedback_policy import (
    ACTION_SCHEMA_VERSION, CONTROLLER_SCHEMA_VERSION, OBSERVATION_SCHEMA_VERSION, SESSION_SCHEMA_VERSION,
    ORACLE_LABELS, ActionChannelSpec, ActionSpec, ActionUpdateMode, ControllerFamily, ControllerSpec,
    ControllerStatefulness, FeedbackProvenance, FeedbackSessionSpec,
    FeedbackTimingSpec, InfeasibleActionStrategy, MemoryFieldSpec,
    MissingStrategy, NoiseModelId, NoiseModelSpec, ObservationAccessClass,
    ObservationChannelSpec, ObservationSpec, PlantFamily, SchedulingMode,
    SyntheticPlantSpec, TransformId, feedback_hash,
)
from .legacy_policy_adapter import legacy_policy_to_v2_spec
from .open_loop_policy_families import compose_with_handoff, load_family_config
from .policies import load_policy


def _prov(kind="SYNTHETIC_TEST_FIXTURE",labels=("MODEL_INDEPENDENT","NOT_MGF_PHYSICS")):
    return FeedbackProvenance(kind,"Run 016 closed synthetic example",None,None,"Feedback plumbing only; no physical claim",tuple(labels))
def _fallback(default=MissingStrategy.REJECT_STEP):return {status:default for status in ("VALID","MISSING","STALE","INVALID","SATURATED")}
def _noise(model=NoiseModelId.NONE,parameters=None,seed=None):return NoiseModelSpec(model,"1",{} if parameters is None else parameters,"abstract",seed,"NUMPY_PCG64_V1" if model is NoiseModelId.ADDITIVE_GAUSSIAN else "DETERMINISTIC_ALGEBRA_V1" if model is not NoiseModelId.NONE else "NONE",_prov())
def _observation(access,noise=None,dropout=False,latency=0.0,communication=0.0,labels=()):
    model=_noise() if noise is None else noise
    if dropout:model=_noise(NoiseModelId.DROPOUT_PATTERN,{"missing_indices":[1]},None)
    channel=ObservationChannelSpec("obs_x","Synthetic state coordinate","Declared synthetic scalar observation","abstract",(1,),"float64","synthetic control-fixture coordinate",access,("x",),(),TransformId.IDENTITY_FIELD,"1",{},.0003,latency,model,{"mode":"EXPLICIT_STATUS"},None,None,None,_prov())
    all_labels=tuple(dict.fromkeys((*labels,*(ORACLE_LABELS if access is ObservationAccessClass.FULL_STATE_ORACLE else ()))))
    return ObservationSpec(OBSERVATION_SCHEMA_VERSION,"run016_observation",access,(channel,),.0003,(),communication,(),all_labels,_prov())
def _plant(family=PlantFamily.STATIC_PLANT):
    params={}
    if family is PlantFamily.DISCRETE_INTEGRATOR_PLANT:params={"input_matrix":[[0.01]]}
    if family is PlantFamily.FIRST_ORDER_LAG_PLANT:params={"input_matrix":[[0.1]],"alpha":0.25}
    return SyntheticPlantSpec("mgf-mot-synthetic-plant-v1","run016_synthetic_plant",family,("x",),("static_shared_detuning_123",),(1.0,),.0003,params,_prov())
def _memory():return (MemoryFieldSpec("step_index","int64",(),None,0,"increment once per controller execution"),MemoryFieldSpec("last_action_hash","string",(),None,"","replace with deterministic action hash"))
def _action_spec(abi):
    channels=[]
    for item in abi.control_channels:
        if item.relationship.value=="AFFINE_DERIVED":continue
        units="Gamma" if item.field=="detuning_gamma" else "saturation_parameter";bounds=(-10.0,3.0) if item.field=="detuning_gamma" else (0.0,4.0);channels.append(ActionChannelSpec(item.channel_id,units,True,*bounds,item.relationship.value))
    return ActionSpec(ACTION_SCHEMA_VERSION,"run016_abi_action_channels",tuple(channels),True,"HOLD_PREVIOUS_VALUE",True,_prov())
def _controller(family,obs,action_spec,parameters,fallback=None,simulation=True):
    return ControllerSpec(CONTROLLER_SCHEMA_VERSION,f"run016_{family.value.lower()}",family,"1",ControllerStatefulness.EXPLICIT_MEMORY,feedback_hash(obs),feedback_hash(action_spec),_memory(),{"packet_only":True},_fallback() if fallback is None else fallback,parameters,_prov(),simulation,False)
def _timing(end=.0009,sensor=0.0,communication=0.0,control=.0003,mode=SchedulingMode.FIXED_CONTROL_CLOCK):return FeedbackTimingSpec(.0003,control,0.0,sensor,communication,0.0,True,"NEAREST_TIES_TO_EVEN",0.0,end,0.0,.001,mode,())


def build_feedback_example(example_id:str,root:Path)->FeedbackSessionSpec:
    static_path=root/"configs/rodriguez_static_3.yaml";static=legacy_policy_to_v2_spec(load_policy(static_path),source_path=static_path);static_fields={item.channel_id:item.field for item in static.control_channels}
    if example_id=="baseline_replay":
        family_path=next((root/"configs/run_015").glob("*piecewise_baseline.yaml"));family=load_family_config(family_path);handoff_path=root/"configs/rodriguez_chirp_to_3_plus_1_handoff.yaml";handoff=legacy_policy_to_v2_spec(load_policy(handoff_path),source_path=handoff_path);family=compose_with_handoff(family,handoff,{"chirp_shared_linear_detuning_123":"pre_shared_linear_detuning_123"});abi=family.abi_spec;obs=_observation(ObservationAccessClass.PARTIAL_STATE_SYNTHETIC);action_spec=_action_spec(abi);controller=_controller(ControllerFamily.BASELINE_REPLAY_CONTROLLER,obs,action_spec,{"update_mode":ActionUpdateMode.PARTIAL_HOLD_UNSPECIFIED.value,"baseline_family_hash":feedback_hash(family)});profile=synthetic_identity_profile({item.channel_id:item.field for item in abi.control_channels});plant=SyntheticPlantSpec("mgf-mot-synthetic-plant-v1","baseline_static_synthetic",PlantFamily.STATIC_PLANT,("x",),(),(1.0,),.00025,{},_prov());timing=_timing(end=.002,control=.00025)
        return FeedbackSessionSpec(SESSION_SCHEMA_VERSION,example_id,obs,action_spec,controller,timing,plant,abi,profile,InfeasibleActionStrategy.TERMINATE_SESSION,None,family,_prov("SOURCE_SUPPORTED_CONTROL_BASELINE"))
    if example_id=="oracle_affine":
        obs=_observation(ObservationAccessClass.FULL_STATE_ORACLE,labels=ORACLE_LABELS);action_spec=_action_spec(static);params={"observation_channel_ids":["obs_x"],"action_channel_ids":["static_shared_detuning_123"],"matrix":[[0.2]],"offset":[-2.0],"lower":[-10.0],"upper":[3.0],"bound_behavior":"EXPLICIT_CLIP","update_mode":ActionUpdateMode.PARTIAL_HOLD_UNSPECIFIED.value};controller=_controller(ControllerFamily.BOUNDED_AFFINE_CONTROLLER,obs,action_spec,params);profile=synthetic_quantized_profile(static_fields);plant=_plant(PlantFamily.DISCRETE_INTEGRATOR_PLANT);timing=_timing()
    elif example_id=="partial_delayed":
        obs=_observation(ObservationAccessClass.PARTIAL_STATE_SYNTHETIC,dropout=True,latency=.0001,communication=.00005);action_spec=_action_spec(static);fallback=_fallback();fallback["MISSING"]=MissingStrategy.HOLD_LAST_ACTION;params={"fixed_action":[{"channel_id":"static_shared_detuning_123","value":-1.0,"units":"Gamma"}],"update_mode":ActionUpdateMode.PARTIAL_HOLD_UNSPECIFIED.value};controller=_controller(ControllerFamily.NO_OP_CONTROLLER,obs,action_spec,params,fallback);profile=synthetic_quantized_profile(static_fields);plant=_plant(PlantFamily.FIRST_ORDER_LAG_PLANT);timing=_timing(sensor=.0001,communication=.00005)
    elif example_id=="infeasible_action":
        obs=_observation(ObservationAccessClass.PARTIAL_STATE_SYNTHETIC);action_spec=_action_spec(static);actions=[[{"channel_id":"static_shared_detuning_123","value":-8.0,"units":"Gamma"}],[{"channel_id":"static_shared_detuning_123","value":2.0,"units":"Gamma"}]];params={"actions":actions,"update_mode":ActionUpdateMode.PARTIAL_HOLD_UNSPECIFIED.value};controller=_controller(ControllerFamily.SCRIPTED_SEQUENCE_CONTROLLER,obs,action_spec,params);profile=synthetic_rate_limited_profile(static_fields);plant=_plant();timing=_timing(end=.0006)
    elif example_id=="deterministic_noise":
        obs=_observation(ObservationAccessClass.SENSOR_MODEL_SYNTHETIC,noise=_noise(NoiseModelId.ADDITIVE_GAUSSIAN,{"standard_deviation":0.02},16016));action_spec=_action_spec(static);params={"fixed_action":[{"channel_id":"static_shared_detuning_123","value":-1.0,"units":"Gamma"}],"update_mode":ActionUpdateMode.PARTIAL_HOLD_UNSPECIFIED.value};controller=_controller(ControllerFamily.NO_OP_CONTROLLER,obs,action_spec,params);profile=synthetic_quantized_profile(static_fields);plant=_plant();timing=_timing()
    else:raise ValueError(f"unknown Run 016 example_id {example_id!r}")
    return FeedbackSessionSpec(SESSION_SCHEMA_VERSION,example_id,obs,action_spec,controller,timing,plant,static,profile,InfeasibleActionStrategy.REJECT_AND_HOLD_PREVIOUS,None,None,_prov())


def load_feedback_example(path:str|Path,root:Path)->FeedbackSessionSpec:
    source=Path(path);data=yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data,Mapping) or set(data)!={"schema_version","example_id","description","provenance_class","labels"}:raise ValueError("feedback example config must use the closed Run 016 schema without hidden defaults")
    if data["schema_version"]!="mgf-mot-feedback-example-v1":raise ValueError("unknown feedback example schema")
    return build_feedback_example(str(data["example_id"]),root)
